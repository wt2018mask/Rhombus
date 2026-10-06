#!/usr/bin/env python3
"""Render canonical representation-aware B5 DEV structure units."""
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
from rudeus.science.known_material_representation_policy import (
    load_representation_evidence_ledger,
    load_representation_policy_registry,
)
from rudeus.science.known_material_structure_resolution import (
    load_structure_resolution_manifest,
    resolve_structure_manifest,
)
ROOT = Path("data/benchmarks/known_material")


def build_canonical_b5_dev_structure_units():
    registry = load_registry(ROOT / "artifact_registry_v1.json")
    retention = load_retention_index(ROOT / "artifact_retention_index_v1.json")
    ledger = resolve_structure_manifest(
        load_structure_resolution_manifest(
            ROOT / "structure_resolution_manifest_v1.json"
        ),
        registry,
        retention,
        policy_registry=load_representation_policy_registry(
            ROOT / "representation_policy_registry_v1.json"
        ),
        policy_evidence_ledger=load_representation_evidence_ledger(
            ROOT / "representation_evidence_ledger_v1.json"
        ),
    )
    freeze = load_b3_split_freeze(ROOT / "b3_split_freeze_v1.json")
    catalog = load_truth_bundle_catalog(ROOT / "truth_bundle_catalog_v1.json")
    bundles = load_cataloged_truth_bundles(catalog, repo_root=Path("."))
    dev_plan = build_b5_dev_diagnostic_plan(
        freeze,
        truth_bundles=bundles,
        structure_ledger=ledger,
    )
    return build_b5_dev_structure_unit_plan(
        dev_plan,
        repo_root=Path("."),
        structure_ledger=ledger,
        artifact_registry=registry,
        retention_index=retention,
    )


def main() -> None:
    print(
        json.dumps(
            build_canonical_b5_dev_structure_units().to_dict(),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"B5_DEV_STRUCTURE_UNIT_PLAN_FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
