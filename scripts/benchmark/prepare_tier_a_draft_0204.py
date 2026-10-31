#!/usr/bin/env python3
"""Metadata-only Tier A handoff generator; never unseals energy targets.

Run from Rhombus repository root:
  python -m scripts.benchmark.prepare_tier_a_draft_0204 \\
    --archive /trusted/nebDFT2k.zip --protocol /trusted/tier_a_protocol_candidate.json \\
    --output-dir /tmp/rhombus-0204-tier-a-draft

The output directory must be new, empty, and outside the repository. The script
never writes into repository tracking paths, CURRENT or HANDOFF.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rhombus.benchmark.tier_a_preflight import (
    build_metadata_registry, load_verified_owner_index,
    readiness_blockers, select_train_only_pilot,
)


def write_new(path: Path, payload: dict) -> None:
    # exclusive create: no overwrite of existing evidence, even on repeated run
    with path.open("x", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=True)
        f.write("\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--protocol", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    if Path.cwd().resolve() == args.output_dir.resolve() or Path.cwd().resolve() in args.output_dir.resolve().parents:
        raise ValueError("OUTPUT_MUST_BE_OUTSIDE_REPOSITORY_WORKSPACE")
    if args.output_dir.exists():
        raise ValueError("OUTPUT_DIR_MUST_BE_NEW_AND_EMPTY")
    if not args.archive.is_file() or not args.protocol.is_file():
        raise ValueError("INPUT_MISSING")
    # No source edits. Source protocol is immutable input.
    protocol = json.loads(args.protocol.read_text("utf-8"))
    readiness = readiness_blockers(protocol)
    registry = build_metadata_registry(load_verified_owner_index(args.archive))
    pilot = select_train_only_pilot(registry)
    # mkdir only after validation. Files created with exclusive mode.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_new(args.output_dir / "tier_a_metadata_registry_draft.json", registry)
    write_new(args.output_dir / "tier_a_tiny_train_pilot_draft.json", pilot)
    write_new(args.output_dir / "tier_a_readiness_blockers.json", readiness)
    print("TIER_A_METADATA_ONLY_DRAFT_READY",
          "edges", registry["counts"]["all_edges"],
          "kept", registry["counts"]["retained_edges"],
          "pilot", pilot["selection_sha256"],
          "execution_authorized", False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
