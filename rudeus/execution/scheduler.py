"""Pure execution planning for scientific-owner TaskSpecs; no provider I/O."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from rudeus.execution.contracts import ExecutionAttempt, FailureClass, TaskSpec
from rudeus.science.contracts import Record, digest, require_hash


TRANSIENT = frozenset({FailureClass.INFRASTRUCTURE, FailureClass.NETWORK,
                       FailureClass.TIMEOUT})
BACKEND_SPECIFIC = frozenset({FailureClass.RESOURCE, FailureClass.SOFTWARE})


@dataclass(frozen=True, kw_only=True)
class AttemptPlan(Record):
    """Instruction to create a fresh ExecutionAttempt for the unchanged task."""

    attempt_id: str
    task_id: str
    task_content_hash: str
    backend: str
    ordinal: int
    predecessor_attempt_id: str | None = None
    resources: Mapping = field(default_factory=dict)
    batch: str | None = None
    shard: str | None = None
    priority: int = 0

    def validate(self):
        super().validate()
        for value in (self.attempt_id, self.task_id, self.task_content_hash):
            require_hash(value)
        if self.predecessor_attempt_id is not None:
            require_hash(self.predecessor_attempt_id)
        if not self.backend or type(self.ordinal) is not int or self.ordinal < 1:
            raise ValueError("invalid attempt plan")
        if type(self.priority) is not int or not isinstance(self.resources, Mapping):
            raise ValueError("invalid operational metadata")
        if any(value is not None and (not isinstance(value, str) or not value)
               for value in (self.batch, self.shard)):
            raise ValueError("invalid batch or shard")


def plan_attempt(task: TaskSpec, backend: str, *, prior_attempts: Sequence[ExecutionAttempt] = (),
                 scientific_verdict: str | None = None, max_attempts: int = 3,
                 resources: Mapping | None = None, batch: str | None = None,
                 shard: str | None = None,
                 priority: int = 0, operational_issue: str | None = None):
    """Return a plan or an explicit no-plan reason, never a modified TaskSpec.

    A completed scientific attempt, missing evidence, or ingestion failure is
    passed back to its owner. Retry policy only addresses operational failure.
    """
    if not isinstance(task, TaskSpec):
        raise TypeError("an existing TaskSpec is required")
    if not backend or type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("backend and positive retry budget required")
    if scientific_verdict not in (None, "PASS", "FAIL", "INDETERMINATE", "UNKNOWN"):
        raise ValueError("invalid scientific verdict")
    if operational_issue not in (None, "ARTIFACT_RECOVERY_REQUEST", "DURABLE_INGESTION_FAILURE"):
        raise ValueError("invalid operational issue")
    attempts = tuple(prior_attempts)
    if any(not isinstance(item, ExecutionAttempt) or item.task_id != task.task_id
           or (item.task_content_hash is not None and item.task_content_hash != task.content_hash)
           for item in attempts):
        raise ValueError("attempt history does not bind to the exact task")
    if len({item.attempt_id for item in attempts}) != len(attempts):
        raise ValueError("duplicate attempt identity")
    if scientific_verdict == "FAIL":
        return {"status": "NO_PLAN", "reason": "scientific_fail_terminal", "plan": None}
    if operational_issue is not None:
        return {"status": "NO_PLAN", "reason": "owner_reconciliation_required", "plan": None}
    if attempts:
        latest = attempts[-1]
        if latest.status == "COMPLETED":
            return {"status": "NO_PLAN", "reason": "completed_attempt_not_retryable", "plan": None}
        failure = FailureClass(latest.failure_class)
        if failure in BACKEND_SPECIFIC and backend == latest.backend:
            return {"status": "NO_PLAN", "reason": "alternate_backend_required", "plan": None}
        if failure not in TRANSIENT | BACKEND_SPECIFIC:
            return {"status": "NO_PLAN", "reason": "permanent_or_unclassified_failure", "plan": None}
    if len(attempts) >= max_attempts:
        return {"status": "NO_PLAN", "reason": "retry_budget_exhausted", "plan": None}
    predecessor = attempts[-1].attempt_id if attempts else None
    identity = digest({"task_content_hash": task.content_hash, "task_id": task.task_id,
                       "backend": backend, "ordinal": len(attempts) + 1,
                       "predecessor_attempt_id": predecessor})
    plan = AttemptPlan(attempt_id=identity, task_id=task.task_id,
                       task_content_hash=task.content_hash, backend=backend,
                       ordinal=len(attempts) + 1, predecessor_attempt_id=predecessor,
                       resources={} if resources is None else resources,
                       batch=batch, shard=shard, priority=priority)
    return {"status": "PLANNED", "reason": "initial" if not attempts else "operational_retry",
            "plan": plan}


def order_plans(plans: Sequence[AttemptPlan]) -> tuple[AttemptPlan, ...]:
    """Stable operational priority without changing task or claim identity."""
    if any(not isinstance(plan, AttemptPlan) for plan in plans):
        raise TypeError("AttemptPlan sequence required")
    return tuple(sorted(plans, key=lambda plan: (-plan.priority, plan.task_id,
                                                  plan.ordinal, plan.backend, plan.attempt_id)))
