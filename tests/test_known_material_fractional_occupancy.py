"""Fractional-occupancy execution contract tests."""
from dataclasses import replace

import pytest

from rudeus.science.known_material_fractional_occupancy import (
    FRACTIONAL_OCCUPANCY_STRATEGY_VERSION,
    FractionalOccupancyExecutionStrategy,
)


def valid_strategy():
    return FractionalOccupancyExecutionStrategy(
        strategy_version=FRACTIONAL_OCCUPANCY_STRATEGY_VERSION,
        source_artifact_hash="1" * 64,
        realization_hashes=("2" * 64, "3" * 64),
        realization_weights=(0.5, 0.5),
        composition_preserved=True,
        occupancy_statistics_preserved=True,
        deterministic_generation=True,
        generation_method="evidence-bound-test-method",
        provenance_refs=("artifact:source", "method:test"),
        bias_assessment=("multiple realizations avoid a single silent ordered proxy",),
    )


def test_fractional_occupancy_strategy_requires_multiple_realizations():
    with pytest.raises(ValueError, match="multiple realizations"):
        replace(
            valid_strategy(),
            realization_hashes=("2" * 64,),
            realization_weights=(1.0,),
        )


def test_fractional_occupancy_strategy_rejects_invalid_weights():
    with pytest.raises(ValueError, match="sum to one"):
        replace(valid_strategy(), realization_weights=(0.7, 0.7))


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("composition_preserved", "preserve benchmark composition"),
        ("occupancy_statistics_preserved", "preserve declared occupancy statistics"),
        ("deterministic_generation", "reproducible"),
    ),
)
def test_fractional_occupancy_strategy_fails_closed_on_scientific_invariants(
    field, message
):
    with pytest.raises(ValueError, match=message):
        replace(valid_strategy(), **{field: False})


def test_fractional_occupancy_strategy_requires_bias_assessment():
    with pytest.raises(ValueError, match="representation-bias"):
        replace(valid_strategy(), bias_assessment=())
