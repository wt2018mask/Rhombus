"""Offline verification of a staged Phase 3 checkpoint pair.

Host binds the directory and checkpoint ID; no Kaggle API, downloading,
execution or science authorization. Verifies actual bytes and the exact
stage_verified_checkpoint manifest before any future restore.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any
from .shard_contract import _sha
from .checkpoint_staging import MAX_BYTES


def verify_staged_checkpoint(*, trusted_directory: Path, checkpoint_id: str) -> dict[str, Any]:
    if type(trusted_directory) is not Path or trusted_directory.is_symlink():
        raise ValueError("trusted_directory must be a host-bound non-symlink Path")
    if not isinstance(checkpoint_id, str) or not 1 <= len(checkpoint_id) <= 64 or any(
        c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in checkpoint_id
    ):
        raise ValueError("unsafe checkpoint_id")
    directory = trusted_directory.resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("checkpoint directory is missing")
    artifact = directory / (checkpoint_id + ".sqlite")
    manifest_file = directory / (checkpoint_id + ".manifest.json")
    for path in (artifact, manifest_file):
        if path.is_symlink() or not path.is_file():
            raise ValueError("checkpoint pair is missing or symbolic")
    if manifest_file.stat().st_size > 4096 or not 0 < artifact.stat().st_size <= MAX_BYTES:
        raise ValueError("checkpoint exceeds resource budget")
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("invalid checkpoint manifest") from exc
    expected = {
        "schema_version", "checkpoint_id", "artifact_filename",
        "artifact_sha256", "source_sha256_declared", "row_count_declared",
        "artifact_bytes_verified", "external_durability_verified",
        "source_stream_verified", "claim_authorized",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected:
        raise ValueError("unexpected checkpoint manifest fields")
    if manifest["schema_version"] != "rhombus-phase3-checkpoint-staging-v1":
        raise ValueError("checkpoint schema mismatch")
    if manifest["checkpoint_id"] != checkpoint_id or manifest["artifact_filename"] != artifact.name:
        raise ValueError("checkpoint identity mismatch")
    _sha(manifest["artifact_sha256"], "artifact_sha256")
    _sha(manifest["source_sha256_declared"], "source_sha256_declared")
    if type(manifest["row_count_declared"]) is not int or not 1 <= manifest["row_count_declared"] <= 100_000_000:
        raise ValueError("invalid declared row count")
    if (manifest["artifact_bytes_verified"] is not True or
        manifest["external_durability_verified"] is not False or
        manifest["source_stream_verified"] is not False or
        manifest["claim_authorized"] is not False):
        raise ValueError("checkpoint authorization fields must remain fail-closed")
    digest = hashlib.sha256()
    with artifact.open("rb") as handle:
        while data := handle.read(8 * 1024 * 1024):
            digest.update(data)
    if digest.hexdigest() != manifest["artifact_sha256"]:
        raise ValueError("checkpoint bytes SHA256 mismatch")
    return {
        "schema_version": "rhombus-phase3-staged-checkpoint-verification-v1",
        "checkpoint_id": checkpoint_id,
        "artifact_sha256": digest.hexdigest(),
        "artifact_bytes_verified": True,
        "sqlite_integrity_verified": False,
        "source_lineage_verified": False,
        "external_durability_verified": False,
        "execution_authorized": False,
        "scientific_verdict": "UNKNOWN",
        "claim_authorized": False,
    }
