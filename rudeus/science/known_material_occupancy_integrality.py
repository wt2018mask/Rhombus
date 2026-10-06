"""Exact integrality analysis for fractional crystallographic occupancies."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import gcd, lcm

from rudeus.science.contracts import Record


OCCUPANCY_INTEGRALITY_VERSION = "known-material-occupancy-integrality-v1"


@dataclass(frozen=True, kw_only=True)
class OccupancySiteConstraint(Record):
    site_id: str
    multiplicity: int
    occupancy_decimal: str

    def validate(self):
        super().validate()
        if not self.site_id or self.multiplicity <= 0:
            raise ValueError("occupancy constraint requires site identity and multiplicity")
        value = Fraction(self.occupancy_decimal)
        if value < 0 or value > 1:
            raise ValueError("occupancy must lie in [0, 1]")


@dataclass(frozen=True, kw_only=True)
class OccupancyIntegralityAnalysis(Record):
    analysis_version: str
    minimum_conventional_cell_replicas: int
    exact_integer_counts: tuple[int, ...]


def analyze_exact_occupancy_integrality(
    constraints: tuple[OccupancySiteConstraint, ...],
) -> OccupancyIntegralityAnalysis:
    if not constraints:
        raise ValueError("occupancy integrality analysis requires constraints")
    replicas = 1
    fractions = []
    for item in constraints:
        count = Fraction(item.occupancy_decimal) * item.multiplicity
        fractions.append(count)
        replicas = lcm(replicas, count.denominator)
    counts = tuple(int(count * replicas) for count in fractions)
    return OccupancyIntegralityAnalysis(
        analysis_version=OCCUPANCY_INTEGRALITY_VERSION,
        minimum_conventional_cell_replicas=replicas,
        exact_integer_counts=counts,
    )
