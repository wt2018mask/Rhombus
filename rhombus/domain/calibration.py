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
    min_reference_count: int
    evidence_ids: tuple[str, ...]
    method: str
    leave_group_out_validated: bool

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
        if self.min_reference_count <= 0:
            raise ValueError("min_reference_count must be positive")
        if not self.method.strip():
            raise ValueError("calibration method must be non-empty")


@dataclass(frozen=True)
class CalibratedApplicability:
    applicability: Applicability
    calibration_id: str
    reference_set_id: str
    nearest_reference_id: str
    nearest_distance: float
    kth_distance: float
    k: int


def classify_coverage(
    *,
    coverage: ReferenceCoverage,
    calibration: DistanceCalibration,
) -> CalibratedApplicability:
    """Classify coverage conservatively under an explicit calibration contract.

    Positive applicability requires supporting calibration evidence,
    leave-group-out validation, and enough reference structures. Otherwise the
    candidate remains UNQUALIFIED even if its raw distance is small.
    """

    if coverage.reference_set_id != calibration.reference_set_id:
        raise ValueError("coverage and calibration reference_set_id must match")

    calibrated = bool(calibration.evidence_ids) and calibration.leave_group_out_validated
    enough_references = coverage.reference_count >= calibration.min_reference_count

    if not calibrated or not enough_references:
        limitations: list[str] = []
        if not calibration.evidence_ids:
            limitations.append("calibration evidence IDs are missing")
        if not calibration.leave_group_out_validated:
            limitations.append("leave-group-out calibration is not validated")
        if not enough_references:
            limitations.append(
                "reference coverage is below the calibration minimum "
                f"({coverage.reference_count} < {calibration.min_reference_count})"
            )
        status = DomainStatus.UNQUALIFIED
    else:
        limitations = [
            "Domain status is valid only for the exact reference set, descriptor "
            "definition, distance function, claim kind, and calibration contract."
        ]
        distance = coverage.kth_distance
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
        limitations=tuple(limitations),
    )
    return CalibratedApplicability(
        applicability=applicability,
        calibration_id=calibration.calibration_id,
        reference_set_id=coverage.reference_set_id,
        nearest_reference_id=coverage.nearest_reference_id,
        nearest_distance=coverage.nearest_distance,
        kth_distance=coverage.kth_distance,
        k=coverage.k,
    )
