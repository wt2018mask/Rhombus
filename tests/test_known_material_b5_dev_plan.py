"""B5 DEV-only diagnostic planning tests."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from rudeus.science.known_material_b3_split import load_b3_split_freeze
from rudeus.science.known_material_b5_dev_plan import B5DevDiagnosticMember
from scripts.benchmark.render_b5_dev_diagnostic_plan import (
    build_canonical_b5_dev_plan,
)


ROOT = Path("data/benchmarks/known_material")


def test_canonical_b5_dev_plan_contains_only_frozen_dev_members():
    plan = build_canonical_b5_dev_plan()
    freeze = load_b3_split_freeze(ROOT / "b3_split_freeze_v1.json")

    expected_dev = sorted(
        member.benchmark_id
        for member in freeze.members
        if member.split == "DEV"
    )
    expected_held_out = {
        member.benchmark_id
        for member in freeze.members
        if member.split == "HELD_OUT"
    }

    assert [member.material_key for member in plan.members] == expected_dev
    assert len(plan.members) == 3
    assert all(member.split == "DEV" for member in plan.members)
    assert {member.structure_mode for member in plan.members} == {
        "DIRECT",
        "PHASE_SET",
        "ENSEMBLE",
    }

    serialized = json.dumps(plan.to_dict(), sort_keys=True)
    assert all(material_key not in serialized for material_key in expected_held_out)


def test_canonical_b5_dev_plan_acknowledges_public_identity_and_truth():
    plan = build_canonical_b5_dev_plan()

    assert plan.identity_exposure_acknowledged is True
    assert plan.truth_exposure_acknowledged is True
    assert plan.diagnostic_only is True
    assert plan.qualification_evidence_authorized is False
    assert plan.held_out_execution_authorized is False
    assert plan.production_search_authorized is False
    assert all(member.scorable_stages for member in plan.members)


def test_b5_dev_member_rejects_held_out_injection():
    plan = build_canonical_b5_dev_plan()

    with pytest.raises(ValueError, match="DEV only"):
        replace(
            plan.members[0],
            split="HELD_OUT",
        )


def test_b5_dev_plan_rejects_qualification_or_production_authorization():
    plan = build_canonical_b5_dev_plan()

    with pytest.raises(ValueError, match="authorizes no qualification"):
        replace(plan, qualification_evidence_authorized=True)
    with pytest.raises(ValueError, match="authorizes no qualification"):
        replace(plan, held_out_execution_authorized=True)
    with pytest.raises(ValueError, match="authorizes no qualification"):
        replace(plan, production_search_authorized=True)


def test_b5_dev_member_requires_mode_correct_hash_binding():
    plan = build_canonical_b5_dev_plan()
    by_material = {member.material_key: member for member in plan.members}

    cubic = by_material["llzo-cubic-al-stabilized"]
    libh4 = by_material["libh4-phase-transition-pair"]
    lialo2 = by_material["lialo2-gamma"]

    assert cubic.structure_mode == "ENSEMBLE"
    assert libh4.structure_mode == "PHASE_SET"
    assert lialo2.structure_mode == "DIRECT"
    assert all(len(member.structure_hash) == 64 for member in plan.members)
