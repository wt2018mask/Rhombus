"""Failure-control contracts for B2 known-material falsification.

Failure controls test whether Rhombus fails honestly. They must distinguish invalid
scientific inputs, unsupported representations, and model-domain limitations from
physical material failure. Infrastructure failure never counts as a successful
scientific control outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Any, Mapping

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_benchmark import STAGES


FAILURE_CONTROL_PLAN_VERSION = "known-material-failure-control-plan-v1"


class FailureControlKind(str, Enum):
    INVALID_SCIENTIFIC_INPUT = "INVALID_SCIENTIFIC_INPUT"
    REPRESENTATION_UNSUPPORTED = "REPRESENTATION_UNSUPPORTED"
    MODEL_DOMAIN_UNSUPPORTED = "MODEL_DOMAIN_UNSUPPORTED"


class FailureControlExpectedBehavior(str, Enum):
    REJECT_INPUT = "REJECT_INPUT"
    BLOCK_BEFORE_EXECUTION = "BLOCK_BEFORE_EXECUTION"
    RETURN_UNKNOWN_OR_INDETERMINATE = "RETURN_UNKNOWN_OR_INDETERMINATE"


class FailureControlCaseState(str, Enum):
    PLANNED = "PLANNED"
    EVIDENCE_BOUND = "EVIDENCE_BOUND"
    EXECUTABLE = "EXECUTABLE"


class FailureControlInputOrigin(str, Enum):
    SYNTHETIC_INVALID = "SYNTHETIC_INVALID"
    KNOWN_MATERIAL = "KNOWN_MATERIAL"
    DERIVED_STRESS_CASE = "DERIVED_STRESS_CASE"


@dataclass(frozen=True, kw_only=True)
class FailureControlRequirement(Record):
    control_kind: str
    target_stages: tuple[str, ...]
    expected_behavior: str
    falsification_events: tuple[str, ...]
    rationale: tuple[str, ...]

    def validate(self):
        super().validate()
        FailureControlKind(self.control_kind)
        FailureControlExpectedBehavior(self.expected_behavior)
        if not self.target_stages or any(stage not in STAGES for stage in self.target_stages):
            raise ValueError("failure-control requirement has invalid target stages")
        if len(self.target_stages) != len(set(self.target_stages)):
            raise ValueError("failure-control requirement contains duplicate stages")
        if not self.falsification_events or any(not item for item in self.falsification_events):
            raise ValueError("failure-control requirement needs falsification events")
        if not self.rationale:
            raise ValueError("failure-control requirement needs rationale")


@dataclass(frozen=True, kw_only=True)
class FailureControlCase(Record):
    control_id: str
    control_kind: str
    state: str
    input_origin: str
    target_stages: tuple[str, ...]
    expected_behavior: str
    input_ref: str
    executor_id: str | None = None
    executor_config: Mapping[str, Any] = field(default_factory=dict)
    provenance_hash: str | None = None
    evidence_refs: tuple[str, ...] = ()
    scientific_material_failure_allowed: bool = False
    infrastructure_failure_counts_as_control_success: bool = False
    rationale: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        FailureControlKind(self.control_kind)
        state = FailureControlCaseState(self.state)
        FailureControlInputOrigin(self.input_origin)
        FailureControlExpectedBehavior(self.expected_behavior)
        if not self.control_id or not self.input_ref:
            raise ValueError("failure-control case identity is incomplete")
        if self.executor_id is not None and not self.executor_id:
            raise ValueError("failure-control executor id cannot be empty")
        if not self.target_stages or any(stage not in STAGES for stage in self.target_stages):
            raise ValueError("failure-control case has invalid target stages")
        if len(self.target_stages) != len(set(self.target_stages)):
            raise ValueError("failure-control case contains duplicate stages")
        if self.scientific_material_failure_allowed is not False:
            raise ValueError(
                "failure control cannot reinterpret control behavior as material failure"
            )
        if self.infrastructure_failure_counts_as_control_success is not False:
            raise ValueError(
                "infrastructure failure cannot satisfy a scientific failure control"
            )
        if state in {
            FailureControlCaseState.EVIDENCE_BOUND,
            FailureControlCaseState.EXECUTABLE,
        }:
            if self.provenance_hash is None:
                raise ValueError("evidence-bound failure control requires provenance hash")
            require_hash(self.provenance_hash)
            if not self.evidence_refs:
                raise ValueError("evidence-bound failure control requires evidence refs")
        elif self.provenance_hash is not None:
            require_hash(self.provenance_hash)
        if state == FailureControlCaseState.EXECUTABLE:
            if not self.rationale:
                raise ValueError("executable failure control requires rationale")
            if not self.executor_id or not self.executor_config:
                raise ValueError(
                    "executable failure control requires executor id and config"
                )


@dataclass(frozen=True, kw_only=True)
class FailureControlPlan(Record):
    plan_version: str
    requirements: tuple[FailureControlRequirement, ...]
    cases: tuple[FailureControlCase, ...]
    b3_split_authorized: bool = False

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["requirements"] = tuple(
            FailureControlRequirement.from_dict(item)
            for item in value["requirements"]
        )
        value["cases"] = tuple(
            FailureControlCase.from_dict(item) for item in value["cases"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.plan_version != FAILURE_CONTROL_PLAN_VERSION:
            raise ValueError("unsupported failure-control plan version")
        if self.b3_split_authorized is not False:
            raise ValueError("failure-control plan never authorizes B3 split")
        kinds = [item.control_kind for item in self.requirements]
        if not kinds or len(kinds) != len(set(kinds)):
            raise ValueError(
                "failure-control plan requires unique control-kind requirements"
            )
        ids = [item.control_id for item in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("failure-control plan requires unique control ids")

        requirement_by_kind = {
            item.control_kind: item for item in self.requirements
        }
        for case in self.cases:
            requirement = requirement_by_kind.get(case.control_kind)
            if requirement is None:
                raise ValueError(
                    "failure-control case uses undeclared control kind"
                )
            if case.expected_behavior != requirement.expected_behavior:
                raise ValueError(
                    "failure-control case behavior differs from its requirement"
                )
            if not set(case.target_stages).issubset(requirement.target_stages):
                raise ValueError(
                    "failure-control case targets stages outside its requirement"
                )


def load_failure_control_plan(path: Path) -> FailureControlPlan:
    return FailureControlPlan.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )


def executable_failure_control_kinds(
    plan: FailureControlPlan,
) -> tuple[str, ...]:
    kinds = {
        case.control_kind
        for case in plan.cases
        if case.state == FailureControlCaseState.EXECUTABLE.value
    }
    return tuple(sorted(kinds))


def missing_executable_failure_control_kinds(
    plan: FailureControlPlan,
) -> tuple[str, ...]:
    required = {item.control_kind for item in plan.requirements}
    executable = set(executable_failure_control_kinds(plan))
    return tuple(sorted(required - executable))
