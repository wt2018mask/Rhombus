from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_reference_error_source_plan_is_fail_closed() -> None:
    plan = json.loads(
        (ROOT / "data/development/phase3_reference_error_source_plan_v1.json")
        .read_text(encoding="utf-8")
    )

    assert plan["status"] == "SOURCE_CANDIDATE_IDENTIFIED_NOT_ADMITTED"
    source = plan["candidate_sources"][0]
    assert source["source_id"] == "matbench-discovery-wbm"
    assert "MPTrj" in plan["target_model"]["training_lineage"]
    assert "sAlex" in plan["target_model"]["training_lineage"]
    assert any("cannot be assumed" in item for item in source["limitations"])
    assert (
        plan["initial_calibration_scope"]["domain_claim"]
        == "NO_UNSEEN_GENERALIZATION_CLAIM_WITHOUT_EXPOSURE_AUDIT"
    )
    assert any(
        "sealed Rhombus qualification cohort" in item
        for item in plan["rejected_shortcuts"]
    )


def test_source_plan_requires_per_structure_error_distance_pairs() -> None:
    plan = json.loads(
        (ROOT / "data/development/phase3_reference_error_source_plan_v1.json")
        .read_text(encoding="utf-8")
    )

    source = plan["candidate_sources"][0]
    requirements = source["admission_requirements"]
    assert any("pair each prediction error" in item for item in requirements)
    assert any("leave-group-out" in item for item in requirements)
    assert any("dataset version and hashes" in item for item in requirements)
