"""S1 frozen prospective isotropic-Brownian calibration plan.

Single frozen scientific contract: analytic ensemble diffusion truth for an
isotropic Brownian generator, disjoint DEV/HELD_OUT seeds, one frozen
estimator configuration. Descriptive diagnostics only; no qualification,
no PASS/FAIL, no acceptance verdict.
"""
import json

from rudeus.science.calibration import (
    CalibrationPlan,
    CalibrationScope,
    SplitAssignment,
    TruthRecord,
    TruthType,
)
from rudeus.science.calibration_batch import materialize_calibration_dataset
from rudeus.science.calibration_diagnostics import diagnose_calibration_errors
from rudeus.science.calibration_estimator import estimate_calibration_replicate
from rudeus.science.calibration_execution import materialize_replicate
from rudeus.science.calibration_s1 import (
    S1_CODE_REVISION,
    S1_DEV_SEEDS,
    S1_ESTIMATOR_CONFIG,
    S1_HELDOUT_SEEDS,
    S1_TRUTH_D_M2_PER_S,
    build_s1_plan_family,
)
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import VALID, validate_graph


def _manifests_for(store, reps):
    manifests = {}
    for rep in reps:
        found = [p for p in (store.root / "calibration_replicates").glob("*.json")
                 if json.loads(p.read_bytes())["replicate_id"] == rep]
        assert len(found) == 1
        manifests[rep] = found[0].stem
    return manifests


def _run_pipeline(store, root, hashes, seeds, dataset_key):
    dataset_h = hashes["datasets"][dataset_key]
    batch = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=dataset_h,
        artifact_root=root, seeds=seeds, code_revision=S1_CODE_REVISION)
    assert batch["failed"] == []
    manifests = _manifests_for(store, tuple(seeds))
    for rep, manifest_h in manifests.items():
        estimate_calibration_replicate(
            calibration_store=store, artifact_root=root,
            replicate_manifest_hash=manifest_h,
            estimator_config=dict(S1_ESTIMATOR_CONFIG),
            code_revision=S1_CODE_REVISION)
    return diagnose_calibration_errors(
        calibration_store=store, artifact_root=root,
        dataset_manifest_hash=dataset_h,
        replicate_manifest_hashes=dict(manifests),
        species="Li", estimator_config=dict(S1_ESTIMATOR_CONFIG),
        code_revision=S1_CODE_REVISION)


def test_s1_plan_freezes_and_validates(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    hashes = build_s1_plan_family(store)
    for dataset_h in hashes["datasets"].values():
        pending = validate_graph(store, hashes["plan"], (dataset_h,), ())
        assert pending.status == "INCOMPLETE"
        assert {v["code"] for v in pending.violations} == {"missing_replicate"}
    _run_pipeline(store, tmp_path / "artifacts", hashes,
                  dict(S1_DEV_SEEDS), "DEV")
    manifests = _manifests_for(store, tuple(S1_DEV_SEEDS))
    assert validate_graph(
        store, hashes["plan"],
        (hashes["datasets"]["DEV"],),
        tuple(manifests.values())).status == VALID
    plan = store.retrieve(CalibrationPlan, hashes["plan"])
    assert set(plan.dev_replicate_ids).isdisjoint(plan.heldout_replicate_ids)


def test_s1_seeds_disjoint(tmp_path):
    assert set(S1_DEV_SEEDS).isdisjoint(S1_HELDOUT_SEEDS)
    assert set(S1_DEV_SEEDS.values()).isdisjoint(S1_HELDOUT_SEEDS.values())
    store = CalibrationStore(tmp_path / "store")
    hashes = build_s1_plan_family(store)
    plan = store.retrieve(CalibrationPlan, hashes["plan"])
    assert set(plan.dev_replicate_ids) == set(S1_DEV_SEEDS)
    assert set(plan.heldout_replicate_ids) == set(S1_HELDOUT_SEEDS)


def test_s1_analytic_truth(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    hashes = build_s1_plan_family(store)
    truth = store.retrieve(TruthRecord, hashes["truth"])
    assert truth.truth_type == TruthType.ANALYTICAL
    assert truth.statistical_interpretation == "ensemble"
    assert truth.window_interpretation == "long_time"
    assert truth.cell_interpretation == "bulk"
    assert truth.value == {"D_m2_per_s": S1_TRUTH_D_M2_PER_S}
    assert truth.unavailable_reason is None


def _scientific_content(payload):
    return {
        "entries": {
            rep: {key: entry[key] for key in
                  ("estimate", "truth", "signed_error", "absolute_error")}
            for rep, entry in payload["entries"].items()
        },
        "aggregate": payload["aggregate"],
    }


def test_s1_end_to_end_replay(tmp_path):
    store_a = CalibrationStore(tmp_path / "store-a")
    hashes_a = build_s1_plan_family(store_a)
    first = _run_pipeline(store_a, tmp_path / "artifacts-a", hashes_a,
                          dict(S1_DEV_SEEDS), "DEV")
    store_b = CalibrationStore(tmp_path / "store-b")
    hashes_b = build_s1_plan_family(store_b)
    assert hashes_b == hashes_a
    second = _run_pipeline(store_b, tmp_path / "artifacts-b", hashes_b,
                           dict(S1_DEV_SEEDS), "DEV")
    payload_a = json.loads((tmp_path / "artifacts-a" / "calibration_diagnostics"
                            / (first["diagnostic_hash"] + ".json")).read_bytes())
    payload_b = json.loads((tmp_path / "artifacts-b" / "calibration_diagnostics"
                            / (second["diagnostic_hash"] + ".json")).read_bytes())
    # Scientific diagnostic content replays bit-identically. Content hashes
    # legitimately differ: estimator results bind replicate manifests, which
    # bind execution attempts carrying wall-clock timestamps (operational
    # provenance, excluded from scientific identity by design).
    assert _scientific_content(payload_a) == _scientific_content(payload_b)
    assert first["n_diagnostics"] == 2 and first["n_missing_or_failed"] == 0
    assert second["n_diagnostics"] == 2 and second["n_missing_or_failed"] == 0


def test_seed_override_equivalence(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    hashes = build_s1_plan_family(store)
    dataset_h = hashes["datasets"]["DEV"]
    batch = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=dataset_h,
        artifact_root=tmp_path / "artifacts", seeds=dict(S1_DEV_SEEDS),
        code_revision=S1_CODE_REVISION)
    assert batch["failed"] == []
    from rudeus.science.calibration_execution import build_calibration_task
    scope = store.retrieve(CalibrationScope, hashes["scope"])
    task = build_calibration_task(
        plan_hash=hashes["plan"], scope_hash=hashes["scope"],
        dataset_manifest_hash=dataset_h, generator_spec_hash=hashes["generator"],
        truth_record_hash=hashes["truth"], replicate_id="s1-dev-1",
        parameter_cell_id="cell-a", split_assignment=SplitAssignment.DEV,
        seed=999, code_revision=S1_CODE_REVISION)
    assert scope.species_composition == {"Li": 2}
    overridden = materialize_replicate(
        task=task, calibration_store=store, artifact_root=tmp_path / "override",
        seed_override=11)
    assert overridden["artifact_status"] == "STORED"
    direct = materialize_replicate(
        task=task, calibration_store=store, artifact_root=tmp_path / "direct",
        seed_override=11)
    assert (overridden["trajectory_logical_hash"]
            == direct["trajectory_logical_hash"])
    seeded_task = build_calibration_task(
        plan_hash=hashes["plan"], scope_hash=hashes["scope"],
        dataset_manifest_hash=dataset_h, generator_spec_hash=hashes["generator"],
        truth_record_hash=hashes["truth"], replicate_id="s1-dev-1",
        parameter_cell_id="cell-a", split_assignment=SplitAssignment.DEV,
        seed=11, code_revision=S1_CODE_REVISION)
    assert seeded_task.task_id != task.task_id


def test_s1_no_qualification(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    hashes = build_s1_plan_family(store)
    result = _run_pipeline(store, tmp_path / "artifacts", hashes,
                           dict(S1_DEV_SEEDS), "DEV")
    payload = json.loads((tmp_path / "artifacts" / "calibration_diagnostics"
                          / (result["diagnostic_hash"] + ".json")).read_bytes())
    assert set(result) == {"diagnostic_hash", "dataset_manifest_hash",
                           "n_diagnostics", "n_missing_or_failed",
                           "artifact_status"}
    encoded = json.dumps(payload)
    for token in ("QualificationRecord", "acceptance", "coverage", "qualified",
                  '"PASS"', '"FAIL"', '"INDETERMINATE"', "threshold"):
        assert token not in encoded
