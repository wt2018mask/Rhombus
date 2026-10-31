#!/usr/bin/env python3
"""Read-only owner archive input-byte identity tool (never launches science)."""
from __future__ import annotations

import argparse
from pathlib import Path

from rhombus.benchmark.tier_a_input_pin import pin_train_initial_xyz_bytes
from scripts.benchmark.prepare_tier_a_budget_draft_0204 import load_json_strict


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hash four TRAIN initial XYZ files, no energy parsing")
    parser.add_argument("--owner-zip", required=True, type=Path)
    parser.add_argument("--budget-draft", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    draft = load_json_strict(args.budget_draft, 1024 * 1024)
    updated, receipt = pin_train_initial_xyz_bytes(draft, args.owner_zip)
    if args.out_dir.exists():
        raise ValueError("OUTPUT_MUST_BE_NEW")
    args.out_dir.mkdir(parents=True, exist_ok=False)
    from json import dumps
    for name, payload in (("tier_a_equal_budget_input_pinned_DRAFT_NOT_AUTHORIZED.json", updated),
                          ("tier_a_four_init_xyz_byte_receipt.json", receipt)):
        (args.out_dir / name).write_text(dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("INITIAL_XYZ_RAW_BYTES_PINNED; SCIENCE_NOT_EXECUTED; RUN_NOT_AUTHORIZED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
