"""Claim-specific applicability preflight from frozen model-domain snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from rhombus.evidence import Applicability, DomainStatus

from .descriptors import CompositionDescriptor


@dataclass(frozen=True)
class ModelElementDomain:
    domain_key: str
    model_id: str
    checkpoint_sha256: str
    supported_atomic_numbers: frozenset[int]
    snapshot_version: str
    snapshot_content_hash: str | None = None

    @classmethod
    def from_snapshot(
        cls,
        snapshot: Mapping[str, Any],
        *,
        snapshot_content_hash: str | None = None,
    ) -> "ModelElementDomain":
        supported = snapshot.get("supported_atomic_numbers")
        if not isinstance(supported, list) or not supported:
            raise ValueError("domain snapshot requires supported_atomic_numbers")
        if any((not isinstance(z, int)) or z < 1 or z > 118 for z in supported):
            raise ValueError("supported_atomic_numbers must be integers in [1, 118]")

        domain_key = str(snapshot.get("domain_key", "")).strip()
        model_id = str(snapshot.get("model_id", "")).strip()
        checkpoint = str(snapshot.get("checkpoint_sha256", "")).strip()
        version = str(snapshot.get("snapshot_version", "")).strip()
        if not domain_key or not model_id or not checkpoint or not version:
            raise ValueError(
                "domain snapshot requires domain_key, model_id, checkpoint_sha256, "
                "and snapshot_version"
            )
        return cls(
            domain_key=domain_key,
            model_id=model_id,
            checkpoint_sha256=checkpoint,
            supported_atomic_numbers=frozenset(supported),
            snapshot_version=version,
            snapshot_content_hash=snapshot_content_hash,
        )


@dataclass(frozen=True)
class ApplicabilityAssessment:
    applicability: Applicability
    candidate_descriptor: CompositionDescriptor
    unsupported_atomic_numbers: tuple[int, ...]
    domain_key: str
    model_id: str
    checkpoint_sha256: str
    assessment_level: str = "ELEMENT_COVERAGE_PREFLIGHT"

    @property
    def domain_status(self) -> DomainStatus:
        return self.applicability.domain_status


def assess_element_coverage(
    *,
    descriptor: CompositionDescriptor,
    domain: ModelElementDomain,
    claim_kind: str,
) -> ApplicabilityAssessment:
    """Return a conservative claim-specific model applicability preflight.

    Element coverage can prove obvious incompatibility, but element inclusion
    alone is not enough to prove IN_DOMAIN. Therefore supported compositions
    remain UNQUALIFIED until structural/chemical distance evidence is added.
    """

    if not claim_kind.strip():
        raise ValueError("claim_kind must be non-empty")
    unsupported = tuple(
        z for z in descriptor.atomic_numbers if z not in domain.supported_atomic_numbers
    )
    if unsupported:
        status = DomainStatus.FAR_OOD
        limitations = (
            "Candidate contains atomic numbers absent from the exact frozen model "
            "element domain.",
            "No atomistic claim should be promoted using this model without a "
            "different qualified model or explicit superseding evidence.",
        )
    else:
        status = DomainStatus.UNQUALIFIED
        limitations = (
            "All candidate elements are represented by the model, but element "
            "coverage alone does not establish structural or chemical IN_DOMAIN status.",
            "Phase 3 distance/coverage calibration evidence is still required.",
        )

    applicability = Applicability(
        claim_kind=claim_kind,
        domain_status=status,
        limitations=limitations,
    )
    return ApplicabilityAssessment(
        applicability=applicability,
        candidate_descriptor=descriptor,
        unsupported_atomic_numbers=unsupported,
        domain_key=domain.domain_key,
        model_id=domain.model_id,
        checkpoint_sha256=domain.checkpoint_sha256,
    )
