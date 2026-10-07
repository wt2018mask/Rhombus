from __future__ import annotations

import pytest

from rhombus.domain import (
    CompositionDescriptor,
    DistanceCalibration,
    ReferenceStructure,
    StructuralDescriptor,
    assess_reference_coverage,
    classify_coverage,
)
from rhombus.evidence import DomainStatus


def _s(a: float) -> StructuralDescriptor:
    return StructuralDescriptor(
        composition=CompositionDescriptor.from_count_mapping({3: 1, 8: 1}),
        cell_lengths=(a, 5.0, 5.0),
        cell_angles_deg=(90.0, 90.0, 90.0),
        volume_per_atom=10.0,
    )


def test_reference_coverage_is_deterministic_and_nearest_bound() -> None:
    coverage = assess_reference_coverage(
        candidate=_s(5.1),
        references=(
            ReferenceStructure("ref:b", _s(6.0)),
            ReferenceStructure("ref:a", _s(5.0)),
        ),
        reference_set_id="set:test-v1",
    )
    assert coverage.reference_count == 2
    assert coverage.nearest_reference_id == "ref:a"
    assert coverage.nearest_distance < coverage.maximum_distance
    assert tuple(row[0] for row in coverage.distances) == ("ref:a", "ref:b")


def test_calibration_requires_evidence_and_exact_reference_set() -> None:
    with pytest.raises(ValueError, match="supporting evidence"):
        DistanceCalibration(
            calibration_id="cal:test",
            reference_set_id="set:test-v1",
            claim_kind="finite_temperature_stability",
            in_domain_max_distance=0.1,
            near_ood_max_distance=0.2,
            evidence_ids=(),
            method="independent held-out error-distance calibration",
        )

    coverage = assess_reference_coverage(
        candidate=_s(5.1),
        references=(ReferenceStructure("ref:a", _s(5.0)),),
        reference_set_id="set:test-v1",
    )
    calibration = DistanceCalibration(
        calibration_id="cal:test",
        reference_set_id="set:other",
        claim_kind="finite_temperature_stability",
        in_domain_max_distance=0.1,
        near_ood_max_distance=0.2,
        evidence_ids=("evidence:sha256:" + "a" * 64,),
        method="independent held-out error-distance calibration",
    )
    with pytest.raises(ValueError, match="reference_set_id"):
        classify_coverage(coverage=coverage, calibration=calibration)


def test_calibrated_domain_status_uses_explicit_thresholds_only() -> None:
    refs=(ReferenceStructure("ref:a", _s(5.0)),)
    cal=DistanceCalibration(
        calibration_id="cal:test",
        reference_set_id="set:test-v1",
        claim_kind="finite_temperature_stability",
        in_domain_max_distance=0.01,
        near_ood_max_distance=0.03,
        evidence_ids=("evidence:sha256:" + "b" * 64,),
        method="independent held-out error-distance calibration",
    )

    inside=classify_coverage(
        coverage=assess_reference_coverage(candidate=_s(5.02), references=refs, reference_set_id="set:test-v1"),
        calibration=cal,
    )
    near=classify_coverage(
        coverage=assess_reference_coverage(candidate=_s(5.5), references=refs, reference_set_id="set:test-v1"),
        calibration=cal,
    )
    far=classify_coverage(
        coverage=assess_reference_coverage(candidate=_s(8.0), references=refs, reference_set_id="set:test-v1"),
        calibration=cal,
    )

    assert inside.applicability.domain_status is DomainStatus.IN_DOMAIN
    assert near.applicability.domain_status is DomainStatus.NEAR_OOD
    assert far.applicability.domain_status is DomainStatus.FAR_OOD
    assert inside.applicability.basis_evidence_ids == cal.evidence_ids
