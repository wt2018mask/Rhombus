"""Synthetic remote-record handoff; no MLIP or scientific compute is launched."""
from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import unittest

import numpy as np

from rudeus.execution.contracts import ArtifactManifest, ExecutionAttempt, ExecutionError
from rudeus.mlip.p2 import protocol_config_hash
from rudeus.mlip.p2_traj import build_traj_payload, write_traj_artifact
from rudeus.mlip.p25 import P25_DEFAULTS, analyze_p25
from rudeus.mlip.sharding import structure_dict_sha256
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science.pipeline_handoff import (plan_p1, plan_p2, plan_p25, plan_p3,
                                             verify_output)
from rudeus.science.p3 import P3Protocol


REVISION = "0c61ee524b1486ca18e5ad7466d2c0d4d327b39d"


def manifest(value, producer, parents=(), *, trajectory_hash=None):
    data = value if isinstance(value, bytes) else canonical_bytes(value)
    artifact = ArtifactManifest(
        logical_hash=trajectory_hash or digest(value),
        canonicalization_version="p2-traj-v1" if trajectory_hash else "canonical-json-v1",
        raw_hash=hashlib.sha256(data).hexdigest(),
        format="p2-traj" if trajectory_hash else "json",
        format_version="p2-traj-v1" if trajectory_hash else "scientific-freeze-v1",
        size_bytes=len(data), durable_locator="fixture", producer_attempt=producer,
        parent_artifact_hashes=tuple(parents), retrieval_verification={})
    return artifact, data


def attempt(task, identity, outputs, *, status="COMPLETED"):
    return ExecutionAttempt(
        attempt_id=identity, task_id=task.task_id, task_content_hash=task.content_hash,
        backend="synthetic-remote", remote_session_id=None, started_at="fixed",
        ended_at="fixed", runtime_s=0, hardware={}, environment={}, precision=None,
        exit_status=0 if status == "COMPLETED" else 1, status=status,
        termination_reason="fixture", failure_class=None if status == "COMPLETED" else "TIMEOUT",
        logs=(), output_manifest=outputs)


class PipelineHandoffTest(unittest.TestCase):
    def test_candidate_through_p25_terminal_and_retry_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            structure = {"lattice": "synthetic", "sites": ["Li", "Li"]}
            candidate = {"batch_id": "fixture-batch", "child_material_id": "fixture-candidate",
                         "parent_id": "fixture-parent", "p0_state": "PLAUSIBLE",
                         "structure_dict": structure,
                         "structure_sha256": structure_dict_sha256(structure)}
            candidate_manifest, candidate_bytes = manifest(candidate, digest("candidate-producer"))
            p1_task = plan_p1(candidate, candidate_manifest, candidate_bytes,
                              {"protocol": "synthetic-P1"}, REVISION)
            rejected = {**candidate, "p0_state": "FAIL"}
            rejected_manifest, rejected_bytes = manifest(rejected, digest("candidate-producer"))
            self.assertIsNone(plan_p1(rejected, rejected_manifest, rejected_bytes,
                                      {"protocol": "synthetic-P1"}, REVISION))
            self.assertEqual(p1_task, plan_p1(candidate, candidate_manifest, candidate_bytes,
                                               {"protocol": "synthetic-P1"}, REVISION))
            relaxed = {"lattice": "synthetic-relaxed", "sites": ["Li", "Li"]}
            p1_record = {**candidate, "result": {"p1_verdict": "KEEP_FOR_P2",
                "input_structure_sha256": candidate["structure_sha256"],
                "relaxed_structure_dict": relaxed,
                "relaxed_structure_sha256": structure_dict_sha256(relaxed)}}
            p1_attempt_id = digest("p1-success")
            p1_manifest, p1_bytes = manifest(p1_record, p1_attempt_id, p1_task.input_artifact_hashes)
            relaxed_manifest, relaxed_bytes = manifest(relaxed, p1_attempt_id,
                                                       p1_task.input_artifact_hashes)
            p1_attempts = [attempt(p1_task, digest("p1-timeout"), {}, status="FAILED"),
                           attempt(p1_task, p1_attempt_id, {"p1.json": p1_manifest.content_hash,
                                           "relaxed.json": relaxed_manifest.content_hash})]
            p1 = verify_output(p1_task, p1_attempts, p1_manifest, p1_bytes, "p1.json")
            relaxed_output = verify_output(p1_task, p1_attempts, relaxed_manifest,
                                           relaxed_bytes, "relaxed.json")
            failed_p1 = replace(p1, value={**p1_record,
                "result": {**p1_record["result"], "p1_verdict": "FAIL_CONVERGENCE"}})
            self.assertIsNone(plan_p2(failed_p1, relaxed_output,
                                      {"p2_protocol_version": "synthetic-P2"}, REVISION,
                                      seed=7, temperature=500))
            protocol = {"p2_protocol_version": "synthetic-P2", "temperature_K": 500}
            p2_task = plan_p2(p1, relaxed_output, protocol, REVISION, seed=7, temperature=500)
            self.assertEqual(p2_task, plan_p2(p1, relaxed_output, protocol, REVISION,
                                               seed=7, temperature=500))
            record = {"species": ["Li", "Li"], "cell": np.eye(3) * 10,
                      "timestep_fs": 10, "sample_interval_steps": 10, "equil_steps": 0,
                      "production_steps": 60, "seed": 7,
                      "frames": [{"phase": "production", "md_step": i * 10,
                                  "positions": np.array([[1., 1., 1.], [2., 2., 2.]])}
                                 for i in range(1, 7)]}
            trajectory = build_traj_payload(record, {"batch_id": candidate["batch_id"],
                "p2_config_hash": protocol_config_hash(protocol), "p2_protocol": protocol})
            trajectory_path = root / "trajectory.npz"
            trajectory_hash = write_traj_artifact(trajectory_path, trajectory)
            p2_record = {"batch_id": candidate["batch_id"], "result": {
                "candidate_material_id": candidate["child_material_id"],
                "parent_id": candidate["parent_id"], "batch_id": candidate["batch_id"],
                "p2_verdict": "PASS", "dynamic_state": "PASS",
                "p2_input_relaxed_sha256": structure_dict_sha256(relaxed),
                "p2_config_hash": protocol_config_hash(protocol), "p2_protocol": protocol,
                "p2_protocol_version": protocol["p2_protocol_version"], "seed": 7,
                "temperature_K": 500, "trajectory_artifact": {
                    "path": str(trajectory_path), "sha256": trajectory_hash,
                    "format_version": "p2-traj-v1"}}}
            p2_attempt_id = digest("p2-success")
            p2_manifest, p2_bytes = manifest(p2_record, p2_attempt_id, p2_task.input_artifact_hashes)
            traj_manifest, traj_bytes = manifest(trajectory_path.read_bytes(), p2_attempt_id,
                              p2_task.input_artifact_hashes, trajectory_hash=trajectory_hash)
            p2_attempts = [attempt(p2_task, p2_attempt_id, {
                "p2.json": p2_manifest.content_hash, "trajectory.npz": traj_manifest.content_hash})]
            p2 = verify_output(p2_task, p2_attempts, p2_manifest, p2_bytes, "p2.json")
            traj = verify_output(p2_task, p2_attempts, traj_manifest, traj_bytes, "trajectory.npz")
            failed_p2 = replace(p2, value={**p2_record,
                "result": {**p2_record["result"], "p2_verdict": "FAIL"}})
            self.assertIsNone(plan_p25(failed_p2, traj, P25_DEFAULTS, REVISION))
            p25_task = plan_p25(p2, traj, P25_DEFAULTS, REVISION)
            p25_record = {"batch_id": candidate["batch_id"], "p25_config": P25_DEFAULTS,
                          "result": analyze_p25(p2_record, dict(P25_DEFAULTS),
                                                p2_result_path="synthetic-p2.json")}
            self.assertEqual(p25_record["result"]["transport_state"], "INDETERMINATE")
            p25_attempt_id = digest("p25-success")
            p25_manifest, p25_bytes = manifest(p25_record, p25_attempt_id,
                                                p25_task.input_artifact_hashes)
            p25 = verify_output(p25_task, [attempt(p25_task, p25_attempt_id,
                {"p25.json": p25_manifest.content_hash})], p25_manifest, p25_bytes, "p25.json")
            self.assertIsNone(plan_p3(p25, p2, traj, P3Protocol(target_species="Li"), REVISION))
            self.assertEqual(p1_task.task_id, p1_attempts[0].task_id)
            self.assertNotEqual(p1_attempts[0].attempt_id, p1_attempts[1].attempt_id)
            with self.assertRaises(ExecutionError):
                verify_output(p2_task, p2_attempts, traj_manifest, b"corrupt", "trajectory.npz")
            with self.assertRaises(ExecutionError):
                plan_p3(p25, p1, traj, P3Protocol(target_species="Li"), REVISION)


if __name__ == "__main__":
    unittest.main()
