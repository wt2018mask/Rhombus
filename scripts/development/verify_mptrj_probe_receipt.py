"""Validate a locally supplied MPTrj prefix diagnostic without data retrieval.

A valid metadata schema does NOT authenticate the run, full source, or model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rhombus.domain.mptrj_probe_receipt import (
    MPTrjProbeReceiptError,
    validate_mptrj_first_frame_receipt,
)

MAX_REPORT_BYTES = 16 * 1024


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    record: dict = {}
    for key, value in pairs:
        if key in record:
            raise MPTrjProbeReceiptError("duplicate JSON field in diagnostic report")
        record[key] = value
    return record


def read_and_validate_receipt(path: Path, expected_bytes: int = 262144) -> dict:
    if path.is_symlink() or not path.is_file():
        raise MPTrjProbeReceiptError("receipt must be an existing regular non-symlink file")
    if path.stat().st_size > MAX_REPORT_BYTES:
        raise MPTrjProbeReceiptError("receipt is larger than diagnostic metadata budget")
    with path.open("rb") as input_file:
        raw = input_file.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        raise MPTrjProbeReceiptError("receipt exceeds metadata byte budget")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    return validate_mptrj_first_frame_receipt(data, expected_prefix_bytes=expected_bytes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True, help="existing small receipt JSON only")
    parser.add_argument("--expected-prefix-bytes", type=int, default=262144)
    args = parser.parse_args(argv)
    try:
        result = read_and_validate_receipt(args.receipt, args.expected_prefix_bytes)
    except (ValueError, OSError, TypeError, UnicodeError) as exc:
        print(f"MPTRJ_DIAGNOSTIC_REPORT_REJECTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("MPTRJ_DIAGNOSTIC_REPORT_SCHEMA_PASS")
    print(f"REPORT_METADATA_SHA256={result['report_metadata_sha256']}")
    print("FULL_SOURCE_NOT_ATTESTED; GITHUB_RUN_ORIGIN_NOT_ATTESTED; MODEL_TRAINING_LINEAGE_UNKNOWN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
