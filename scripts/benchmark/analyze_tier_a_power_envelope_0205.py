#!/usr/bin/env python3
"""Metadata-only Tier A statistical sensitivity CLI. No target/model execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rhombus.benchmark.tier_a_power_envelope import metadata_only_power_envelope

MAX_REGISTRY_BYTES = 3_000_000


def _no_duplicate_fields(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("DUPLICATE_JSON_FIELD")
        d[k] = v
    return d


def _nonfinite(s):
    raise ValueError("NONFINITE_JSON_VALUE")


def run(*, registry_file: Path, output: Path, risk_target: float,
        confidence: float) -> dict:
    registry_file, output = Path(registry_file), Path(output)
    if registry_file.is_symlink() or not registry_file.is_file():
        raise ValueError("REGISTRY_MUST_BE_LOCAL_REGULAR_FILE")
    if output.exists() or output.is_symlink() or output.resolve() == registry_file.resolve():
        raise ValueError("OUTPUT_MUST_BE_NEW_AND_DISTINCT")
    with registry_file.open("rb") as f:
        raw = f.read(MAX_REGISTRY_BYTES + 1)
    if not 0 < len(raw) <= MAX_REGISTRY_BYTES:
        raise ValueError("REGISTRY_TOO_LARGE_OR_EMPTY")
    try:
        registry = json.loads(raw, object_pairs_hook=_no_duplicate_fields,
                              parse_constant=_nonfinite)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("REGISTRY_JSON_INVALID") from exc
    result = metadata_only_power_envelope(registry, risk_target=risk_target,
                                          confidence=confidence)
    with output.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, sort_keys=True, indent=2,
                  allow_nan=False)
        f.write("\n")
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="Best-case IID group-risk feasibility sensitivity (non-scoring)")
    p.add_argument("--registry", required=True, type=Path)
    p.add_argument("--risk-target", required=True, type=float)
    p.add_argument("--confidence", required=True, type=float)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    report = run(registry_file=args.registry, output=args.output,
                 risk_target=args.risk_target, confidence=args.confidence)
    print(json.dumps({"status": "HYPOTHETICAL_NOT_QUALIFIED",
                      "test_groups": report["retained_chemsys_candidate"]["test"]["retained_chemsys_groups"],
                      "owner_preregistration_required": True,
                      "output_file_created": True}, sort_keys=True))


if __name__ == "__main__":
    main()
