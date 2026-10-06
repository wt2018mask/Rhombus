"""Ensemble diversity contract tests."""
from dataclasses import replace

import pytest

from rudeus.science.known_material_ensemble_diversity import (
    ENSEMBLE_DIVERSITY_VERSION,
    EnsembleDiversityEvidence,
    EnsembleRealizationEvidence,
)


def member(i):
    return EnsembleRealizationEvidence(
        realization_hash=f"{i:064x}",
        site_assignment_hash=f"{i + 100:064x}",
        generation_seed=i,
        generator_version="test-generator-v1",
    )


def evidence():
    return EnsembleDiversityEvidence(
        evidence_version=ENSEMBLE_DIVERSITY_VERSION,
        realizations=(member(1), member(2)),
        source_structure_hash="a" * 64,
        generation_policy_hash="b" * 64,
    )


def test_ensemble_diversity_accepts_distinct_reproducible_members():
    evidence().validate()


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("realization_hash", "structures must be unique"),
        ("site_assignment_hash", "site assignments must be unique"),
        ("generation_seed", "generation seeds must be unique"),
    ),
)
def test_ensemble_diversity_rejects_duplicate_evidence(field, message):
    first = member(1)
    second = replace(member(2), **{field: getattr(first, field)})
    with pytest.raises(ValueError, match=message):
        replace(evidence(), realizations=(first, second))
