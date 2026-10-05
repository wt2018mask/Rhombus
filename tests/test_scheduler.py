from dataclasses import replace

import pytest

from rudeus.execution.contracts import ExecutionAttempt, FailureClass, TaskSpec
from rudeus.execution.scheduler import plan_attempt, order_plans
from rudeus.science.contracts import digest


def task(seed=1):
    return TaskSpec(candidate_id="synthetic", stage="P3", protocol_hash=digest("protocol"),
                    config={"estimator": "explicit"}, input_artifact_hashes=(digest("input"),),
                    dependencies=(), code_revision="a" * 40, resource_requirements={},
                    expected_outputs=("analysis.json",), retry_policy={}, seed=seed)


def attempt(spec, backend, failure, ordinal=1):
    return ExecutionAttempt(attempt_id=digest((spec.task_id, backend, ordinal)),
                            task_id=spec.task_id, task_content_hash=spec.content_hash,
                            backend=backend, remote_session_id=None, started_at="t0", ended_at="t1",
                            runtime_s=1, hardware={}, environment={}, precision=None,
                            exit_status=1 if failure else 0,
                            status="FAILED" if failure else "COMPLETED",
                            termination_reason="failure" if failure else "done",
                            failure_class=failure, logs=(), output_manifest={})


def test_transient_retry_keeps_scientific_identity_and_makes_new_attempt_plan():
    spec = task()
    first = plan_attempt(spec, "local")["plan"]
    failed = attempt(spec, "local", FailureClass.NETWORK)
    second = plan_attempt(spec, "local", prior_attempts=(failed,))["plan"]
    assert first.task_id == second.task_id == spec.task_id
    assert second.attempt_id != first.attempt_id
    assert second.predecessor_attempt_id == failed.attempt_id
    assert second.task_content_hash == spec.content_hash


def test_backend_specific_failure_needs_alternate_backend_same_task():
    spec = task()
    failed = attempt(spec, "backend-a", FailureClass.RESOURCE)
    assert plan_attempt(spec, "backend-a", prior_attempts=(failed,))["reason"] == "alternate_backend_required"
    changed = plan_attempt(spec, "backend-b", prior_attempts=(failed,))["plan"]
    assert changed.task_id == spec.task_id and changed.backend == "backend-b"
    assert changed.ordinal == 2


@pytest.mark.parametrize("failure", [FailureClass.INTEGRITY, FailureClass.UNSUPPORTED_INPUT,
                                      FailureClass.NUMERICAL, FailureClass.UNKNOWN])
def test_permanent_or_unclassified_failure_has_no_retry(failure):
    spec = task()
    assert plan_attempt(spec, "other", prior_attempts=(attempt(spec, "local", failure),))["plan"] is None


def test_scientific_fail_and_completed_science_are_terminal():
    spec = task()
    assert plan_attempt(spec, "local", scientific_verdict="FAIL")["reason"] == "scientific_fail_terminal"
    assert plan_attempt(spec, "local", prior_attempts=(attempt(spec, "local", None),))["plan"] is None


def test_recovery_and_ingestion_failure_require_owner_reconciliation():
    spec = task()
    for issue in ("ARTIFACT_RECOVERY_REQUEST", "DURABLE_INGESTION_FAILURE"):
        assert plan_attempt(spec, "local", operational_issue=issue)["reason"] == "owner_reconciliation_required"


def test_operational_metadata_and_retry_budget_cannot_change_science():
    spec = task()
    first = plan_attempt(spec, "a", resources={"gpu": 1}, batch="batch-a",
                         shard="0/2", priority=10)["plan"]
    second = plan_attempt(spec, "b", resources={"cpu": 8}, batch="batch-b", shard="1/2",
                          priority=0, max_attempts=1)["plan"]
    assert first.task_id == second.task_id == spec.task_id
    assert first.task_content_hash == second.task_content_hash == spec.content_hash
    assert spec.config == {"estimator": "explicit"}
    assert plan_attempt(spec, "a", prior_attempts=(attempt(spec, "a", FailureClass.TIMEOUT),),
                        max_attempts=1)["reason"] == "retry_budget_exhausted"


def test_ordering_is_deterministic_and_new_scientific_task_has_new_identity():
    specs = (task(2), task(1))
    plans = [plan_attempt(spec, "local", priority=1)["plan"] for spec in specs]
    assert order_plans(plans) == order_plans(tuple(reversed(plans)))
    assert [plan.task_id for plan in order_plans(plans)] == sorted(spec.task_id for spec in specs)
    assert replace(specs[0], seed=3).task_id != specs[0].task_id


def test_mismatched_history_cannot_be_reused():
    with pytest.raises(ValueError, match="does not bind"):
        plan_attempt(task(2), "local", prior_attempts=(attempt(task(1), "local", FailureClass.NETWORK),))
