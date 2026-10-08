"""Offline, bounded-memory verification of the canonical MPTrj Figshare source.

Does NOT download MPTrj, parse its 12 GB JSON, attest model training lineage,
build a membership index, execute a WBM audit, or authorize unseen claims.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

from scripts.development.hash_remote_file import stream_hash

ROOT = Path(__file__).resolve().parents[2]
FROZEN_SOURCE = ROOT / "data/development/phase3_mptrj_figshare_metadata_v1.json"
EXISTING_RESOLUTION = ROOT / "data/development/phase3_training_snapshot_resolution_v1.json"
FIGSHARE_ARTICLE_ID = 23713842
FIGSHARE_VERSION = 2
FIGSHARE_FILE_ID = 41619375
FIGSHARE_FILENAME = "MPtrj_2022.9_full.json"
FIGSHARE_SIZE = 12_188_168_685
FIGSHARE_MD5 = "50ead5f27f9a4f6beb7564c4188f1e9f"


class SourceEvidenceError(ValueError):
    """Fail-closed identity or local file preflight."""


def canonical_source():
    """Read two checked-in sources and reject drift from official Figshare identity."""
    metadata = json.loads(FROZEN_SOURCE.read_text(encoding="utf-8"))
    resolution = json.loads(EXISTING_RESOLUTION.read_text(encoding="utf-8"))
    source = metadata.get("canonical_source")
    legacy = resolution.get("mptrj", {}).get("canonical_source", {})
    if not isinstance(source, dict):
        raise SourceEvidenceError("canonical MPTrj metadata record is unavailable")
    required = {
        "article_id": FIGSHARE_ARTICLE_ID,
        "article_version": FIGSHARE_VERSION,
        "file_id": FIGSHARE_FILE_ID,
        "file_name": FIGSHARE_FILENAME,
        "size": FIGSHARE_SIZE,
        "md5": FIGSHARE_MD5,
    }
    if any(source.get(key) != value for key, value in required.items()):
        raise SourceEvidenceError("Figshare metadata differs from frozen source identity")
    if any(legacy.get(key) != value for key, value in required.items()):
        raise SourceEvidenceError("training snapshot source differs from frozen Figshare identity")
    if metadata.get("authorization", {}).get("unseen_generalization_claim") is not False:
        raise SourceEvidenceError("unseen-generalization gate must remain closed")
    if metadata.get("authorization", {}).get("model_training_bytes_attested") is not False:
        raise SourceEvidenceError("training representation cannot be attested by metadata")
    return source


def verify_existing_source(
    source_file: Path,
    *,
    expected_size: int,
    expected_md5: str,
    expected_sha256: str | None = None,
    chunk_size: int = 8 * 1024 * 1024,
) -> dict:
    """Hash a local file once; never fetch/copy or trust a partial hash.

    Separate declared file identity from training-lineage attestation.
    The SHA256 is computed locally, NOT a separately published authoritative
    SHA256 unless a distinct expected SHA256 was provided and matched.
    """
    if chunk_size <= 0 or expected_size <= 0:
        raise SourceEvidenceError("chunk size and expected size must be positive")
    if len(expected_md5) != 32:
        raise SourceEvidenceError("invalid frozen MD5")
    try:
        int(expected_md5, 16)
    except ValueError as exc:
        raise SourceEvidenceError("invalid frozen MD5") from exc
    if expected_sha256 is not None:
        if len(expected_sha256) != 64:
            raise SourceEvidenceError("invalid expected SHA256")
        try:
            int(expected_sha256, 16)
        except ValueError as exc:
            raise SourceEvidenceError("invalid expected SHA256") from exc
    if source_file.name != FIGSHARE_FILENAME or source_file.is_symlink():
        raise SourceEvidenceError("original canonical filename required; symlinks refused")
    if not source_file.is_file():
        raise SourceEvidenceError("local original MPTrj source file not found")
    before = source_file.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size != expected_size:
        raise SourceEvidenceError("source size/type mismatch before reading")
    with source_file.open("rb") as reader:
        descriptor = os.fstat(reader.fileno())
        if (descriptor.st_dev, descriptor.st_ino, descriptor.st_size) != (
            before.st_dev, before.st_ino, before.st_size
        ):
            raise SourceEvidenceError("source changed before reading")
        size, md5, sha256 = stream_hash(reader, chunk_size=chunk_size)
        after_handle = os.fstat(reader.fileno())
    after = source_file.stat()
    for observed in (after_handle, after):
        if (
            observed.st_dev, observed.st_ino, observed.st_size,
            observed.st_mtime_ns
        ) != (
            before.st_dev, before.st_ino, before.st_size,
            before.st_mtime_ns
        ):
            raise SourceEvidenceError("source mutated during verification")
    if size != expected_size or md5 != expected_md5.lower():
        raise SourceEvidenceError("source size/official Figshare MD5 mismatch")
    if expected_sha256 is not None and sha256 != expected_sha256.lower():
        raise SourceEvidenceError("source SHA256 differs from pinned hash")
    return {
        "schema_version": "rhombus-mptrj-local-source-identity-v1",
        "canonical_figshare_source": {
            "article_id": FIGSHARE_ARTICLE_ID,
            "article_version": FIGSHARE_VERSION,
            "file_id": FIGSHARE_FILE_ID,
            "filename": FIGSHARE_FILENAME,
            "source_size_bytes": size,
            "figshare_declared_md5": expected_md5.lower(),
        },
        "local_verification": {
            "whole_file_stream_consumed": True,
            "observed_size_bytes": size,
            "computed_md5": md5,
            "computed_sha256": sha256,
            "figshare_size_md5_match": True,
            "independent_sha256_match": expected_sha256 is not None,
            "structure_rows_parsed": False,
        },
        "training_lineage": {
            "model_id": "medium-mpa-0",
            "exact_training_byte_representation": "UNATTESTED",
            "matbench_converted_extxyz_is_canonical": False,
        },
        "authorization": {
            "execute_exposure_audit": False,
            "empirical_calibration_use": False,
            "unseen_generalization_claim": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path,
                        help="Local exact Figshare JSON already present; never downloaded by this tool")
    parser.add_argument("--report", type=Path,
                        help="Optional new JSON report; refuse overwrite")
    args = parser.parse_args(argv)
    try:
        source = canonical_source()
        result = verify_existing_source(
            args.source,
            expected_size=source["size"],
            expected_md5=source["md5"],
        )
        if args.report:
            if args.report.is_symlink():
                raise SourceEvidenceError("report symlink refused")
            # Exclusive creation: never mutate existing provenance evidence.
            with args.report.open("x", encoding="utf-8") as writer:
                json.dump(result, writer, indent=2)
                writer.write("\n")
        print("MPTRJ_OFFLINE_SOURCE_SIZE_MD5_PASS", result["local_verification"]["computed_sha256"])
        print("TRAINING_BYTES_UNATTESTED; EXPOSURE_AUDIT_NOT_AUTHORIZED")
        return 0
    except (SourceEvidenceError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"MPTRJ_SOURCE_FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
