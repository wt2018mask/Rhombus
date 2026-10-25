"""Versioned research context and declaration routing, never model qualification.

Family labels are host-supplied metadata, independent of composition, structure,
processing and observable. Matching a declaration cannot authorize execution or
turn element coverage into scientific applicability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import math
from typing import Any, Mapping

from rhombus.evidence import (
    Applicability, DomainStatus, EvidenceRecord, OperationalStatus,
    ScientificVerdict, Uncertainty,
)
from rhombus.evidence.identity import SourceBinding

CONTEXT_VERSION = "rhombus-research-context-v1"


def _text(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(f"{name} must be nonempty text of at most 256 characters")


@dataclass(frozen=True)
class ResearchContext:
    domain_id: str
    family_id: str
    candidate_id: str
    observable_id: str
    unit: str
    composition_id: str | None = None
    structure_artifact_id: str | None = None
    processing_state_id: str | None = None
    measurement_temperature_K: float | None = None
    schema_version: str = CONTEXT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CONTEXT_VERSION:
            raise ValueError("unsupported research context schema")
        for name in ("domain_id", "family_id", "candidate_id", "observable_id", "unit"):
            _text(name, getattr(self, name))
        for name in ("composition_id", "structure_artifact_id", "processing_state_id"):
            value = getattr(self, name)
            if value is not None:
                _text(name, value)
        t = self.measurement_temperature_K
        if t is not None and (type(t) not in (int, float) or not math.isfinite(t) or t <= 0):
            raise ValueError("measurement_temperature_K must be positive finite Kelvin")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> ResearchContext:
        if not isinstance(row, Mapping) or set(row) - {f.name for f in fields(cls)}:
            raise ValueError("unexpected research context fields")
        if row.get("schema_version") != CONTEXT_VERSION:
            raise ValueError("explicit supported research context schema required")
        try:
            return cls(**row)
        except TypeError as exc:
            raise ValueError("incomplete research context") from exc


@dataclass(frozen=True)
class CapabilityDeclaration:
    """Host declaration of an intended research adapter, not qualified support."""

    capability: str
    domain_id: str
    family_id: str
    observable_id: str
    unit: str
    model_id: str
    protocol_id: str

    def __post_init__(self) -> None:
        for field in fields(self):
            _text(field.name, getattr(self, field.name))


def assess_declared_capability(
    context: ResearchContext,
    declaration: CapabilityDeclaration,
    *,
    source_bindings: tuple[SourceBinding, ...] = (),
) -> EvidenceRecord:
    """Represent and route a candidate while refusing unqualified inference.

Even exact matches abstain. This contract has no qualification authority,
backend, prediction, estimated cost or physical-science activation path.
"""
    if not isinstance(context, ResearchContext) or not isinstance(declaration, CapabilityDeclaration):
        raise ValueError("typed research context and capability declaration required")
    if type(source_bindings) is not tuple or any(not isinstance(s, SourceBinding) for s in source_bindings):
        raise ValueError("source_bindings must be a tuple of SourceBinding objects")
    mismatches = tuple(
        name for name in ("domain_id", "family_id", "observable_id", "unit")
        if getattr(context, name) != getattr(declaration, name)
    )
    verdict = ScientificVerdict.NOT_APPLICABLE if mismatches else ScientificVerdict.UNKNOWN
    limitations = (
        "DECLARED_RESEARCH_CONTEXT_NOT_QUALIFIED_MODEL_APPLICABILITY",
        "FAMILY_LABEL_DOES_NOT_CERTIFY_COMPOSITION_STRUCTURE_OR_PHASE",
        "SOURCE_BINDING_IS_NOT_INDEPENDENT_PHYSICAL_SPECIMEN_AUTHENTICATION",
        "NO_PREDICTION_EXECUTION_OR_PRODUCTION_AUTHORIZATION",
    )
    return EvidenceRecord.create(
        candidate_id=context.candidate_id,
        evidence_kind="DECLARED_DOMAIN_CAPABILITY_PREFLIGHT",
        capability=declaration.capability,
        operational_status=OperationalStatus.SUCCEEDED,
        scientific_verdict=verdict,
        applicability=Applicability(
            claim_kind=context.observable_id, domain_status=DomainStatus.UNQUALIFIED,
            limitations=limitations,
        ),
        uncertainty=Uncertainty(status="UNKNOWN", reason="No domain-specific qualification supplied"),
        limitations=limitations,
        protocol_id=declaration.protocol_id,
        source_bindings=source_bindings,
        provenance={"capability_declaration": asdict(declaration)},
        payload={
            "research_context": context.to_dict(),
            "routing_decision": "NOT_APPLICABLE" if mismatches else "ABSTAIN",
            "mismatched_fields": list(mismatches),
            "execution_authorized": False,
            "prediction": None,
        },
    )
