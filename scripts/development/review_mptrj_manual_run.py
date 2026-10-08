"""Review explicitly saved GitHub run/artifact JSON and a local diagnostic receipt.

No network, no writes, no claims of cryptographic authenticity. To establish
live origin, separately compare these inputs against the GitHub API yourself.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rhombus.domain.mptrj_run_metadata import (
    MPTrjRunMetadataError,
    validate_mptrj_manual_run_metadata,
)
from scripts.development.verify_mptrj_probe_receipt import read_and_validate_receipt


MAX_API_JSON_BYTES = 128 * 1024


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise MPTrjRunMetadataError("duplicate JSON key in supplied GitHub API metadata")
        out[key] = value
    return out


def _read_small_json(path: Path) -> object:
    if path.is_symlink() or not path.is_file():
        raise MPTrjRunMetadataError("API snapshot must be a regular non-symlink file")
    if path.stat().st_size > MAX_API_JSON_BYTES:
        raise MPTrjRunMetadataError("API snapshot exceeds the 128KiB bound")
    with path.open("rb") as handle:
        raw = handle.read(MAX_API_JSON_BYTES + 1)
    if len(raw) > MAX_API_JSON_BYTES:
        raise MPTrjRunMetadataError("API snapshot exceeds the 128KiB read bound")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-json", type=Path, required=True)
    parser.add_argument("--artifacts-json", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--expected-head-sha", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = read_and_validate_receipt(args.receipt, expected_bytes=262144)
        review = validate_mptrj_manual_run_metadata(
            _read_small_json(args.run_json),
            _read_small_json(args.artifacts_json),
            expected_head_sha=args.expected_head_sha,
        )
    except (ValueError, OSError, UnicodeError, TypeError) as exc:
        print(f"MPTRJ_MANUAL_RUN_REVIEW_REJECTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("MPTRJ_MANUAL_RUN_API_METADATA_CONSISTENCY_PASS_UNTRUSTED_INPUT")
    print(f"RUN_ID={review['run_id']}; RUN_ATTEMPT={review['run_attempt']}")
    print(f"ARTIFACT_ID={review['artifact_id']}; HEAD_SHA={review['head_sha']}")
    print(f"LOCAL_RECEIPT_METADATA_SHA256={receipt['report_metadata_sha256']}")
    print("GITHUB_API_ORIGIN_NOT_AUTHENTICATED; RECEIPT_NOT_BOUND_TO_ARTIFACT")
    print("FULL_SOURCE_NOT_ATTESTED; MACE_MPA0_TRAINING_MEMBERSHIP_UNKNOWN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
