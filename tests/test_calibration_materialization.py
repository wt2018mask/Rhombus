"""Commit B tests: Brownian materialization and artifact/attempt binding."""
import json

import numpy as np
import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration import (
    CalibrationClass,
    CalibrationDatasetManifest,
    CalibrationPlan,
    CalibrationReplicateManifest,
    CalibrationScope,
    GeneratorSpec,
    SplitAssignment,
    TruthRecord,
    TruthType,
)
from rudeus.science.calibration_execution import (
    build_calibration_task,
    materialize_replicate,
)
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.contracts import canonical_bytes, digest


def _h(*parts):
    return digest({"test": list(parts)})


def _scope():
    return CalibrationScope(
        estimator="free_intercept_OLS_MSD", estimator_version="v1",
        resampling_method="m", resampling_version="2", protocol_hash=_h("protocol"),
        estimand="D_self", units="m2/s",
        generator_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_version="gv",
        truth_type=TruthType.GENERATED_MODEL, truth_model_version="tmv",
        species_composition={"Li": 4}, n_particles=4,
        duration_ps=80.0, sampling_interval_ps=1.0, lag_steps=(1, 2),
        code_revision="f" * 40)


def _truth():
    return TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.GENERATED_MODEL,
        value={"D_m2_per_s": 1.5e-9}, code_revision="f" * 40)


def _generator(**over):
    params = dict(n_frames=20, n_ions=4,
                  diffusion_tensor=np.eye(3).tolist(), dt_ps=1.0)
    params.update(over)
    return GeneratorSpec(
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_name="brownian",
        generator_version="synthetic-v1", parameters=params,
        initialization_spec={}, seed_semantics="pcg64",
        output_coordinate_contract={}, code_hash=_h("code"))


def _graph(store, generator=None):
    scope_h = store.store(_scope())
    truth_h = store.store(_truth())
    gen_h = store.store(generator or _generator())
    plan = CalibrationPlan(
        objective="pilot", scope_hashes=(scope_h,),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",), truth_requirements={},
        split_rules={}, seed_policy={}, dev_replicate_ids=("rep-1",),
        heldout_replicate_ids=(), independence_rules={},
        selection_stopping_policy={}, frozen_analysis_fields=("estimator",),
        code_revision="f" * 40)
    plan_h = store.store(plan)
    dataset = CalibrationDatasetManifest(
        dataset_id="ds-1", plan_hash=plan_h, scope_hash=scope_h,
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",), trajectory_ids=("traj-1",),
        truth_record_hashes=(truth_h,), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(gen_h,), artifact_manifest_hashes=(),
        attempted_replicate_ids=("rep-1",))
    dataset_h = store.store(dataset)
    task = build_calibration_task(
        plan_hash=plan_h, scope_hash=scope_h, dataset_manifest_hash=dataset_h,
        generator_spec_hash=gen_h, truth_record_hash=truth_h,
        replicate_id="rep-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.DEV, seed=7, code_revision="f" * 40)
    return {"task": task, "plan": plan_h, "scope": scope_h, "dataset": dataset_h,
            "generator": gen_h, "truth": truth_h}


def test_same_task_same_seed_byte_identical(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    first = materialize_replicate(task=graph["task"], calibration_store=store,
                                  artifact_root=tmp_path / "artifacts")
    second = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    assert first["artifact_status"] == second["artifact_status"] == "STORED"
    assert first["trajectory_logical_hash"] == second["trajectory_logical_hash"]
    first_bytes = (tmp_path / "artifacts" / "blobs"
                   / first["trajectory_logical_hash"]).read_bytes()
    assert first_bytes == (tmp_path / "artifacts" / "blobs"
                           / second["trajectory_logical_hash"]).read_bytes()


def test_different_seeds_separately_addressable(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    task = graph["task"]
    other = build_calibration_task(
        plan_hash=task.config["plan_hash"], scope_hash=task.config["scope_hash"],
        dataset_manifest_hash=task.config["dataset_manifest_hash"],
        generator_spec_hash=task.config["generator_spec_hash"],
        truth_record_hash=task.config["truth_record_hash"],
        replicate_id="rep-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.DEV, seed=8, code_revision="f" * 40)
    assert other.task_id != task.task_id
    first = materialize_replicate(task=task, calibration_store=store,
                                  artifact_root=tmp_path / "artifacts")
    second = materialize_replicate(task=other, calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    assert first["trajectory_logical_hash"] != second["trajectory_logical_hash"]
    assert first["replicate_manifest_hash"] != second["replicate_manifest_hash"]


def test_logical_hash_is_digest_of_decoded_object(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    result = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    data = (tmp_path / "artifacts" / "blobs"
            / result["trajectory_logical_hash"]).read_bytes()
    assert digest(json.loads(data)) == result["trajectory_logical_hash"]


def test_readback_equals_serialized_object(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    result = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    data = (tmp_path / "artifacts" / "blobs"
            / result["trajectory_logical_hash"]).read_bytes()
    payload = json.loads(data)
    assert payload["format"] == "calibration-trajectory-v1"
    assert payload["species"] == ["Li"] * 4
    assert payload["seed"] == 7
    assert len(payload["positions"]) == 20
    assert payload["frame_steps"] == list(range(20))
    assert canonical_bytes(payload) == data


def test_attempt_binds_task(tmp_path):
    from rudeus.execution.contracts import ExecutionAttempt
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    result = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    matches = list((tmp_path / "artifacts" / "attempts").glob("*.json"))
    assert len(matches) == 1
    attempt = ExecutionAttempt.from_dict(json.loads(matches[0].read_text()))
    assert attempt.attempt_id == result["attempt_id"]
    assert attempt.task_id == graph["task"].task_id
    assert attempt.task_content_hash == graph["task"].content_hash
    assert attempt.status == "COMPLETED" and attempt.failure_class is None


def test_manifest_binds_attempt_and_parents(tmp_path):
    from rudeus.execution.contracts import ArtifactManifest
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    result = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    matches = list((tmp_path / "artifacts" / "trajectory_manifests").glob("*.json"))
    assert len(matches) == 1
    manifest = ArtifactManifest.from_dict(json.loads(matches[0].read_text()))
    assert manifest.logical_hash == result["trajectory_logical_hash"]
    assert manifest.producer_attempt == result["attempt_id"]
    assert (set(manifest.parent_artifact_hashes)
            == set(graph["task"].input_artifact_hashes))
    assert manifest.format == "json"
    assert manifest.format_version == "calibration-trajectory-v1"


def test_replicate_binds_all_hashes(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    result = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    replicate = store.retrieve(CalibrationReplicateManifest,
                               result["replicate_manifest_hash"])
    assert replicate.trajectory_artifact_hash == result["trajectory_logical_hash"]
    assert replicate.truth_record_hash == graph["truth"]
    assert replicate.scientific_outcome == "COMPLETED"
    assert replicate.computational_outcome is None
    assert replicate.event_info is None
    assert replicate.conditions["scope_hash"] == graph["scope"]
    assert replicate.conditions["seed"] == 7


def test_n_frames_one_succeeds(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, generator=_generator(n_frames=1))
    result = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    assert result["artifact_status"] == "STORED"
    payload = json.loads((tmp_path / "artifacts" / "blobs"
                          / result["trajectory_logical_hash"]).read_bytes())
    assert len(payload["positions"]) == 1


def test_zero_diffusion_succeeds(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, generator=_generator(
        diffusion_tensor=np.zeros((3, 3)).tolist()))
    result = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    assert result["artifact_status"] == "STORED"
    replicate = store.retrieve(CalibrationReplicateManifest,
                               result["replicate_manifest_hash"])
    assert replicate.scientific_outcome == "COMPLETED"
    assert replicate.event_info is None


def test_unsupported_class_rejected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    other = GeneratorSpec(
        calibration_class=CalibrationClass.CAGED_CONFINED, generator_name="caged",
        generator_version="synthetic-v1", parameters={}, initialization_spec={},
        seed_semantics="pcg64", output_coordinate_contract={}, code_hash=_h("code"))
    other_h = store.store(other)
    scope = _scope()
    scope_h = store.store(scope)
    truth_h = store.store(_truth())
    plan = CalibrationPlan(
        objective="pilot", scope_hashes=(scope_h,),
        class_inventory=(CalibrationClass.CAGED_CONFINED,),
        parameter_cell_ids=("cell-a",), truth_requirements={},
        split_rules={}, seed_policy={}, dev_replicate_ids=("rep-1",),
        heldout_replicate_ids=(), independence_rules={},
        selection_stopping_policy={}, frozen_analysis_fields=("estimator",),
        code_revision="f" * 40)
    plan_h = store.store(plan)
    dataset = CalibrationDatasetManifest(
        dataset_id="ds-1", plan_hash=plan_h, scope_hash=scope_h,
        calibration_class=CalibrationClass.CAGED_CONFINED,
        parameter_cell_ids=("cell-a",), trajectory_ids=("traj-1",),
        truth_record_hashes=(truth_h,), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(other_h,), artifact_manifest_hashes=(),
        attempted_replicate_ids=("rep-1",))
    dataset_h = store.store(dataset)
    task = build_calibration_task(
        plan_hash=plan_h, scope_hash=scope_h, dataset_manifest_hash=dataset_h,
        generator_spec_hash=other_h, truth_record_hash=truth_h,
        replicate_id="rep-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.DEV, seed=7, code_revision="f" * 40)
    result = materialize_replicate(task=task, calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    assert result["artifact_status"] == "FAILED"
    assert result["failure_class"] == "UNSUPPORTED_INPUT"


def test_generator_failure_persists_failed_attempt(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, generator=_generator(
        diffusion_tensor=(-np.eye(3)).tolist()))
    result = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    assert result["artifact_status"] == "FAILED"
    assert "replicate_manifest_hash" not in result
    matches = list((tmp_path / "artifacts" / "attempts").glob("*.json"))
    assert len(matches) == 1
    from rudeus.execution.contracts import ExecutionAttempt
    attempt = ExecutionAttempt.from_dict(json.loads(matches[0].read_text()))
    assert attempt.status == "FAILED" and attempt.failure_class is not None


def test_persistence_conflict_fails_closed(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    probe = materialize_replicate(task=graph["task"], calibration_store=store,
                                  artifact_root=tmp_path / "probe")
    assert probe["artifact_status"] == "STORED"
    logical = probe["trajectory_logical_hash"]
    blocked = tmp_path / "blocked" / "blobs"
    blocked.mkdir(parents=True)
    (blocked / logical).write_bytes(b'{"forged": true}')
    result = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "blocked")
    assert result["artifact_status"] == "FAILED"
    assert result["failure_class"] == "INTEGRITY"
    assert (blocked / logical).read_bytes() == b'{"forged": true}'


def test_idempotent_rematerialization(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    first = materialize_replicate(task=graph["task"], calibration_store=store,
                                  artifact_root=tmp_path / "artifacts")
    second = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    assert first["artifact_status"] == second["artifact_status"] == "STORED"
    assert (first["trajectory_logical_hash"] == second["trajectory_logical_hash"]
            and first["replicate_manifest_hash"] != second["replicate_manifest_hash"])
    assert first["attempt_id"] != second["attempt_id"]


def test_scientific_bytes_carry_no_operational_data(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    result = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    data = (tmp_path / "artifacts" / "blobs"
            / result["trajectory_logical_hash"]).read_bytes()
    payload = json.loads(data)
    assert set(payload) == {"format", "replicate_id", "species", "cell", "positions",
                            "frame_steps", "dt_ps", "seed", "generator_spec_hash",
                            "scope_hash", "numpy_version"}
    text = data.decode("utf-8")
    assert str(tmp_path) not in text
    assert "artifact_status" not in text and "failure_class" not in text


def test_result_has_no_scientific_verdict(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    result = materialize_replicate(task=graph["task"], calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    assert set(result) == {"replicate_manifest_hash", "trajectory_logical_hash",
                           "attempt_id", "artifact_status"}
    for key in ("verdict", "PASS", "FAIL", "qualification", "bounds", "coverage"):
        assert key not in result
