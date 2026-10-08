"""Small, offline, deterministic source-identity tests; no MPTrj download."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.development import verify_mptrj_source as verifier


@pytest.fixture
def original(tmp_path):
    data = b'{"mp-1":{"task-1":{"structure":{"@module":"pymatgen.core.structure"}}}}'
    path = tmp_path / verifier.FIGSHARE_FILENAME
    path.write_bytes(data)
    return path, data, hashlib.md5(data).hexdigest(), hashlib.sha256(data).hexdigest()


def test_metadata_is_bound_to_existing_frozen_snapshot():
    source = verifier.canonical_source()
    assert source["file_id"] == 41619375
    assert source["size"] == 12188168685
    assert source["md5"] == "50ead5f27f9a4f6beb7564c4188f1e9f"
    metadata = json.loads(verifier.FROZEN_SOURCE.read_text(encoding="utf-8"))
    assert metadata["content_description"]["structure_count_declared"] == 1580395
    assert metadata["training_lineage"]["mptrj_byte_representation_attested"] is False
    assert metadata["authorization"]["execute_exposure_audit"] is False


def test_full_bounded_stream_verifies_and_closes_claims(original):
    path, data, md5, sha256 = original
    result = verifier.verify_existing_source(
        path, expected_size=len(data), expected_md5=md5,
        expected_sha256=sha256, chunk_size=3,
    )
    observed = result["local_verification"]
    assert observed["observed_size_bytes"] == len(data)
    assert observed["computed_sha256"] == sha256
    assert observed["independent_sha256_match"] is True
    assert observed["structure_rows_parsed"] is False
    assert result["training_lineage"]["exact_training_byte_representation"] == "UNATTESTED"
    assert result["authorization"]["execute_exposure_audit"] is False
    assert result["authorization"]["unseen_generalization_claim"] is False


def test_self_computed_sha_does_not_claim_independent_sha(original):
    path, data, md5, _ = original
    result = verifier.verify_existing_source(
        path, expected_size=len(data), expected_md5=md5,
    )
    assert result["local_verification"]["independent_sha256_match"] is False


def test_short_source_rejected_before_stream(original):
    path, data, md5, _ = original
    with pytest.raises(verifier.SourceEvidenceError, match="size/type"):
        verifier.verify_existing_source(
            path, expected_size=len(data) + 1, expected_md5=md5,
        )


def test_corrupted_full_source_rejected_without_report(original, tmp_path, monkeypatch):
    path, data, md5, _ = original
    path.write_bytes(data[:-1] + b"X")
    with pytest.raises(verifier.SourceEvidenceError, match="MD5 mismatch"):
        verifier.verify_existing_source(path, expected_size=len(data), expected_md5=md5)
    report = tmp_path / "report.json"
    monkeypatch.setattr(verifier, "canonical_source", lambda: {
        "size": len(data), "md5": md5
    })
    assert verifier.main(["--source", str(path), "--report", str(report)]) == 1
    assert not report.exists()


def test_wrong_sha_or_filename_rejected(original, tmp_path):
    path, data, md5, _ = original
    with pytest.raises(verifier.SourceEvidenceError, match="SHA256 differs"):
        verifier.verify_existing_source(
            path, expected_size=len(data), expected_md5=md5,
            expected_sha256="a" * 64,
        )
    renamed = tmp_path / "converted_mp_trj.extxyz"
    renamed.write_bytes(data)
    with pytest.raises(verifier.SourceEvidenceError, match="canonical filename"):
        verifier.verify_existing_source(
            renamed, expected_size=len(data), expected_md5=md5,
        )


def test_symlink_does_not_count_as_canonical_original(original, tmp_path):
    path, data, md5, _ = original
    alias = tmp_path / "alias" / verifier.FIGSHARE_FILENAME
    alias.parent.mkdir()
    alias.symlink_to(path)
    with pytest.raises(verifier.SourceEvidenceError, match="symlinks refused"):
        verifier.verify_existing_source(alias, expected_size=len(data), expected_md5=md5)


def test_report_created_only_after_success_and_never_overwritten(original, tmp_path, monkeypatch):
    path, data, md5, sha256 = original
    monkeypatch.setattr(verifier, "canonical_source", lambda: {
        "size": len(data), "md5": md5
    })
    report = tmp_path / "source-evidence.json"
    assert verifier.main(["--source", str(path), "--report", str(report)]) == 0
    saved = json.loads(report.read_text(encoding="utf-8"))
    assert saved["local_verification"]["computed_sha256"] == sha256
    assert saved["authorization"]["unseen_generalization_claim"] is False
    assert verifier.main(["--source", str(path), "--report", str(report)]) == 1
    assert json.loads(report.read_text(encoding="utf-8")) == saved


def test_cli_does_not_download_or_permit_full_audit():
    script = (verifier.ROOT / "scripts/development/verify_mptrj_source.py").read_text()
    assert "urlopen(" not in script
    assert "urlretrieve(" not in script
    assert "requests.get(" not in script
    assert '"execute_exposure_audit": False' in script
    assert '"unseen_generalization_claim": False' in script
