#!/usr/bin/env python3
"""Audit all known-material structure-resolution cases from canonical data."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

from rudeus.science.known_material_artifact_curation import (
    load_registry,
    load_retention_index,
)
from rudeus.science.known_material_representation_policy import (
    load_representation_evidence_ledger,
    load_representation_policy_registry,
)
from rudeus.science.known_material_structure_resolution import (
    load_structure_resolution_manifest,
    resolve_structure_manifest,
)


DATA_ROOT = Path("data/benchmarks/known_material")


def main() -> None:
    ledger = resolve_structure_manifest(
        load_structure_resolution_manifest(
            DATA_ROOT / "structure_resolution_manifest_v1.json"
        ),
        load_registry(DATA_ROOT / "artifact_registry_v1.json"),
        load_retention_index(DATA_ROOT / "artifact_retention_index_v1.json"),
        policy_registry=load_representation_policy_registry(
            DATA_ROOT / "representation_policy_registry_v1.json"
        ),
        policy_evidence_ledger=load_representation_evidence_ledger(
            DATA_ROOT / "representation_evidence_ledger_v1.json"
        ),
    )
    counts = Counter(case.status for case in ledger.cases)
    payload = {
        "ledger_version": ledger.ledger_version,
        "case_count": len(ledger.cases),
        "status_counts": dict(sorted(counts.items())),
        "cases": [
            {
                "resolution_key": case.resolution_key,
                "material_key": case.material_key,
                "mode": case.mode,
                "status": case.status,
                "representation_policy_id": case.representation_policy_id,
                "requested_artifact_keys": list(case.requested_artifact_keys),
                "retained_artifact_keys": list(case.retained_artifact_keys),
                "missing_artifact_keys": list(case.missing_artifact_keys),
                "unresolved_requirements": list(case.unresolved_requirements),
                "scientific_blockers": list(case.scientific_blockers),
            }
            for case in ledger.cases
        ],
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"STRUCTURE_RESOLUTION_AUDIT_FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
