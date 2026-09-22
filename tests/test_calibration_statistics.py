"""Replicate-level descriptive statistics tests (no qualification)."""
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
from rudeus.science.calibration_batch import materialize_calibration_dataset
from rudeus.science.calibration_estimator import estimate_calibration_replicate
from rudeus.science.calibration_statistics import summarize_calibration_estimates
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


def _estimator_config(**over):
    params = dict(lag_steps=[1, 2], fit_window_ps=[0.5, 2.5],
                  selected_species=["Li"], volume_A3=1000.0,
                  temperature_K=550.0, reference_frame="simulation_cell")
    params.update(over)
    return params


def _prepared(tmp_path, reps=("rep-a", "rep-b", "rep-c")):
    store = CalibrationStore(tmp_path / "store")
    root = tmp_path / "artifacts"
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
        split_rules={}, seed_policy={}, dev_replicate_ids=tuple(reps),
        heldout_replicate_ids=(), independence_rules={},
        selection_stopping_policy={}, frozen_analysis_fields=("estimator",),
        code_revision="f" * 40))
    dataset_h = store.store(CalibrationDatasetManifest(
        dataset_id="ds-1", plan_hash=plan_h, scope_hash=scope_h,
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",),
        trajectory_ids=tuple(f"traj-{rep}" for rep in reps),
        truth_record_hashes=(truth_h,), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(gen_h,), artifact_manifest_hashes=(),
        attempted_replicate_ids=tuple(reps)))
    seeds = {rep: 100 + i for i, rep in enumerate(reps)}
    batch = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=dataset_h,
        artifact_root=root, seeds=seeds, code_revision="f" * 40)
    assert batch["failed"] == []
    manifests = {}
    for rep in reps:
        found = [p for p in (store.root / "calibration_replicates").glob("*.json")
                 if json.loads(p.read_bytes())["replicate_id"] == rep]
        assert len(found) == 1
        manifests[rep] = found[0].stem
        estimate_calibration_replicate(
            calibration_store=store, artifact_root=root,
            replicate_manifest_hash=found[0].stem,
            estimator_config=_estimator_config(), code_revision="f" * 40)
    return store, root, dataset_h, manifests


def _summarize(store, root, dataset_h, manifests, **over):
    params = dict(calibration_store=store, artifact_root=root,
                  dataset_manifest_hash=dataset_h,
                  replicate_manifest_hashes=dict(manifests),
                  species="Li", estimator_config=_estimator_config(),
                  code_revision="f" * 40)
    params.update(over)
    return summarize_calibration_estimates(**params)


def test_all_success_summary(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    result = _summarize(store, root, dataset_h, manifests)
    assert result["n_successful"] == 3 and result["n_missing_or_failed"] == 0
    payload = json.loads((root / "estimate_summaries"
                          / (result["summary_hash"] + ".json")).read_bytes())
    assert payload["replicate_ids"] == ["rep-a", "rep-b", "rep-c"]
    assert payload["statistics"]["n"] == 3
    assert payload["missing_ids"] == {} and payload["failed_ids"] == {}


def test_ordering_and_moments_against_hand_values(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    values = []
    for rep in ("rep-a", "rep-b", "rep-c"):
        manifest_hash = manifests[rep]
        candidates = [p for p in (root / "estimator_results").glob("*.json")
                      if json.loads(p.read_bytes())["replicate_manifest_hash"]
                      == manifest_hash]
        assert len(candidates) == 1
        values.append(json.loads(candidates[0].read_bytes())["result"]
                      ["self_diffusion_by_species"]["Li"]["D_m2_per_s"])
    sample = np.asarray(values)
    result = _summarize(store, root, dataset_h, manifests)
    payload = json.loads((root / "estimate_summaries"
                          / (result["summary_hash"] + ".json")).read_bytes())
    stats = payload["statistics"]
    assert stats["mean"] == pytest.approx(float(np.mean(sample)))
    assert stats["std"] == pytest.approx(float(np.std(sample, ddof=1)))
    assert stats["min"] == pytest.approx(float(np.min(sample)))
    assert stats["max"] == pytest.approx(float(np.max(sample)))
    assert payload["source_estimator_result_hashes"] == {
        rep: [p.stem for p in (root / "estimator_results").glob("*.json")
              if json.loads(p.read_bytes())["replicate_manifest_hash"]
              == manifests[rep]][0] for rep in ("rep-a", "rep-b", "rep-c")}


def test_n_zero_behavior(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    root = tmp_path / "artifacts"
    scope_h = store.store(_scope())
    plan_h = store.store(CalibrationPlan(
        objective="pilot", scope_hashes=(scope_h,),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",), truth_requirements={},
        split_rules={}, seed_policy={}, dev_replicate_ids=(),
        heldout_replicate_ids=(), independence_rules={},
        selection_stopping_policy={}, frozen_analysis_fields=("estimator",),
        code_revision="f" * 40))
    dataset_h = store.store(CalibrationDatasetManifest(
        dataset_id="ds-0", plan_hash=plan_h, scope_hash=scope_h,
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",), trajectory_ids=(),
        truth_record_hashes=(), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(), artifact_manifest_hashes=(),
        attempted_replicate_ids=()))
    result = _summarize(store, root, dataset_h, {})
    assert result["n_successful"] == 0
    payload = json.loads((root / "estimate_summaries"
                          / (result["summary_hash"] + ".json")).read_bytes())
    assert payload["statistics"] == {"n": 0, "mean": None, "std": None,
                                     "min": None, "max": None}


def test_n_one_behavior(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path, reps=("rep-a",))
    result = _summarize(store, root, dataset_h, manifests)
    payload = json.loads((root / "estimate_summaries"
                          / (result["summary_hash"] + ".json")).read_bytes())
    stats = payload["statistics"]
    assert stats["n"] == 1 and stats["std"] is None
    assert stats["mean"] == stats["min"] == stats["max"]


def test_partial_missing_reporting(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    partial = {rep: manifests[rep] for rep in ("rep-a", "rep-c")}
    result = _summarize(store, root, dataset_h, partial)
    assert result["n_successful"] == 2 and result["n_missing_or_failed"] == 1
    payload = json.loads((root / "estimate_summaries"
                          / (result["summary_hash"] + ".json")).read_bytes())
    assert payload["missing_ids"] == {"rep-b": "undeclared_selection"}
    assert payload["failed_ids"] == {}
    assert payload["statistics"]["n"] == 2


def test_forged_result_fails_closed(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    target = [p for p in (root / "estimator_results").glob("*.json")
              if json.loads(p.read_bytes())["replicate_manifest_hash"]
              == manifests["rep-a"]][0]
    payload = json.loads(target.read_bytes())
    payload["result"]["self_diffusion_by_species"]["Li"]["D_m2_per_s"] *= 2.0
    target.write_bytes(json.dumps(payload).encode("utf-8"))
    with pytest.raises(ExecutionError) as failure:
        _summarize(store, root, dataset_h, manifests)
    assert failure.value.failure_class.value == "INTEGRITY"


def test_wrong_dataset_binding_fails_closed(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    other_h = store.store(CalibrationDatasetManifest(
        dataset_id="ds-2", plan_hash=_h("plan"), scope_hash=_h("scope"),
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",), trajectory_ids=(),
        truth_record_hashes=(), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(), artifact_manifest_hashes=(),
        attempted_replicate_ids=("rep-a",)))
    with pytest.raises(ExecutionError):
        _summarize(store, root, other_h, manifests)


def test_mixed_estimator_config_fails_closed(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    with pytest.raises(ExecutionError) as failure:
        _summarize(store, root, dataset_h, manifests,
                   estimator_config=_estimator_config(volume_A3=2000.0))
    assert failure.value.failure_class.value == "INTEGRITY"


def test_deterministic_bytes_and_idempotence(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    first = _summarize(store, root, dataset_h, manifests)
    second = _summarize(store, root, dataset_h, manifests)
    assert first["summary_hash"] == second["summary_hash"]
    path = root / "estimate_summaries" / (first["summary_hash"] + ".json")
    assert path.read_bytes() == canonical_bytes(json.loads(path.read_bytes()))


def test_conflicting_summary_fails_closed(tmp_path):
    from rudeus.science.evidence import append_file
    store, root, dataset_h, manifests = _prepared(tmp_path)
    first = _summarize(store, root, dataset_h, manifests)
    path = root / "estimate_summaries" / (first["summary_hash"] + ".json")
    forged = b'{"forged": true}'
    path.write_bytes(forged)
    with pytest.raises(ExecutionError):
        append_file(path, canonical_bytes({"other": 1}))
    assert path.read_bytes() == forged
    with pytest.raises(ExecutionError) as failure:
        _summarize(store, root, dataset_h, manifests)
    assert failure.value.failure_class.value == "INTEGRITY"


def test_provenance_chain(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    result = _summarize(store, root, dataset_h, manifests)
    payload = json.loads((root / "estimate_summaries"
                          / (result["summary_hash"] + ".json")).read_bytes())
    assert payload["dataset_manifest_hash"] == dataset_h
    assert set(payload["source_estimator_result_hashes"]) == {"rep-a", "rep-b", "rep-c"}
    assert set(payload["truth_record_hashes"]) == {"rep-a", "rep-b", "rep-c"}
    assert set(payload["parameter_cells"]) == {"rep-a", "rep-b", "rep-c"}
    for rep, manifest_hash in manifests.items():
        assert payload["source_estimator_result_hashes"][rep] in {
            p.stem for p in (root / "estimator_results").glob("*.json")}
        record = json.loads((store.root / "calibration_replicates"
                             / f"{manifest_hash}.json").read_bytes())
        assert record["replicate_id"] == rep


def test_no_truth_comparison_or_qualification(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    result = _summarize(store, root, dataset_h, manifests)
    assert set(result) == {"summary_hash", "dataset_manifest_hash", "n_successful",
                           "n_missing_or_failed", "artifact_status"}
    texts = [(root / "estimate_summaries" / (result["summary_hash"] + ".json")).read_bytes()
             .decode("utf-8")]
    for text in texts:
        for token in ("bias", "relative_error", "absolute_error", "coverage",
                      "QualificationRecord", "acceptance", "qualified",
                      '"PASS"', '"FAIL"', '"INDETERMINATE"', "confidence",
                      "effective", "bootstrap"):
            assert token not in text
