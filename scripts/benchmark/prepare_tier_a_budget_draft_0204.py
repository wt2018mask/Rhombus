#!/usr/bin/env python3
"""Prepare NON-EXECUTABLE 0204 cost-telemetry draft from sealed metadata receipts.

No ZIP access and no scientific model imports. Does not prepare or dispatch runs.

python -m scripts.benchmark.prepare_tier_a_budget_draft_0204 \
  --registry /trusted/tier_a_metadata_registry_draft.json \
  --pilot /trusted/tier_a_tiny_train_pilot_draft.json \
  --protocol /trusted/tier_a_protocol_candidate.json \
  --out-dir /tmp/new-0204-budget-draft
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rhombus.benchmark.tier_a_budget_contract import (
    inspect_budget_draft, make_execution_disabled_budget_draft,
)

ROOT = Path(__file__).resolve().parents[2]


def load_json_strict(path: Path, maximum: int) -> dict:
    if not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("INPUT_MISSING_OR_TOO_LARGE")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def reject_constant(token):
        raise ValueError("NONFINITE_JSON_NUMBER")

    return json.loads(path.read_text("utf-8"), object_pairs_hook=unique,
                      parse_constant=reject_constant)


def write_new(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("OUTPUT_MUST_BE_OUTSIDE_REPOSITORY")
    if out.exists() or not out.parent.is_dir():
        raise ValueError("OUTPUT_MUST_BE_NEW_WITH_EXISTING_PARENT")
    registry = load_json_strict(args.registry, 2_000_000)
    pilot = load_json_strict(args.pilot, 32_768)
    protocol = load_json_strict(args.protocol, 262_144)
    draft = make_execution_disabled_budget_draft(registry, pilot, protocol)
    diagnostic = inspect_budget_draft(draft)
    out.mkdir(mode=0o700)
    write_new(out / "tier_a_equal_budget_execution_disabled_draft.json", draft)
    write_new(out / "tier_a_budget_readiness_diagnostic.json", diagnostic)
    print("TIER_A_EQUAL_BUDGET_DRAFT_ONLY", "pairs", diagnostic["paired_rows_required"],
          "blockers", len(diagnostic["blockers"]), "execution_authorized", False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
