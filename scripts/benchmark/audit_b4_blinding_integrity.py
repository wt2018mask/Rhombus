#!/usr/bin/env python3
"""Emit the canonical B4 blinding-integrity audit as JSON."""
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
from rudeus.science.known_material_b4_blinding_integrity import (
    audit_b4_blinding_integrity,
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


def main() -> None:
    freeze = load_b3_split_freeze(ROOT / "b3_split_freeze_v1.json")
    catalog = load_truth_bundle_catalog(ROOT / "truth_bundle_catalog_v1.json")
    bundles = load_cataloged_truth_bundles(catalog, repo_root=Path("."))
    ledger = resolve_structure_manifest(
        load_structure_resolution_manifest(
            ROOT / "structure_resolution_manifest_v1.json"
        ),
        load_registry(ROOT / "artifact_registry_v1.json"),
        load_retention_index(ROOT / "artifact_retention_index_v1.json"),
        policy_registry=load_representation_policy_registry(
            ROOT / "representation_policy_registry_v1.json"
        ),
        policy_evidence_ledger=load_representation_evidence_ledger(
            ROOT / "representation_evidence_ledger_v1.json"
        ),
    )
    audit = audit_b4_blinding_integrity(freeze, bundles, ledger)
    print(json.dumps(audit.to_dict(), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"B4_BLINDING_INTEGRITY_AUDIT_FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
