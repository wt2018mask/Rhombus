"""Backend-neutral, read-only handoff of the legacy P1/P2/P2.5 records.

This adapter does not assign scientific verdicts. It verifies retained bytes and
execution bindings before using the existing stage verdicts to plan the next
scientific task. The legacy batch runners remain responsible for the science.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from rudeus.execution.contracts import ArtifactManifest, ExecutionAttempt, ExecutionError, TaskSpec
from rudeus.mlip.p2 import protocol_config_hash
from rudeus.mlip.p25 import p25_config_hash
from rudeus.mlip.sharding import structure_dict_sha256
from rudeus.science.contracts import digest
from rudeus.science.evidence import verified_bytes
from rudeus.science.p3 import P3Protocol


@dataclass(frozen=True)
class VerifiedOutput:
    task: TaskSpec
    attempt: ExecutionAttempt
    manifest: ArtifactManifest
    value: object


def verify_output(task: TaskSpec, attempts: Sequence[ExecutionAttempt],
                  manifest: ArtifactManifest, data: bytes, logical_name: str) -> VerifiedOutput:
    """Select one immutable successful attempt; failed backend attempts may coexist."""
    if len({a.attempt_id for a in attempts}) != len(attempts):
        raise ExecutionError("duplicate execution attempt", "INTEGRITY")
    if not attempts or any(a.task_id != task.task_id or a.task_content_hash != task.content_hash
                           for a in attempts):
        raise ExecutionError("attempt changed scientific task identity", "INTEGRITY")
    if sum(a.status == "COMPLETED" for a in attempts) != 1:
        raise ExecutionError("ambiguous successful scientific execution", "INTEGRITY")
    if logical_name not in task.expected_outputs:
        raise ExecutionError("output not declared by task", "INTEGRITY")
    matches = [a for a in attempts if a.attempt_id == manifest.producer_attempt]
    if len(matches) != 1:
        raise ExecutionError("artifact producer attempt unavailable", "INTEGRITY")
    attempt = matches[0]
    if set(attempt.output_manifest) != set(task.expected_outputs):
        raise ExecutionError("successful attempt output set differs from task", "INTEGRITY")
    if (attempt.task_content_hash != task.content_hash or attempt.status != "COMPLETED"
            or attempt.exit_status != 0 or attempt.output_manifest.get(logical_name) != manifest.content_hash):
        raise ExecutionError("artifact is not bound to a successful full TaskSpec", "INTEGRITY")
    if set(manifest.parent_artifact_hashes) != set(task.input_artifact_hashes):
        raise ExecutionError("artifact input ancestry mismatch", "INTEGRITY")
    return VerifiedOutput(task, attempt, manifest, verified_bytes(manifest, data))


def _task(stage: str, candidate_id: str, config: Mapping, inputs: Sequence[str],
          dependencies: Sequence[str], code_revision: str, outputs: tuple[str, ...],
          *, temperature: float | None = None, seed: int | None = None,
          provenance: Mapping | None = None) -> TaskSpec:
    if len(code_revision) not in (40, 64) or any(c not in "0123456789abcdef" for c in code_revision):
        raise ExecutionError("scientific task needs an explicit code commit", "UNSUPPORTED_INPUT")
    return TaskSpec(candidate_id=candidate_id, stage=stage, protocol_hash=digest(config),
                    config=config, input_artifact_hashes=tuple(inputs),
                    dependencies=tuple(dependencies), code_revision=code_revision,
                    resource_requirements={"execution": "remote"}, expected_outputs=outputs,
                    retry_policy={"infrastructure": "new_attempt_same_task"},
                    temperature=temperature, seed=seed, provenance=provenance)


def plan_p1(candidate: Mapping, candidate_manifest: ArtifactManifest, candidate_bytes: bytes,
            config: Mapping, code_revision: str) -> TaskSpec | None:
    """P0 rejection is terminal. Candidate bytes and legacy structure hash must agree."""
    if verified_bytes(candidate_manifest, candidate_bytes) != candidate:
        raise ExecutionError("candidate artifact differs from supplied record", "INTEGRITY")
    if candidate.get("p0_state") == "FAIL":
        return None
    if candidate.get("p0_state") not in ("PLAUSIBLE", "SUPPORTED"):
        raise ExecutionError("P0 eligibility unresolved", "UNSUPPORTED_INPUT")
    candidate_id = candidate.get("child_material_id")
    if (not candidate_id or not candidate.get("batch_id") or not candidate.get("parent_id")
            or not isinstance(candidate.get("structure_dict"), dict)
            or candidate.get("structure_sha256") != structure_dict_sha256(candidate["structure_dict"])):
        raise ExecutionError("candidate identity or structure binding incomplete", "INTEGRITY")
    return _task("P1", candidate_id, config, (candidate_manifest.logical_hash,), (),
                 code_revision, ("p1.json", "relaxed.json"),
                 provenance={"batch_id": candidate["batch_id"],
                             "parent_id": candidate["parent_id"],
                             "p0_state": candidate["p0_state"],
                             "legacy_structure_sha256": candidate["structure_sha256"]})


def plan_p2(p1: VerifiedOutput, relaxed_output: VerifiedOutput, config: Mapping, code_revision: str,
            *, seed: int, temperature: float) -> TaskSpec | None:
    record = p1.value
    if (p1.task.stage != "P1" or p1.task != relaxed_output.task
            or p1.attempt.attempt_id != relaxed_output.attempt.attempt_id
            or not isinstance(record, dict)):
        raise ExecutionError("expected verified P1 record", "INTEGRITY")
    result = record.get("result") or {}
    if not isinstance(result, dict):
        raise ExecutionError("malformed P1 result", "INTEGRITY")
    provenance = p1.task.provenance or {}
    if result.get("p1_verdict") != "KEEP_FOR_P2":
        return None
    relaxed = result.get("relaxed_structure_dict")
    if (record.get("child_material_id") != p1.task.candidate_id
            or record.get("parent_id") != provenance.get("parent_id")
            or record.get("batch_id") != provenance.get("batch_id")
            or record.get("p0_state") != provenance.get("p0_state")
            or record.get("structure_sha256") != provenance.get("legacy_structure_sha256")
            or not isinstance(relaxed, dict) or relaxed_output.value != relaxed
            or result.get("relaxed_structure_sha256") != structure_dict_sha256(relaxed)
            or result.get("input_structure_sha256") != record.get("structure_sha256")
            or record.get("p0_state") == "FAIL"):
        raise ExecutionError("P1 identity, P0, or relaxed structure binding mismatch", "INTEGRITY")
    return _task("P2", p1.task.candidate_id, config,
                 (p1.manifest.logical_hash, relaxed_output.manifest.logical_hash), (p1.task.task_id,),
                 code_revision, ("p2.json", "trajectory.npz"), temperature=temperature, seed=seed,
                 provenance={"legacy_relaxed_sha256": structure_dict_sha256(relaxed),
                             "batch_id": record["batch_id"], "parent_id": record["parent_id"]})


def plan_p25(p2: VerifiedOutput, trajectory: VerifiedOutput, config: Mapping,
             code_revision: str) -> TaskSpec | None:
    if (p2.task.stage != "P2" or p2.task != trajectory.task
            or p2.attempt.attempt_id != trajectory.attempt.attempt_id):
        raise ExecutionError("P2 result and trajectory have different scientific tasks", "INTEGRITY")
    record = p2.value
    if not isinstance(record, dict):
        raise ExecutionError("malformed P2 record", "INTEGRITY")
    result = record.get("result") or {}
    if not isinstance(result, dict):
        raise ExecutionError("malformed P2 result", "INTEGRITY")
    provenance = p2.task.provenance or {}
    if result.get("p2_verdict") != "PASS":
        return None
    binding = result.get("trajectory_artifact") or {}
    if (result.get("candidate_material_id") != p2.task.candidate_id
            or result.get("batch_id") != record.get("batch_id")
            or record.get("batch_id") != provenance.get("batch_id")
            or result.get("parent_id") != provenance.get("parent_id")
            or result.get("dynamic_state") != "PASS"
            or result.get("p2_input_relaxed_sha256") != provenance.get("legacy_relaxed_sha256")
            or result.get("p2_protocol") != dict(p2.task.config)
            or result.get("p2_config_hash") != protocol_config_hash(dict(p2.task.config))
            or result.get("temperature_K") != p2.task.temperature
            or result.get("seed") != p2.task.seed
            or binding.get("sha256") != trajectory.manifest.logical_hash
            or binding.get("format_version") != trajectory.manifest.format_version):
        raise ExecutionError("P2 identity, config, or trajectory binding mismatch", "INTEGRITY")
    return _task("P2.5", p2.task.candidate_id, config,
                 (p2.manifest.logical_hash, trajectory.manifest.logical_hash),
                 (p2.task.task_id,), code_revision, ("p25.json",),
                 temperature=p2.task.temperature, seed=p2.task.seed)


def plan_p3(p25: VerifiedOutput, p2: VerifiedOutput, trajectory: VerifiedOutput,
            protocol: P3Protocol, code_revision: str) -> TaskSpec | None:
    if (p25.task.stage != "P2.5" or p2.task.stage != "P2"
            or trajectory.task != p2.task
            or trajectory.attempt.attempt_id != p2.attempt.attempt_id):
        raise ExecutionError("expected verified P2 and P2.5 records", "INTEGRITY")
    if not isinstance(p25.value, dict) or not isinstance(p2.value, dict):
        raise ExecutionError("malformed P2/P2.5 record", "INTEGRITY")
    result = p25.value.get("result") or {}
    if not isinstance(result, dict):
        raise ExecutionError("malformed P2.5 result", "INTEGRITY")
    provenance = result.get("provenance") or {}
    if (p25.task.candidate_id != p2.task.candidate_id
            or p2.task.task_id not in p25.task.dependencies
            or result.get("candidate_material_id") != p25.task.candidate_id
            or result.get("batch_id") != p2.value.get("batch_id")
            or result.get("parent_id") != p2.value["result"].get("parent_id")
            or result.get("p2_verdict") != "PASS"
            or result.get("p2_dynamic_state") != "PASS"
            or result.get("temperature_K") != p2.value["result"].get("temperature_K")
            or result.get("temperature_K") != p25.task.temperature
            or provenance.get("trajectory_artifact_sha256") != trajectory.manifest.logical_hash
            or provenance.get("p2_config_hash") != p2.value["result"].get("p2_config_hash")
            or provenance.get("p2_protocol_version") != p2.value["result"].get("p2_protocol_version")
            or provenance.get("p2_seed") != p2.task.seed
            or provenance.get("artifact_format_version") != trajectory.manifest.format_version
            or digest(p25.value.get("p25_config")) != p25.task.config_hash
            or provenance.get("p25_config_hash") != p25_config_hash(dict(p25.task.config))
            or not {p2.manifest.logical_hash, trajectory.manifest.logical_hash} <= set(
                p25.task.input_artifact_hashes)
            or result.get("target_species") != protocol.target_species):
        raise ExecutionError("P2.5 lineage or scientific scope mismatch", "INTEGRITY")
    if result.get("transport_state") != result.get("p25_verdict"):
        raise ExecutionError("P2.5 transport verdict aliases disagree", "INTEGRITY")
    if result.get("transport_state") != "DIFFUSIVE":
        return None
    return _task("P3", p25.task.candidate_id, protocol.to_dict(),
                 (p25.manifest.logical_hash, p2.manifest.logical_hash,
                  trajectory.manifest.logical_hash), (p25.task.task_id,),
                 code_revision, ("p3.json",), temperature=p25.task.temperature)
