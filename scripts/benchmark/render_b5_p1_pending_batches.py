#!/usr/bin/env python3
import json
from pathlib import Path

import yaml

from rudeus.science.known_material_b5_p0 import materialize_b5_p0_structure
from rudeus.science.known_material_b5_p0_material_semantics import aggregate_b5_p0_materials
from rudeus.science.known_material_b5_p1_batch_materialization import (
    materialize_b5_p1_pending_batches,
)
from rudeus.science.known_material_b5_p1_entry import build_p1_entry_decisions
from rudeus.science.known_material_b5_p1_execution_plan import build_b5_p1_execution_plan
from rudeus.science.known_material_representation_policy import load_representation_evidence_ledger
from rudeus.science.known_material_structure_resolution import load_structure_resolution_manifest
from run_b5_dev_p0 import build_canonical_b5_dev_structure_units, run_canonical_b5_p0


ROOT = Path("data/benchmarks/known_material")
MARGINAL_ONLY_SCOPE = "MARGINAL_OCCUPANCIES_ONLY_SOURCE_DOES_NOT_RESOLVE_CORRELATIONS"


def unsupported_checks_by_material():
    manifest = load_structure_resolution_manifest(ROOT / "structure_resolution_manifest_v1.json")
    evidence = load_representation_evidence_ledger(ROOT / "representation_evidence_ledger_v1.json")
    evidence_by_policy = {entry.policy_id: entry for entry in evidence.entries}
    result = {}
    for spec in manifest.specs:
        if spec.mode != "ENSEMBLE":
            continue
        entry = evidence_by_policy.get(spec.representation_policy_id)
        if entry is not None and entry.payload.get("correlation_scope") == MARGINAL_ONLY_SCOPE:
            result[spec.material_key] = ("neutrality",)
    return result


def main() -> int:
    structure_plan = build_canonical_b5_dev_structure_units(repo_root=Path("."))
    raw = run_canonical_b5_p0(repo_root=Path("."))
    assessments = aggregate_b5_p0_materials(
        raw.observations,
        unsupported_checks_by_material=unsupported_checks_by_material(),
    )
    decisions = build_p1_entry_decisions(assessments)
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    execution_plan = build_b5_p1_execution_plan(
        structure_plan,
        decisions,
        mlip_config=config["mlip"],
    )
    source_by_identity = {
        (unit.material_key, unit.component_label): unit
        for unit in structure_plan.units
    }
    structures = {}
    for unit in execution_plan.units:
        source = source_by_identity[(unit.material_key, unit.component_label)]
        structure = materialize_b5_p0_structure(source, repo_root=Path("."))
        structures[unit.content_hash] = structure.as_dict()

    pending = materialize_b5_p1_pending_batches(
        execution_plan,
        structures_by_execution_unit_hash=structures,
    )
    print(json.dumps({
        "materialization_version": "known-material-b5-p1-batch-materialization-v1",
        "source_execution_plan_hash": execution_plan.content_hash,
        "batch_count": len(pending),
        "batches": [item.to_dict() for item in pending],
        "p1_execution_started": False,
        "qualification_evidence_authorized": False,
        "held_out_execution_authorized": False,
        "production_search_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
