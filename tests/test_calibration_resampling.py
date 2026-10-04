"""Replicate-level bootstrap tests (resampling distribution only)."""
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
from rudeus.science.calibration_resampling import bootstrap_calibration_diagnostics
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


def _prepared(tmp_path, reps=("rep-a", "rep-b"), cells=None):
    store = CalibrationStore(tmp_path / "store")
    root = tmp_path / "artifacts"
    cells = cells or {rep: "cell-a" for rep in reps}
    scope_h = store.store(_scope())
    truth_h = store.store(TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.GENERATED_MODEL,
        value={"D_m2_per_s": TRUTH_D}, code_revision="f" * 40))
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
        parameter_cell_ids=tuple(sorted(set(cells.values()))),
        truth_requirements={}, split_rules={},
        seed_policy={}, dev_replicate_ids=tuple(reps), heldout_replicate_ids=(),
        independence_rules={}, selection_stopping_policy={},
        frozen_analysis_fields=("estimator",), code_revision="f" * 40))
    dataset_h = store.store(CalibrationDatasetManifest(
        dataset_id="ds-1", plan_hash=plan_h, scope_hash=scope_h,
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=tuple(sorted(set(cells.values()))),
        trajectory_ids=tuple(f"traj-{rep}" for rep in reps),
        truth_record_hashes=(truth_h,), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(gen_h,), artifact_manifest_hashes=(),
        attempted_replicate_ids=tuple(reps)))
    seeds = {rep: 100 + i for i, rep in enumerate(reps)}
    batch = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=dataset_h,
        artifact_root=root, seeds=seeds, cells=dict(cells),
        code_revision="f" * 40)
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
    diagnostic = diagnose_calibration_errors(
        calibration_store=store, artifact_root=root,
        dataset_manifest_hash=dataset_h,
        replicate_manifest_hashes=dict(manifests),
        species="Li", estimator_config=_estimator_config(),
        code_revision="f" * 40)
    return store, root, dataset_h, manifests, diagnostic


def _bootstrap(store, root, dataset_h, diagnostic, reps, **over):
    params = dict(calibration_store=store, artifact_root=root,
                  dataset_manifest_hash=dataset_h,
                  diagnostic_hash=diagnostic["diagnostic_hash"],
                  replicate_ids=list(reps), species="Li",
                  estimator_config=_estimator_config(),
                  code_revision="f" * 40, seed=11, n_bootstrap=4)
    params.update(over)
    return bootstrap_calibration_diagnostics(**params)


def _payload(root, result):
    return json.loads((root / "calibration_resamples"
                       / (result["bootstrap_hash"] + ".json")).read_bytes())


def _source_values(root, diagnostic, reps):
    record = json.loads((root / "calibration_diagnostics"
                         / (diagnostic["diagnostic_hash"] + ".json")).read_bytes())
    signed = [record["entries"][rep]["signed_error"] for rep in reps]
    absolute = [record["entries"][rep]["absolute_error"] for rep in reps]
    return signed, absolute


def test_hand_checkable_bootstrap(tmp_path):
    store, root, dataset_h, manifests, diagnostic = _prepared(tmp_path)
    reps = ["rep-a", "rep-b"]
    result = _bootstrap(store, root, dataset_h, diagnostic, reps)
    signed, absolute = _source_values(root, diagnostic, reps)
    expected_idx = np.random.default_rng(11).integers(0, 2, size=(4, 2)).tolist()
    payload = _payload(root, result)
    assert payload["bootstrap_indices"] == expected_idx
    index_array = np.asarray(expected_idx)
    assert payload["signed_error_means"] == pytest.approx(
        np.mean(np.asarray(signed)[index_array], axis=1).tolist())
    assert payload["absolute_error_means"] == pytest.approx(
        np.mean(np.asarray(absolute)[index_array], axis=1).tolist())
    assert payload["rng"] == {"algorithm": "numpy.random.Generator(PCG64)",
                              "seed": 11, "numpy_version": np.__version__}
    assert payload["n_observations"] == 2 and payload["n_bootstrap"] == 4


def test_seed_determinism_and_sensitivity(tmp_path):
    store, root, dataset_h, manifests, diagnostic = _prepared(tmp_path)
    reps = ["rep-a", "rep-b"]
    first = _bootstrap(store, root, dataset_h, diagnostic, reps)
    second = _bootstrap(store, root, dataset_h, diagnostic, reps)
    assert first["bootstrap_hash"] == second["bootstrap_hash"]
    other = _bootstrap(store, root, dataset_h, diagnostic, reps, seed=12)
    assert other["bootstrap_hash"] != first["bootstrap_hash"]
    assert _payload(root, other)["bootstrap_indices"] != \
        _payload(root, first)["bootstrap_indices"]


def test_replacement_sampling_and_statistics(tmp_path):
    store, root, dataset_h, manifests, diagnostic = _prepared(tmp_path)
    reps = ["rep-a", "rep-b"]
    result = _bootstrap(store, root, dataset_h, diagnostic, reps,
                        seed=11, n_bootstrap=50)
    payload = _payload(root, result)
    indices = payload["bootstrap_indices"]
    assert len(indices) == 50 and all(len(draw) == 2 for draw in indices)
    assert all(0 <= i < 2 for draw in indices for i in draw)
    signed, absolute = _source_values(root, diagnostic, reps)
    assert payload["source_signed_errors"] == pytest.approx(signed)
    assert payload["source_absolute_errors"] == pytest.approx(absolute)
    index_array = np.asarray(indices)
    assert payload["signed_error_means"] == pytest.approx(
        np.mean(np.asarray(signed)[index_array], axis=1).tolist())
    assert payload["absolute_error_means"] == pytest.approx(
        np.mean(np.asarray(absolute)[index_array], axis=1).tolist())


def test_provenance_preserved(tmp_path):
    store, root, dataset_h, manifests, diagnostic = _prepared(tmp_path)
    result = _bootstrap(store, root, dataset_h, diagnostic, ["rep-a", "rep-b"])
    payload = _payload(root, result)
    assert payload["dataset_manifest_hash"] == dataset_h
    assert payload["diagnostic_hash"] == diagnostic["diagnostic_hash"]
    assert payload["replicate_ids"] == ["rep-a", "rep-b"]
    assert payload["parameter_cell_id"] == "cell-a"
    assert payload["estimator"] == "analyze_trajectory"
    assert payload["species"] == "Li"
    assert set(result) == {"bootstrap_hash", "diagnostic_hash",
                           "dataset_manifest_hash", "n_observations",
                           "n_bootstrap", "artifact_status"}


def test_cell_mixing_rejected(tmp_path):
    store, root, dataset_h, manifests, diagnostic = _prepared(
        tmp_path, reps=("rep-a", "rep-b"),
        cells={"rep-a": "cell-a", "rep-b": "cell-b"})
    with pytest.raises(ExecutionError) as failure:
        _bootstrap(store, root, dataset_h, diagnostic, ["rep-a", "rep-b"])
    assert failure.value.failure_class.value == "INTEGRITY"


def test_missing_diagnostic_fails_closed(tmp_path):
    store, root, dataset_h, manifests, diagnostic = _prepared(tmp_path)
    with pytest.raises(ExecutionError) as failure:
        _bootstrap(store, root, dataset_h, {**diagnostic,
                                            "diagnostic_hash": _h("absent")},
                   ["rep-a"])
    assert failure.value.failure_class.value == "INTEGRITY"


def test_forged_diagnostic_fails_closed(tmp_path):
    store, root, dataset_h, manifests, diagnostic = _prepared(tmp_path)
    path = (root / "calibration_diagnostics"
            / (diagnostic["diagnostic_hash"] + ".json"))
    payload = json.loads(path.read_bytes())
    payload["entries"]["rep-a"]["signed_error"] *= 2.0
    path.write_bytes(json.dumps(payload).encode("utf-8"))
    with pytest.raises(ExecutionError) as failure:
        _bootstrap(store, root, dataset_h, diagnostic, ["rep-a", "rep-b"])
    assert failure.value.failure_class.value == "INTEGRITY"


def test_hash_mismatch_fails_closed(tmp_path):
    store, root, dataset_h, manifests, diagnostic = _prepared(tmp_path)
    with pytest.raises(ExecutionError):
        _bootstrap(store, root, dataset_h,
                   {**diagnostic, "diagnostic_hash": _h("nope")}, ["rep-a"])


def test_invalid_seed_and_count_fail_closed(tmp_path):
    store, root, dataset_h, manifests, diagnostic = _prepared(tmp_path)
    for bad_seed in (True, 1.5, "11", None):
        with pytest.raises(ExecutionError) as failure:
            _bootstrap(store, root, dataset_h, diagnostic, ["rep-a"],
                       seed=bad_seed)
        assert failure.value.failure_class.value == "UNSUPPORTED_INPUT"
    for bad_count in (0, -3, True, 2.5, "4"):
        with pytest.raises(ExecutionError) as failure:
            _bootstrap(store, root, dataset_h, diagnostic, ["rep-a"],
                       n_bootstrap=bad_count)
        assert failure.value.failure_class.value == "UNSUPPORTED_INPUT"


def test_empty_population_fails_closed(tmp_path):
    store, root, dataset_h, manifests, diagnostic = _prepared(tmp_path)
    with pytest.raises(ExecutionError) as failure:
        _bootstrap(store, root, dataset_h, diagnostic, [])
    assert failure.value.failure_class.value == "INTEGRITY"


def test_idempotent_and_conflict(tmp_path):
    from rudeus.science.evidence import append_file
    store, root, dataset_h, manifests, diagnostic = _prepared(tmp_path)
    first = _bootstrap(store, root, dataset_h, diagnostic, ["rep-a", "rep-b"])
    second = _bootstrap(store, root, dataset_h, diagnostic, ["rep-a", "rep-b"])
    assert first["bootstrap_hash"] == second["bootstrap_hash"]
    path = root / "calibration_resamples" / (first["bootstrap_hash"] + ".json")
    assert path.read_bytes() == canonical_bytes(json.loads(path.read_bytes()))
    forged = b'{"forged": true}'
    path.write_bytes(forged)
    with pytest.raises(ExecutionError):
        append_file(path, canonical_bytes({"other": 1}))
    assert path.read_bytes() == forged
    with pytest.raises(ExecutionError) as failure:
        _bootstrap(store, root, dataset_h, diagnostic, ["rep-a", "rep-b"])
    assert failure.value.failure_class.value == "INTEGRITY"


def test_no_coverage_or_qualification(tmp_path):
    store, root, dataset_h, manifests, diagnostic = _prepared(tmp_path)
    result = _bootstrap(store, root, dataset_h, diagnostic, ["rep-a", "rep-b"])
    texts = [(root / "calibration_resamples"
              / (result["bootstrap_hash"] + ".json")).read_bytes().decode("utf-8")]
    for text in texts:
        for token in ("coverage", "nominal", "confidence", "interval",
                      "tolerance", "QualificationRecord", "qualified",
                      "acceptance", "threshold", '"PASS"', '"FAIL"',
                      '"INDETERMINATE"', "uncertainty", "transfer", "MLIP"):
            assert token not in text
