"""Estimator adapter tests: verified trajectory -> existing P3 estimator."""
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
from rudeus.science.calibration_estimator import estimate_calibration_replicate
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
        species_composition={"Li": 2}, n_particles=2,
        duration_ps=8.0, sampling_interval_ps=1.0, lag_steps=(1, 2),
        code_revision="f" * 40)


def _config(**over):
    params = dict(lag_steps=[1, 2], fit_window_ps=[0.5, 2.5],
                  selected_species=["Li"], volume_A3=1000.0,
                  temperature_K=550.0, reference_frame="simulation_cell")
    params.update(over)
    return params


def _materialized(tmp_path, store=None, generator=None, seed=7):
    store = store or CalibrationStore(tmp_path / "store")
    scope_h = store.store(_scope())
    truth_h = store.store(TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.GENERATED_MODEL,
        value={"D_m2_per_s": 1.5e-9}, code_revision="f" * 40))
    gen_params = dict(n_frames=8, n_ions=2,
                      diffusion_tensor=(0.1 * np.eye(3)).tolist(), dt_ps=1.0)
    if generator is not None:
        gen_params.update(generator)
    gen_h = store.store(GeneratorSpec(
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_name="brownian",
        generator_version="synthetic-v1", parameters=gen_params,
        initialization_spec={}, seed_semantics="pcg64",
        output_coordinate_contract={}, code_hash=_h("code")))
    plan_h = store.store(CalibrationPlan(
        objective="pilot", scope_hashes=(scope_h,),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",), truth_requirements={},
        split_rules={}, seed_policy={}, dev_replicate_ids=("rep-1",),
        heldout_replicate_ids=(), independence_rules={},
        selection_stopping_policy={}, frozen_analysis_fields=("estimator",),
        code_revision="f" * 40))
    dataset_h = store.store(CalibrationDatasetManifest(
        dataset_id="ds-1", plan_hash=plan_h, scope_hash=scope_h,
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",), trajectory_ids=("traj-1",),
        truth_record_hashes=(truth_h,), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(gen_h,), artifact_manifest_hashes=(),
        attempted_replicate_ids=("rep-1",)))
    task = build_calibration_task(
        plan_hash=plan_h, scope_hash=scope_h, dataset_manifest_hash=dataset_h,
        generator_spec_hash=gen_h, truth_record_hash=truth_h,
        replicate_id="rep-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.DEV, seed=seed, code_revision="f" * 40)
    result = materialize_replicate(task=task, calibration_store=store,
                                   artifact_root=tmp_path / "artifacts")
    assert result["artifact_status"] == "STORED"
    return store, result


def _estimate(store, root, replicate_hash, **over):
    return estimate_calibration_replicate(
        calibration_store=store, artifact_root=root,
        replicate_manifest_hash=replicate_hash,
        estimator_config=_config(**over), code_revision="f" * 40)


def test_successful_estimation_binds_provenance(tmp_path):
    store, materialized = _materialized(tmp_path)
    result = _estimate(store, tmp_path / "artifacts",
                       materialized["replicate_manifest_hash"])
    assert result["trajectory_artifact_hash"] == materialized["trajectory_logical_hash"]
    replicate = store.retrieve(CalibrationReplicateManifest,
                               result["replicate_manifest_hash"])
    assert replicate.replicate_id == "rep-1"
    data = (tmp_path / "artifacts" / "estimator_results"
            / (result["estimator_result_hash"] + ".json")).read_bytes()
    payload = json.loads(data)
    assert payload["estimator"] == "analyze_trajectory"
    assert payload["estimator_module"] == "rudeus.science.transport"
    assert payload["code_revision"] == "f" * 40
    assert isinstance(result["estimator_result_hash"], str)


def test_artifact_verified_before_estimation(tmp_path):
    store, materialized = _materialized(tmp_path)
    logical = materialized["trajectory_logical_hash"]
    path = tmp_path / "artifacts" / "blobs" / logical
    payload = json.loads(path.read_bytes())
    payload["positions"][3][0][0] += 5.0
    path.write_bytes(json.dumps(payload).encode("utf-8"))
    with pytest.raises(ExecutionError) as failure:
        _estimate(store, tmp_path / "artifacts",
                  materialized["replicate_manifest_hash"])
    assert failure.value.failure_class.value == "INTEGRITY"
    assert list((tmp_path / "artifacts").glob("estimator_results/*.json")) == []


def test_existing_estimator_output_preserved(tmp_path):
    store, materialized = _materialized(tmp_path)
    result = _estimate(store, tmp_path / "artifacts",
                       materialized["replicate_manifest_hash"])
    data = (tmp_path / "artifacts" / "estimator_results"
            / (result["estimator_result_hash"] + ".json")).read_bytes()
    payload = json.loads(data)
    species = payload["result"]["self_diffusion_by_species"]["Li"]
    assert isinstance(species["D_m2_per_s"], float)
    assert species["scalar_definition"] == "trace(D_tensor)/3"
    assert species["origin_population_hash"] is not None
    assert payload["result"]["conductivity_estimate"]["status"] == "UNKNOWN"


def test_deterministic_canonical_result(tmp_path):
    store, materialized = _materialized(tmp_path)
    first = _estimate(store, tmp_path / "artifacts",
                      materialized["replicate_manifest_hash"])
    second = _estimate(store, tmp_path / "artifacts",
                       materialized["replicate_manifest_hash"])
    assert first["estimator_result_hash"] == second["estimator_result_hash"]
    path = (tmp_path / "artifacts" / "estimator_results"
            / (first["estimator_result_hash"] + ".json"))
    assert path.read_bytes() == canonical_bytes(json.loads(path.read_bytes()))


def test_conflicting_result_fails_closed(tmp_path):
    store, materialized = _materialized(tmp_path)
    first = _estimate(store, tmp_path / "artifacts",
                      materialized["replicate_manifest_hash"])
    path = (tmp_path / "artifacts" / "estimator_results"
            / (first["estimator_result_hash"] + ".json"))
    forged = b'{"forged": true}'
    path.write_bytes(forged)
    with pytest.raises(ExecutionError):
        from rudeus.science.evidence import append_file
        append_file(path, canonical_bytes({"other": 1}))
    assert path.read_bytes() == forged
    with pytest.raises(ExecutionError) as failure:
        _estimate(store, tmp_path / "artifacts",
                  materialized["replicate_manifest_hash"])
    assert failure.value.failure_class.value == "INTEGRITY"


def test_missing_replicate_fails_closed(tmp_path):
    store, _ = _materialized(tmp_path)
    with pytest.raises(ExecutionError) as failure:
        _estimate(store, tmp_path / "artifacts", _h("absent"))
    assert failure.value.failure_class.value == "INTEGRITY"


def test_missing_artifact_fails_closed(tmp_path):
    store, materialized = _materialized(tmp_path)
    logical = materialized["trajectory_logical_hash"]
    (tmp_path / "artifacts" / "blobs" / logical).unlink()
    with pytest.raises(ExecutionError) as failure:
        _estimate(store, tmp_path / "artifacts",
                  materialized["replicate_manifest_hash"])
    assert failure.value.failure_class.value == "INTEGRITY"


def test_malformed_trajectory_fails_closed(tmp_path):
    store, materialized = _materialized(tmp_path)
    logical = materialized["trajectory_logical_hash"]
    path = tmp_path / "artifacts" / "blobs" / logical
    payload = json.loads(path.read_bytes())
    payload["positions"] = [[[0.0, 0.0]]]
    path.write_bytes(json.dumps(payload).encode("utf-8"))
    with pytest.raises(ExecutionError) as failure:
        _estimate(store, tmp_path / "artifacts",
                  materialized["replicate_manifest_hash"])
    assert failure.value.failure_class.value in ("INTEGRITY", "UNSUPPORTED_INPUT")


def test_single_frame_follows_estimator_semantics(tmp_path):
    store, materialized = _materialized(
        tmp_path, generator={"n_frames": 1})
    with pytest.raises(ExecutionError) as failure:
        _estimate(store, tmp_path / "artifacts",
                  materialized["replicate_manifest_hash"])
    assert failure.value.failure_class.value == "UNSUPPORTED_INPUT"
    assert list((tmp_path / "artifacts").glob("estimator_results/*.json")) == []


def test_zero_displacement_follows_estimator_semantics(tmp_path):
    store, materialized = _materialized(
        tmp_path, generator={"diffusion_tensor": np.zeros((3, 3)).tolist()})
    result = _estimate(store, tmp_path / "artifacts",
                       materialized["replicate_manifest_hash"])
    species = json.loads((tmp_path / "artifacts" / "estimator_results"
                          / (result["estimator_result_hash"] + ".json")).read_bytes()
                         )["result"]["self_diffusion_by_species"]["Li"]
    assert species["D_m2_per_s"] == 0.0


def test_failed_estimation_creates_no_result(tmp_path):
    store, materialized = _materialized(
        tmp_path, generator={"n_frames": 1})
    with pytest.raises(ExecutionError):
        _estimate(store, tmp_path / "artifacts",
                  materialized["replicate_manifest_hash"],
                  fit_window_ps=[100.0, 200.0])
    assert list((tmp_path / "artifacts").glob("estimator_results/*.json")) == []


def test_no_qualification_fields_emitted(tmp_path):
    store, materialized = _materialized(tmp_path)
    result = _estimate(store, tmp_path / "artifacts",
                       materialized["replicate_manifest_hash"])
    assert set(result) == {"estimator_result_hash", "replicate_manifest_hash",
                           "trajectory_artifact_hash"}
    texts = []
    for path in (tmp_path / "artifacts" / "estimator_results").glob("*.json"):
        texts.append(path.read_bytes().decode("utf-8"))
    for text in texts:
        for token in ("QualificationRecord", "acceptance", "coverage", "bias",
                      "qualified", '"PASS"', '"FAIL"', '"INDETERMINATE"',
                      "confidence"):
            assert token not in text
