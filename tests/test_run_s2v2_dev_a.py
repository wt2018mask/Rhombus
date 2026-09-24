"""Focused tests for the S2 v2 DEV-A runner (tmp dirs + fixtures only).

No real Brownian execution, no estimator calls, no real evidence roots.
All store/artifact content is synthetic fixture JSON in tmp_path.
"""
import json
from pathlib import Path

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science import calibration_s2v2_populations as pop
from rudeus.science import run_s2v2_dev_a as runner
from rudeus.science.calibration_s2v2_stageb import (
    build_s2v2_score_record,
    freeze_s2v2_calibration_package,
)
from rudeus.science.contracts import digest

REVISION = "runner-fixture-revision"


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _manifest(replicate_id, seed, truth="t" * 64):
    return {"replicate_id": replicate_id, "seed": seed,
            "dataset_id": runner.S2V2_DEV_A_DATASET_ID,
            "split_assignment": "DEV", "trajectory_artifact_hash": "u" * 64,
            "truth_record_hash": truth,
            "execution_attempt_hash": "v" * 64}


def _estimator(replicate_id, manifest_hash, revision=REVISION):
    return {"replicate_id": replicate_id,
            "replicate_manifest_hash": manifest_hash,
            "estimator_config": {"lag_steps": [1, 2],
                                 "fit_window_ps": [0.5, 2.5],
                                 "selected_species": ["Li"],
                                 "volume_A3": 1000.0, "temperature_K": 550.0,
                                 "reference_frame": "simulation_cell",
                                 "charge_numbers": None},
            "code_revision": revision,
            "result": {"self_diffusion_by_species": {
                "Li": {"D_m2_per_s": 1.05e-9}}}}


def test_preflight_passes_on_empty_root(tmp_path):
    assert runner.check_deva_target_root_empty(
        store_root=tmp_path / "store",
        artifact_root=tmp_path / "artifacts") is None


def test_preflight_refuses_planted_manifest(tmp_path):
    _write(tmp_path / "store" / "calibration_replicates" / "m.json",
           _manifest("s2v2-dev-a-001", 265))
    with pytest.raises(ExecutionError):
        runner.check_deva_target_root_empty(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts")


def test_preflight_refuses_planted_score(tmp_path):
    _write(tmp_path / "artifacts" / runner.SCORE_DIR / "s.json",
           {"replicate_id": "s2v2-dev-a-050", "score_value": 1e-10})
    with pytest.raises(ExecutionError):
        runner.check_deva_target_root_empty(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts")


def test_preflight_refuses_planted_package(tmp_path):
    _write(tmp_path / "artifacts" / runner.PACKAGE_DIR / "p.json", {"n": 99})
    with pytest.raises(ExecutionError):
        runner.check_deva_target_root_empty(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts")


def test_preflight_refuses_planted_identity(tmp_path):
    _write(tmp_path / "artifacts" / runner.IDENTITY_DIR / "i.json", {})
    with pytest.raises(ExecutionError):
        runner.check_deva_target_root_empty(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts")


def test_preflight_ignores_unrelated_evidence(tmp_path):
    _write(tmp_path / "store" / "calibration_replicates" / "v1.json",
           _manifest("s2-dev-01", 201))
    _write(tmp_path / "artifacts" / runner.SCORE_DIR / "other.json",
           {"replicate_id": "other-pop", "score_value": 1e-10})
    _write(tmp_path / "artifacts" / "estimator_results" / "junk.json",
           {"not": "attributable"})
    assert runner.check_deva_target_root_empty(
        store_root=tmp_path / "store",
        artifact_root=tmp_path / "artifacts") is None


def test_v1_evidence_not_consumed(tmp_path):
    _write(tmp_path / "store" / "calibration_replicates" / "v1.json",
           _manifest("s2-dev-01", 201))
    with pytest.raises(ExecutionError):
        runner.find_deva_replicate_manifest(tmp_path / "store", "s2v2-dev-a-001")
    with pytest.raises(ExecutionError):
        build_s2v2_score_record(
            replicate_id="s2-dev-01", estimate_D=1e-9, truth_D=1e-9,
            replicate_manifest_hash="a" * 64, estimator_result_hash="b" * 64,
            truth_record_hash="c" * 64, code_revision=REVISION)


def test_runner_hard_bound_to_deva_inventory():
    assert runner.S2V2_DEV_A_SEEDS is pop.S2V2_DEV_A_SEEDS
    assert len(runner.S2V2_DEV_A_SEEDS) == 99
    text = Path(runner.__file__).read_text()
    assert "DEV_B_SEEDS" not in text and "HELDOUT_SEEDS" not in text


def test_no_population_selector():
    import argparse
    actions = set()
    original = argparse.ArgumentParser.add_argument

    def spy(self, *names, **kwargs):
        actions.update(names)
        return original(self, *names, **kwargs)

    argparse.ArgumentParser.add_argument = spy
    try:
        runner.main(["--help"])
    except SystemExit:
        pass
    finally:
        argparse.ArgumentParser.add_argument = original
    assert actions == {"--store-root", "--artifact-root", "--code-revision",
                       "--preflight-only", "-h", "--help"}


def test_exact_count_and_mapping():
    assert len(runner.S2V2_DEV_A_SEEDS) == 99
    assert runner.S2V2_DEV_A_SEEDS["s2v2-dev-a-001"] == 265
    assert runner.S2V2_DEV_A_SEEDS["s2v2-dev-a-099"] == 363


def test_exact_one_manifest_lookup(tmp_path):
    store = tmp_path / "store"
    _write(store / "calibration_replicates" / "a.json",
           _manifest("s2v2-dev-a-010", 274))
    manifest_hash, record = runner.find_deva_replicate_manifest(
        store, "s2v2-dev-a-010")
    assert manifest_hash == "a"
    assert record["seed"] == 274
    runner.verify_manifest_for_scoring(
        record, replicate_id="s2v2-dev-a-010", seed=274,
        dataset_id=runner.S2V2_DEV_A_DATASET_ID, truth_hash="t" * 64)
    with pytest.raises(ExecutionError):
        runner.verify_manifest_for_scoring(
            dict(record, seed=999), replicate_id="s2v2-dev-a-010", seed=274,
            dataset_id=runner.S2V2_DEV_A_DATASET_ID, truth_hash="t" * 64)
    with pytest.raises(ExecutionError):
        runner.find_deva_replicate_manifest(store, "s2v2-dev-a-011")


def test_estimator_revision_mismatch_rejected():
    estimator = _estimator("s2v2-dev-a-010", "m" * 64, revision="other-rev")
    with pytest.raises(ExecutionError):
        runner.verify_estimator_for_scoring(
            estimator, replicate_id="s2v2-dev-a-010", manifest_hash="m" * 64,
            expected_config=dict(runner.S2V2_EXPECTED_CONFIG),
            code_revision=REVISION)


def test_truth_mismatch_rejected():
    with pytest.raises(ExecutionError):
        runner.verify_manifest_for_scoring(
            _manifest("s2v2-dev-a-010", 274, truth="d" * 64),
            replicate_id="s2v2-dev-a-010", seed=274,
            dataset_id=runner.S2V2_DEV_A_DATASET_ID, truth_hash="t" * 64)


def test_duplicate_manifest_rejected(tmp_path):
    store = tmp_path / "store"
    _write(store / "calibration_replicates" / "a.json",
           _manifest("s2v2-dev-a-010", 274))
    _write(store / "calibration_replicates" / "b.json",
           _manifest("s2v2-dev-a-010", 274))
    with pytest.raises(ExecutionError):
        runner.find_deva_replicate_manifest(store, "s2v2-dev-a-010")


def test_missing_estimator_result_rejected(tmp_path):
    with pytest.raises(ExecutionError):
        runner.find_estimator_result(tmp_path / "artifacts", "m" * 64)


def test_duplicate_estimator_result_rejected(tmp_path):
    root = tmp_path / "artifacts"
    _write(root / "estimator_results" / "e1.json",
           _estimator("s2v2-dev-a-010", "m" * 64))
    _write(root / "estimator_results" / "e2.json",
           _estimator("s2v2-dev-a-010", "m" * 64))
    with pytest.raises(ExecutionError):
        runner.find_estimator_result(root, "m" * 64)


def test_estimator_extraction_and_config(tmp_path):
    root = tmp_path / "artifacts"
    _write(root / "estimator_results" / "e1.json",
           _estimator("s2v2-dev-a-010", "m" * 64))
    estimator = runner.find_estimator_result(root, "m" * 64)
    estimate = runner.verify_estimator_for_scoring(
        estimator, replicate_id="s2v2-dev-a-010", manifest_hash="m" * 64,
        expected_config=dict(runner.S2V2_EXPECTED_CONFIG),
        code_revision=REVISION)
    assert estimate == 1.05e-9
    with pytest.raises(ExecutionError):
        runner.verify_estimator_for_scoring(
            dict(estimator, estimator_config=dict(estimator["estimator_config"],
                                                  lag_steps=[1, 3])),
            replicate_id="s2v2-dev-a-010", manifest_hash="m" * 64,
            expected_config=dict(runner.S2V2_EXPECTED_CONFIG),
            code_revision=REVISION)


def test_persisted_score_digest_matches(tmp_path):
    record = build_s2v2_score_record(
        replicate_id="s2v2-dev-a-001", estimate_D=1.1e-9, truth_D=1e-9,
        replicate_manifest_hash="a" * 64, estimator_result_hash="b" * 64,
        truth_record_hash="c" * 64, code_revision=REVISION)
    identity = runner.persist_json_record(
        tmp_path / "artifacts", runner.SCORE_DIR, record)
    assert identity == digest(record)
    stored = json.loads((tmp_path / "artifacts" / runner.SCORE_DIR
                         / f"{identity}.json").read_text())
    assert stored == record


def test_99_fixture_scores_feed_committed_freeze():
    records = []
    for position, replicate_id in enumerate(sorted(pop.S2V2_DEV_A_SEEDS)):
        records.append(build_s2v2_score_record(
            replicate_id=replicate_id,
            estimate_D=1e-9 + position * 1e-11, truth_D=1e-9,
            replicate_manifest_hash="a" * 64,
            estimator_result_hash="b" * 64, truth_record_hash="c" * 64,
            code_revision=REVISION))
    package = freeze_s2v2_calibration_package(
        score_records=records, code_revision=REVISION)
    assert package["n"] == 99
    assert package["k"] == 90


def test_fixture_package_n_k():
    records = []
    for position, replicate_id in enumerate(sorted(pop.S2V2_DEV_A_SEEDS)):
        records.append(build_s2v2_score_record(
            replicate_id=replicate_id,
            estimate_D=1e-9 + position * 1e-11, truth_D=1e-9,
            replicate_manifest_hash="a" * 64,
            estimator_result_hash="b" * 64, truth_record_hash="c" * 64,
            code_revision=REVISION))
    package = freeze_s2v2_calibration_package(
        score_records=records, code_revision=REVISION)
    assert (package["n"], package["k"]) == (99, 90)
    assert package["q_hat"] == sorted(
        record["score_value"] for record in records)[89]


def test_complete_identity_binds_package_hash():
    from rudeus.science.calibration_s2v2_stageb import (
        build_complete_pre_heldout_identity,
    )
    identity = build_complete_pre_heldout_identity(
        calibration_package_hash="e" * 64, code_revision=REVISION)
    assert identity["calibration_package_hash"] == "e" * 64
    assert identity["phase"] == {"calibration": "frozen",
                                 "dev_b": "not-evaluated",
                                 "heldout": "unopened"}


def test_no_v1_interval_import():
    text = Path(runner.__file__).read_text()
    for marker in ("estimate_interval_for_replicate",
                   "matched_origin_block_bootstrap", "calibration_intervals",
                   "block_origins", "bootstrap", "run_s2_dev_coverage"):
        assert marker not in text, marker


def test_no_qualification_state():
    text = Path(runner.__file__).read_text()
    assert "QualificationRecord(" not in text
    assert "Uncertainty(" not in text
    assert ".bounds" not in text
    assert "Verdict" not in text and "verdict" not in text.lower()


def test_no_heldout_execution_path():
    text = Path(runner.__file__).read_text()
    for marker in ("HELDOUT_SEEDS", "DEV_B_SEEDS", "HeldoutEvaluation",
                   "unblind", "run_heldout", "open_heldout", "--heldout",
                   "--held-out", "--dev-b"):
        assert marker not in text, marker


def test_rerun_after_partial_write_refuses(tmp_path):
    _write(tmp_path / "store" / "calibration_replicates" / "m.json",
           _manifest("s2v2-dev-a-001", 265))
    _write(tmp_path / "artifacts" / "estimator_results" / "e.json",
           _estimator("s2v2-dev-a-001", "m"))
    _write(tmp_path / "artifacts" / runner.SCORE_DIR / "s.json",
           {"replicate_id": "s2v2-dev-a-001", "score_value": 1e-10})
    with pytest.raises(ExecutionError):
        runner.check_deva_target_root_empty(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts")
