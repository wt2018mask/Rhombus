"""Static/configuration tests for the frozen S2 DEV run script.

No calibration is executed here: no materialization, no estimation, no
coverage run. These tests verify frozen configuration, wiring, and scope
discipline only.
"""
from pathlib import Path

from rudeus.science import run_s2_dev_coverage as runner
from rudeus.science.calibration_s2 import S2_DEV_REPLICATES, S2_DEV_SEEDS
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import VALID, validate_dataset


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
    assert "brownian" not in text
    assert "QualificationRecord" not in text
    assert "PASS" not in text
    assert "coverage_experiment" in text


def test_cli_interface_exists():
    import argparse
    assert callable(runner.main)
    assert callable(runner.run_s2_dev_coverage)
