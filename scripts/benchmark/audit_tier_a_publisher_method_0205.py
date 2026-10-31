#!/usr/bin/env python3
"""Offline source-only public notebook audit. Does not run any model or notebook cell."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from rhombus.benchmark.tier_a_publisher_method_audit import (
    compare_to_symmetric_tier_a_draft, read_notebook_file,
)


def main() -> int:
    p=argparse.ArgumentParser(description="Only static AST audit of LiTraj author notebook")
    p.add_argument("--notebook", required=True, type=Path)
    p.add_argument("--budget-draft", type=Path,
                   help="Optional already-existing non-executable Tier A draft JSON")
    p.add_argument("--output", required=True, type=Path)
    args=p.parse_args()
    audit=read_notebook_file(args.notebook)
    if args.budget_draft is not None:
        if args.budget_draft.is_symlink() or not args.budget_draft.is_file():
            raise ValueError("BUDGET_DRAFT_NOT_REGULAR_FILE")
        if args.budget_draft.stat().st_size > 300_000:
            raise ValueError("BUDGET_DRAFT_TOO_LARGE")
        draft=json.loads(args.budget_draft.read_text(encoding="utf-8"))
        audit["rhombus_symmetric_protocol_comparison"] = compare_to_symmetric_tier_a_draft(audit,draft)
    if args.output.is_symlink() or args.output.is_dir():
        raise ValueError("UNSAFE_AUDIT_OUTPUT")
    if args.output.resolve() == args.notebook.resolve():
        raise ValueError("OUTPUT_OVERLAPS_NOTEBOOK")
    if args.budget_draft is not None and args.output.resolve() == args.budget_draft.resolve():
        raise ValueError("OUTPUT_OVERLAPS_DRAFT")
    # O_EXCL makes the audit append-only rather than rewriting prior receipts.
    content=json.dumps(audit,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n"
    fd=os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            stream.write(content)
    except BaseException:
        try:
            args.output.unlink()
        except OSError:
            pass
        raise
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
