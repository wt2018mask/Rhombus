#!/usr/bin/env python3
"""Emit the canonical B2 known-material coverage audit as JSON."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from rudeus.science.known_material_artifact_curation import (
    load_registry,
    load_retention_index,
)
from rudeus.science.known_material_b2_coverage import (
    build_b2_coverage_audit,
    load_cataloged_truth_bundles,
    load_external_assessment_ledger,
    load_truth_bundle_catalog,
)
from rudeus.science.known_material_failure_control import (
    load_failure_control_plan,
)
from rudeus.science.known_material_representation_policy import (
    load_representation_evidence_ledger,
    load_representation_policy_registry,
)
from rudeus.science.known_material_structure_resolution import (
    load_structure_resolution_manifest,
    resolve_structure_manifest,
)
from rudeus.science.known_material_universe import MaterialUniverseIntake


ROOT = Path("data/benchmarks/known_material")


def main() -> None:
    universe = MaterialUniverseIntake.from_dict(
        json.loads(
            (ROOT / "b2_universe_intake_v1.json").read_text(encoding="utf-8")
        )
    )
    structure_ledger = resolve_structure_manifest(
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
    catalog = load_truth_bundle_catalog(
        ROOT / "truth_bundle_catalog_v1.json"
    )
    audit = build_b2_coverage_audit(
        universe,
        structure_ledger,
        truth_bundles=load_cataloged_truth_bundles(
            catalog,
            repo_root=Path("."),
        ),
        external_assessments=load_external_assessment_ledger(
            ROOT / "b2_external_assessment_v1.json"
        ),
        failure_control_plan=load_failure_control_plan(
            ROOT / "failure_control_plan_v1.json"
        ),
    )
    print(json.dumps(audit.to_dict(), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"B2_COVERAGE_AUDIT_FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
