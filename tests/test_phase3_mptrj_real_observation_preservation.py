"""Offline reproducibility of the first REAL bounded MPTrj observation.

This test consumes fixed original GitHub diagnostic artifact bytes, not mock
scientific data. It never downloads Figshare, runs workflows, or calls GitHub.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest

from rhombus.domain.mptrj_artifact_zip import (
    MPTrjArtifactZipError,
    verify_mptrj_diagnostic_zip_binding,
)
from rhombus.domain.mptrj_probe_receipt import validate_mptrj_first_frame_receipt

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data/development/observations/mptrj-run-37852263493"


def _paths():
    return DIR / "manifest.json", DIR / "diagnostic.zip", DIR / "mptrj-first-frame-observation.json"


def test_frozen_actual_run_artifact_and_receipt_byte_integrity():
    manifest_path, archive, receipt = _paths()
    frozen = json.loads(manifest_path.read_text(encoding="utf-8"))
    r = frozen["github_run"]
    a = frozen["github_artifact"]
    o = frozen["observation"]
    limits = frozen["limits_and_claims"]
    assert frozen["status"] == "FIRST_REAL_MPTRJ_PREFIX_DIAGNOSTIC_OBSERVED_BOUNDED_ONLY"
    assert r["run_id"] == 37852263493
    assert r["attempt"] == 1 and r["event"] == "workflow_dispatch"
    assert r["head_sha"] == "573fda0c5e5604911416d2746c2d7e7eb23cbbf8"
    assert r["head_branch"] == "main" and r["conclusion"] == "success"
    assert a["archive_path"] == str(archive.relative_to(ROOT))
    assert a["member_path"] == str(receipt.relative_to(ROOT))
    assert archive.stat().st_size == 758 and receipt.stat().st_size == 1292
    assert sha256(archive.read_bytes()).hexdigest() == a["archive_sha256"]
    assert sha256(receipt.read_bytes()).hexdigest() == a["member_sha256"]
    assert a["archive_sha256"] == a["github_api_digest"].removeprefix("sha256:")
    assert a["canonical_receipt_metadata_sha256"] == "180f17fdd406dd0da9820c6bd8c82b5ac71779b3eccc84e5d60f51a55fc0da28"
    validated = validate_mptrj_first_frame_receipt(json.loads(receipt.read_text()), expected_prefix_bytes=262144)
    assert validated["report_metadata_sha256"] == a["canonical_receipt_metadata_sha256"]
    bound = verify_mptrj_diagnostic_zip_binding(
        archive, receipt, expected_artifact_digest=a["github_api_digest"],
    )
    assert bound["artifact_zip_sha256"] == a["archive_sha256"]
    assert bound["receipt_byte_sha256"] == a["member_sha256"]
    assert bound["receipt_metadata_sha256"] == a["canonical_receipt_metadata_sha256"]

    observed = json.loads(receipt.read_text())["observation"]
    assert observed["prefix_sha256"] == o["prefix_sha256"]
    assert observed["first_material_id"] == o["first_material_id"]
    assert observed["first_frame_id"] == o["first_frame_id"]
    structure = observed["first_frame_structure"]
    assert structure["site_count"] == o["site_count"] == 28
    assert structure["reduced_formula"] == o["reduced_formula"] == "Sm2CuAs3O"
    assert structure["energy_fields_present"] == o["energy_fields_present"]
    assert observed["complete_frame_parsed"] is True
    assert limits["github_api_archive_digest_and_local_zip_consistent"] is True
    assert limits["first_frame_receipt_and_archive_member_preserved"] is True
    for key in (
        "original_256k_raw_prefix_preserved",
        "full_original_source_sha256_verified",
        "mace_mpa0_checkpoint_training_membership_attested",
        "model_training_selection_manifest_attested",
        "execute_exposure_audit", "empirical_calibration_use",
        "unseen_generalization_claim", "github_signed_provenance_attested",
    ):
        assert limits[key] is False
    assert bound["github_archive_origin_authenticated"] is False


def test_real_2026_archive_is_strict_single_member_not_full_source():
    import zipfile
    _, archive, receipt = _paths()
    with zipfile.ZipFile(archive) as z:
        assert z.namelist() == ["mptrj-first-frame-observation.json"]
        assert z.read(z.namelist()[0]) == receipt.read_bytes()
    assert archive.stat().st_size < 1024
    assert not any(DIR.glob("*.bin"))


def test_modified_copies_cannot_revalidate_as_observation(tmp_path):
    manifest, archive, receipt = _paths()
    bad_zip = tmp_path / "altered.zip"
    bad_zip.write_bytes(archive.read_bytes()[:-1] + b"X")
    with pytest.raises((MPTrjArtifactZipError, ValueError)):
        verify_mptrj_diagnostic_zip_binding(
            bad_zip, receipt, expected_artifact_digest="sha256:" +
            sha256(archive.read_bytes()).hexdigest(),
        )
    copied_zip = tmp_path / "original.zip"
    shutil.copy2(archive, copied_zip)
    bad_receipt = tmp_path / "altered.json"
    bad_receipt.write_bytes(receipt.read_bytes().replace(b"Sm2CuAs3O", b"Sm2CuAs2O"))
    with pytest.raises(MPTrjArtifactZipError, match="differ"):
        verify_mptrj_diagnostic_zip_binding(
            copied_zip, bad_receipt,
            expected_artifact_digest="sha256:" + sha256(archive.read_bytes()).hexdigest(),
        )
