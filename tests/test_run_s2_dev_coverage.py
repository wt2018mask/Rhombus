"""Static/configuration tests for the frozen S2 DEV run script.

No calibration is executed here: no materialization, no estimation, no
coverage run. These tests verify frozen configuration, wiring, and scope
discipline only.
"""
from pathlib import Path

import numpy as np
import pytest

from rudeus.science import run_s2_dev_coverage as runner
from rudeus.science.calibration import CalibrationDatasetManifest, CalibrationPlan
from rudeus.science.calibration_s2 import S2_DEV_REPLICATES, S2_DEV_SEEDS
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import (
    VALID,
    validate_dataset,
    validate_graph,
    validate_plan,
)


def test_frozen_preconditions_hold_without_execution():
    assert runner.assert_frozen_preconditions() is None


def test_dataset_manifest_builds_and_validates(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    family = runner.build_s1_family_for_run(store)
    dataset_hash = runner.build_s2_dev_dataset(store, family)
    assert validate_dataset(store, dataset_hash).status == VALID
    assert set(S2_DEV_SEEDS) == set(S2_DEV_REPLICATES)


def test_no_raw_generation_or_qualification_in_script():
    text = Path(runner.__file__).read_text()
    assert "brownian(" not in text
    assert "from rudeus.science.synthetic import" not in text
    assert "QualificationRecord" not in text
    assert "PASS" not in text
    assert "coverage_experiment" in text


def test_s2_plan_permits_exactly_the_64_s2_replicates(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    family = runner.build_s1_family_for_run(store)
    plan_hash = runner.build_s2_plan(store, family)
    plan = store.retrieve(CalibrationPlan, plan_hash)
    assert tuple(plan.dev_replicate_ids) == S2_DEV_REPLICATES
    assert tuple(plan.heldout_replicate_ids) == ()
    assert tuple(plan.scope_hashes) == (family["scope"],)
    assert validate_plan(store, plan_hash).status == VALID


def test_s2_dataset_references_s2_plan(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    family = runner.build_s1_family_for_run(store)
    dataset_hash = runner.build_s2_dev_dataset(store, family)
    manifest = store.retrieve(CalibrationDatasetManifest, dataset_hash)
    plan_hash = runner.build_s2_plan(store, family)
    assert manifest.plan_hash == plan_hash
    assert manifest.plan_hash != family["plan"]
    result = validate_graph(store, plan_hash, (dataset_hash,))
    assert result.status == "INCOMPLETE"
    assert {v["code"] for v in result.violations} == {"missing_replicate"}
    assert {v["identity"] for v in result.violations} == set(S2_DEV_REPLICATES)
    plan = store.retrieve(CalibrationPlan, plan_hash)
    assert set(manifest.attempted_replicate_ids) == set(S2_DEV_REPLICATES)
    assert set(manifest.attempted_replicate_ids) <= set(plan.dev_replicate_ids)


def test_cli_interface_exists():
    import argparse
    assert callable(runner.main)
    assert callable(runner.run_s2_dev_coverage)


def _one_rep_graph(tmp_path):
    """Materialize, estimate, and interval-fit one S1 replicate (tmp dirs only)."""
    import json

    from rudeus.science.calibration import CalibrationClass, SplitAssignment
    from rudeus.science.calibration_batch import materialize_calibration_dataset
    from rudeus.science.calibration_estimator import (
        estimate_calibration_replicate,
        estimate_interval_for_replicate,
    )
    from rudeus.science.calibration_s1 import S1_ESTIMATOR_CONFIG

    store = CalibrationStore(tmp_path / "store")
    root = tmp_path / "artifacts"
    family = runner.build_s1_family_for_run(store)
    dataset = CalibrationDatasetManifest(
        dataset_id="ds-regression-single",
        plan_hash=family["plan"],
        scope_hash=family["scope"],
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",),
        trajectory_ids=("traj-s1-dev-1",),
        truth_record_hashes=(family["truth"],),
        split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(family["generator"],),
        artifact_manifest_hashes=(),
        attempted_replicate_ids=("s1-dev-1",),
    )
    dataset_hash = store.store(dataset)
    assert validate_dataset(store, dataset_hash).status == VALID
    batch = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=dataset_hash,
        artifact_root=root, seeds={"s1-dev-1": 11}, code_revision="f" * 40)
    assert batch["failed"] == []
    manifest_hash = next(
        p.stem for p in (store.root / "calibration_replicates").glob("*.json")
        if json.loads(p.read_bytes())["replicate_id"] == "s1-dev-1")
    estimated = estimate_calibration_replicate(
        calibration_store=store, artifact_root=root,
        replicate_manifest_hash=manifest_hash,
        estimator_config=dict(S1_ESTIMATOR_CONFIG), code_revision="f" * 40)
    interval = estimate_interval_for_replicate(
        calibration_store=store, artifact_root=root,
        estimator_result_hash=estimated["estimator_result_hash"],
        resampling_spec=runner._frozen_resampling_spec(),
        code_revision="f" * 40)
    assert set(interval.keys()) >= {"interval_hash", "estimator_result_hash"}
    return store, root, manifest_hash, estimated, interval


def test_estimator_lookup_rejects_bare_replicate_id(tmp_path):
    """Bug 1 regression: replicate IDs are not content hashes."""
    from rudeus.execution.contracts import ExecutionError

    store = CalibrationStore(tmp_path / "store")
    family = runner.build_s1_family_for_run(store)
    assert family["plan"]
    with pytest.raises(ExecutionError):
        runner._find_estimator_result(tmp_path / "artifacts", "s1-dev-1")


def test_coverage_estimator_closure_retrieves_persisted_evidence(tmp_path):
    """Bug 1+2 regression: end-to-end closure over real persisted artifacts."""
    store, root, manifest_hash, estimated, interval = _one_rep_graph(tmp_path)
    estimator = runner._make_estimator(
        root, manifest_hash, estimated["estimator_result_hash"])
    out = estimator(np.zeros((8, 2, 3)))
    assert np.isfinite(out["estimate"])
    lo, hi = out["interval"]
    assert np.isfinite(lo) and np.isfinite(hi) and lo <= hi
