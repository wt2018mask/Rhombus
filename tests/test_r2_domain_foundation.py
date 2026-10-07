from __future__ import annotations

import json
from pathlib import Path

from rhombus.domain import (
    CompositionDescriptor,
    ModelElementDomain,
    assess_element_coverage,
)
from rhombus.evidence import DomainStatus


ROOT = Path(__file__).resolve().parents[1]


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_composition_descriptor_is_deterministic() -> None:
    descriptor = CompositionDescriptor.from_atomic_numbers([3, 8, 13, 8, 3])

    assert descriptor.total_atoms == 5
    assert descriptor.element_count == 3
    assert descriptor.element_counts == ((3, 2), (8, 2), (13, 1))
    assert descriptor.atomic_numbers == (3, 8, 13)
    assert descriptor.atomic_number_min == 3
    assert descriptor.atomic_number_max == 13


def test_exact_model_snapshot_builds_element_domain() -> None:
    snapshot = _load(
        "data/benchmarks/known_material/model_domains/medium-mpa-0-domain-v1.json"
    )
    index = _load(
        "data/benchmarks/known_material/model_domain_snapshot_index_v1.json"
    )
    row = index["entries"][0]
    domain = ModelElementDomain.from_snapshot(
        snapshot, snapshot_content_hash=row["snapshot_content_hash"]
    )

    assert domain.model_id == "medium-mpa-0"
    assert domain.checkpoint_sha256 == row["checkpoint_sha256"]
    assert domain.snapshot_content_hash == row["snapshot_content_hash"]
    assert 3 in domain.supported_atomic_numbers
    assert 8 in domain.supported_atomic_numbers


def test_supported_elements_remain_unqualified_not_in_domain() -> None:
    snapshot = _load(
        "data/benchmarks/known_material/model_domains/medium-mpa-0-domain-v1.json"
    )
    domain = ModelElementDomain.from_snapshot(snapshot)
    descriptor = CompositionDescriptor.from_count_mapping({3: 1, 13: 1, 8: 2})

    assessment = assess_element_coverage(
        descriptor=descriptor,
        domain=domain,
        claim_kind="finite_temperature_stability",
    )

    assert assessment.domain_status is DomainStatus.UNQUALIFIED
    assert assessment.unsupported_atomic_numbers == ()
    assert assessment.applicability.claim_kind == "finite_temperature_stability"
    assert any(
        "does not establish" in limitation
        for limitation in assessment.applicability.limitations
    )


def test_unsupported_element_fails_closed_as_far_ood() -> None:
    snapshot = _load(
        "data/benchmarks/known_material/model_domains/medium-mpa-0-domain-v1.json"
    )
    domain = ModelElementDomain.from_snapshot(snapshot)
    descriptor = CompositionDescriptor.from_atomic_numbers([3, 8, 84])

    assessment = assess_element_coverage(
        descriptor=descriptor,
        domain=domain,
        claim_kind="finite_temperature_stability",
    )

    assert assessment.domain_status is DomainStatus.FAR_OOD
    assert assessment.unsupported_atomic_numbers == (84,)
    assert assessment.assessment_level == "ELEMENT_COVERAGE_PREFLIGHT"
