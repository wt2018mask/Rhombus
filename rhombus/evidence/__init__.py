"""Rhombus 2.0 evidence ledger primitives and compatibility views."""

from .identity import (
    ArtifactBinding,
    Limitation,
    ModelIdentity,
    ModelLineage,
    ProtocolIdentity,
    SourceBinding,
)
from .legacy import adapt_legacy_evidence, adapt_legacy_evidence_records
from .schema import (
    Applicability,
    ClaimRecord,
    DomainStatus,
    EvidenceRecord,
    OperationalStatus,
    ScientificVerdict,
    Uncertainty,
)

__all__ = [
    "Applicability",
    "ArtifactBinding",
    "ClaimRecord",
    "DomainStatus",
    "EvidenceRecord",
    "Limitation",
    "ModelIdentity",
    "ModelLineage",
    "OperationalStatus",
    "ProtocolIdentity",
    "ScientificVerdict",
    "SourceBinding",
    "Uncertainty",
    "adapt_legacy_evidence",
    "adapt_legacy_evidence_records",
]
