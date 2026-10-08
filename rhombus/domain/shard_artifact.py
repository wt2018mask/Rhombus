"""Local, host-bound verification of completed Phase 3 membership SQLite artifacts.

No remote IO, no execution/resume/dispatch, and no claim of source-stream validity.
Do not use on live, WAL-backed or untrusted paths supplied by an AI model.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from .shard_contract import _sha

MAX_SQLITE_BYTES = 2 * 1024 * 1024 * 1024


def verify_membership_shard_file(
    *,
    trusted_path: Path,
    expected_sha256: str,
    expected_source_sha256: str,
    expected_row_count: int,
) -> dict[str, Any]:
    """Verify an already finalized host-selected membership DB against a receipt.

    A valid artifact still does NOT attest to the frozen sAlex source stream,
    shard completeness, scientific correctness or unseen generalization.
    """
    expected_sha256 = _sha(expected_sha256, "expected_sha256")
    expected_source_sha256 = _sha(expected_source_sha256, "expected_source_sha256")
    if type(expected_row_count) is not int or not 1 <= expected_row_count <= 100_000_000:
        raise ValueError("invalid expected_row_count")
    if type(trusted_path) is not Path:
        raise ValueError("trusted_path must be host-provisioned pathlib.Path")
    if trusted_path.is_symlink():
        raise ValueError("symlink artifact paths are not accepted")
    path = trusted_path.resolve(strict=True)
    if not path.is_file() or path.is_symlink():
        raise ValueError("expected an existing finalized regular file")
    if Path(str(path) + "-wal").exists() or Path(str(path) + "-shm").exists():
        raise ValueError("live SQLite WAL/SHM present; finalize a consistent snapshot first")
    stat = path.stat()
    if not 0 < stat.st_size <= MAX_SQLITE_BYTES:
        raise ValueError("SQLite artifact exceeds resource budget")

    def digest() -> str:
        h = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                h.update(chunk)
        return h.hexdigest()

    if digest() != expected_sha256:
        raise ValueError("SQLite artifact SHA256 does not match receipt")

    # Immutable read-only connection prevents SQLite from creating journal files.
    # Only trusted local host software may select the path.
    uri = path.as_uri() + "?mode=ro&immutable=1"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=1)
        try:
            connection.execute("PRAGMA query_only=ON")
            check = connection.execute("PRAGMA integrity_check").fetchone()
            if check != ("ok",):
                raise ValueError("SQLite integrity check failed")
            required = {"dataset_id", "record_id", "source_locator", "composition_key",
                        "site_count", "structure_fingerprint_sha256", "prototype_group"}
            observed_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(membership)")}
            if not required <= observed_columns:
                raise ValueError("SQLite membership schema mismatch")
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
            if metadata.get("dataset_id") != "sAlex":
                raise ValueError("dataset identity mismatch")
            if metadata.get("source_file_sha256") != expected_source_sha256:
                raise ValueError("source identity mismatch")
            count = connection.execute("SELECT COUNT(*) FROM membership").fetchone()[0]
            if count != expected_row_count:
                raise ValueError("membership row count mismatch")
            if metadata.get("row_count") != str(expected_row_count):
                raise ValueError("metadata row count mismatch")
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise ValueError("invalid or unreadable membership SQLite artifact") from exc

    # Detect in-place mutation during the SQLite verification window.
    if path.stat().st_size != stat.st_size or digest() != expected_sha256:
        raise ValueError("SQLite artifact changed during verification")
    return {
        "schema_version": "rhombus-phase3-membership-shard-file-verification-v1",
        "artifact_sha256": expected_sha256,
        "source_sha256_declared_in_artifact": expected_source_sha256,
        "membership_row_count": expected_row_count,
        "artifact_bytes_verified": True,
        "sqlite_integrity_verified": True,
        "source_stream_verified": False,
        "shard_coverage_verified": False,
        "scientific_verdict": "UNKNOWN",
        "claim_authorized": False,
        "limitations": [
            "HOST_SELECTED_FINALIZED_FILE_ONLY",
            "ARTIFACT_DIGEST_NOT_SOURCE_STREAM_ATTESTATION",
            "ROW_COUNT_NOT_COMPLETE_SHARD_COVERAGE",
            "NO_SCIENTIFIC_PASS",
        ],
    }


__all__ = ["verify_membership_shard_file"]
