"""Execute one explicit P3 self-diffusion reanalysis and ingest verified evidence.

No scheduling or retries. Requires the requested Git revision checked out with
unchanged tracked Python sources. Local verification is not Git durability;
EvidenceStore.acknowledge_git remains the separate durability receipt operation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import uuid

import numpy as np

from rudeus.execution.contracts import (ArtifactManifest, ExecutionAttempt,
    ExecutionError, TaskSpec, classify_failure)
from rudeus.science.contracts import ClaimSpec, canonical_bytes, digest
from rudeus.science.evidence import (EvidenceStore, append_file, inside,
    integrity_errors, require, verified_bytes)
from rudeus.science.followups import generate_followups
from rudeus.science.p3 import P3Protocol, analyze_p3


def _supported(condition, message):
    if not condition:
        raise ExecutionError(message, "UNSUPPORTED_INPUT")


def _code_identity(task):
    root = Path(__file__).resolve().parents[2]
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True).stdout.decode().strip()
    with integrity_errors():
        revision = git("rev-parse", "HEAD")
        require(revision == task.code_revision, "requested code revision is not checked out")
        # The new runner can be tested before its commit. Its exact bytes are
        # recorded independently; existing computation code must match HEAD.
        require(not git("diff", "HEAD", "--", "rudeus", ":(exclude)rudeus/execution/local.py"),
                "tracked computation code differs from requested revision")
        untracked = git("ls-files", "--others", "--exclude-standard", "--", "rudeus").splitlines()
        require(not any(p.endswith(".py") and p != "rudeus/execution/local.py" for p in untracked),
                "untracked computation code is not pinned by the requested revision")
    return {"git_revision": revision,
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def _inputs(task, store, temporary):
    with integrity_errors():
        require(task.provenance is not None, "task has no originating evidence")
        origin = store.verify(task.provenance["evidence_hash"])
        generated = generate_followups(store, task.provenance["evidence_hash"])
        require(any(item["task"] == task.to_dict() for item in generated["tasks"]),
                "task differs from explicit verified follow-up request")
        source = origin["provenance"]
        spec = ClaimSpec.from_dict(origin["scientific_record"]["claim_spec"])
        protocol = P3Protocol.from_dict(task.to_dict()["config"])
        _supported(task.stage == "P3" and len(task.expected_outputs) == 1,
                   "local execution supports one P3 scientific record output")
        _supported(task.protocol_hash == spec.protocol_hash,
                   "local reanalysis requires the originating claim protocol")
        _supported(not any((protocol.charge_numbers, protocol.charge_species,
                            protocol.charge_justification)), "collective transport is not supported")
        _supported(task.replica is None, "replica execution is not supported")
        _supported(task.seed is None or (protocol.resampling is not None
                   and task.seed == protocol.resampling.seed), "task seed does not bind resampling")
        _supported(set(task.dependencies) == {TaskSpec.from_dict(source["task"]).task_id},
                   "only the verified originating task dependency is supported")
        _supported(not source["checks"] and not origin["scientific_record"]["assessment"]["conflicting_evidence"],
                   "local reanalysis does not supply additional assessment checks or conflicts")
        manifests = [ArtifactManifest.from_dict(value) for value in source["manifests"]]
        by_logical = {m.logical_hash: m for m in manifests}
        selected = set()
        def visit(identity):
            if identity in selected:
                return
            require(identity in by_logical, "missing task input artifact")
            selected.add(identity)
            for parent in by_logical[identity].parent_artifact_hashes:
                visit(parent)
        for identity in task.input_artifact_hashes:
            visit(identity)
        manifests = [m for m in manifests if m.logical_hash in selected]
        producer_ids = {m.producer_attempt for m in manifests}
        attempts = [a for a in source["attempts"] if a["attempt_id"] in producer_ids]
        manifest_ids = {m.content_hash for m in manifests}
        _supported(all(set(a["output_manifest"].values()) <= manifest_ids for a in attempts),
                   "input ancestry must contain every declared producer output")
        require({spec.protocol_hash, spec.provenance_identity} <= selected,
                "task inputs omit required scientific provenance")
        decoded = {}
        for manifest in manifests:
            data = store.path(f"blobs/{manifest.raw_hash}").read_bytes()
            decoded[manifest.logical_hash] = verified_bytes(manifest, data)
            append_file(inside(temporary, manifest.durable_locator), data)
        provenance = decoded[spec.provenance_identity]
        p2, p25 = provenance["p2"], provenance["p25"]
        require(p2["result"]["candidate_material_id"] == task.candidate_id,
                "trajectory candidate differs from task")
        binding = p2["result"]["trajectory_artifact"]
        require(binding["sha256"] in selected, "trajectory is not a task input ancestor")
        _supported(task.temperature is None or task.temperature == p2["result"]["temperature_K"],
                   "task temperature differs from verified trajectory")
        trajectory = by_logical[binding["sha256"]]
        # Restore a verified snapshot at the original relative binding. Never
        # rewrite historical payloads or dereference their old absolute paths.
        append_file(inside(temporary, binding["path"]),
                    store.path(f"blobs/{trajectory.raw_hash}").read_bytes())
    return spec, protocol, p2, p25, manifests, attempts


def execute_local(task: TaskSpec, store: EvidenceStore):
    """Run a generated immutable task once, returning a persisted attempt/ref.

    Failed runs append an ExecutionAttempt and expose no scientific verdict.
    A result is VERIFIED_LOCAL only after EvidenceStore publication succeeds.
    Filesystem failures preventing attempt persistence propagate to the caller.
    """
    started = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    identity = digest({"task_id": task.task_id, "execution_nonce": uuid.uuid4().hex})
    environment = {"python": sys.version, "numpy": np.__version__,
                   "scipy": version("scipy"), "ase": version("ase"),
                   "platform": platform.platform(), "executable": sys.executable,
                   "thread_settings": {key: os.environ.get(key) for key in
                       ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}}
    hardware = {"machine": platform.machine(), "processor": platform.processor(),
                "logical_cpu_count": os.cpu_count()}
    def attempt(error=None, outputs=None):
        return ExecutionAttempt(attempt_id=identity, task_id=task.task_id, backend="local",
            task_content_hash=task.content_hash,
            remote_session_id=None, started_at=started,
            ended_at=datetime.now(timezone.utc).isoformat(), runtime_s=time.perf_counter()-clock,
            hardware=hardware, environment=environment, precision="float64",
            exit_status=0 if error is None else 1, status="COMPLETED" if error is None else "FAILED",
            termination_reason="completed" if error is None else str(error),
            failure_class=None if error is None else classify_failure(error),
            logs=() if error is None else (str(error),), output_manifest=outputs or {})
    append_file(store.path(f"tasks/{task.content_hash}.json"), canonical_bytes(task))
    try:
        environment.update(_code_identity(task))
        with tempfile.TemporaryDirectory(prefix="rhombus-local-") as directory:
            temporary = Path(directory)
            spec, protocol, p2, p25, manifests, ancestors = _inputs(task, store, temporary)
            result = analyze_p3(p2, p25, protocol, artifact_root=temporary,
                                timestamp=started, claim_spec=spec)
            # Execution time belongs to the attempt, not the logical output.
            record = result["p3_scientific_record"]
            data = canonical_bytes(record)
            logical_hash = digest(record)
            output = ArtifactManifest(logical_hash=logical_hash,
                raw_hash=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
                format="json", format_version=spec.schema_version,
                canonicalization_version="canonical-json-v1", durable_locator=f"blobs/{logical_hash}",
                producer_attempt=identity, parent_artifact_hashes=task.input_artifact_hashes,
                retrieval_verification={"status": "VERIFIED_LOCAL", "verifier": "canonical-json-v1"})
            append_file(inside(temporary, output.durable_locator), data)
            verified_bytes(output, inside(temporary, output.durable_locator).read_bytes())
            completed = attempt(outputs={task.expected_outputs[0]: output.content_hash})
            request = {"task": task.to_dict(), "attempts": ancestors+[completed.to_dict()],
                "manifests": [m.to_dict() for m in manifests]+[output.to_dict()],
                "record_manifest": output.content_hash}
            evidence = store.publish(request, source_root=temporary)
        response = {"artifact_status": "VERIFIED_LOCAL", "artifact": output.to_dict(),
                    "evidence_hash": evidence.logical_hash, "git_ingestion": "NOT_ATTESTED",
                    "scientific_verdict": record["assessment"]["verdict"]}
    except Exception as exc:
        completed = attempt(error=exc)
        response = {"artifact_status": "FAILED", "scientific_verdict": None,
                    "failure_class": completed.failure_class.value, "reason": str(exc)}
    append_file(store.path(f"attempts/{identity}.json"), canonical_bytes(completed))
    return {**response, "task_id": task.task_id, "attempt": completed.to_dict()}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", help="one generated TaskSpec JSON file")
    parser.add_argument("--store-root", required=True)
    args = parser.parse_args(argv)
    try:
        with integrity_errors():
            task = TaskSpec.from_dict(json.loads(Path(args.task).read_text(encoding="utf-8-sig")))
        result = execute_local(task, EvidenceStore(args.store_root))
    except Exception as exc:
        result = {"artifact_status": "FAILED", "scientific_verdict": None,
                  "failure_class": classify_failure(exc).value, "reason": str(exc)}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["artifact_status"] == "VERIFIED_LOCAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
