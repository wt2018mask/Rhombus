"""Executable failure-control harness tests."""
from dataclasses import replace
from pathlib import Path

from rudeus.science.known_material_failure_control import (
    FailureControlCaseState,
    load_failure_control_plan,
)
from rudeus.science.known_material_failure_control_execution import (
    FailureControlErrorClass,
    FailureControlExecutionStatus,
    execute_failure_control,
    run_failure_control_plan,
)


ROOT = Path(".")
PLAN = Path("data/benchmarks/known_material/failure_control_plan_v1.json")


def canonical_plan():
    return load_failure_control_plan(PLAN)


def test_canonical_executable_failure_controls_both_pass():
    report = run_failure_control_plan(canonical_plan(), repo_root=ROOT)
    by_id = {item.control_id: item for item in report.observations}

    assert set(by_id) == {
        "fc:p0:synthetic-overlap-v1",
        "fc:representation:llzo-fractional-occupancy-v1",
    }
    assert all(
        item.status == FailureControlExecutionStatus.PASS.value
        for item in report.observations
    )
    assert report.skipped_control_ids == (
        "fc:model-domain:medium-mpa-0-v1",
    )


def test_p0_overlap_control_is_rejected_for_geometry_not_execution_error():
    plan = canonical_plan()
    case = next(
        item for item in plan.cases
        if item.control_id == "fc:p0:synthetic-overlap-v1"
    )
    observation = execute_failure_control(case, repo_root=ROOT)

    assert observation.status == FailureControlExecutionStatus.PASS.value
    assert observation.observed_behavior == "REJECT_INPUT"
    assert observation.infrastructure_error is False
    assert observation.error_class is None
    assert observation.details["existence_state"] == "FAIL"
    assert observation.details["geometry_ok"] is False
    assert observation.details["p0_details"]["geometry"]["clash_detected"] is True


def test_llzo_representation_control_blocks_before_execution_not_material_failure():
    plan = canonical_plan()
    case = next(
        item for item in plan.cases
        if item.control_id
        == "fc:representation:llzo-fractional-occupancy-v1"
    )
    observation = execute_failure_control(case, repo_root=ROOT)

    assert observation.status == FailureControlExecutionStatus.PASS.value
    assert observation.observed_behavior == "BLOCK_BEFORE_EXECUTION"
    assert observation.infrastructure_error is False
    assert observation.error_class is None
    assert observation.details["resolution_status"] == "BLOCKED_POLICY"
    assert observation.details["representation_policy_id"] == (
        "fractional-occupancy-explicit-v1"
    )
    assert observation.details["unresolved_requirements"] == (
        "fractional_occupancy_execution_strategy",
    )


def test_missing_fixture_is_data_error_never_infrastructure_success(tmp_path):
    plan = canonical_plan()
    base = next(
        item for item in plan.cases
        if item.control_id == "fc:p0:synthetic-overlap-v1"
    )
    broken = replace(
        base,
        executor_config={
            "fixture_path":
            "data/benchmarks/known_material/failure_controls/missing.json"
        },
    )
    observation = execute_failure_control(broken, repo_root=tmp_path)

    assert observation.status == FailureControlExecutionStatus.ERROR.value
    assert observation.observed_behavior == "ERROR"
    assert observation.error_class == (
        FailureControlErrorClass.DATA_OR_CONFIGURATION.value
    )
    assert observation.infrastructure_error is False


def test_fixture_hash_mismatch_is_data_integrity_error_not_scientific_fail(tmp_path):
    plan = canonical_plan()
    base = next(
        item for item in plan.cases
        if item.control_id == "fc:p0:synthetic-overlap-v1"
    )
    fixture = tmp_path / base.executor_config["fixture_path"]
    fixture.parent.mkdir(parents=True)
    fixture.write_text("{}", encoding="utf-8")

    observation = execute_failure_control(base, repo_root=tmp_path)

    assert observation.status == FailureControlExecutionStatus.ERROR.value
    assert observation.error_class == (
        FailureControlErrorClass.DATA_OR_CONFIGURATION.value
    )
    assert observation.infrastructure_error is False


def test_planned_model_domain_case_cannot_be_executed_prematurely():
    plan = canonical_plan()
    case = next(
        item for item in plan.cases
        if item.control_id == "fc:model-domain:medium-mpa-0-v1"
    )
    assert case.state == FailureControlCaseState.PLANNED.value

    try:
        execute_failure_control(case, repo_root=ROOT)
    except ValueError as exc:
        assert "only executable" in str(exc)
    else:
        raise AssertionError("planned model-domain control executed prematurely")
