"""Provider-neutral remote records and verification, without scheduling."""
from dataclasses import dataclass, field, replace
from collections.abc import Mapping
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


def _unknown_capability():
    return {"state": "UNKNOWN", "value": None}


@dataclass(frozen=True, kw_only=True)
class BackendCapabilities(Record):
    """Provider capability evidence; unknown is explicit and never inferred."""
    backend_identity: str
    verification_state: str = "UNKNOWN"
    cpu: dict = field(default_factory=_unknown_capability)
    gpu: dict = field(default_factory=_unknown_capability)
    gpu_type: dict = field(default_factory=_unknown_capability)
    memory_bytes: dict = field(default_factory=_unknown_capability)
    runtime_limit_s: dict = field(default_factory=_unknown_capability)
    preemption: dict = field(default_factory=_unknown_capability)
    network: dict = field(default_factory=_unknown_capability)
    persistent_storage: dict = field(default_factory=_unknown_capability)
    submission: dict = field(default_factory=_unknown_capability)
    status_polling: dict = field(default_factory=_unknown_capability)
    artifact_retrieval: dict = field(default_factory=_unknown_capability)
    authentication: dict = field(default_factory=_unknown_capability)
    quota_availability: dict = field(default_factory=_unknown_capability)
    supported_task_modes: dict = field(default_factory=_unknown_capability)
    version: str = "backend-capabilities-v1"

    def validate(self):
        super().validate()
        if not self.backend_identity or self.version != "backend-capabilities-v1":
            raise ValueError("invalid backend capability identity/version")
        if self.verification_state not in ("UNKNOWN", "VERIFIED"):
            raise ValueError("invalid capability verification state")
        for name in ("cpu", "gpu", "gpu_type", "memory_bytes", "runtime_limit_s", "preemption",
                     "network", "persistent_storage", "submission", "status_polling",
                     "artifact_retrieval", "authentication", "quota_availability", "supported_task_modes"):
            item = getattr(self, name)
            if set(item) != {"state", "value"} or item["state"] not in ("UNKNOWN", "VERIFIED", "UNSUPPORTED"):
                raise ValueError(f"invalid capability evidence: {name}")
            if item["state"] == "UNKNOWN" and item["value"] is not None:
                raise ValueError(f"unknown capability must not invent a value: {name}")


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
                or code.bundle_hash != self.bundle_hash or code.code_revision != task.code_revision
                or (task.code_bundle_hash is not None and task.code_bundle_hash != self.bundle_hash)):
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
    "CREATED": {"PREPARED", "FAILED"},
    "PREPARED": {"SUBMITTED", "FAILED"},
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
    task_id: str | None = field(default=None, metadata={"omit_none": True})
    task_content_hash: str
    task_bundle_hash: str
    backend: str
    state: str = "CREATED"
    remote_run_id: str | None = None
    provider_provenance: dict | None = field(default=None, metadata={"omit_none": True})
    previous_hash: str | None = None
    failure_class: str | None = None
    evidence_hash: str | None = None
    receipt_hash: str | None = None
    creation_provenance: dict | None = field(default=None, metadata={"omit_none": True})
    version: str = "backend-attempt-v1"

    def validate(self):
        super().validate()
        for value in (self.attempt_id, self.task_content_hash, self.task_bundle_hash):
            require_hash(value)
        if self.task_id is not None:
            require_hash(self.task_id)
        for value in (self.previous_hash, self.evidence_hash, self.receipt_hash):
            if value is not None:
                require_hash(value)
        if self.version != "backend-attempt-v1" or self.state not in TRANSITIONS or not self.backend:
            raise ValueError("invalid backend attempt")
        if self.provider_provenance is not None:
            if (not isinstance(self.provider_provenance, Mapping)
                    or self.provider_provenance.get("backend_identity") != self.backend
                    or self.state not in ("SUBMITTED", "RUNNING", "COMPLETED", "PREEMPTED", "INTERRUPTED", "FAILED")):
                raise ValueError("provider provenance must be bound to an attempted provider submission")
        if self.state == "PREPARED" and self.previous_hash is None:
            raise ValueError("prepared attempt must link to its CREATED snapshot")
        if self.creation_provenance is not None:
            if (self.creation_provenance.get("contract") != self.version
                    or self.creation_provenance.get("task_bundle_hash") != self.task_bundle_hash
                    or self.creation_provenance.get("task_id", self.task_id) != self.task_id
                    or self.creation_provenance.get("backend_identity") != self.backend):
                raise ValueError("attempt creation provenance binding mismatch")
        failed = self.state in ("FAILED", "PREEMPTED", "INTERRUPTED")
        if failed != (self.failure_class is not None):
            raise ValueError("operational failure classification required only for failure")
        if self.failure_class is not None and self.failure_class not in {item.value for item in FailureClass}:
            raise ValueError("unsupported operational failure class")
        if self.state not in ("CREATED", "PREPARED", "FAILED") and not self.remote_run_id:
            raise ValueError("provider run identity required")
        if (self.state in ("RETRIEVED", "DURABLY_INGESTED")) != (self.evidence_hash is not None):
            raise ValueError("retrieval evidence identity mismatch")
        if (self.state == "DURABLY_INGESTED") != (self.receipt_hash is not None):
            raise ValueError("durability receipt identity mismatch")


def new_attempt(bundle, backend):
    task = TaskSpec.from_dict(bundle.task)
    return BackendAttempt(attempt_id=digest({"nonce": uuid.uuid4().hex, "bundle": bundle.content_hash}),
                          task_id=task.task_id,
                          task_content_hash=bundle.task_content_hash,
                          task_bundle_hash=bundle.content_hash, backend=backend,
                          creation_provenance={"contract": "backend-attempt-v1",
                                               "task_bundle_hash": bundle.content_hash,
                                               "task_id": task.task_id,
                                               "backend_identity": backend})


def prepare_attempt(bundle, backend):
    """Create an immutable PREPARED snapshot without performing provider I/O."""
    return _advance(new_attempt(bundle, backend), "PREPARED")


def validate_prepared_attempt(attempt, bundle, backend):
    """Fail closed unless a PREPARED snapshot is bound to this exact task/bundle/backend."""
    if not isinstance(bundle, TaskBundle):
        bundle = TaskBundle.from_dict(bundle)
    bundle.validate()
    if not isinstance(attempt, BackendAttempt):
        raise ExecutionError("prepared backend attempt required", "INTEGRITY")
    attempt.validate()
    task = TaskSpec.from_dict(bundle.task)
    if (attempt.state != "PREPARED" or attempt.backend != backend
            or attempt.task_id != task.task_id
            or attempt.task_content_hash != bundle.task_content_hash
            or attempt.task_bundle_hash != bundle.content_hash
            or (task.code_bundle_hash is not None and task.code_bundle_hash != bundle.bundle_hash)):
        raise ExecutionError("prepared attempt task, bundle, code, or backend binding mismatch", "INTEGRITY")
    return bundle


def advance(attempt, state, **changes):
    if state in ("RETRIEVED", "DURABLY_INGESTED"):
        raise ExecutionError("artifact/receipt verification required for this transition", "INTEGRITY")
    return _advance(attempt, state, **changes)


def _advance(attempt, state, **changes):
    if state not in TRANSITIONS[attempt.state] or set(changes) - {
            "remote_run_id", "provider_provenance", "failure_class", "evidence_hash", "receipt_hash"}:
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
    return classify_failure(exc).value


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
    def prepare(self, task_bundle: TaskBundle, resource_requirements: dict) -> BackendAttempt: ...
    def submit(self, attempt: BackendAttempt, task_bundle: TaskBundle,
               resource_requirements: dict) -> BackendAttempt: ...
    def status(self, attempt: BackendAttempt) -> BackendAttempt: ...
    def retrieve(self, attempt: BackendAttempt) -> BackendAttempt: ...
