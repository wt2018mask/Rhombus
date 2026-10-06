"""Exact weighted small-cell ensemble schedule for cubic Al-LLZO occupancies."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product

from rudeus.science.contracts import Record


CUBIC_LLZO_WEIGHTED_ENSEMBLE_VERSION = (
    "known-material-cubic-llzo-weighted-ensemble-v1"
)


@dataclass(frozen=True, kw_only=True)
class WeightedCubicLlzoCountPattern(Record):
    member_index: int
    li1_count: int
    al1_count: int
    li2_count: int
    weight_numerator: int
    weight_denominator: int

    @property
    def weight(self) -> Fraction:
        return Fraction(self.weight_numerator, self.weight_denominator)


def _upper_probability(occupancy: str, site_count: int) -> tuple[int, Fraction]:
    expected = Fraction(occupancy) * site_count
    lower = expected.numerator // expected.denominator
    return lower, expected - lower


def build_exact_weighted_cubic_llzo_count_patterns(
) -> tuple[WeightedCubicLlzoCountPattern, ...]:
    # Two conventional cells contain 48 Li1/Al1 sites and 192 Li2 sites.
    # The COD refinement declares only marginal occupancies for these site pools.
    li1_lower, li1_upper_p = _upper_probability("0.54", 48)
    al1_lower, al1_upper_p = _upper_probability("0.06530", 48)
    li2_lower, li2_upper_p = _upper_probability("0.37", 192)

    probabilities = (li1_upper_p, al1_upper_p, li2_upper_p)
    patterns = []
    for member_index, bits in enumerate(product((0, 1), repeat=3)):
        weight = Fraction(1, 1)
        for bit, upper_p in zip(bits, probabilities):
            weight *= upper_p if bit else (1 - upper_p)
        patterns.append(
            WeightedCubicLlzoCountPattern(
                member_index=member_index,
                li1_count=li1_lower + bits[0],
                al1_count=al1_lower + bits[1],
                li2_count=li2_lower + bits[2],
                weight_numerator=weight.numerator,
                weight_denominator=weight.denominator,
            )
        )
    return tuple(patterns)
