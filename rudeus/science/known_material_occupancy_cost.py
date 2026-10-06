"""Composition and atom-count diagnostics for occupancy rationalization."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rudeus.science.contracts import Record
from rudeus.science.known_material_occupancy_frontier import OccupancyFrontierPoint


@dataclass(frozen=True, kw_only=True)
class RationalizationCostPoint(Record):
    replicas: int
    variable_atom_count: int
    fixed_atom_count: int
    total_atom_count: int
    formula_li: str
    formula_al: str
    formula_li_absolute_error: str
    formula_al_absolute_error: str


def cubic_al_llzo_cost_point(point: OccupancyFrontierPoint) -> RationalizationCostPoint:
    by_site = {item.site_id: item for item in point.approximations}
    if set(by_site) != {"Li1", "Al1", "Li2"}:
        raise ValueError("cubic Al-LLZO diagnostics require Li1, Al1, and Li2")
    n = point.replicas
    li = by_site["Li1"].integer_count + by_site["Li2"].integer_count
    al = by_site["Al1"].integer_count
    # The conventional Ia-3d cell has Z=8: La24 Zr16 O96 are fully occupied.
    fixed = 136 * n
    total = fixed + li + al
    formula_li = Decimal(li) / Decimal(8 * n)
    formula_al = Decimal(al) / Decimal(8 * n)
    target_li = Decimal("6.060")
    target_al = Decimal("0.196")
    return RationalizationCostPoint(
        replicas=n,
        variable_atom_count=li + al,
        fixed_atom_count=fixed,
        total_atom_count=total,
        formula_li=format(formula_li, "f"),
        formula_al=format(formula_al, "f"),
        formula_li_absolute_error=format(abs(formula_li - target_li), "f"),
        formula_al_absolute_error=format(abs(formula_al - target_al), "f"),
    )
