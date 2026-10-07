from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from scripts.development.hash_remote_file import stream_hash


def test_stream_hash_matches_reference_without_destination() -> None:
    payload = (b"rhombus-training-source-" * 100_000) + b"tail"
    source = io.BytesIO(payload)

    size, md5_hex, sha256_hex = stream_hash(source, chunk_size=97)

    assert size == len(payload)
    assert md5_hex == hashlib.md5(payload).hexdigest()
    assert sha256_hex == hashlib.sha256(payload).hexdigest()


def test_stream_hash_rejects_invalid_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        stream_hash(io.BytesIO(b"x"), chunk_size=0)


def test_hash_only_verifier_has_no_output_file_argument() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts/development/hash_remote_file.py"
    ).read_text(encoding="utf-8")

    assert "REMOTE_FILE_HASHED" in script
    assert "--output" not in script
    assert ".write(" not in script
    assert ".read_bytes()" not in script


def test_salex_hash_request_is_one_shot_and_fail_closed() -> None:
    import json

    root = Path(__file__).resolve().parents[1]
    request = json.loads(
        (root / "data/development/phase3_training_source_hash_request_v1.json")
        .read_text(encoding="utf-8")
    )
    identity = json.loads(
        (root / "data/development/phase3_salex_archive_identity_v1.json")
        .read_text(encoding="utf-8")
    )

    assert request["enabled"] is False
    assert request["dataset_id"] == "sAlex"
    assert request["verification"]["mode"] == "hash-only-stream"
    assert request["verification"]["persist_download"] is False
    assert request["verification"]["expected_size_bytes"] == 8071921954
    assert request["verification"]["expected_md5"] == "8ad69db0c2261541530ae8bc772c5b6d"
    assert request["verification"]["expected_sha256"] == "48eb3664d95331e7fd84bfe1f04f5e741600bffcfb1253334c82dae92cebf1ef"
    assert identity["byte_identity"]["status"] == "VERIFIED"
    assert identity["authorization"]["build_membership_index"] is True
    assert identity["authorization"]["execute_exposure_audit"] is False
