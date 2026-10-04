"""Retained execution records for Git receipts; not execution attestation."""
import json

from rudeus.execution.code_bundle import CodeBundle, verify_bundle
from rudeus.execution.contracts import TaskSpec
from rudeus.execution.runtime import ExecutionManifest, RuntimeRecord, verify_execution_records
from rudeus.science.contracts import canonical_bytes, digest, require_hash
from rudeus.science.evidence import require


REFERENCE_FIELDS = frozenset(("execution_manifest_hash", "runtime_record_hash", "bundle_hash",
                              "launch_policy_version", "actual_execution_identity"))


def execution_context(archive):
    """Absent metadata is legacy; partial metadata must never silently downgrade."""
    provenance = archive["provenance"]
    output = next(m for m in provenance["manifests"] if digest(m) == provenance["record_manifest"])
    attempt = next(a for a in provenance["attempts"] if a["attempt_id"] == output["producer_attempt"])
    environment = attempt["environment"]
    require("code_identity" not in environment, "unqualified code identity is unsupported")
    if not REFERENCE_FIELDS.intersection(environment):
        return None
    require(REFERENCE_FIELDS <= environment.keys(), "incomplete execution provenance")
    require(environment["actual_execution_identity"] == "NOT_ATTESTED",
            "execution observations cannot attest actual execution identity")
    return TaskSpec.from_dict(provenance["task"]), attempt, environment


def verify_retained_execution(store, archive, *, git_root):
    """Reconstruct repository bytes and verify retained observations' references.

    The caller must additionally prove every returned path exists in its Git
    durability commit. Observations' historical truth is not independently proven.
    """
    task, attempt, environment = execution_context(archive)
    paths = set()

    def read(directory, identity, record_type):
        require_hash(identity)
        relative = f"{directory}/{identity}.json"
        data = store.path(relative).read_bytes()
        record = record_type.from_dict(json.loads(data))
        require(record.content_hash == identity and canonical_bytes(record) == data,
                "retained execution record identity/serialization mismatch")
        paths.add(relative)
        return record

    bundle = read("code_bundles", environment["bundle_hash"], CodeBundle)
    manifest = read("execution_manifests", environment["execution_manifest_hash"], ExecutionManifest)
    runtime = read("runtime_records", environment["runtime_record_hash"], RuntimeRecord)
    verify_bundle(bundle, environment["bundle_hash"], task, git_root=git_root)
    statuses = verify_execution_records(manifest, environment["execution_manifest_hash"], runtime,
                                       environment["runtime_record_hash"], bundle, task)
    require(manifest.attempt_id == attempt["attempt_id"]
            and manifest.task_content_hash == attempt["task_content_hash"]
            and manifest.launch_policy_version == environment["launch_policy_version"],
            "producing attempt/execution manifest binding mismatch")
    return {
        "code_revision": task.code_revision, "task_content_hash": task.content_hash,
        "attempt_id": attempt["attempt_id"], "bundle_hash": bundle.bundle_hash,
        "execution_manifest_hash": manifest.content_hash, "runtime_record_hash": runtime.content_hash,
        "launch_policy_version": manifest.launch_policy_version,
        "repository_bundle": "VERIFIED", **statuses,
    }, paths
