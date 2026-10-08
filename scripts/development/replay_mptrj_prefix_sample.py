"""Offline independent replay of an operator-captured bounded MPTrj prefix.

Does not make network requests or authenticate the source, GitHub, or MACE.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import hmac
import json
from pathlib import Path
import sys

from rhombus.domain.mptrj_probe_receipt import validate_mptrj_first_frame_receipt
from scripts.development.probe_mptrj_source_prefix import (
    DEFAULT_PREFIX_BYTES, inspect_first_complete_frame_prefix,
)
from scripts.development.verify_mptrj_probe_receipt import (
    MAX_REPORT_BYTES, _unique_pairs,
)


class MPTrjPrefixReplayError(ValueError):
    """Invalid, oversized or inconsistent locally supplied MPTrj sample."""


def _read_regular_bounded(path: Path, *, exact_bytes: int | None, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise MPTrjPrefixReplayError("input must be a regular non-symlink file")
    if not 1 <= path.stat().st_size <= maximum:
        raise MPTrjPrefixReplayError("file exceeds bounded replay size")
    with path.open("rb") as handle:
        raw = handle.read(maximum + 1)
    if not 1 <= len(raw) <= maximum or (exact_bytes is not None and len(raw) != exact_bytes):
        raise MPTrjPrefixReplayError("captured prefix length does not match frozen 256KiB budget")
    return raw


def replay_mptrj_prefix_sample(*, sample: Path, receipt: Path) -> dict:
    """Hash and reparse raw locally supplied source bytes, fail closed on any mismatch."""
    prefix = _read_regular_bounded(sample, exact_bytes=DEFAULT_PREFIX_BYTES, maximum=DEFAULT_PREFIX_BYTES)
    report_raw = _read_regular_bounded(receipt, exact_bytes=None, maximum=MAX_REPORT_BYTES)
    document = json.loads(report_raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    validated = validate_mptrj_first_frame_receipt(
        document, expected_prefix_bytes=DEFAULT_PREFIX_BYTES,
    )
    digest = sha256(prefix).hexdigest()
    observed = document["observation"]
    if not hmac.compare_digest(digest, observed["prefix_sha256"]):
        raise MPTrjPrefixReplayError("sample prefix SHA256 does not match the receipt")
    actual = inspect_first_complete_frame_prefix(prefix)
    expected = observed["first_frame_structure"]
    if actual != expected:
        raise MPTrjPrefixReplayError("reparsed structure/energy fields differ from receipt")
    if (actual["material_id"] != observed["first_material_id"]
            or actual["frame_id"] != observed["first_frame_id"]):
        raise MPTrjPrefixReplayError("reparsed first frame identifiers disagree with receipt")
    return {
        "schema_version": "rhombus-phase3-mptrj-local-prefix-replay-v1",
        "status": "LOCAL_PREFIX_BYTES_AND_FIRST_FRAME_CONCORDANT_ONLY",
        "sample_bytes": len(prefix),
        "sample_sha256": digest,
        "receipt_metadata_sha256": validated["report_metadata_sha256"],
        "first_material_id": actual["material_id"],
        "first_frame_id": actual["frame_id"],
        "site_count": actual["site_count"],
        "full_source_sha256_verified": False,
        "github_origin_authenticated": False,
        "mace_mpa0_training_frames_attested": False,
        "execute_exposure_audit": False,
        "empirical_calibration_use": False,
        "unseen_generalization_claim": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = replay_mptrj_prefix_sample(sample=args.sample, receipt=args.receipt)
    except (ValueError, OSError, UnicodeError, TypeError) as exc:
        print(f"MPTRJ_LOCAL_PREFIX_REPLAY_REJECTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("MPTRJ_LOCAL_PREFIX_REPLAY_FIRST_FRAME_CONCORDANCE_PASS")
    print(f"SAMPLE_SHA256={result['sample_sha256']}")
    print(f"FIRST_MATERIAL_ID={result['first_material_id']}; FRAME_ID={result['first_frame_id']}")
    print("FULL_SOURCE_NOT_HASHED; MACE_MPA0_TRAINING_SELECTION_UNATTESTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
