"""Fixture-only bounded ZIP member binding: no live GitHub requests."""
from __future__ import annotations

from copy import deepcopy
import io
import json
import stat
import zipfile

import pytest

from rhombus.domain.mptrj_artifact_zip import (
    MPTrjArtifactZipError,
    verify_mptrj_diagnostic_zip_binding,
)
from scripts.development.review_mptrj_manual_run import main as review_main

SHA = "d" * 40
NAME = "mptrj-first-frame-observation.json"


def receipt():
    return {
        "schema_version": "rhombus-phase3-mptrj-range-prefix-probe-v1",
        "source_metadata": {
            "figshare_file_id": 41619375,
            "expected_total_size_bytes_from_registry": 12_188_168_685,
            "server_content_range_total_declared": 12_188_168_685,
            "redirect_host": "ndownloader.figshare.com",
        },
        "observation": {
            "prefix_size_bytes": 262144, "prefix_sha256": "0" * 64,
            "first_material_id": "mp-1", "first_frame_id": "frame-1",
            "first_frame_structure_object_start_seen": True,
            "complete_frame_parsed": True, "complete_original_source_hashed": False,
            "first_frame_structure": {
                "material_id": "mp-1", "frame_id": "frame-1",
                "site_count": 2, "reduced_formula": "LiO",
                "complete_frame_parsed": True,
                "energy_fields_present": {
                    "uncorrected_total_energy": False,
                    "corrected_total_energy": True,
                    "energy_per_atom": True,
                },
            },
        },
        "training_lineage": {
            "mace_mpa0_exact_training_bytes_attested": False,
            "training_frame_selection_attested": False,
        },
        "authorization": {
            "execute_exposure_audit": False,
            "empirical_calibration_use": False,
            "unseen_generalization_claim": False,
        },
    }


def make_zip(path, entries):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, data in entries:
            bundle.writestr(name, data)


def setup(tmp_path):
    local = tmp_path / "receipt.json"
    artifact = tmp_path / "artifact.zip"
    raw = json.dumps(receipt(), sort_keys=True).encode("utf-8")
    local.write_bytes(raw)
    make_zip(artifact, [(NAME, raw)])
    return artifact, local


def test_bound_archive_is_only_local_byte_equality(tmp_path):
    artifact, local = setup(tmp_path)
    before = sorted(x.name for x in tmp_path.iterdir())
    r = verify_mptrj_diagnostic_zip_binding(artifact, local)
    assert r["status"] == "LOCAL_ARTIFACT_ZIP_RECEIPT_BYTES_MATCH_ONLY"
    assert len(r["receipt_byte_sha256"]) == 64
    for field in (
        "github_archive_origin_authenticated", "github_api_response_authenticated",
        "full_source_byte_identity_verified", "model_training_frame_membership_attested",
        "execute_exposure_audit", "empirical_calibration_use", "unseen_generalization_claim",
    ):
        assert r[field] is False
    assert sorted(x.name for x in tmp_path.iterdir()) == before


def test_different_local_receipt_rejected(tmp_path):
    artifact, local = setup(tmp_path)
    value = receipt()
    value["observation"]["first_frame_structure"]["site_count"] = 3
    local.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(MPTrjArtifactZipError, match="differ"):
        verify_mptrj_diagnostic_zip_binding(artifact, local)


@pytest.mark.parametrize("names", [
    ["../mptrj-first-frame-observation.json"],
    ["folder/mptrj-first-frame-observation.json"],
    ["different.json"],
    [NAME, NAME],
    [],
])
def test_traversal_unexpected_and_multiple_members_rejected(tmp_path, names):
    artifact, local = setup(tmp_path)
    raw = local.read_bytes()
    make_zip(artifact, [(name, raw) for name in names])
    with pytest.raises(MPTrjArtifactZipError):
        verify_mptrj_diagnostic_zip_binding(artifact, local)


def test_symlink_member_rejected(tmp_path):
    artifact, local = setup(tmp_path)
    item = zipfile.ZipInfo(NAME)
    item.create_system = 3
    item.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr(item, b"receipt.json")
    with pytest.raises(MPTrjArtifactZipError, match="symlink"):
        verify_mptrj_diagnostic_zip_binding(artifact, local)


def test_zip_and_member_byte_caps_are_enforced(tmp_path):
    artifact, local = setup(tmp_path)
    artifact.write_bytes(b"Q" * (64 * 1024 + 1))
    with pytest.raises(MPTrjArtifactZipError, match="budget"):
        verify_mptrj_diagnostic_zip_binding(artifact, local)
    make_zip(artifact, [(NAME, b"A" * (16 * 1024 + 1))])
    with pytest.raises(MPTrjArtifactZipError, match="16KiB"):
        verify_mptrj_diagnostic_zip_binding(artifact, local)


def test_bad_zip_and_symlink_inputs_rejected(tmp_path):
    artifact, local = setup(tmp_path)
    artifact.write_bytes(b"not a zip")
    with pytest.raises(MPTrjArtifactZipError, match="ZIP"):
        verify_mptrj_diagnostic_zip_binding(artifact, local)
    artifact, local = setup(tmp_path)
    link = tmp_path / "alias.zip"
    link.symlink_to(artifact)
    with pytest.raises(MPTrjArtifactZipError, match="non-symlink"):
        verify_mptrj_diagnostic_zip_binding(link, local)


def test_identical_malicious_report_is_still_invalid(tmp_path):
    artifact, local = setup(tmp_path)
    value = receipt()
    value["authorization"]["execute_exposure_audit"] = True
    raw = json.dumps(value).encode()
    local.write_bytes(raw)
    make_zip(artifact, [(NAME, raw)])
    with pytest.raises(ValueError, match="unsupported claim"):
        verify_mptrj_diagnostic_zip_binding(artifact, local)


def test_identical_duplicate_json_keys_still_rejected(tmp_path):
    artifact, local = setup(tmp_path)
    raw = json.dumps(receipt()).replace(
        '"figshare_file_id": 41619375',
        '"figshare_file_id": 41619375, "figshare_file_id": 41619375',
    ).encode()
    local.write_bytes(raw)
    make_zip(artifact, [(NAME, raw)])
    with pytest.raises(MPTrjArtifactZipError, match="duplicate"):
        verify_mptrj_diagnostic_zip_binding(artifact, local)


def test_review_cli_checks_zip_when_explicit(tmp_path, capsys):
    artifact, local = setup(tmp_path)
    run = {
        "id": 999, "run_attempt": 1, "event": "workflow_dispatch",
        "name": "Phase 3 MPTrj Capped Source Prefix",
        "path": ".github/workflows/phase3-mptrj-first-frame-manual.yml",
        "head_branch": "main", "head_sha": SHA,
        "status": "completed", "conclusion": "success",
        "html_url": "https://github.com/wt2018mask/Rhombus/actions/runs/999",
        "repository": {"full_name": "wt2018mask/Rhombus"},
    }
    arts = {"artifacts": [{
        "id": 123, "name": "mptrj-first-frame-observation",
        "size_in_bytes": 1000, "expired": False,
        "archive_download_url": "https://api.github.com/repos/wt2018mask/Rhombus/actions/artifacts/123/zip",
        "workflow_run": {"id": 999, "head_sha": SHA},
    }]}
    run_file, art_file = tmp_path / "run.json", tmp_path / "artifacts.json"
    run_file.write_text(json.dumps(run), encoding="utf-8")
    art_file.write_text(json.dumps(arts), encoding="utf-8")
    args = [
        "--run-json", str(run_file), "--artifacts-json", str(art_file),
        "--receipt", str(local), "--artifact-zip", str(artifact),
        "--expected-head-sha", SHA,
    ]
    assert review_main(args) == 0
    output = capsys.readouterr().out
    assert "LOCAL_ARTIFACT_ZIP_RECEIPT_BYTES_MATCH_SHA256=" in output
    assert "GITHUB_ARCHIVE_ORIGIN_NOT_AUTHENTICATED" in output
    local.write_bytes(b"not the same")
    assert review_main(args) == 1
