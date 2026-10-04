"""Truth-linked raw error diagnostics tests (descriptive only)."""
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
from rudeus.science.calibration_diagnostics import diagnose_calibration_errors
from rudeus.science.calibration_estimator import estimate_calibration_replicate
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.contracts import canonical_bytes, digest


TRUTH_D = 2.0e-9


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


def _prepared(tmp_path, reps=("rep-a", "rep-b", "rep-c"), truth_value=None):
    store = CalibrationStore(tmp_path / "store")
    root = tmp_path / "artifacts"
    scope_h = store.store(_scope())
    truth_h = store.store(TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.GENERATED_MODEL,
        value={"D_m2_per_s": TRUTH_D if truth_value is None else truth_value},
        code_revision="f" * 40))
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


def _diagnose(store, root, dataset_h, manifests, **over):
    params = dict(calibration_store=store, artifact_root=root,
                  dataset_manifest_hash=dataset_h,
                  replicate_manifest_hashes=dict(manifests),
                  species="Li", estimator_config=_estimator_config(),
                  code_revision="f" * 40)
    params.update(over)
    return diagnose_calibration_errors(**params)


def _payload(root, result):
    return json.loads((root / "calibration_diagnostics"
                       / (result["diagnostic_hash"] + ".json")).read_bytes())


def _estimate_of(root, manifests, rep):
    candidates = [p for p in (root / "estimator_results").glob("*.json")
                  if json.loads(p.read_bytes())["replicate_manifest_hash"]
                  == manifests[rep]]
    assert len(candidates) == 1
    return json.loads(candidates[0].read_bytes())["result"] \
        ["self_diffusion_by_species"]["Li"]["D_m2_per_s"]


def test_error_values_are_hand_correct(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    result = _diagnose(store, root, dataset_h, manifests)
    payload = _payload(root, result)
    assert result["n_diagnostics"] == 3
    for rep in ("rep-a", "rep-b", "rep-c"):
        estimate = _estimate_of(root, manifests, rep)
        entry = payload["entries"][rep]
        assert entry["estimate"] == pytest.approx(estimate)
        assert entry["truth"] == pytest.approx(TRUTH_D)
        assert entry["signed_error"] == pytest.approx(estimate - TRUTH_D)
        assert entry["absolute_error"] == pytest.approx(abs(estimate - TRUTH_D))


def test_aggregate_mean_signed_error(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    result = _diagnose(store, root, dataset_h, manifests)
    payload = _payload(root, result)
    signed = [payload["entries"][rep]["signed_error"]
              for rep in ("rep-a", "rep-b", "rep-c")]
    assert payload["aggregate"] == {"n": 3, "mean_signed_error": pytest.approx(
        float(np.mean(signed)))}
    assert result["n_missing_or_failed"] == 0


def test_truth_provenance_binding(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    result = _diagnose(store, root, dataset_h, manifests)
    payload = _payload(root, result)
    assert payload["dataset_manifest_hash"] == dataset_h
    assert set(payload["truth_record_hashes"]) == {"rep-a", "rep-b", "rep-c"}
    assert len(set(payload["truth_record_hashes"].values())) == 1
    for rep, truth_hash in payload["truth_record_hashes"].items():
        truth = store.retrieve(TruthRecord, truth_hash)
        assert truth.value == {"D_m2_per_s": TRUTH_D}


def test_missing_truth_reported(tmp_path):
    from rudeus.science.calibration import CalibrationReplicateManifest
    store, root, dataset_h, manifests = _prepared(tmp_path)
    ghost = CalibrationReplicateManifest(
        replicate_id="rep-a", dataset_id="ds-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.DEV, independence_declaration={},
        trajectory_artifact_hash=_h("traj"),
        truth_record_hash=_h("absent-truth"))
    ghost_h = store.store(ghost)
    altered = dict(manifests)
    altered["rep-a"] = ghost_h
    result = _diagnose(store, root, dataset_h, altered)
    assert result["n_diagnostics"] == 2
    payload = _payload(root, result)
    assert payload["failed_ids"] == {"rep-a": "unresolved_truth"}


def test_forged_truth_fails_closed(tmp_path):
    from rudeus.science.calibration import CalibrationReplicateManifest
    store, root, dataset_h, manifests = _prepared(tmp_path)
    truth_hashes = [p for p in (store.root / "truth_records").glob("*.json")]
    assert len(truth_hashes) == 1
    payload = json.loads(truth_hashes[0].read_text())
    payload["value"] = {"D_m2_per_s": 9.9e-9}
    truth_hashes[0].write_text(json.dumps(payload))
    with pytest.raises(ExecutionError) as failure:
        _diagnose(store, root, dataset_h, manifests)
    assert failure.value.failure_class.value == "INTEGRITY"
    assert list((root / "calibration_diagnostics").glob("*.json")) == []


def test_cell_mismatch_fails_closed(tmp_path):
    from rudeus.science.calibration import CalibrationReplicateManifest
    store, root, dataset_h, manifests = _prepared(tmp_path)
    foreign = CalibrationReplicateManifest(
        replicate_id="rep-a", dataset_id="ds-1", parameter_cell_id="cell-zzz",
        split_assignment=SplitAssignment.DEV, independence_declaration={},
        trajectory_artifact_hash=_h("traj"),
        truth_record_hash=_h("truth"))
    foreign_h = store.store(foreign)
    altered = dict(manifests)
    altered["rep-a"] = foreign_h
    with pytest.raises(ExecutionError) as failure:
        _diagnose(store, root, dataset_h, altered)
    assert failure.value.failure_class.value == "INTEGRITY"


def test_species_mismatch_fails_closed(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    with pytest.raises(ExecutionError) as failure:
        _diagnose(store, root, dataset_h, manifests, species="Na")
    assert failure.value.failure_class.value == "INTEGRITY"


def test_missing_estimator_result_reported(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    for path in (root / "estimator_results").glob("*.json"):
        if json.loads(path.read_bytes())["replicate_manifest_hash"] \
                == manifests["rep-c"]:
            path.unlink()
    result = _diagnose(store, root, dataset_h, manifests)
    assert result["n_diagnostics"] == 2
    payload = _payload(root, result)
    assert payload["failed_ids"] == {"rep-c": "missing_estimator_result"}
    assert payload["aggregate"]["n"] == 2


def test_config_mismatch_fails_closed(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    with pytest.raises(ExecutionError) as failure:
        _diagnose(store, root, dataset_h, manifests,
                  estimator_config=_estimator_config(volume_A3=2000.0))
    assert failure.value.failure_class.value == "INTEGRITY"


def test_forged_estimator_fails_closed(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    target = [p for p in (root / "estimator_results").glob("*.json")
              if json.loads(p.read_bytes())["replicate_manifest_hash"]
              == manifests["rep-a"]][0]
    payload = json.loads(target.read_bytes())
    payload["result"]["self_diffusion_by_species"]["Li"]["D_m2_per_s"] *= 2.0
    target.write_bytes(json.dumps(payload).encode("utf-8"))
    with pytest.raises(ExecutionError) as failure:
        _diagnose(store, root, dataset_h, manifests)
    assert failure.value.failure_class.value == "INTEGRITY"


def test_deterministic_idempotent_and_conflict(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    first = _diagnose(store, root, dataset_h, manifests)
    second = _diagnose(store, root, dataset_h, manifests)
    assert first["diagnostic_hash"] == second["diagnostic_hash"]
    path = root / "calibration_diagnostics" / (first["diagnostic_hash"] + ".json")
    assert path.read_bytes() == canonical_bytes(json.loads(path.read_bytes()))
    forged = b'{"forged": true}'
    path.write_bytes(forged)
    from rudeus.science.evidence import append_file
    with pytest.raises(ExecutionError):
        append_file(path, canonical_bytes({"other": 1}))
    assert path.read_bytes() == forged


def test_no_qualification_fields(tmp_path):
    store, root, dataset_h, manifests = _prepared(tmp_path)
    result = _diagnose(store, root, dataset_h, manifests)
    assert set(result) == {"diagnostic_hash", "dataset_manifest_hash",
                           "n_diagnostics", "n_missing_or_failed",
                           "artifact_status"}
    texts = [(root / "calibration_diagnostics"
              / (result["diagnostic_hash"] + ".json")).read_bytes().decode("utf-8")]
    for text in texts:
        for token in ("QualificationRecord", "acceptance", "coverage", "bias",
                      "qualified", '"PASS"', '"FAIL"', '"INDETERMINATE"',
                      "confidence", "tolerance", "threshold", "bootstrap",
                      "relative_error"):
            assert token not in text
