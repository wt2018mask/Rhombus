"""Small-cell ensemble occupancy averaging diagnostics."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rudeus.science.contracts import Record
from rudeus.science.known_material_occupancy_integrality import OccupancySiteConstraint


@dataclass(frozen=True, kw_only=True)
class EnsembleOccupancyApproximation(Record):
    site_id: str
    replicas_per_realization: int
    realization_count: int
    lower_integer_count: int
    upper_integer_count: int
    upper_realization_count: int
    ensemble_average_occupancy: str
    absolute_error: str


def nearest_equal_weight_ensemble_average(
    constraint: OccupancySiteConstraint,
    *,
    replicas_per_realization: int,
    realization_count: int,
) -> EnsembleOccupancyApproximation:
    if replicas_per_realization <= 0 or realization_count < 2:
        raise ValueError("ensemble requires positive replicas and at least two realizations")
    target = Decimal(constraint.occupancy_decimal)
    slots = constraint.multiplicity * replicas_per_realization
    scaled = target * slots
    lower = int(scaled)
    upper = lower if scaled == lower else lower + 1
    if lower == upper:
        upper_members = 0
    else:
        ideal_upper = (scaled - Decimal(lower)) * realization_count
        upper_members = int(ideal_upper + Decimal("0.5"))
        upper_members = max(0, min(realization_count, upper_members))
    total_atoms = lower * (realization_count - upper_members) + upper * upper_members
    average = Decimal(total_atoms) / Decimal(slots * realization_count)
    return EnsembleOccupancyApproximation(
        site_id=constraint.site_id,
        replicas_per_realization=replicas_per_realization,
        realization_count=realization_count,
        lower_integer_count=lower,
        upper_integer_count=upper,
        upper_realization_count=upper_members,
        ensemble_average_occupancy=format(average, "f"),
        absolute_error=format(abs(average - target), "f"),
    )
