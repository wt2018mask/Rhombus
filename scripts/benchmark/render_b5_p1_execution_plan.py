#!/usr/bin/env python3
import json
from pathlib import Path

import yaml

from rudeus.science.known_material_b5_p0_material_semantics import (
    aggregate_b5_p0_materials,
)
from rudeus.science.known_material_b5_p1_entry import build_p1_entry_decisions
from rudeus.science.known_material_b5_p1_execution_plan import (
    build_b5_p1_execution_plan,
)
from rudeus.science.known_material_representation_policy import (
    load_representation_evidence_ledger,
)
from rudeus.science.known_material_structure_resolution import (
    load_structure_resolution_manifest,
)
from run_b5_dev_p0 import (
    build_canonical_b5_dev_structure_units,
    run_canonical_b5_p0,
)


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
    plan = build_b5_p1_execution_plan(
        structure_plan,
        decisions,
        mlip_config=config["mlip"],
    )
    print(json.dumps(plan.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
