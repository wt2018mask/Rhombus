#!/usr/bin/env python3
"""Offline, read-only inputs, no model loading or scientific execution.

Usage:
 python -m scripts.benchmark.inspect_tier_a_model_neb_0204 \\
   --draft pinned_DRAFT_NOT_AUTHORIZED.json --binding-receipt pin_receipt.json \\
   --output review.json

Optional --small-model / --medium-model only compute direct file byte SHA256;
none is ever deserialized. No automatic download, shell dispatch, or network IO.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import json

from rhombus.benchmark.tier_a_model_neb_preflight import (
    inspect_offline_run_review, propose_shared_neb_numeric_candidate,
)

MAX_JSON_BYTES = 512 * 1024


def load_strict_json(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("UNSAFE_OR_OVERSIZED_JSON_INPUT")

    def unique_pairs(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError("DUPLICATE_JSON_KEY")
            d[k] = v
        return d

    def reject_constant(value):
        raise ValueError("NONFINITE_JSON_NUMBER")

    d = json.loads(path.read_text(encoding="utf-8"),
                   object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    if type(d) is not dict:
        raise ValueError("JSON_OBJECT_REQUIRED")
    return d


def main(args=None):
    parser = argparse.ArgumentParser(description="Rhombus 0204 offline model/NEB review; NO execution")
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--binding-receipt", type=Path, required=True)
    parser.add_argument("--small-model", type=Path)
    parser.add_argument("--medium-model", type=Path)
    parser.add_argument("--runtime-declaration", type=Path)
    parser.add_argument("--candidate-neb-settings", action="store_true",
                        help="write separate non-authorizing proposed numeric settings")
    parser.add_argument("--output", type=Path, required=True)
    ns = parser.parse_args(args)
    draft = load_strict_json(ns.draft)
    receipt = load_strict_json(ns.binding_receipt)
    models = {}
    if ns.small_model:
        models["MACE_MP_0_SMALL_PUBLISHER_EXAMPLE"] = ns.small_model
    if ns.medium_model:
        models["MACE_MPA_0_MEDIUM_RHOMBUS"] = ns.medium_model
    runtime = load_strict_json(ns.runtime_declaration) if ns.runtime_declaration else None
    review = inspect_offline_run_review(draft=draft, input_binding_receipt=receipt,
                                        model_files=models, runtime_declaration=runtime)
    # Prevent existing output modification and output path collisions with inputs.
    blocked = {p.resolve() for p in (ns.draft, ns.binding_receipt,
                                      *(models.values()),
                                      *((ns.runtime_declaration,) if ns.runtime_declaration else ()))}
    if ns.output.resolve() in blocked or ns.output.is_symlink():
        raise ValueError("OUTPUT_OVERLAPS_SOURCE")
    # Validate both destinations before writing either output. No overwrite.
    suggested_path = None
    if ns.candidate_neb_settings:
        candidate = propose_shared_neb_numeric_candidate(draft)
        suggested_path = ns.output.with_name(ns.output.stem + "_SUGGESTED_NEB_NOT_FROZEN.json")
    for destination in (ns.output, *((suggested_path,) if suggested_path else ())):
        if destination.resolve() in blocked or destination.is_symlink():
            raise ValueError("OUTPUT_OVERLAPS_SOURCE")
        if destination.exists():
            raise FileExistsError(f"OUTPUT_EXISTS: {destination.name}")
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    with ns.output.open("x", encoding="utf-8") as f:
        json.dump(review, f, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        f.write("\n")
    if suggested_path is not None:
        with suggested_path.open("x", encoding="utf-8") as f:
            json.dump(candidate, f, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
            f.write("\n")
    print(json.dumps({"status": review["operational_status"],
                      "execution_authorized": False,
                      "blockers": review["preflight_blockers"],
                      "model_evaluation": "NOT_RUN"}, sort_keys=True))
    return review


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"OFFLINE_TIER_A_REVIEW_REJECTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
