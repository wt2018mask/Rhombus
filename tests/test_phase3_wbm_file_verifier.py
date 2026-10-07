from __future__ import annotations

import hashlib
import io
from pathlib import Path

from scripts.development.verify_wbm_file import stream_copy_and_hash


def test_wbm_stream_hashing_matches_reference_without_reread() -> None:
    payload = (b"rhombus-wbm-streaming-fixture-" * 100_000) + b"tail"
    source = io.BytesIO(payload)
    destination = io.BytesIO()

    size, md5_hex, sha256_hex = stream_copy_and_hash(source, destination)

    assert size == len(payload)
    assert destination.getvalue() == payload
    assert md5_hex == hashlib.md5(payload).hexdigest()
    assert sha256_hex == hashlib.sha256(payload).hexdigest()


def test_wbm_verifier_keeps_fail_closed_markers() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts/development/verify_wbm_file.py"
    source = script.read_text(encoding="utf-8")

    assert "WBM_FILE_VERIFIED" in source
    assert "MD5_MISMATCH" in source
    assert "SIZE_MISMATCH" in source
    assert "ndownloader/files" in source
    assert ".read_bytes()" not in source
