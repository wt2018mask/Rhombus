"""Explicit distance-to-domain calibration contracts.

Thresholds are supplied only after independent calibration. This module does
not learn thresholds from the candidate being assessed and does not infer them
from a small benchmark cohort.
"""

from __future__ import annotations

from dataclasses import dataclass

from rhombus.evidence import Applicability, DomainStatus

from .coverage import ReferenceCoverage


@dataclass(frozen=True)
class DistanceCalibration:
    calibration_id: str
    reference_set_id: str
    claim_kind: str
    in_domain_max_distance: float
    near_ood_max_distance: float
    evidence_ids: tuple[str, ...]
    method: str

    def __post_init__(self) -> None:
        if not self.calibration_id.strip():
            raise ValueError("calibration_id must be non-empty")
        if not self.reference_set_id.strip():
            raise ValueError("reference_set_id must be non-empty")
        if not self.claim_kind.strip():
            raise ValueError("claim_kind must be non-empty")
        if self.in_domain_max_distance < 0:
            raise ValueError("in_domain_max_distance must be non-negative")
        if self.near_ood_max_distance < self.in_domain_max_distance:
            raise ValueError(
                "near_ood_max_distance must be >= in_domain_max_distance"
            )
        if not self.evidence_ids:
            raise ValueError("calibration requires supporting evidence_ids")
        if not self.method.strip():
            raise ValueError("calibration method must be non-empty")


@dataclass(frozen=True)
class CalibratedApplicability:
    applicability: Applicability
    calibration_id: str
    reference_set_id: str
    nearest_reference_id: str
    nearest_distance: float


def classify_coverage(
    *,
    coverage: ReferenceCoverage,
    calibration: DistanceCalibration,
) -> CalibratedApplicability:
    if coverage.reference_set_id != calibration.reference_set_id:
        raise ValueError("coverage and calibration reference_set_id must match")

    distance = coverage.nearest_distance
    if distance <= calibration.in_domain_max_distance:
        status = DomainStatus.IN_DOMAIN
    elif distance <= calibration.near_ood_max_distance:
        status = DomainStatus.NEAR_OOD
    else:
        status = DomainStatus.FAR_OOD

    applicability = Applicability(
        claim_kind=calibration.claim_kind,
        domain_status=status,
        basis_evidence_ids=calibration.evidence_ids,
        limitations=(
            "Domain status is valid only for the exact reference set, descriptor "
            "definition, distance function, claim kind, and calibration contract.",
        ),
    )
    return CalibratedApplicability(
        applicability=applicability,
        calibration_id=calibration.calibration_id,
        reference_set_id=coverage.reference_set_id,
        nearest_reference_id=coverage.nearest_reference_id,
        nearest_distance=distance,
    )
