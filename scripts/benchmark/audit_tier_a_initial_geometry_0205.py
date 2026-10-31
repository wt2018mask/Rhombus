"""Offline-only, output-new, geometry audit of four pinned TRAIN initial XYZ.

No DFT relaxed/test files, no energy/force label values, no model execution.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from rhombus.benchmark.tier_a_initial_geometry import audit_pinned_train_initial_geometry
from scripts.benchmark.prepare_tier_a_budget_draft_0204 import load_json_strict, write_new


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-zip", required=True, type=Path)
    parser.add_argument("--pinned-draft", required=True, type=Path)
    parser.add_argument("--input-receipt", required=True, type=Path)
    parser.add_argument("--out-file", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.out_file.resolve()
    if output.exists() or output.is_symlink() or any(
            output == p.resolve() for p in
            (args.owner_zip, args.pinned_draft, args.input_receipt)):
        raise ValueError("OUTPUT_MUST_BE_NEW_AND_NOT_AN_INPUT")
    draft = load_json_strict(args.pinned_draft, 256 * 1024)
    receipt = load_json_strict(args.input_receipt, 256 * 1024)
    report = audit_pinned_train_initial_geometry(
        draft=draft, receipt=receipt, owner_zip=args.owner_zip)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_new(output, report)
    print("FOUR_TRAIN_INITIAL_GEOMETRY_ONLY_NO_DFT_TARGETS_NO_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
