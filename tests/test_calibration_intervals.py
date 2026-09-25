"""Interval + coverage-summary glue tests (descriptive only, no qualification)."""
import json

import numpy as np
import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration import (
    CalibrationClass,
    CalibrationDatasetManifest,
    CalibrationPlan,
    CalibrationScope,
    GeneratorSpec,
    SplitAssignment,
    TruthRecord,
    TruthType,
)
from rudeus.science.calibration_estimator import (
    estimate_calibration_replicate,
    estimate_interval_for_replicate,
    persist_coverage_summary,
)
from rudeus.science.calibration_execution import (
    build_calibration_task,
    materialize_replicate,
)
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science.statistics import (
    MATCHED_ORIGIN_BLOCKS_V2,
    ResamplingSpec,
    coverage_experiment,
)


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


def _spec(**over):
    params = dict(block_origins=2, min_blocks_provisional=1, n_resamples=16,
                  nominal_coverage_provisional=0.68, seed=7,
                  replica_scheme="single_trajectory_no_replica_resampling",
                  joint_quantities=("D:Li",), method=MATCHED_ORIGIN_BLOCKS_V2)
    params.update(over)
    return ResamplingSpec(**params)


def _materialized(tmp_path, store=None, seed=7):
    store = store or CalibrationStore(tmp_path / "store")
    scope_h = store.store(_scope())
    truth_h = store.store(TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.GENERATED_MODEL,
        value={"D_m2_per_s": 1.5e-9}, code_revision="f" * 40))
    gen_h = store.store(GeneratorSpec(
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_name="brownian",
        generator_version="synthetic-v1",
        parameters={"n_frames": 8, "n_ions": 2,
                    "diffusion_tensor": (0.1 * np.eye(3)).tolist(), "dt_ps": 1.0},
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


def _estimated(store, root, replicate_hash):
    return estimate_calibration_replicate(
        calibration_store=store, artifact_root=root,
        replicate_manifest_hash=replicate_hash,
        estimator_config=_config(), code_revision="f" * 40)


def _interval(store, root, estimator_hash, **over):
    return estimate_interval_for_replicate(
        calibration_store=store, artifact_root=root,
        estimator_result_hash=estimator_hash,
        resampling_spec=_spec(**over), code_revision="f" * 40)


def test_interval_provenance_binding(tmp_path):
    store, materialized = _materialized(tmp_path)
    estimated = _estimated(store, tmp_path / "artifacts",
                           materialized["replicate_manifest_hash"])
    spec = _spec()
    result = _interval(store, tmp_path / "artifacts",
                       estimated["estimator_result_hash"])
    assert result["estimator_result_hash"] == estimated["estimator_result_hash"]
    payload = json.loads((tmp_path / "artifacts" / "calibration_intervals"
                          / (result["interval_hash"] + ".json")).read_bytes())
    assert payload["replicate_manifest_hash"] == materialized["replicate_manifest_hash"]
    assert payload["trajectory_artifact_hash"] == materialized["trajectory_logical_hash"]
    assert payload["resampling_spec_hash"] == spec.content_hash
    assert payload["seed"] == spec.seed
    assert set(payload["intervals"]) == {"D:Li"}
    assert payload["code_revision"] == "f" * 40


def test_interval_deterministic_serialization(tmp_path):
    store, materialized = _materialized(tmp_path)
    estimated = _estimated(store, tmp_path / "artifacts",
                           materialized["replicate_manifest_hash"])
    first = _interval(store, tmp_path / "artifacts",
                      estimated["estimator_result_hash"])
    second = _interval(store, tmp_path / "artifacts",
                       estimated["estimator_result_hash"])
    assert first["interval_hash"] == second["interval_hash"]
    path = (tmp_path / "artifacts" / "calibration_intervals"
            / (first["interval_hash"] + ".json"))
    assert path.read_bytes() == canonical_bytes(json.loads(path.read_bytes()))


def test_coverage_summary_provenance(tmp_path):
    from rudeus.science.synthetic import brownian
    from rudeus.science.transport import analyze_trajectory
    store, materialized = _materialized(tmp_path)
    estimated = _estimated(store, tmp_path / "artifacts",
                           materialized["replicate_manifest_hash"])
    interval = _interval(store, tmp_path / "artifacts",
                         estimated["estimator_result_hash"])

    def generator(seed):
        return brownian(n_frames=8, n_ions=2,
                        diffusion_tensor=(0.1 * np.eye(3)).tolist(),
                        dt_ps=1.0, seed=seed)

    def estimator(positions):
        point = analyze_trajectory(
            positions, ["Li", "Li"], list(range(8)), 1000.0, **_config())
        return {"estimate": point["self_diffusion_by_species"]["Li"]["D_m2_per_s"],
                "interval": [0.0, 3.0e-9]}

    coverage = coverage_experiment(
        generator, estimator, seeds=[101, 102, 103], truth=1.5e-9,
        nominal_coverage=0.68, monte_carlo_confidence=0.95,
        generating_protocol={"scope": "test-scope"})
    s2_procedure = {"version": "s2-test-v1", "nominal_coverage": 0.68}
    s2_hash = digest(s2_procedure)
    result = persist_coverage_summary(
        artifact_root=tmp_path / "artifacts", coverage=coverage,
        s2_procedure_hash=s2_hash, s2_procedure=s2_procedure,
        dataset_manifest_hash=_h("dataset"),
        replicate_ids=["rep-1", "rep-2", "rep-3"],
        seeds={"rep-1": 101, "rep-2": 102, "rep-3": 103},
        estimator_identity={"name": "analyze_trajectory",
                            "module": "rudeus.science.transport",
                            "config_hash": _h("config")},
        resampling_identity={"method": MATCHED_ORIGIN_BLOCKS_V2,
                             "spec_hash": _spec().content_hash},
        truth={"record_hash": _h("truth"),
               "value": {"D_m2_per_s": 1.5e-9}, "units": "m2/s"})
    payload = json.loads((tmp_path / "artifacts" / "calibration_coverage"
                          / (result["coverage_hash"] + ".json")).read_bytes())
    assert payload["s2_procedure_hash"] == s2_hash
    assert payload["s2_procedure"] == s2_procedure
    assert payload["replicate_ids"] == ["rep-1", "rep-2", "rep-3"]
    assert payload["seeds"] == {"rep-1": 101, "rep-2": 102, "rep-3": 103}
    assert payload["coverage"]["coverage_unconditional"] == pytest.approx(1.0)
    assert payload["coverage"]["truth"] == 1.5e-9
    assert interval["interval_hash"]  # interval record exists alongside


def test_coverage_summary_deterministic_identity(tmp_path):
    from rudeus.science.synthetic import brownian
    from rudeus.science.transport import analyze_trajectory

    def generator(seed):
        return brownian(n_frames=8, n_ions=2,
                        diffusion_tensor=(0.1 * np.eye(3)).tolist(),
                        dt_ps=1.0, seed=seed)

    def estimator(positions):
        point = analyze_trajectory(
            positions, ["Li", "Li"], list(range(8)), 1000.0, **_config())
        return {"estimate": point["self_diffusion_by_species"]["Li"]["D_m2_per_s"],
                "interval": [0.0, 3.0e-9]}

    coverage = coverage_experiment(
        generator, estimator, seeds=[101, 102], truth=1.5e-9,
        nominal_coverage=0.68, monte_carlo_confidence=0.95,
        generating_protocol={"scope": "test-scope"})
    kwargs = dict(coverage=coverage, s2_procedure_hash=_h("proc"),
                  s2_procedure={"version": "s2-test-v1"},
                  dataset_manifest_hash=_h("dataset"),
                  replicate_ids=["rep-1", "rep-2"],
                  seeds={"rep-1": 101, "rep-2": 102},
                  estimator_identity={"name": "analyze_trajectory",
                                      "module": "rudeus.science.transport",
                                      "config_hash": _h("config")},
                  resampling_identity={"method": MATCHED_ORIGIN_BLOCKS_V2,
                                       "spec_hash": _h("spec")},
                  truth={"value": {"D_m2_per_s": 1.5e-9}})
    first = persist_coverage_summary(artifact_root=tmp_path / "artifacts", **kwargs)
    second = persist_coverage_summary(artifact_root=tmp_path / "artifacts", **kwargs)
    assert first["coverage_hash"] == second["coverage_hash"]


def test_no_qualification_artifacts(tmp_path):
    store, materialized = _materialized(tmp_path)
    estimated = _estimated(store, tmp_path / "artifacts",
                           materialized["replicate_manifest_hash"])
    _interval(store, tmp_path / "artifacts", estimated["estimator_result_hash"])
    texts = []
    for directory in ("calibration_intervals", "calibration_coverage"):
        path = tmp_path / "artifacts" / directory
        if path.is_dir():
            texts.extend(p.read_bytes().decode("utf-8") for p in path.glob("*.json"))
    assert texts
    for text in texts:
        for token in ("QualificationRecord", "qualified", '"PASS"', '"FAIL"',
                      "acceptance", '"bounds"'):
            assert token not in text


def test_invalid_trajectory_produces_no_interval(tmp_path):
    store, materialized = _materialized(tmp_path)
    estimated = _estimated(store, tmp_path / "artifacts",
                           materialized["replicate_manifest_hash"])
    with pytest.raises(ExecutionError):
        _interval(store, tmp_path / "artifacts", _h("absent-result"))
    assert list((tmp_path / "artifacts" / "calibration_intervals").glob("*.json")) == [] \
        if (tmp_path / "artifacts" / "calibration_intervals").exists() else True


def test_mismatched_identity_fails_closed(tmp_path):
    store, materialized = _materialized(tmp_path)
    estimated = _estimated(store, tmp_path / "artifacts",
                           materialized["replicate_manifest_hash"])
    with pytest.raises(ExecutionError) as failure:
        estimate_interval_for_replicate(
            calibration_store=store, artifact_root=tmp_path / "artifacts",
            estimator_result_hash=estimated["estimator_result_hash"],
            resampling_spec=_spec(), code_revision="0" * 40)
    assert failure.value.failure_class.value == "INTEGRITY"
