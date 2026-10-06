"""Replacement strong-blind qualification-cohort repair tests."""
from dataclasses import replace
from pathlib import Path

import pytest

from rudeus.science.known_material_b3_split import load_b3_split_freeze
from rudeus.science.known_material_b4_ingress import VISIBLE_FIELDS
from rudeus.science.known_material_qualification_cohort import (
    QUALIFICATION_COHORT_VERSION,
    REQUIRED_SEALED_FIELDS,
    SEALED_UNTIL,
    load_qualification_cohort_repair_plan,
)


ROOT = Path("data/benchmarks/known_material")
PLAN_PATH = ROOT / "qualification_cohort_repair_plan_v1.json"


def _plan():
    return load_qualification_cohort_repair_plan(PLAN_PATH)


def test_v2_repair_plan_binds_contaminated_v1_without_reusing_held_out():
    plan = _plan()
    v1_freeze = load_b3_split_freeze(ROOT / "b3_split_freeze_v1.json")

    assert plan.qualification_cohort_version == QUALIFICATION_COHORT_VERSION
    assert plan.contaminated_v1_split_freeze_hash == v1_freeze.content_hash
    assert plan.minimum_held_out_per_role == {
        "POSITIVE": 1,
        "NEGATIVE": 1,
        "BORDERLINE": 1,
    }
    assert plan.execution_visible_fields == VISIBLE_FIELDS
    assert plan.sealed_fields == REQUIRED_SEALED_FIELDS
    assert plan.sealed_until == SEALED_UNTIL

    assert plan.v1_held_out_qualification_reuse_authorized is False
    assert plan.v1_dev_diagnostic_reuse_authorized is True
    assert plan.held_out_execution_authorized is False
    assert plan.production_search_authorized is False


def test_public_repair_plan_contains_no_v1_member_or_truth_identity():
    raw = PLAN_PATH.read_text(encoding="utf-8")
    v1_freeze = load_b3_split_freeze(ROOT / "b3_split_freeze_v1.json")

    assert all(member.benchmark_id not in raw for member in v1_freeze.members)
    assert all(member.truth_bundle_hash not in raw for member in v1_freeze.members)


def test_repair_plan_fails_closed_on_public_or_execution_authorization():
    plan = _plan()

    with pytest.raises(ValueError, match="cannot expose"):
        replace(plan, repository_member_identity_authorized=True)
    with pytest.raises(ValueError, match="cannot expose"):
        replace(plan, repository_truth_binding_authorized=True)
    with pytest.raises(ValueError, match="cannot expose"):
        replace(plan, repository_structure_identity_binding_authorized=True)
    with pytest.raises(ValueError, match="cannot expose"):
        replace(plan, held_out_execution_authorized=True)
    with pytest.raises(ValueError, match="cannot expose"):
        replace(plan, v1_held_out_qualification_reuse_authorized=True)


def test_repair_plan_requires_nonzero_role_quota_and_b0_visible_schema():
    plan = _plan()

    with pytest.raises(ValueError, match="at least one"):
        replace(
            plan,
            minimum_held_out_per_role={
                "POSITIVE": 1,
                "NEGATIVE": 1,
                "BORDERLINE": 0,
            },
        )
    with pytest.raises(ValueError, match="B0 visible schema"):
        replace(
            plan,
            execution_visible_fields=(
                "benchmark_id",
                "split",
                "benchmark_protocol_hash",
            ),
        )
