"""Source-bound weighted cubic Al-LLZO representation evidence tests."""
from fractions import Fraction
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_weighted_evidence import (
    CORRELATION_SCOPE,
    build_cubic_llzo_weighted_representation_evidence,
)


CIF = Path(
    "data/benchmarks/known_material/structures/cod/7215448-r176453.cif"
)
SOURCE_HASH = "db5f259f418edca7111136c0bc3a48b7f7cccde87411d54c48ebf71821217eec"


def test_weighted_representation_evidence_binds_source_and_exact_weights():
    evidence = build_cubic_llzo_weighted_representation_evidence(
        CIF, source_artifact_hash=SOURCE_HASH
    )

    assert evidence.source_artifact_hash == SOURCE_HASH
    assert evidence.correlation_scope == CORRELATION_SCOPE
    assert len(evidence.bindings) == 8
    assert sum((item.weight for item in evidence.bindings), Fraction(0, 1)) == 1
    assert len({item.structure_hash for item in evidence.bindings}) == 8
    assert len({item.assignment_hash for item in evidence.bindings}) == 8


def test_weighted_representation_evidence_preserves_declared_marginals_without_correlation_claim():
    evidence = build_cubic_llzo_weighted_representation_evidence(
        CIF, source_artifact_hash=SOURCE_HASH
    )

    assert (
        evidence.declared_li1_occupancy,
        evidence.declared_al1_occupancy,
        evidence.declared_li2_occupancy,
    ) == ("0.54", "0.06530", "0.37")
    assert evidence.weighted_li_formula == "6.06"
    assert evidence.weighted_al_formula == "0.1959"
    assert evidence.reported_li_formula == "6.060"
    assert evidence.reported_al_formula == "0.196"
    assert "DOES_NOT_RESOLVE_CORRELATIONS" in evidence.correlation_scope


def test_weighted_representation_evidence_is_reproducible():
    first = build_cubic_llzo_weighted_representation_evidence(
        CIF, source_artifact_hash=SOURCE_HASH
    )
    second = build_cubic_llzo_weighted_representation_evidence(
        CIF, source_artifact_hash=SOURCE_HASH
    )
    assert first == second
