"""Provider-neutral remote records and verification, without scheduling."""
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from typing import Protocol
import hashlib
import uuid

from rudeus.execution.code_bundle import CodeBundle, verify_bundle
from rudeus.execution.contracts import ExecutionError, FailureClass, TaskSpec, classify_failure
from rudeus.execution.receipt_records import execution_context, verify_retained_execution
from rudeus.science.contracts import Record, canonical_bytes, digest, require_hash
from rudeus.science.evidence import append_file, integrity_errors, require
from rudeus.science.followups import generate_followups


@dataclass(frozen=True, kw_only=True)
class TaskBundle(Record):
    """Transfer inventory; byte payloads remain in Git and the evidence store."""
    task: dict
    task_content_hash: str
    code_bundle: dict
    bundle_hash: str
    retained_files: tuple
    version: str = "remote-task-bundle-v1"

    def validate(self):
        super().validate()
        task, code = TaskSpec.from_dict(self.task), CodeBundle.from_dict(self.code_bundle)
        if (self.version != "remote-task-bundle-v1" or task.content_hash != self.task_content_hash
                or code.bundle_hash != self.bundle_hash or code.code_revision != task.code_revision):
            raise ValueError("task bundle binding mismatch")
        paths = []
        for item in self.retained_files:
            if set(item) != {"relative_path", "raw_sha256", "size_bytes"}:
                raise ValueError("invalid retained file entry")
            path = item["relative_path"]
            parts = PurePosixPath(path).parts
            if (len(parts) != 2 or parts[0] not in ("evidence", "blobs", "code_bundles",
                    "execution_manifests", "runtime_records") or "\\" in path
                    or PurePosixPath(path).as_posix() != path):
                raise ValueError("external or invalid retained file path")
            require_hash(parts[1] if parts[0] == "blobs" else parts[1].removesuffix(".json"))
            require_hash(item["raw_sha256"])
            if type(item["size_bytes"]) is not int or item["size_bytes"] < 0:
                raise ValueError("invalid retained file size")
            paths.append(path)
        if not paths or paths != sorted(set(paths)):
            raise ValueError("empty, duplicate or unsorted retained inventory")


def build_task_bundle(task, code_bundle, *, store, git_root):
    """Validate existing follow-up inputs, exact TaskSpec and committed code."""
    with integrity_errors():
        verify_bundle(code_bundle, code_bundle.bundle_hash, task, git_root=git_root)
        require(task.provenance is not None, "remote task requires verified originating evidence")
        origin = task.provenance["evidence_hash"]
        require(any(row["task"] == task.to_dict() for row in generate_followups(store, origin)["tasks"]),
                "task differs from verified follow-up")
        paths, visited = set(), set()

        def collect(identity):
            require(identity not in visited, "cyclic originating evidence")
            visited.add(identity)
            archive = store.verify(identity)
            paths.update((f"evidence/{identity}.json", f"blobs/{identity}"))
            paths.update(f"blobs/{m['raw_hash']}" for m in archive["provenance"]["manifests"])
            if execution_context(archive) is not None:
                _, retained = verify_retained_execution(store, archive, git_root=git_root)
                paths.update(retained)
            source_task = TaskSpec.from_dict(archive["provenance"]["task"])
            if source_task.provenance is not None:
                collect(source_task.provenance["evidence_hash"])

        collect(origin)
        inventory = []
        for path in sorted(paths):
            data = store.path(path).read_bytes()
            inventory.append({"relative_path": path, "raw_sha256": hashlib.sha256(data).hexdigest(),
                              "size_bytes": len(data)})
        return TaskBundle(task=task.to_dict(), task_content_hash=task.content_hash,
                          code_bundle=code_bundle.to_dict(), bundle_hash=code_bundle.bundle_hash,
                          retained_files=tuple(inventory))


def verify_task_bundle(bundle, identity, *, store, git_root):
    with integrity_errors():
        require_hash(identity)
        bundle = bundle if isinstance(bundle, TaskBundle) else TaskBundle.from_dict(bundle)
        require(bundle.content_hash == identity, "task bundle hash mismatch")
        expected = build_task_bundle(TaskSpec.from_dict(bundle.task), CodeBundle.from_dict(bundle.code_bundle),
                                     store=store, git_root=git_root)
        require(canonical_bytes(bundle) == canonical_bytes(expected), "task bundle inventory mismatch")
        return bundle


TRANSITIONS = {
    "CREATED": {"SUBMITTED", "FAILED"},
    "SUBMITTED": {"RUNNING", "COMPLETED", "PREEMPTED", "INTERRUPTED", "FAILED"},
    "RUNNING": {"COMPLETED", "PREEMPTED", "INTERRUPTED", "FAILED"},
    "COMPLETED": {"RETRIEVED"}, "RETRIEVED": {"DURABLY_INGESTED"},
    "PREEMPTED": set(), "INTERRUPTED": set(), "FAILED": set(), "DURABLY_INGESTED": set(),
}


@dataclass(frozen=True, kw_only=True)
class BackendAttempt(Record):
    """Immutable operational snapshots; terminal scientific attempts stay unchanged.

    Provider status is an observation, not artifact verification. Append snapshots
    by content hash; never replace previous snapshots or reuse a retry's attempt ID.
    """
    attempt_id: str
    task_content_hash: str
    task_bundle_hash: str
    backend: str
    state: str = "CREATED"
    remote_run_id: str | None = None
    previous_hash: str | None = None
    failure_class: str | None = None
    evidence_hash: str | None = None
    receipt_hash: str | None = None
    version: str = "backend-attempt-v1"

    def validate(self):
        super().validate()
        for value in (self.attempt_id, self.task_content_hash, self.task_bundle_hash):
            require_hash(value)
        for value in (self.previous_hash, self.evidence_hash, self.receipt_hash):
            if value is not None:
                require_hash(value)
        if self.version != "backend-attempt-v1" or self.state not in TRANSITIONS or not self.backend:
            raise ValueError("invalid backend attempt")
        failed = self.state in ("FAILED", "PREEMPTED", "INTERRUPTED")
        if failed != (self.failure_class is not None):
            raise ValueError("operational failure classification required only for failure")
        if self.failure_class is not None and self.failure_class not in {
                "INFRASTRUCTURE", "RESOURCE", "NUMERICAL", "SOFTWARE", "INTEGRITY", "UNSUPPORTED_INPUT"}:
            raise ValueError("unsupported operational failure class")
        if self.state not in ("CREATED", "FAILED") and not self.remote_run_id:
            raise ValueError("provider run identity required")
        if (self.state in ("RETRIEVED", "DURABLY_INGESTED")) != (self.evidence_hash is not None):
            raise ValueError("retrieval evidence identity mismatch")
        if (self.state == "DURABLY_INGESTED") != (self.receipt_hash is not None):
            raise ValueError("durability receipt identity mismatch")


def new_attempt(bundle, backend):
    return BackendAttempt(attempt_id=digest({"nonce": uuid.uuid4().hex, "bundle": bundle.content_hash}),
                          task_content_hash=bundle.task_content_hash,
                          task_bundle_hash=bundle.content_hash, backend=backend)


def advance(attempt, state, **changes):
    if state in ("RETRIEVED", "DURABLY_INGESTED"):
        raise ExecutionError("artifact/receipt verification required for this transition", "INTEGRITY")
    return _advance(attempt, state, **changes)


def _advance(attempt, state, **changes):
    if state not in TRANSITIONS[attempt.state] or set(changes) - {
            "remote_run_id", "failure_class", "evidence_hash", "receipt_hash"}:
        raise ExecutionError("invalid backend transition", "INTEGRITY")
    if attempt.remote_run_id is not None and changes.get("remote_run_id", attempt.remote_run_id) != attempt.remote_run_id:
        raise ExecutionError("remote run identity cannot change", "INTEGRITY")
    with integrity_errors():
        return replace(attempt, state=state, previous_hash=attempt.content_hash, **changes)


def retain_attempt(attempt, *, store):
    """Append an operational snapshot without claiming Git ingestion."""
    append_file(store.path(f"backend_attempts/{attempt.content_hash}.json"), canonical_bytes(attempt))
    return attempt.content_hash


def operational_failure(exc):
    value = classify_failure(exc)
    return (FailureClass.INFRASTRUCTURE if value in
            (FailureClass.NETWORK, FailureClass.TIMEOUT, FailureClass.UNKNOWN) else value).value


def verify_retrieved(attempt, bundle, *, store, evidence_hash, git_root):
    """Verify downloaded bytes with the existing artifact path; no durability claim."""
    with integrity_errors():
        require(attempt.state == "COMPLETED" and attempt.task_bundle_hash == bundle.content_hash
                and attempt.task_content_hash == bundle.task_content_hash, "retrieval attempt binding mismatch")
        archive = store.verify(evidence_hash)
        require(archive["provenance"]["task"] == bundle.to_dict()["task"], "remote TaskSpec mismatch")
        context = execution_context(archive)
        require(context is not None, "remote execution records unavailable")
        _, producer, _ = context
        require(producer["attempt_id"] == attempt.attempt_id and producer["backend"] == attempt.backend
                and producer["remote_session_id"] == attempt.remote_run_id, "remote producing attempt mismatch")
        records, _ = verify_retained_execution(store, archive, git_root=git_root)
        require(records["bundle_hash"] == bundle.bundle_hash, "remote code bundle mismatch")
        return _advance(attempt, "RETRIEVED", evidence_hash=evidence_hash)


def verify_ingested(attempt, *, store, receipt_hash, git_root):
    with integrity_errors():
        require(attempt.state == "RETRIEVED", "verified retrieval required")
        receipt = store.verify_git_receipt(receipt_hash, git_root=git_root)
        require(receipt["format_version"] == "claim-evidence-git-v2"
                and receipt["evidence_hash"] == attempt.evidence_hash
                and receipt["producer_attempt"] == attempt.attempt_id
                and receipt["execution_records"][attempt.evidence_hash]["task_content_hash"]
                    == attempt.task_content_hash, "durability receipt attempt mismatch")
        return _advance(attempt, "DURABLY_INGESTED", receipt_hash=receipt_hash)


class ComputeBackend(Protocol):
    def capabilities(self) -> dict: ...
    def submit(self, task_bundle: TaskBundle, resource_requirements: dict) -> BackendAttempt: ...
    def status(self, attempt: BackendAttempt) -> BackendAttempt: ...
    def retrieve(self, attempt: BackendAttempt) -> BackendAttempt: ...
