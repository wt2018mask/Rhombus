#!/usr/bin/env python3
"""Run canonical raw P0 observations for the v1 B5 DEV structure units."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from rudeus.science.known_material_artifact_curation import (
    load_registry,
    load_retention_index,
)
from rudeus.science.known_material_b2_coverage import (
    load_cataloged_truth_bundles,
    load_truth_bundle_catalog,
)
from rudeus.science.known_material_b3_split import load_b3_split_freeze
from rudeus.science.known_material_b5_dev_plan import build_b5_dev_diagnostic_plan
from rudeus.science.known_material_b5_dev_units import (
    build_b5_dev_structure_unit_plan,
)
from rudeus.science.known_material_b5_p0 import (
    require_clean_b5_p0_execution,
    run_b5_p0_raw_execution,
)
from rudeus.science.known_material_representation_policy import (
    load_representation_evidence_ledger,
    load_representation_policy_registry,
)
from rudeus.science.known_material_structure_resolution import (
    load_structure_resolution_manifest,
    resolve_structure_manifest,
)


DATA_RELATIVE_ROOT = Path("data/benchmarks/known_material")


def build_canonical_b5_dev_structure_units(*, repo_root: Path):
    data_root = repo_root / DATA_RELATIVE_ROOT
    registry = load_registry(data_root / "artifact_registry_v1.json")
    retention = load_retention_index(data_root / "artifact_retention_index_v1.json")
    ledger = resolve_structure_manifest(
        load_structure_resolution_manifest(
            data_root / "structure_resolution_manifest_v1.json"
        ),
        registry,
        retention,
        policy_registry=load_representation_policy_registry(
            data_root / "representation_policy_registry_v1.json"
        ),
        policy_evidence_ledger=load_representation_evidence_ledger(
            data_root / "representation_evidence_ledger_v1.json"
        ),
    )
    freeze = load_b3_split_freeze(data_root / "b3_split_freeze_v1.json")
    catalog = load_truth_bundle_catalog(data_root / "truth_bundle_catalog_v1.json")
    bundles = load_cataloged_truth_bundles(catalog, repo_root=repo_root)
    dev_plan = build_b5_dev_diagnostic_plan(
        freeze,
        truth_bundles=bundles,
        structure_ledger=ledger,
    )
    return build_b5_dev_structure_unit_plan(
        dev_plan,
        repo_root=repo_root,
        structure_ledger=ledger,
        artifact_registry=registry,
        retention_index=retention,
    )


def run_canonical_b5_p0(*, repo_root: Path):
    return run_b5_p0_raw_execution(
        build_canonical_b5_dev_structure_units(repo_root=repo_root),
        repo_root=repo_root,
    )


def main() -> None:
    report = run_canonical_b5_p0(repo_root=Path("."))
    print(json.dumps(report.to_dict(), sort_keys=True))
    require_clean_b5_p0_execution(report)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"B5_P0_RAW_EXECUTION_FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
