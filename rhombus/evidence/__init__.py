"""Rhombus 2.0 evidence ledger primitives and compatibility views."""

from .legacy import adapt_legacy_evidence
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
    "ClaimRecord",
    "DomainStatus",
    "EvidenceRecord",
    "OperationalStatus",
    "ScientificVerdict",
    "Uncertainty",
    "adapt_legacy_evidence",
]
