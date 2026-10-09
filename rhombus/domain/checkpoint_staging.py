"""Atomic, local-only staging of already finalized Phase 3 shard artifacts.

The caller (trusted host) supplies the source and output directory. This does
not upload to durable external storage or make a live Kaggle run recoverable.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from .shard_contract import _sha

MAX_BYTES = 2 * 1024 * 1024 * 1024


def stage_verified_checkpoint(
    *, finalized_source: Path, trusted_directory: Path, checkpoint_id: str,
    expected_sha256: str, source_sha256: str, row_count: int,
) -> dict[str, Any]:
    """Atomically stage bytes and an identity-bound manifest; never overwrite.

    Caller must separately check SQLite integrity, record coverage, source
    streaming lineage and external persistence. This is an output staging
    primitive, not a crash-safe remote checkpoint or scientific attestation.
    """
    expected_sha256 = _sha(expected_sha256, "expected_sha256")
    source_sha256 = _sha(source_sha256, "source_sha256")
    if type(row_count) is not int or not 1 <= row_count <= 100_000_000:
        raise ValueError("row_count is invalid")
    if not isinstance(checkpoint_id, str) or not 1 <= len(checkpoint_id) <= 64 or any(
        c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in checkpoint_id
    ):
        raise ValueError("unsafe checkpoint_id")
    if not isinstance(finalized_source, Path) or not isinstance(trusted_directory, Path):
        raise ValueError("trusted paths must be pathlib.Path")
    if finalized_source.is_symlink() or trusted_directory.is_symlink():
        raise ValueError("symlink paths are not accepted")
    source = finalized_source.resolve(strict=True)
    directory = trusted_directory.resolve(strict=True)
    if not source.is_file() or not directory.is_dir():
        raise ValueError("source and output directory must already exist")
    if Path(str(source) + "-wal").exists() or Path(str(source) + "-shm").exists():
        raise ValueError("SQLite source is not finalized")
    size = source.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise ValueError("source file exceeds staging limits")
    artifact = directory / (checkpoint_id + ".sqlite")
    manifest_path = directory / (checkpoint_id + ".manifest.json")
    if artifact.exists() or manifest_path.exists():
        raise FileExistsError("checkpoint already staged")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".rhombus-checkpoint-", suffix=".tmp",
                                         dir=directory, delete=False) as target:
            tmp_path = Path(target.name)
            digest = hashlib.sha256()
            with source.open("rb") as inp:
                while chunk := inp.read(8 * 1024 * 1024):
                    digest.update(chunk)
                    target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        if digest.hexdigest() != expected_sha256 or tmp_path.stat().st_size != size:
            raise ValueError("source bytes changed or hash mismatch")
        # Hard-link creation with exclusivity avoids overwriting existing files.
        os.link(tmp_path, artifact, follow_symlinks=False)
        tmp_path.unlink()
        tmp_path = None
        manifest = {
            "schema_version": "rhombus-phase3-checkpoint-staging-v1",
            "checkpoint_id": checkpoint_id,
            "artifact_filename": artifact.name,
            "artifact_sha256": expected_sha256,
            "source_sha256_declared": source_sha256,
            "row_count_declared": row_count,
            "artifact_bytes_verified": True,
            "external_durability_verified": False,
            "source_stream_verified": False,
            "claim_authorized": False,
        }
        raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
        fd = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Directory fsync best effort on platforms that support it.
        if hasattr(os, "O_DIRECTORY"):
            try:
                dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            except OSError:
                pass
        return manifest
    except Exception:
        # Never erase a successful concurrent artifact: only remove temp bytes.
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


__all__ = ["stage_verified_checkpoint"]
