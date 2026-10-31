#!/usr/bin/env python3
"""Create a sealed-target-safe, NON-EXECUTABLE Tier-A selective decision draft.

Reads only an existing non-executable budget contract. No LiTraj ZIP, targets,
MACE models, NEB, inference, scoring, calibration, or compute dispatch.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rhombus.benchmark.tier_a_selective_design import (
    inspect_decision_design,
    make_decision_design,
)
from scripts.benchmark.prepare_tier_a_budget_draft_0204 import load_json_strict

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--budget-draft', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    ns = p.parse_args(argv)
    source = ns.budget_draft.resolve(strict=True)
    out = ns.out_dir.resolve()
    if source == out or out == ROOT or ROOT in out.parents:
        raise ValueError('OUTPUT_MUST_BE_NEW_OUTSIDE_REPOSITORY')
    if ns.out_dir.is_symlink() or out.exists() or not out.parent.is_dir():
        raise ValueError('OUTPUT_MUST_BE_NEW_WITH_EXISTING_PARENT')
    draft = load_json_strict(source, 262_144)
    design = make_decision_design(draft)
    inspection = inspect_decision_design(design, draft)
    if inspection['execution_authorized'] is not False:
        raise AssertionError('UNEXPECTED_EXECUTION_AUTHORIZATION')
    out.mkdir(mode=0o700)
    for name, value in (
        ('tier_a_selective_decision_NON_EXECUTABLE.json', design),
        ('tier_a_selective_design_inspection.json', inspection),
    ):
        with (out / name).open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False)
            f.write('\n')
    print('TIER_A_SELECTIVE_DESIGN_ONLY', 'execution_authorized', False,
          'thresholds_unset', len(inspection['owner_thresholds_missing']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
