#!/usr/bin/env python3
"""Validate an externally sealed v2 qualification cohort without leaking members."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rudeus.science.known_material_b3_split import load_b3_split_freeze
from rudeus.science.known_material_qualification_cohort import (
    load_qualification_cohort_repair_plan,
)
from rudeus.science.known_material_qualification_manifest import (
    load_external_sealed_qualification_manifest,
    validate_sealed_qualification_manifest,
)


DATA_RELATIVE_ROOT = Path("data/benchmarks/known_material")


def validate_external_manifest(
    *,
    repo_root: Path,
    manifest_path: Path,
):
    repo_root = repo_root.resolve()
    data_root = repo_root / DATA_RELATIVE_ROOT
    repair_plan = load_qualification_cohort_repair_plan(
        data_root / "qualification_cohort_repair_plan_v1.json"
    )
    v1_freeze = load_b3_split_freeze(
        data_root / "b3_split_freeze_v1.json"
    )
    manifest = load_external_sealed_qualification_manifest(
        manifest_path,
        repo_root=repo_root,
    )
    return validate_sealed_qualification_manifest(
        manifest,
        repair_plan=repair_plan,
        contaminated_v1_freeze=v1_freeze,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate external v2 qualification-cohort sealed state and emit only "
            "a public-safe aggregate summary."
        )
    )
    parser.add_argument(
        "sealed_manifest",
        type=Path,
        help="external sealed manifest; this file must remain outside the repository",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Rhombus repository root",
    )
    args = parser.parse_args()

    validation = validate_external_manifest(
        repo_root=args.repo_root,
        manifest_path=args.sealed_manifest,
    )
    print(json.dumps(validation.to_dict(), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"SEALED_QUALIFICATION_MANIFEST_VALIDATION_FAILED: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
