"""Diagnostic decomposition of cubic Al-LLZO raw-P0 failures.

This module is diagnostic only. It does not alter P0 thresholds, ensemble weights,
or material-level verdict semantics. It exposes why each exact-weighted ordered
member fails current composition/geometry checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rudeus.science.contracts import Record
from rudeus.science.known_material_cubic_llzo_coordinates import (
    extract_cubic_llzo_two_cell_coordinate_pools,
)
from rudeus.science.known_material_cubic_llzo_weighted_ordered import (
    build_weighted_cubic_llzo_ordered_structures,
)
from rudeus.science.known_material_cubic_llzo_weighted_plan import (
    build_weighted_cubic_llzo_realization_plans,
)


DIAGNOSTIC_VERSION = "known-material-cubic-llzo-p0-diagnostic-v1"
CLASH_RATIO = 0.60


@dataclass(frozen=True, kw_only=True)
class CubicLlzoMemberP0Diagnostic(Record):
    diagnostic_version: str
    member_index: int
    formula: str
    nominal_charge_residual: float
    min_li_li_distance: float
    min_li_li_pair_kind: str
    li_li_clash_pair_count: int
    min_allowed_li_li: float
    weight_numerator: int
    weight_denominator: int


def _pair_kind(i: int, j: int, *, host_count: int, li1_count: int, al1_count: int) -> str:
    li1_start = host_count
    al1_start = li1_start + li1_count
    li2_start = al1_start + al1_count

    def kind(index: int) -> str:
        if index < host_count:
            return "HOST"
        if index < al1_start:
            return "LI1"
        if index < li2_start:
            return "AL1"
        return "LI2"

    return "-".join(sorted((kind(i), kind(j))))


def build_cubic_llzo_p0_diagnostics(cif_path: Path) -> tuple[CubicLlzoMemberP0Diagnostic, ...]:
    members = build_weighted_cubic_llzo_ordered_structures(cif_path)
    plans = build_weighted_cubic_llzo_realization_plans()
    if len(members) != len(plans):
        raise ValueError("cubic LLZO diagnostic member/plan count mismatch")

    shared_pool, li2_pool = extract_cubic_llzo_two_cell_coordinate_pools(cif_path)
    _ = shared_pool, li2_pool  # provenance-bound pool extraction must succeed

    diagnostics = []
    for member, plan in zip(members, plans):
        structure = member.structure
        amounts = structure.composition.get_el_amt_dict()
        residual = (
            float(amounts.get("Li", 0.0))
            + 3.0 * float(amounts.get("La", 0.0))
            + 4.0 * float(amounts.get("Zr", 0.0))
            + 3.0 * float(amounts.get("Al", 0.0))
            - 2.0 * float(amounts.get("O", 0.0))
        )

        host_count = int(amounts["La"] + amounts["Zr"] + amounts["O"])
        li_indices = [
            i for i, site in enumerate(structure)
            if site.is_ordered and site.specie.symbol == "Li"
        ]
        li_radius = next(
            site.specie.atomic_radius
            for site in structure
            if site.is_ordered and site.specie.symbol == "Li"
        ) or 1.0
        min_allowed = float((li_radius + li_radius) * CLASH_RATIO)

        min_distance = float("inf")
        min_pair = ""
        clash_count = 0
        dm = structure.distance_matrix
        for offset, i in enumerate(li_indices):
            for j in li_indices[offset + 1:]:
                distance = float(dm[i, j])
                if distance < min_distance:
                    min_distance = distance
                    min_pair = _pair_kind(
                        i,
                        j,
                        host_count=host_count,
                        li1_count=len(plan.li1_indices),
                        al1_count=len(plan.al1_indices),
                    )
                if distance < min_allowed:
                    clash_count += 1

        diagnostics.append(
            CubicLlzoMemberP0Diagnostic(
                diagnostic_version=DIAGNOSTIC_VERSION,
                member_index=member.member_index,
                formula=str(structure.composition.reduced_formula),
                nominal_charge_residual=residual,
                min_li_li_distance=min_distance,
                min_li_li_pair_kind=min_pair,
                li_li_clash_pair_count=clash_count,
                min_allowed_li_li=min_allowed,
                weight_numerator=member.weight_numerator,
                weight_denominator=member.weight_denominator,
            )
        )
    return tuple(diagnostics)
