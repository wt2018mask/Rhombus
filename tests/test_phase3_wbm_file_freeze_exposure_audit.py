from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhombus.domain import (
    FrozenRemoteFile,
    MaterialExposureRecord,
    summarize_exposure_audit,
    verify_frozen_bytes,
)

ROOT = Path(__file__).resolve().parents[1]


def test_wbm_file_freeze_requires_download_hash_verification() -> None:
    data = json.loads(
        (ROOT / "data/development/phase3_wbm_file_freeze_v1.json")
        .read_text(encoding="utf-8")
    )
    assert data["status"] == "REMOTE_IDENTITIES_FROZEN_LOCAL_SHA256_PENDING_DOWNLOAD"
    assert data["audit_policy"]["download_must_verify_md5"] is True
    assert data["audit_policy"]["download_must_record_sha256"] is True
    assert data["authorization"]["empirical_calibration_use"] is False
    assert data["authorization"]["unseen_generalization_claim"] is False


def test_verify_frozen_bytes_checks_registry_md5_and_returns_sha256() -> None:
    payload = b"rhombus-wbm-test"
    import hashlib

    spec = FrozenRemoteFile(
        file_id="fixture",
        url="https://example.invalid/file",
        relative_path="fixture.bin",
        expected_md5=hashlib.md5(payload).hexdigest(),
        expected_size=len(payload),
    )
    md5_hex, sha256_hex = verify_frozen_bytes(payload, spec)
    assert md5_hex == hashlib.md5(payload).hexdigest()
    assert sha256_hex == hashlib.sha256(payload).hexdigest()

    with pytest.raises(ValueError, match="MD5 mismatch"):
        verify_frozen_bytes(payload + b"x", spec)


def test_exposure_audit_is_fail_closed_for_missing_basis_and_overlap() -> None:
    rows = (
        MaterialExposureRecord("a", False, False, False, ("audit:1",)),
        MaterialExposureRecord("b", True, False, False, ("audit:2",)),
        MaterialExposureRecord("c", False, True, False, ("audit:3",)),
        MaterialExposureRecord("d", False, False, True, ("audit:4",)),
        MaterialExposureRecord("e", False, False, False, ()),
    )
    summary = summarize_exposure_audit(rows)

    assert summary.material_count == 5
    assert summary.unseen_generalization_eligible_count == 1
    assert summary.exact_match_count == 1
    assert summary.near_duplicate_count == 1
    assert summary.prototype_overlap_count == 1
    assert summary.unresolved_count == 1
