"""Offline tests: GitHub metadata consistency is not source authentication."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from rhombus.domain.mptrj_run_metadata import (
    MPTrjRunMetadataError,
    validate_mptrj_manual_run_metadata,
)
from scripts.development.review_mptrj_manual_run import _read_small_json, main

SHA = "b" * 40


def snapshots():
    run = {
        "id": 9876543, "run_attempt": 1, "event": "workflow_dispatch",
        "name": "Phase 3 MPTrj Capped Source Prefix",
        "path": ".github/workflows/phase3-mptrj-first-frame-manual.yml@refs/heads/main",
        "head_branch": "main", "head_sha": SHA,
        "status": "completed", "conclusion": "success",
        "html_url": "https://github.com/wt2018mask/Rhombus/actions/runs/9876543",
        "repository": {"full_name": "wt2018mask/Rhombus"},
    }
    artifacts = {
        "total_count": 1,
        "artifacts": [{
            "id": 123, "name": "mptrj-first-frame-observation",
            "size_in_bytes": 1450, "expired": False,
            "archive_download_url": "https://api.github.com/repos/wt2018mask/Rhombus/actions/artifacts/123/zip",
            "workflow_run": {"id": 9876543, "head_sha": SHA},
        }],
    }
    return run, artifacts


def test_consistent_metadata_is_never_claimed_as_provenance_or_science():
    run, artifacts = snapshots()
    r = validate_mptrj_manual_run_metadata(run, artifacts, expected_head_sha=SHA)
    assert r["run_id"] == 9876543
    assert r["status"].endswith("CONSISTENT_ONLY")
    for key in (
        "github_api_response_authenticated", "receipt_bytes_bound_to_artifact",
        "full_source_byte_identity_verified", "mace_mpa0_training_membership_attested",
        "execute_exposure_audit", "empirical_calibration_use", "unseen_generalization_claim",
    ):
        assert r[key] is False


@pytest.mark.parametrize(("where", "key", "bad"), [
    ("run", "event", "pull_request"),
    ("run", "head_branch", "worker/unreviewed"),
    ("run", "status", "in_progress"),
    ("run", "conclusion", "failure"),
    ("run", "head_sha", "a" * 40),
    ("run", "path", ".github/workflows/other.yml"),
    ("run", "html_url", "https://github.com/elsewhere"),
    ("artifact", "size_in_bytes", 100000),
    ("artifact", "expired", True),
    ("artifact", "archive_download_url", "https://wrong.example/a"),
])
def test_mismatches_reject_without_promotion(where, key, bad):
    run, collection = snapshots()
    if where == "run":
        run[key] = bad
    else:
        collection["artifacts"][0][key] = bad
    with pytest.raises(MPTrjRunMetadataError):
        validate_mptrj_manual_run_metadata(run, collection, expected_head_sha=SHA)


def test_other_run_and_duplicate_named_artifacts_are_rejected():
    run, collection = snapshots()
    collection["artifacts"][0]["workflow_run"]["id"] = 444
    with pytest.raises(MPTrjRunMetadataError):
        validate_mptrj_manual_run_metadata(run, collection, expected_head_sha=SHA)
    run, collection = snapshots()
    collection["artifacts"].append(deepcopy(collection["artifacts"][0]))
    with pytest.raises(MPTrjRunMetadataError):
        validate_mptrj_manual_run_metadata(run, collection, expected_head_sha=SHA)


def test_bounded_offline_json_loader_rejects_duplicates_symlinks_and_large_inputs(tmp_path):
    path = tmp_path / "run.json"
    path.write_text('{"id": 1, "id": 2}', encoding="utf-8")
    with pytest.raises(MPTrjRunMetadataError, match="duplicate"):
        _read_small_json(path)
    path.write_bytes(b"x" * (128 * 1024 + 1))
    with pytest.raises(MPTrjRunMetadataError, match="128KiB"):
        _read_small_json(path)
    path.write_text("{}", encoding="utf-8")
    link = tmp_path / "linked.json"
    link.symlink_to(path)
    with pytest.raises(MPTrjRunMetadataError, match="non-symlink"):
        _read_small_json(link)


def test_cli_fails_closed_without_valid_receipt(tmp_path, capsys):
    run, artifacts = snapshots()
    r = tmp_path / "run.json"
    a = tmp_path / "artifacts.json"
    p = tmp_path / "receipt.json"
    r.write_text(json.dumps(run), encoding="utf-8")
    a.write_text(json.dumps(artifacts), encoding="utf-8")
    p.write_text("{}", encoding="utf-8")
    result = main([
        "--run-json", str(r), "--artifacts-json", str(a),
        "--receipt", str(p), "--expected-head-sha", SHA,
    ])
    assert result == 1
    assert "REJECTED" in capsys.readouterr().err
