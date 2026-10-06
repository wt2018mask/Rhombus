#!/usr/bin/env python3
import json
from pathlib import Path

from rudeus.science.known_material_b5_p0_material_semantics import (
    aggregate_b5_p0_materials,
)
from rudeus.science.known_material_representation_policy import (
    load_representation_evidence_ledger,
)
from rudeus.science.known_material_structure_resolution import (
    load_structure_resolution_manifest,
)
from run_b5_dev_p0 import run_canonical_b5_p0


ROOT = Path("data/benchmarks/known_material")
MARGINAL_ONLY_SCOPE = "MARGINAL_OCCUPANCIES_ONLY_SOURCE_DOES_NOT_RESOLVE_CORRELATIONS"


def _unsupported_checks_by_material():
    manifest = load_structure_resolution_manifest(
        ROOT / "structure_resolution_manifest_v1.json"
    )
    evidence = load_representation_evidence_ledger(
        ROOT / "representation_evidence_ledger_v1.json"
    )
    evidence_by_policy = {entry.policy_id: entry for entry in evidence.entries}
    result = {}
    for spec in manifest.specs:
        if spec.mode != "ENSEMBLE":
            continue
        entry = evidence_by_policy.get(spec.representation_policy_id)
        if entry is None:
            continue
        if entry.payload.get("correlation_scope") == MARGINAL_ONLY_SCOPE:
            result[spec.material_key] = ("neutrality",)
    return result


def main() -> int:
    report = run_canonical_b5_p0(repo_root=Path("."))
    assessments = aggregate_b5_p0_materials(
        report.observations,
        unsupported_checks_by_material=_unsupported_checks_by_material(),
    )
    print(json.dumps({
        "semantics_version": "known-material-b5-p0-material-semantics-v1",
        "diagnostic_only": True,
        "material_verdicts": [item.to_dict() for item in assessments],
        "qualification_evidence_authorized": False,
        "production_search_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
