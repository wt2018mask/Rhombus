"""Semantic Rhombus 2.0 evidence schemas.

These objects deliberately keep operational state, scientific verdict,
applicability, uncertainty, limitations, artifacts, protocol identity, and
provenance separate.  They do not reinterpret historical evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Mapping

from .identity import (
    ArtifactBinding,
    Limitation,
    ModelIdentity,
    ModelLineage,
    ProtocolIdentity,
    SourceBinding,
)


EVIDENCE_SCHEMA_VERSION = "rhombus-evidence-record-v1"
CLAIM_SCHEMA_VERSION = "rhombus-claim-record-v1"


class OperationalStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class ScientificVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    INDETERMINATE = "INDETERMINATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DomainStatus(str, Enum):
    IN_DOMAIN = "IN_DOMAIN"
    NEAR_OOD = "NEAR_OOD"
    FAR_OOD = "FAR_OOD"
    UNQUALIFIED = "UNQUALIFIED"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _content_id(prefix: str, payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}:sha256:{digest}"


@dataclass(frozen=True)
class Applicability:
    claim_kind: str
    domain_status: DomainStatus = DomainStatus.UNQUALIFIED
    basis_evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.claim_kind.strip():
            raise ValueError("claim_kind must be non-empty")


@dataclass(frozen=True)
class Uncertainty:
    status: str = "UNKNOWN"
    reason: str | None = None
    metrics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.status.strip():
            raise ValueError("uncertainty status must be non-empty")


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    candidate_id: str
    evidence_kind: str
    capability: str
    operational_status: OperationalStatus
    scientific_verdict: ScientificVerdict
    applicability: Applicability
    uncertainty: Uncertainty
    limitations: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    protocol_id: str | None
    provenance: Mapping[str, Any]
    payload: Mapping[str, Any]
    legacy_stage: str | None = None
    source_bindings: tuple[SourceBinding, ...] = ()
    artifact_bindings: tuple[ArtifactBinding, ...] = ()
    model_identity: ModelIdentity | None = None
    model_lineage: ModelLineage | None = None
    protocol_identity: ProtocolIdentity | None = None
    limitation_records: tuple[Limitation, ...] = ()
    schema_version: str = EVIDENCE_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        candidate_id: str,
        evidence_kind: str,
        capability: str,
        operational_status: OperationalStatus,
        scientific_verdict: ScientificVerdict,
        applicability: Applicability,
        uncertainty: Uncertainty | None = None,
        limitations: tuple[str, ...] = (),
        artifact_ids: tuple[str, ...] = (),
        protocol_id: str | None = None,
        provenance: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
        legacy_stage: str | None = None,
        source_bindings: tuple[SourceBinding, ...] = (),
        artifact_bindings: tuple[ArtifactBinding, ...] = (),
        model_identity: ModelIdentity | None = None,
        model_lineage: ModelLineage | None = None,
        protocol_identity: ProtocolIdentity | None = None,
        limitation_records: tuple[Limitation, ...] = (),
    ) -> "EvidenceRecord":
        if not candidate_id.strip():
            raise ValueError("candidate_id must be non-empty")
        if not evidence_kind.strip():
            raise ValueError("evidence_kind must be non-empty")
        if not capability.strip():
            raise ValueError("capability must be non-empty")

        uncertainty = uncertainty or Uncertainty()
        provenance = provenance or {}
        payload = payload or {}
        body = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "evidence_kind": evidence_kind,
            "capability": capability,
            "operational_status": operational_status.value,
            "scientific_verdict": scientific_verdict.value,
            "applicability": {
                "claim_kind": applicability.claim_kind,
                "domain_status": applicability.domain_status.value,
                "basis_evidence_ids": list(applicability.basis_evidence_ids),
                "limitations": list(applicability.limitations),
            },
            "uncertainty": {
                "status": uncertainty.status,
                "reason": uncertainty.reason,
                "metrics": dict(uncertainty.metrics),
            },
            "limitations": list(limitations),
            "artifact_ids": list(artifact_ids),
            "protocol_id": protocol_id,
            "provenance": dict(provenance),
            "payload": dict(payload),
            "legacy_stage": legacy_stage,
            "source_bindings": [asdict(item) for item in source_bindings],
            "artifact_bindings": [asdict(item) for item in artifact_bindings],
            "model_identity": asdict(model_identity) if model_identity else None,
            "model_lineage": asdict(model_lineage) if model_lineage else None,
            "protocol_identity": asdict(protocol_identity) if protocol_identity else None,
            "limitation_records": [asdict(item) for item in limitation_records],
        }
        return cls(evidence_id=_content_id("evidence", body), **{
            "candidate_id": candidate_id,
            "evidence_kind": evidence_kind,
            "capability": capability,
            "operational_status": operational_status,
            "scientific_verdict": scientific_verdict,
            "applicability": applicability,
            "uncertainty": uncertainty,
            "limitations": limitations,
            "artifact_ids": artifact_ids,
            "protocol_id": protocol_id,
            "provenance": provenance,
            "payload": payload,
            "legacy_stage": legacy_stage,
            "source_bindings": source_bindings,
            "artifact_bindings": artifact_bindings,
            "model_identity": model_identity,
            "model_lineage": model_lineage,
            "protocol_identity": protocol_identity,
            "limitation_records": limitation_records,
        })

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["operational_status"] = self.operational_status.value
        row["scientific_verdict"] = self.scientific_verdict.value
        row["applicability"]["domain_status"] = self.applicability.domain_status.value
        row["applicability"]["basis_evidence_ids"] = list(
            self.applicability.basis_evidence_ids
        )
        row["applicability"]["limitations"] = list(self.applicability.limitations)
        row["limitations"] = list(self.limitations)
        row["artifact_ids"] = list(self.artifact_ids)
        row["source_bindings"] = [asdict(item) for item in self.source_bindings]
        row["artifact_bindings"] = [asdict(item) for item in self.artifact_bindings]
        row["model_identity"] = asdict(self.model_identity) if self.model_identity else None
        row["model_lineage"] = asdict(self.model_lineage) if self.model_lineage else None
        row["protocol_identity"] = asdict(self.protocol_identity) if self.protocol_identity else None
        row["limitation_records"] = [asdict(item) for item in self.limitation_records]
        return row


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: str
    candidate_id: str
    claim_kind: str
    scientific_verdict: ScientificVerdict
    evidence_ids: tuple[str, ...]
    applicability: Applicability
    uncertainty: Uncertainty
    limitations: tuple[str, ...]
    protocol_id: str | None
    schema_version: str = CLAIM_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        candidate_id: str,
        claim_kind: str,
        scientific_verdict: ScientificVerdict,
        evidence_ids: tuple[str, ...],
        applicability: Applicability,
        uncertainty: Uncertainty | None = None,
        limitations: tuple[str, ...] = (),
        protocol_id: str | None = None,
    ) -> "ClaimRecord":
        if not candidate_id.strip() or not claim_kind.strip():
            raise ValueError("candidate_id and claim_kind must be non-empty")
        if scientific_verdict is ScientificVerdict.PASS:
            if not evidence_ids:
                raise ValueError("PASS claim requires supporting evidence")
            if applicability.domain_status is DomainStatus.UNQUALIFIED:
                raise ValueError("PASS claim requires qualified applicability")
        uncertainty = uncertainty or Uncertainty()
        body = {
            "schema_version": CLAIM_SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "claim_kind": claim_kind,
            "scientific_verdict": scientific_verdict.value,
            "evidence_ids": list(evidence_ids),
            "applicability": {
                "claim_kind": applicability.claim_kind,
                "domain_status": applicability.domain_status.value,
                "basis_evidence_ids": list(applicability.basis_evidence_ids),
                "limitations": list(applicability.limitations),
            },
            "uncertainty": {
                "status": uncertainty.status,
                "reason": uncertainty.reason,
                "metrics": dict(uncertainty.metrics),
            },
            "limitations": list(limitations),
            "protocol_id": protocol_id,
        }
        return cls(
            claim_id=_content_id("claim", body),
            candidate_id=candidate_id,
            claim_kind=claim_kind,
            scientific_verdict=scientific_verdict,
            evidence_ids=evidence_ids,
            applicability=applicability,
            uncertainty=uncertainty,
            limitations=limitations,
            protocol_id=protocol_id,
        )
