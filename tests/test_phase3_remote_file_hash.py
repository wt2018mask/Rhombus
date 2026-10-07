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
