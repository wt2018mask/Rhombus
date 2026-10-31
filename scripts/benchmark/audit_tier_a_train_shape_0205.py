#!/usr/bin/env python3
"""OFFLINE only: four TRAIN initial XYZ frame/species counts, never energy."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rhombus.benchmark.tier_a_train_shape_only import audit_owner_train_shape_only


def _load_json(path: Path) -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024:
        raise ValueError("INVALID_SMALL_INPUT_JSON")
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if type(obj) is not dict:
        raise ValueError("EXPECTED_JSON_OBJECT")
    return obj


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Non-executing TRAIN initial XYZ shape audit")
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--draft", type=Path, required=True)
    p.add_argument("--input-binding-receipt", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    if args.output.is_symlink() or args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("OUTPUT_ALREADY_EXISTS_OR_INVALID_PARENT")
    if args.output.resolve() in {args.archive.resolve(),args.draft.resolve(),
                                 args.input_binding_receipt.resolve()}:
        raise ValueError("OUTPUT_INPUT_COLLISION")
    report = audit_owner_train_shape_only(
        archive=args.archive, draft=_load_json(args.draft),
        input_binding_receipt=_load_json(args.input_binding_receipt))
    with args.output.open("x", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=True, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
