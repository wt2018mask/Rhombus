"""Synthetic fixture tests for the 0130 real-source CPU audit runner."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.science.obelix_real_source_pipeline import (
    _EXPECTED, SCHEMA, main, run_three_stage_obelix,
)
from tests.test_phase3_obelix_benchmark_intake import checkout, _git


def test_three_stage_pipeline_produces_exact_provenance_and_no_science_go(tmp_path):
    root, commit = checkout(tmp_path)
    destination = tmp_path / "out"
    manifest = run_three_stage_obelix(
        root, destination, expected_commit=commit,
        require_official_counts=False,
    )
    assert manifest["schema_version"] == SCHEMA
    assert manifest["scope"] == "SYNTHETIC_FIXTURE_ONLY"
    assert manifest["source_records"] == 4
    assert manifest["official_train"] == 3
    assert manifest["official_test"] == 1
    assert manifest["linked_cif_files"] == 2
    assert manifest["possible_overlap_pairs"] == 0
    assert manifest["independent_material_count"] is None
    assert manifest["qualified_experimental_transport_count"] is None
    assert manifest["new_externally_blinded_count"] == 0
    assert not manifest["model_training_membership_independently_verified"]
    assert not manifest["experimental_source_truth_independently_adjudicated"]
    assert not manifest["scientific_qualification_authorized"]
    assert not manifest["kaggle_gpu_submitted"]
    assert _git(root, "status", "--porcelain") == ""
    assert json.loads((destination / "manifest.json").read_text()) == manifest
    for name, metadata in manifest["files"].items():
        raw = (destination / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == metadata["sha256"]
        assert len(raw) == metadata["size_bytes"]
    assert len((destination / "0127/records.jsonl").read_bytes().splitlines()) == 4
    assert len((destination / "0129/scoreability_records.jsonl").read_bytes().splitlines()) == 4


def test_unexpected_official_count_does_not_write_partial_artifact(tmp_path, monkeypatch):
    # Inject a synthetic record set at the *count gate* specifically, while
    # retaining the exact immutable production commit requirement.
    import scripts.science.obelix_real_source_pipeline as pipeline
    root, fixture_commit = checkout(tmp_path)
    actual_reader = pipeline.build_obelix_benchmark_intake

    def fixture_at_count_gate(checkout_path, *, expected_commit):
        assert expected_commit == pipeline.SOURCE_COMMIT
        return actual_reader(checkout_path, expected_commit=fixture_commit)

    monkeypatch.setattr(pipeline, "build_obelix_benchmark_intake",
                        fixture_at_count_gate)
    target = tmp_path / "result"
    with pytest.raises(ValueError, match="approved version"):
        run_three_stage_obelix(
            root, target, expected_commit=pipeline.SOURCE_COMMIT,
            require_official_counts=True,
        )
    assert not target.exists()


def test_official_commit_is_mandatory_by_default(tmp_path):
    root, _ = checkout(tmp_path)
    target = tmp_path / "target"
    with pytest.raises(ValueError, match="pinned exact commit"):
        run_three_stage_obelix(root, target)
    assert not target.exists()


def test_synthetic_commit_cannot_claim_official_source_even_if_record_count_matches(tmp_path):
    root, commit = checkout(tmp_path)
    assert commit != "4eaac889809dd489e3bae468c45d5c0e02b9147a"
    assert _EXPECTED == {
        "records": 599, "train": 478, "test": 121, "cif": 321,
        "match": 260, "close_match": 61, "no_match": 278,
    }
    result = run_three_stage_obelix(root, tmp_path / "fixture",
                                    expected_commit=commit,
                                    require_official_counts=False)
    assert result["scope"] == "SYNTHETIC_FIXTURE_ONLY"


def test_repeat_run_does_not_overwrite_prior_evidence(tmp_path):
    root, commit = checkout(tmp_path)
    target = tmp_path / "immutable"
    first = run_three_stage_obelix(root, target, expected_commit=commit,
                                   require_official_counts=False)
    with pytest.raises(ValueError, match="pre-exist"):
        run_three_stage_obelix(root, target, expected_commit=commit,
                               require_official_counts=False)
    assert json.loads((target / "manifest.json").read_text()) == first


def test_output_inside_upstream_checkout_is_forbidden(tmp_path):
    root, commit = checkout(tmp_path)
    with pytest.raises(ValueError, match="checkout"):
        run_three_stage_obelix(root, root / "output", expected_commit=commit,
                               require_official_counts=False)
    assert _git(root, "status", "--porcelain") == ""


def test_damaged_source_checkout_does_not_write_results(tmp_path):
    root, commit = checkout(tmp_path)
    (root / "data" / "processed.csv").write_text("corrupted input")
    target = tmp_path / "no-output"
    with pytest.raises(ValueError):
        run_three_stage_obelix(root, target, expected_commit=commit,
                               require_official_counts=False)
    assert not target.exists()


def test_two_runs_have_identical_hashes_on_same_pinned_fixture(tmp_path):
    root, commit = checkout(tmp_path)
    first = run_three_stage_obelix(root, tmp_path / "first",
                                   expected_commit=commit,
                                   require_official_counts=False)
    second = run_three_stage_obelix(root, tmp_path / "second",
                                    expected_commit=commit,
                                    require_official_counts=False)
    assert first == second


def test_cli_does_not_accept_unpinned_fixture_as_real_obelix(tmp_path):
    root, _ = checkout(tmp_path)
    target = tmp_path / "unqualified"
    with pytest.raises(SystemExit):
        main(["--obelix-checkout", str(root), "--output-dir", str(target)])
    assert not target.exists()
