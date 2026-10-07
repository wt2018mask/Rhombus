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


def _coverage():
    return assess_reference_coverage(
        candidate=_s(5.0),
        references=(
            ReferenceStructure("ref:a", _s(5.0), group_id="family:a"),
            ReferenceStructure("ref:b", _s(5.2), group_id="family:b"),
            ReferenceStructure("ref:c", _s(5.4), group_id="family:c"),
            ReferenceStructure("ref:d", _s(6.0), group_id="family:d"),
        ),
        reference_set_id="set:test-v1",
        k=3,
    )


def test_reference_coverage_is_deterministic_and_k_neighbor_bound() -> None:
    coverage = _coverage()

    assert coverage.reference_count == 4
    assert coverage.nearest_reference_id == "ref:a"
    assert coverage.nearest_distance <= coverage.kth_distance
    assert coverage.k == 3
    assert tuple(row[0] for row in coverage.distances)[:2] == ("ref:a", "ref:b")


def test_unvalidated_calibration_cannot_promote_in_domain() -> None:
    coverage = _coverage()
    calibration = DistanceCalibration(
        calibration_id="cal:test",
        reference_set_id="set:test-v1",
        claim_kind="finite_temperature_stability",
        in_domain_max_distance=1.0,
        near_ood_max_distance=2.0,
        min_reference_count=3,
        evidence_ids=("evidence:sha256:" + "a" * 64,),
        method="synthetic-contract-test",
        leave_group_out_validated=False,
    )

    result = classify_coverage(coverage=coverage, calibration=calibration)

    assert result.applicability.domain_status is DomainStatus.UNQUALIFIED
    assert any(
        "leave-group-out" in item for item in result.applicability.limitations
    )


def test_missing_calibration_evidence_cannot_promote_in_domain() -> None:
    coverage = _coverage()
    calibration = DistanceCalibration(
        calibration_id="cal:test",
        reference_set_id="set:test-v1",
        claim_kind="finite_temperature_stability",
        in_domain_max_distance=1.0,
        near_ood_max_distance=2.0,
        min_reference_count=3,
        evidence_ids=(),
        method="synthetic-contract-test",
        leave_group_out_validated=True,
    )

    result = classify_coverage(coverage=coverage, calibration=calibration)

    assert result.applicability.domain_status is DomainStatus.UNQUALIFIED


def test_too_few_references_cannot_promote_in_domain() -> None:
    coverage = _coverage()
    calibration = DistanceCalibration(
        calibration_id="cal:test",
        reference_set_id="set:test-v1",
        claim_kind="finite_temperature_stability",
        in_domain_max_distance=1.0,
        near_ood_max_distance=2.0,
        min_reference_count=10,
        evidence_ids=("evidence:sha256:" + "b" * 64,),
        method="leave-group-out-synthetic-contract-test",
        leave_group_out_validated=True,
    )

    result = classify_coverage(coverage=coverage, calibration=calibration)

    assert result.applicability.domain_status is DomainStatus.UNQUALIFIED


def test_validated_calibration_uses_kth_distance_for_status() -> None:
    coverage = _coverage()
    d = coverage.kth_distance
    calibration = DistanceCalibration(
        calibration_id="cal:validated",
        reference_set_id="set:test-v1",
        claim_kind="finite_temperature_stability",
        in_domain_max_distance=d,
        near_ood_max_distance=d + 1.0,
        min_reference_count=4,
        evidence_ids=("evidence:sha256:" + "c" * 64,),
        method="leave-group-out-synthetic-contract-test",
        leave_group_out_validated=True,
    )

    result = classify_coverage(coverage=coverage, calibration=calibration)

    assert result.applicability.domain_status is DomainStatus.IN_DOMAIN
    assert result.kth_distance == pytest.approx(d)
    assert result.k == 3
    assert result.applicability.basis_evidence_ids == calibration.evidence_ids


def test_reference_set_mismatch_fails_closed() -> None:
    coverage = _coverage()
    calibration = DistanceCalibration(
        calibration_id="cal:mismatch",
        reference_set_id="set:other",
        claim_kind="finite_temperature_stability",
        in_domain_max_distance=0.1,
        near_ood_max_distance=0.2,
        min_reference_count=1,
        evidence_ids=("evidence:sha256:" + "d" * 64,),
        method="leave-group-out-synthetic-contract-test",
        leave_group_out_validated=True,
    )

    with pytest.raises(ValueError, match="reference_set_id"):
        classify_coverage(coverage=coverage, calibration=calibration)
