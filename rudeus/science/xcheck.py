"""Independent-model cross-check contracts (stage X).

Stage X consumes already-produced scientific observations and records whether an
independent model reproduces them under an explicitly bound comparison scope.
It never upgrades the primary scientific verdict and never treats model
agreement as qualification by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from rudeus.science.contracts import Record, require_hash


class XStatus(str, Enum):
    AGREEMENT = "AGREEMENT"
    DISAGREEMENT = "DISAGREEMENT"
    INDETERMINATE = "INDETERMINATE"
    BLOCKED_NOT_INDEPENDENT = "BLOCKED_NOT_INDEPENDENT"
    BLOCKED_SCOPE_MISMATCH = "BLOCKED_SCOPE_MISMATCH"


@dataclass(frozen=True, kw_only=True)
class XModelIdentity(Record):
    model_name: str
    model_family: str
    checkpoint_sha256: str
    code_revision: str
    implementation_id: str

    def validate(self):
        super().validate()
        require_hash(self.checkpoint_sha256)
        require_hash(self.code_revision)
        if not self.model_name or not self.model_family or not self.implementation_id:
            raise ValueError("complete X model identity is required")


@dataclass(frozen=True, kw_only=True)
class XInputBinding(Record):
    candidate_id: str
    structure_sha256: str
    protocol_hash: str
    quantity: str
    units: str
    conditions: Mapping[str, Any]

    def validate(self):
        super().validate()
        require_hash(self.structure_sha256)
        require_hash(self.protocol_hash)
        if not self.candidate_id or not self.quantity or not self.units:
            raise ValueError("complete X input binding is required")


@dataclass(frozen=True, kw_only=True)
class XObservation(Record):
    """One model's scalar result bound to model, input scope and raw evidence."""

    model_hash: str
    input_binding_hash: str
    quantity: str
    units: str
    value: float | None
    evidence_hash: str
    estimator_id: str

    def validate(self):
        super().validate()
        for value in (self.model_hash, self.input_binding_hash, self.evidence_hash):
            require_hash(value)
        if not self.quantity or not self.units or not self.estimator_id:
            raise ValueError("complete X observation identity is required")


@dataclass(frozen=True, kw_only=True)
class XComparisonSpec(Record):
    quantity: str
    units: str
    absolute_tolerance: float | None = None
    relative_tolerance: float | None = None
    justification: str = ""
    status: str = "PROVISIONAL"

    def validate(self):
        super().validate()
        if not self.quantity or not self.units or not self.justification:
            raise ValueError("X comparison requires quantity, units and justification")
        if self.status != "PROVISIONAL":
            raise ValueError("X comparison criterion must remain PROVISIONAL")
        if self.absolute_tolerance is None and self.relative_tolerance is None:
            raise ValueError("X comparison requires an explicit tolerance")
        if self.absolute_tolerance is not None and self.absolute_tolerance < 0:
            raise ValueError("absolute tolerance must be nonnegative")
        if self.relative_tolerance is not None and self.relative_tolerance < 0:
            raise ValueError("relative tolerance must be nonnegative")


@dataclass(frozen=True, kw_only=True)
class XAssessment(Record):
    status: XStatus
    primary_model_hash: str
    cross_model_hash: str
    input_binding_hash: str
    comparison_spec_hash: str
    primary_value: float | None
    cross_value: float | None
    absolute_difference: float | None
    relative_difference: float | None
    reason_codes: tuple[str, ...]
    supporting_evidence: tuple[str, ...] = ()
    conflicting_evidence: tuple[str, ...] = ()
    primary_verdict_changed: bool = False

    def validate(self):
        super().validate()
        XStatus(self.status)
        for value in (
            self.primary_model_hash,
            self.cross_model_hash,
            self.input_binding_hash,
            self.comparison_spec_hash,
        ):
            require_hash(value)
        for evidence in self.supporting_evidence + self.conflicting_evidence:
            require_hash(evidence)
        if self.primary_verdict_changed:
            raise ValueError("stage X must never upgrade or rewrite the primary verdict")
        if self.status in (XStatus.AGREEMENT, XStatus.DISAGREEMENT):
            if self.primary_value is None or self.cross_value is None:
                raise ValueError("decisive X comparison requires both values")


def independent_models(primary: XModelIdentity, cross: XModelIdentity) -> tuple[bool, tuple[str, ...]]:
    """Fail closed on model/checkpoint/implementation dependence."""
    reasons = []
    if primary.checkpoint_sha256 == cross.checkpoint_sha256:
        reasons.append("same_checkpoint")
    if primary.model_family == cross.model_family:
        reasons.append("same_model_family")
    if primary.implementation_id == cross.implementation_id:
        reasons.append("same_implementation")
    return (not reasons, tuple(reasons))


def _relative_difference(a: float, b: float) -> float | None:
    scale = max(abs(a), abs(b))
    if scale == 0:
        return 0.0
    return abs(a - b) / scale


def assess_x_observations(
    *,
    primary_model: XModelIdentity,
    cross_model: XModelIdentity,
    primary_binding: XInputBinding,
    cross_binding: XInputBinding,
    comparison: XComparisonSpec,
    primary_observation: XObservation,
    cross_observation: XObservation,
) -> XAssessment:
    """Assess two persisted X observations after strict identity validation."""
    expected = (
        (primary_observation, primary_model, primary_binding, "primary"),
        (cross_observation, cross_model, cross_binding, "cross"),
    )
    for observation, model, binding, label in expected:
        if observation.model_hash != model.content_hash:
            raise ValueError(f"{label} observation model binding mismatch")
        if observation.input_binding_hash != binding.content_hash:
            raise ValueError(f"{label} observation input binding mismatch")
        if observation.quantity != binding.quantity or observation.units != binding.units:
            raise ValueError(f"{label} observation quantity/units mismatch")

    return assess_x(
        primary_model=primary_model,
        cross_model=cross_model,
        primary_binding=primary_binding,
        cross_binding=cross_binding,
        comparison=comparison,
        primary_value=primary_observation.value,
        cross_value=cross_observation.value,
        primary_evidence_hash=primary_observation.evidence_hash,
        cross_evidence_hash=cross_observation.evidence_hash,
    )


def assess_x(
    *,
    primary_model: XModelIdentity,
    cross_model: XModelIdentity,
    primary_binding: XInputBinding,
    cross_binding: XInputBinding,
    comparison: XComparisonSpec,
    primary_value: float | None,
    cross_value: float | None,
    primary_evidence_hash: str | None = None,
    cross_evidence_hash: str | None = None,
) -> XAssessment:
    """Create a conservative X assessment without altering upstream science."""
    independent, dependence_reasons = independent_models(primary_model, cross_model)
    if not independent:
        return XAssessment(
            status=XStatus.BLOCKED_NOT_INDEPENDENT,
            primary_model_hash=primary_model.content_hash,
            cross_model_hash=cross_model.content_hash,
            input_binding_hash=primary_binding.content_hash,
            comparison_spec_hash=comparison.content_hash,
            primary_value=primary_value,
            cross_value=cross_value,
            absolute_difference=None,
            relative_difference=None,
            reason_codes=dependence_reasons,
        )

    if primary_binding != cross_binding:
        return XAssessment(
            status=XStatus.BLOCKED_SCOPE_MISMATCH,
            primary_model_hash=primary_model.content_hash,
            cross_model_hash=cross_model.content_hash,
            input_binding_hash=primary_binding.content_hash,
            comparison_spec_hash=comparison.content_hash,
            primary_value=primary_value,
            cross_value=cross_value,
            absolute_difference=None,
            relative_difference=None,
            reason_codes=("input_binding_mismatch",),
        )

    if comparison.quantity != primary_binding.quantity or comparison.units != primary_binding.units:
        return XAssessment(
            status=XStatus.BLOCKED_SCOPE_MISMATCH,
            primary_model_hash=primary_model.content_hash,
            cross_model_hash=cross_model.content_hash,
            input_binding_hash=primary_binding.content_hash,
            comparison_spec_hash=comparison.content_hash,
            primary_value=primary_value,
            cross_value=cross_value,
            absolute_difference=None,
            relative_difference=None,
            reason_codes=("comparison_scope_mismatch",),
        )

    if primary_value is None or cross_value is None:
        return XAssessment(
            status=XStatus.INDETERMINATE,
            primary_model_hash=primary_model.content_hash,
            cross_model_hash=cross_model.content_hash,
            input_binding_hash=primary_binding.content_hash,
            comparison_spec_hash=comparison.content_hash,
            primary_value=primary_value,
            cross_value=cross_value,
            absolute_difference=None,
            relative_difference=None,
            reason_codes=("missing_comparable_value",),
        )

    absolute = abs(float(primary_value) - float(cross_value))
    relative = _relative_difference(float(primary_value), float(cross_value))
    checks = []
    if comparison.absolute_tolerance is not None:
        checks.append(absolute <= comparison.absolute_tolerance)
    if comparison.relative_tolerance is not None:
        checks.append(relative is not None and relative <= comparison.relative_tolerance)
    agreement = all(checks)

    primary_refs = () if primary_evidence_hash is None else (primary_evidence_hash,)
    cross_refs = () if cross_evidence_hash is None else (cross_evidence_hash,)
    for ref in primary_refs + cross_refs:
        require_hash(ref)

    return XAssessment(
        status=XStatus.AGREEMENT if agreement else XStatus.DISAGREEMENT,
        primary_model_hash=primary_model.content_hash,
        cross_model_hash=cross_model.content_hash,
        input_binding_hash=primary_binding.content_hash,
        comparison_spec_hash=comparison.content_hash,
        primary_value=float(primary_value),
        cross_value=float(cross_value),
        absolute_difference=absolute,
        relative_difference=relative,
        reason_codes=("within_explicit_tolerance",) if agreement else ("outside_explicit_tolerance",),
        supporting_evidence=primary_refs + cross_refs if agreement else (),
        conflicting_evidence=primary_refs + cross_refs if not agreement else (),
        primary_verdict_changed=False,
    )


def x_record(
    *,
    primary_model: XModelIdentity,
    cross_model: XModelIdentity,
    primary_binding: XInputBinding,
    cross_binding: XInputBinding,
    comparison: XComparisonSpec,
    primary_observation: XObservation,
    cross_observation: XObservation,
) -> Dict[str, Any]:
    """Canonical append-only X record; persistence must not alter assessment."""
    assessment = assess_x_observations(
        primary_model=primary_model,
        cross_model=cross_model,
        primary_binding=primary_binding,
        cross_binding=cross_binding,
        comparison=comparison,
        primary_observation=primary_observation,
        cross_observation=cross_observation,
    )
    return {
        "stage": "X",
        "primary_model": primary_model.to_dict(),
        "cross_model": cross_model.to_dict(),
        "primary_binding": primary_binding.to_dict(),
        "cross_binding": cross_binding.to_dict(),
        "comparison": comparison.to_dict(),
        "primary_observation": primary_observation.to_dict(),
        "cross_observation": cross_observation.to_dict(),
        "assessment": assessment.to_dict(),
    }


def verify_x_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Rebuild an X assessment from serialized inputs and require exact replay."""
    required = {
        "stage", "primary_model", "cross_model", "primary_binding",
        "cross_binding", "comparison", "primary_observation",
        "cross_observation", "assessment",
    }
    if set(record) != required or record.get("stage") != "X":
        raise ValueError("invalid X record schema")

    primary_model = XModelIdentity.from_dict(record["primary_model"])
    cross_model = XModelIdentity.from_dict(record["cross_model"])
    primary_binding = XInputBinding.from_dict(record["primary_binding"])
    cross_binding = XInputBinding.from_dict(record["cross_binding"])
    comparison = XComparisonSpec.from_dict(record["comparison"])
    primary_observation = XObservation.from_dict(record["primary_observation"])
    cross_observation = XObservation.from_dict(record["cross_observation"])
    stored = XAssessment.from_dict(record["assessment"])

    replayed = assess_x_observations(
        primary_model=primary_model,
        cross_model=cross_model,
        primary_binding=primary_binding,
        cross_binding=cross_binding,
        comparison=comparison,
        primary_observation=primary_observation,
        cross_observation=cross_observation,
    )
    if stored != replayed:
        raise ValueError("X assessment replay mismatch")

    return {
        "record": dict(record),
        "record_hash": __import__("rudeus.science.contracts", fromlist=["digest"]).digest(record),
        "assessment": replayed.to_dict(),
        "scientific_status": replayed.status.value,
        "primary_verdict_changed": False,
    }
