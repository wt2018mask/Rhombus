"""Compute a deterministic integer-rationalization error frontier for occupancies."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from rudeus.science.contracts import Record
from rudeus.science.known_material_occupancy_integrality import OccupancySiteConstraint


OCCUPANCY_ERROR_FRONTIER_VERSION = "known-material-occupancy-error-frontier-v1"


@dataclass(frozen=True, kw_only=True)
class OccupancyApproximation(Record):
    site_id: str
    replicas: int
    integer_count: int
    approximated_occupancy: str
    absolute_error: str


@dataclass(frozen=True, kw_only=True)
class OccupancyFrontierPoint(Record):
    replicas: int
    approximations: tuple[OccupancyApproximation, ...]
    max_absolute_error: str


def nearest_integer_occupancy_frontier(
    constraints: tuple[OccupancySiteConstraint, ...],
    replicas: tuple[int, ...],
) -> tuple[OccupancyFrontierPoint, ...]:
    if not constraints or not replicas:
        raise ValueError("frontier requires occupancy constraints and replica counts")
    if any(n <= 0 for n in replicas) or tuple(sorted(set(replicas))) != replicas:
        raise ValueError("replica counts must be positive, unique, and ascending")
    points = []
    for n in replicas:
        approximations = []
        errors = []
        for item in constraints:
            target = Decimal(item.occupancy_decimal)
            slots = item.multiplicity * n
            integer_count = int(
                (target * slots).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            approx = Decimal(integer_count) / Decimal(slots)
            error = abs(approx - target)
            errors.append(error)
            approximations.append(OccupancyApproximation(
                site_id=item.site_id,
                replicas=n,
                integer_count=integer_count,
                approximated_occupancy=format(approx, "f"),
                absolute_error=format(error, "f"),
            ))
        points.append(OccupancyFrontierPoint(
            replicas=n,
            approximations=tuple(approximations),
            max_absolute_error=format(max(errors), "f"),
        ))
    return tuple(points)
