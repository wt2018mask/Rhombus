"""Adversarial release binary verification: bytes, not publisher digest claims."""
import hashlib
import json
from pathlib import Path

import pytest

from rhombus.domain.mpa0_release_binary_observation import (
    ASSET_ID, ASSET_SIZE, DOWNLOAD_URL, MAX_OBSERVABLE_BYTES, PUBLIC_SHA256,
    SCHEMA, _hash_file_full, observe_mpa0_official_release_file, main,
)


def test_exact_fixture_full_file_hash_includes_every_byte(tmp_path):
    payload = (b"binary-for-hashing" * 140000) + b"LAST_B!"
    path = tmp_path / "model"
    path.write_bytes(payload)
    size, sha = _hash_file_full(
        path, expected_size=len(payload),
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )
    assert size == len(payload) and sha == hashlib.sha256(payload).hexdigest()
    raw = bytearray(payload)
    raw[-1] ^= 1
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="SHA256"):
        _hash_file_full(
            path, expected_size=len(payload),
            expected_sha256=hashlib.sha256(payload).hexdigest())


def test_truncation_and_extra_byte_fail_even_if_digest_argument_is_forged(tmp_path):
    path = tmp_path / "model"
    raw = b"abcdef"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="size mismatch"):
        _hash_file_full(path, expected_size=7, expected_sha256="0"*64)
    with pytest.raises(ValueError, match="size mismatch"):
        _hash_file_full(path, expected_size=5, expected_sha256="0"*64)


def test_official_interface_cannot_promote_tiny_fixture(tmp_path):
    path = tmp_path / "model"
    path.write_bytes(b"synthetic-test-only")
    with pytest.raises(ValueError, match="size mismatch"):
        observe_mpa0_official_release_file(path)
    assert ASSET_SIZE == 79_462_305
    assert ASSET_ID == 213937064
    assert DOWNLOAD_URL.endswith("/mace_mpa_0/mace-mpa-0-medium.model")
    assert len(PUBLIC_SHA256) == 64 and SCHEMA.endswith("0140-v1")


def test_invalid_checksum_byte_budget_or_bool_size_rejected(tmp_path):
    path = tmp_path / "model"
    path.write_bytes(b"xx")
    for kwargs in [
        {"expected_size": True, "expected_sha256": hashlib.sha256(b"xx").hexdigest()},
        {"expected_size": MAX_OBSERVABLE_BYTES+1, "expected_sha256": "a"*64},
        {"expected_size": 2, "expected_sha256": "a"*63},
        {"expected_size": 2, "expected_sha256": "Z"*64},
    ]:
        with pytest.raises(ValueError, match="expected digest or byte budget"):
            _hash_file_full(path, **kwargs)


def test_symlink_and_non_regular_input_denied(tmp_path):
    p = tmp_path / "actual"
    p.write_bytes(b"abc")
    symlink = tmp_path / "symbolic"
    symlink.symlink_to(p)
    with pytest.raises(ValueError, match="symlink"):
        _hash_file_full(
            symlink, expected_size=3,
            expected_sha256=hashlib.sha256(b"abc").hexdigest())
    with pytest.raises(ValueError, match="regular file"):
        _hash_file_full(
            tmp_path, expected_size=3,
            expected_sha256=hashlib.sha256(b"abc").hexdigest())


def test_cli_cannot_override_publisher_digest_size_or_source(tmp_path):
    m = tmp_path / "test.model"
    m.write_bytes(b"forged")
    with pytest.raises(SystemExit):
        main(["--model-binary", str(m), "--output-dir", str(tmp_path / "report")])
    assert not (tmp_path / "report").exists()


def test_provenance_receipt_contract_without_real_model_has_no_science_go():
    # The public function can only produce a real report after the genuine
    # ~80 MB whole-file SHA256 agrees with the separately recorded constant.
    from inspect import getsource
    method = getsource(observe_mpa0_official_release_file)
    assert "_hash_file_full" in method
    assert '"scientific_release_authorized": False' in method
    assert '"checkpoint_selected_MPTrj_frames_attested": False' in method
    assert '"checkpoint_selected_sAlex_frames_attested": False' in method
    assert '"authenticated_independent_scientific_auditor": False' in method
