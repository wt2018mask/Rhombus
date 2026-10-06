"""Failure-control contract tests."""
from dataclasses import replace
from pathlib import Path

import pytest

from rudeus.science.known_material_failure_control import (
    FAILURE_CONTROL_PLAN_VERSION,
    FailureControlCase,
    FailureControlCaseState,
    FailureControlExpectedBehavior,
    FailureControlInputOrigin,
    FailureControlKind,
    FailureControlPlan,
    FailureControlRequirement,
    executable_failure_control_kinds,
    load_failure_control_plan,
    missing_executable_failure_control_kinds,
)


DATA = Path("data/benchmarks/known_material/failure_control_plan_v1.json")


def requirement(
    kind=FailureControlKind.INVALID_SCIENTIFIC_INPUT.value,
    behavior=FailureControlExpectedBehavior.REJECT_INPUT.value,
    stages=("P0",),
):
    return FailureControlRequirement(
        control_kind=kind,
        target_stages=stages,
        expected_behavior=behavior,
        falsification_events=("wrong_behavior",),
        rationale=("test requirement",),
    )


def case(
    *,
    kind=FailureControlKind.INVALID_SCIENTIFIC_INPUT.value,
    behavior=FailureControlExpectedBehavior.REJECT_INPUT.value,
    state=FailureControlCaseState.PLANNED.value,
    stages=("P0",),
    provenance_hash=None,
    evidence_refs=(),
    executor_id=None,
    executor_config=None,
):
    return FailureControlCase(
        control_id="control-1",
        control_kind=kind,
        state=state,
        input_origin=FailureControlInputOrigin.SYNTHETIC_INVALID.value,
        target_stages=stages,
        expected_behavior=behavior,
        input_ref="fixture:control-1",
        executor_id=executor_id,
        executor_config=executor_config or {},
        provenance_hash=provenance_hash,
        evidence_refs=evidence_refs,
        rationale=("test control",),
    )


def test_canonical_plan_binds_all_three_executable_controls():
    plan = load_failure_control_plan(DATA)
    assert plan.plan_version == FAILURE_CONTROL_PLAN_VERSION
    assert len(plan.cases) == 3
    assert {item.control_kind for item in plan.requirements} == {
        FailureControlKind.INVALID_SCIENTIFIC_INPUT.value,
        FailureControlKind.REPRESENTATION_UNSUPPORTED.value,
        FailureControlKind.MODEL_DOMAIN_UNSUPPORTED.value,
    }
    assert executable_failure_control_kinds(plan) == (
        FailureControlKind.INVALID_SCIENTIFIC_INPUT.value,
        FailureControlKind.MODEL_DOMAIN_UNSUPPORTED.value,
        FailureControlKind.REPRESENTATION_UNSUPPORTED.value,
    )
    assert missing_executable_failure_control_kinds(plan) == ()
    by_id = {item.control_id: item for item in plan.cases}
    assert by_id["fc:model-domain:medium-mpa-0-v1"].state == (
        FailureControlCaseState.EXECUTABLE.value
    )
    assert by_id["fc:model-domain:medium-mpa-0-v1"].executor_id == (
        "model-domain-support-v1"
    )
    assert by_id["fc:model-domain:medium-mpa-0-v1"].provenance_hash == (
        "7d7958f318707c59d616dd34c332618bec52329ae2549fa737e2e6cf5b0e8fb7"
    )
    assert by_id["fc:p0:synthetic-overlap-v1"].executor_id == "p0-static-filter-v1"
    assert (
        by_id["fc:representation:synthetic-missing-strategy-v1"].executor_id
        == "representation-policy-v1"
    )
    assert plan.b3_split_authorized is False


def test_failure_control_never_turns_infrastructure_failure_into_success():
    with pytest.raises(ValueError, match="infrastructure failure"):
        replace(
            case(),
            infrastructure_failure_counts_as_control_success=True,
        )


def test_failure_control_never_claims_physical_material_failure():
    with pytest.raises(ValueError, match="material failure"):
        replace(
            case(),
            scientific_material_failure_allowed=True,
        )


def test_evidence_bound_control_requires_provenance_and_refs():
    with pytest.raises(ValueError, match="provenance hash"):
        replace(
            case(),
            state=FailureControlCaseState.EVIDENCE_BOUND.value,
        )

    with pytest.raises(ValueError, match="evidence refs"):
        replace(
            case(),
            state=FailureControlCaseState.EVIDENCE_BOUND.value,
            provenance_hash="1" * 64,
        )


def test_executable_control_counts_only_after_evidence_binding():
    req = requirement()
    planned = case()
    executable = replace(
        planned,
        state=FailureControlCaseState.EXECUTABLE.value,
        provenance_hash="1" * 64,
        evidence_refs=("artifact:failure-control",),
        executor_id="fixture-executor-v1",
        executor_config={"fixture_path": "fixture.json"},
    )

    planned_plan = FailureControlPlan(
        plan_version=FAILURE_CONTROL_PLAN_VERSION,
        requirements=(req,),
        cases=(planned,),
    )
    executable_plan = replace(planned_plan, cases=(executable,))

    assert executable_failure_control_kinds(planned_plan) == ()
    assert executable_failure_control_kinds(executable_plan) == (
        FailureControlKind.INVALID_SCIENTIFIC_INPUT.value,
    )



def test_executable_control_requires_executor_identity():
    with pytest.raises(ValueError, match="executor id and config"):
        replace(
            case(),
            state=FailureControlCaseState.EXECUTABLE.value,
            provenance_hash="1" * 64,
            evidence_refs=("artifact:failure-control",),
        )


def test_case_cannot_change_required_behavior():
    req = requirement()
    mismatched = case(
        behavior=FailureControlExpectedBehavior.BLOCK_BEFORE_EXECUTION.value
    )
    with pytest.raises(ValueError, match="behavior differs"):
        FailureControlPlan(
            plan_version=FAILURE_CONTROL_PLAN_VERSION,
            requirements=(req,),
            cases=(mismatched,),
        )


def test_case_cannot_target_undeclared_stage():
    req = requirement(stages=("P0",))
    expanded = case(stages=("P0", "P1"))
    with pytest.raises(ValueError, match="outside its requirement"):
        FailureControlPlan(
            plan_version=FAILURE_CONTROL_PLAN_VERSION,
            requirements=(req,),
            cases=(expanded,),
        )


def test_plan_requires_unique_control_kind_requirements():
    req = requirement()
    with pytest.raises(ValueError, match="unique control-kind"):
        FailureControlPlan(
            plan_version=FAILURE_CONTROL_PLAN_VERSION,
            requirements=(req, req),
            cases=(),
        )


def test_model_domain_requirement_explicitly_uses_unknown_or_indeterminate():
    plan = load_failure_control_plan(DATA)
    model = next(
        item for item in plan.requirements
        if item.control_kind == FailureControlKind.MODEL_DOMAIN_UNSUPPORTED.value
    )
    assert (
        model.expected_behavior
        == FailureControlExpectedBehavior.RETURN_UNKNOWN_OR_INDETERMINATE.value
    )
    assert "P2.5" in model.target_stages
    assert "P3" in model.target_stages
