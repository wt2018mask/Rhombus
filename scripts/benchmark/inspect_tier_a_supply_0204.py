#!/usr/bin/env python3
"""Offline model supply-chain metadata+byte inspection only; NEVER computes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rhombus.benchmark.tier_a_checkpoint_supply import (
    MEDIUM_ID, SMALL_ID, inspect_supply, make_small_digest_candidate,
)
from scripts.benchmark.inspect_tier_a_model_neb_0204 import load_strict_json


def _dump_new(path: Path, record: dict) -> None:
    if path.is_symlink() or path.exists():
        raise FileExistsError("OUTPUT_ALREADY_EXISTS_OR_IS_SYMLINK")
    # Exclusive creation ensures repeated invocations cannot change evidence.
    with path.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


def main(args=None):
    parser = argparse.ArgumentParser(description="Tier A MACE supply audit (offline; never runs MACE)")
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--small-model", type=Path)
    parser.add_argument("--medium-model", type=Path)
    parser.add_argument("--candidate-draft", type=Path,
                        help="only if small checkpoint bytes have been verified; NOT execution approval")
    parser.add_argument("--report", type=Path, required=True)
    ns = parser.parse_args(args)
    if ns.candidate_draft is not None and ns.small_model is None:
        parser.error("--candidate-draft requires --small-model")
    files = {}
    if ns.small_model is not None:
        files[SMALL_ID] = ns.small_model
    if ns.medium_model is not None:
        files[MEDIUM_ID] = ns.medium_model
    inputs = {ns.draft.resolve(), *(f.resolve() for f in files.values())}
    outputs = [ns.report, *((ns.candidate_draft,) if ns.candidate_draft else ())]
    if any(p.is_symlink() or p.resolve() in inputs or p.exists() for p in outputs):
        raise ValueError("OUTPUT_OVERLAPS_INPUT_OR_ALREADY_EXISTS")
    if len({p.resolve() for p in outputs}) != len(outputs):
        raise ValueError("OUTPUTS_COLLIDE")
    draft = load_strict_json(ns.draft)
    report = inspect_supply(draft, provided_files=files)
    candidate = None
    if ns.candidate_draft is not None:
        candidate = make_small_digest_candidate(draft, report, small_model_file=ns.small_model)
    # Only create report after all scientific checks succeeded.
    for dest in outputs:
        dest.parent.mkdir(parents=True, exist_ok=True)
    _dump_new(ns.report, report)
    if candidate is not None:
        _dump_new(ns.candidate_draft, candidate)
    print(json.dumps({"status": "OFFLINE_SUPPLY_REVIEW_ONLY", "execution_authorized": False,
                      "source_hash_is_publisher_attested": False,
                      "small_model_file_verified": (
                          report["model_arms"][SMALL_ID]["local_observation"] is not None),
                      "models_run": 0}, sort_keys=True))
    return report


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"TIER_A_SUPPLY_REVIEW_REJECTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
