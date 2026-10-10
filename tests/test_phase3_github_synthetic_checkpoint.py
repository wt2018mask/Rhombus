"""Synthetic cross-job checkpoint transfer: tiny no-network falsification tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.development.prove_github_synthetic_checkpoint import (
    make_fixture, verify_fixture, main, BUNDLE_ID,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/phase3-github-synthetic-checkpoint-roundtrip.yml"


def _made(tmp_path):
    root = tmp_path / "new"
    record = make_fixture(root)
    assert record["external_storage_verified"] is False
    return root / "bundle"


def test_synthetic_sqlite_8_rows_roundtrip_rebuilds_exact_hash_and_rows(tmp_path):
    folder = _made(tmp_path)
    verified = verify_fixture(folder)
    assert verified["rows_verified"] == 8
    assert verified["part_count"] >= 2
    assert verified["source_lineage_verified"] is False
    assert verified["external_durability_verified_by_local_verifier"] is False
    assert verified["actual_kaggle_resume_verified"] is False
    assert verified["scientific_verdict"] == "UNKNOWN"
    assert verified["claim_authorized"] is False


def test_missing_and_corrupt_checkpoint_parts_fail_closed(tmp_path):
    folder = _made(tmp_path)
    part = folder / (BUNDLE_ID + ".part-00000")
    before = part.read_bytes()
    part.write_bytes(b"!" + before[1:])
    with pytest.raises(ValueError, match="checksum"):
        verify_fixture(folder)
    part.write_bytes(before)
    part.unlink()
    with pytest.raises(ValueError, match="missing"):
        verify_fixture(folder)


def test_claim_promotion_or_oversized_bundle_fails_before_restore(tmp_path):
    folder = _made(tmp_path)
    manifest = folder / (BUNDLE_ID + ".bundle.json")
    original = json.loads(manifest.read_text())
    changed = dict(original)
    changed["external_durability_verified"] = True
    manifest.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="unauthorized"):
        verify_fixture(folder)
    changed = dict(original)
    changed["total_bytes"] = 2**30
    manifest.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="resource budget"):
        verify_fixture(folder)


def test_no_overwrite_and_missing_artifact_cli_fails_closed(tmp_path):
    folder = _made(tmp_path)
    with pytest.raises(FileExistsError):
        make_fixture(folder.parent)
    assert main(["--verify", str(folder / "missing")]) == 1


def test_actions_proves_cross_job_external_artifact_not_fake_local_only():
    data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert data["permissions"] == {"contents": "read"}
    assert set(data["on"]) == {"pull_request", "workflow_dispatch"}
    assert data["on"]["workflow_dispatch"]["inputs"]["run_synthetic_roundtrip"]["default"] == "false"
    assert set(data["jobs"]) == {"stage", "verify-cross-job"}
    maker = data["jobs"]["stage"]
    consumer = data["jobs"]["verify-cross-job"]
    assert consumer["needs"] == "stage"
    assert "runs-on" in maker and "runs-on" in consumer
    assert maker["timeout-minutes"] == "5"
    assert consumer["timeout-minutes"] == "5"
    writer = next(s for s in maker["steps"] if s.get("uses","").startswith("actions/upload-artifact@"))
    reader = next(s for s in consumer["steps"] if s.get("uses","").startswith("actions/download-artifact@"))
    assert writer["with"]["name"] == reader["with"]["name"] == "phase3-synthetic-checkpoint-8row"
    assert writer["with"]["retention-days"] == "7"
    assert "safe-export/synthetic-checkpoint.json" in writer["with"]["path"]
    assert all("KAGGLE_API_TOKEN" not in str(x) for j in data["jobs"].values() for x in j["steps"])
    assert "workflow_dispatch" in data["on"]
    assert "schedule" not in data["on"] and "push" not in data["on"]


def test_public_synthetic_transport_scans_only_readable_fixed_fixture_json():
    data=yaml.load(WORKFLOW.read_text(),Loader=yaml.BaseLoader)
    stage=data['jobs']['stage']['steps']
    upload_index=next(i for i,s in enumerate(stage) if s.get('uses','').startswith('actions/upload-artifact@'))
    assert any('scan_outgoing_artifacts.py' in s.get('run','') for s in stage[:upload_index])
    upload=stage[upload_index]
    assert upload['with']['path'].endswith('/safe-export/synthetic-checkpoint.json')
    assert '--allow synthetic-checkpoint.json' in str(stage)


def test_fixed_readable_synthetic_export_roundtrip_and_corrupt_data_rejection(tmp_path):
    from scripts.development.prove_github_synthetic_checkpoint import make_safe_export, verify_safe_export
    from scripts.security.scan_outgoing_artifacts import scan_directory
    root=tmp_path/'safe'
    made=make_safe_export(root)
    folder=root/'safe-export'
    assert not made['opaque_artifacts_exported']
    assert scan_directory(folder, allowed_paths={'synthetic-checkpoint.json'})[0] > 0
    checked=verify_safe_export(folder)
    assert checked['rows_verified']==8
    assert not checked['external_sqlite_durability_verified']
    assert not checked['actual_kaggle_resume_verified']
    path=folder/'synthetic-checkpoint.json'
    value=json.loads(path.read_text());value['records'][0][1]='non-synthetic-content'
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='not exact'):verify_safe_export(folder)
