"""Negative-control and falsification contracts (stage N).

Stage N probes a scientific claim with predeclared controls. A control that
behaves as expected can validate the control machinery, but it never upgrades
the target scientific claim. A violated control is preserved as falsification
evidence requiring downstream resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from rudeus.science.contracts import Record, digest, require_hash


class NStatus(str, Enum):
    CONTROL_PASSED = "CONTROL_PASSED"
    FALSIFIED = "FALSIFIED"
    INDETERMINATE = "INDETERMINATE"
    BLOCKED_SCOPE_MISMATCH = "BLOCKED_SCOPE_MISMATCH"


@dataclass(frozen=True, kw_only=True)
class NControlSpec(Record):
    control_id: str
    target_claim_hash: str
    protocol_hash: str
    control_kind: str
    expected: bool
    scope: Mapping[str, Any]
    justification: str
    status: str = "PROVISIONAL"

    def validate(self):
        super().validate()
        require_hash(self.target_claim_hash)
        require_hash(self.protocol_hash)
        if not self.control_id or not self.control_kind or not self.scope:
            raise ValueError("complete N control identity and scope are required")
        if not self.justification or self.status != "PROVISIONAL":
            raise ValueError("N control criterion requires PROVISIONAL justification")
        if not isinstance(self.expected, bool):
            raise ValueError("N control expected outcome must be boolean")


@dataclass(frozen=True, kw_only=True)
class NObservation(Record):
    control_id: str
    protocol_hash: str
    observed: bool | None
    scope: Mapping[str, Any]
    evidence_hashes: tuple[str, ...]
    producer_identity: str

    def validate(self):
        super().validate()
        require_hash(self.protocol_hash)
        for value in self.evidence_hashes:
            require_hash(value)
        if not self.control_id or not self.scope or not self.producer_identity:
            raise ValueError("complete N observation identity and scope are required")
        if self.observed is not None and not isinstance(self.observed, bool):
            raise ValueError("N observed outcome must be boolean or unavailable")


@dataclass(frozen=True, kw_only=True)
class NAssessment(Record):
    status: NStatus
    target_claim_hash: str
    control_spec_hash: str
    observation_hash: str | None
    reason_codes: tuple[str, ...]
    control_evidence: tuple[str, ...] = ()
    conflicting_evidence: tuple[str, ...] = ()
    target_verdict_changed: bool = False

    def validate(self):
        super().validate()
        NStatus(self.status)
        require_hash(self.target_claim_hash)
        require_hash(self.control_spec_hash)
        if self.observation_hash is not None:
            require_hash(self.observation_hash)
        for value in self.control_evidence + self.conflicting_evidence:
            require_hash(value)
        if self.target_verdict_changed:
            raise ValueError("stage N must never rewrite the target claim verdict")
        if self.status == NStatus.FALSIFIED and not self.conflicting_evidence:
            raise ValueError("falsification requires preserved conflicting evidence")


def assess_n(spec: NControlSpec, observation: NObservation | None) -> NAssessment:
    """Assess one predeclared control with asymmetric scientific semantics."""
    if observation is None:
        return NAssessment(
            status=NStatus.INDETERMINATE,
            target_claim_hash=spec.target_claim_hash,
            control_spec_hash=spec.content_hash,
            observation_hash=None,
            reason_codes=("control_observation_unavailable",),
        )

    if (observation.control_id != spec.control_id
            or observation.protocol_hash != spec.protocol_hash
            or dict(observation.scope) != dict(spec.scope)):
        return NAssessment(
            status=NStatus.BLOCKED_SCOPE_MISMATCH,
            target_claim_hash=spec.target_claim_hash,
            control_spec_hash=spec.content_hash,
            observation_hash=observation.content_hash,
            reason_codes=("control_scope_mismatch",),
            control_evidence=observation.evidence_hashes,
        )

    if observation.observed is None:
        return NAssessment(
            status=NStatus.INDETERMINATE,
            target_claim_hash=spec.target_claim_hash,
            control_spec_hash=spec.content_hash,
            observation_hash=observation.content_hash,
            reason_codes=("control_outcome_unavailable",),
            control_evidence=observation.evidence_hashes,
        )

    if observation.observed == spec.expected:
        return NAssessment(
            status=NStatus.CONTROL_PASSED,
            target_claim_hash=spec.target_claim_hash,
            control_spec_hash=spec.content_hash,
            observation_hash=observation.content_hash,
            reason_codes=("expected_control_behavior_observed",),
            control_evidence=observation.evidence_hashes,
            conflicting_evidence=(),
            target_verdict_changed=False,
        )

    return NAssessment(
        status=NStatus.FALSIFIED,
        target_claim_hash=spec.target_claim_hash,
        control_spec_hash=spec.content_hash,
        observation_hash=observation.content_hash,
        reason_codes=("negative_control_violated",),
        control_evidence=observation.evidence_hashes,
        conflicting_evidence=observation.evidence_hashes,
        target_verdict_changed=False,
    )


def n_record(spec: NControlSpec, observation: NObservation | None) -> dict[str, Any]:
    assessment = assess_n(spec, observation)
    return {
        "stage": "N",
        "control_spec": spec.to_dict(),
        "observation": observation.to_dict() if observation is not None else None,
        "assessment": assessment.to_dict(),
    }


def verify_n_record(record: Mapping[str, Any]) -> dict[str, Any]:
    required = {"stage", "control_spec", "observation", "assessment"}
    if set(record) != required or record.get("stage") != "N":
        raise ValueError("invalid N record schema")

    spec = NControlSpec.from_dict(record["control_spec"])
    observation = (
        None if record["observation"] is None
        else NObservation.from_dict(record["observation"])
    )
    stored = NAssessment.from_dict(record["assessment"])
    replayed = assess_n(spec, observation)
    if stored != replayed:
        raise ValueError("N assessment replay mismatch")

    return {
        "record": dict(record),
        "record_hash": digest(record),
        "status": replayed.status.value,
        "target_claim_hash": replayed.target_claim_hash,
        "target_verdict_changed": False,
        "conflicting_evidence": list(replayed.conflicting_evidence),
    }
