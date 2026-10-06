"""Deterministic site-assignment plans for the exact weighted cubic Al-LLZO ensemble."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from fractions import Fraction

from rudeus.science.contracts import Record
from rudeus.science.known_material_cubic_llzo_weighted_ensemble import (
    build_exact_weighted_cubic_llzo_count_patterns,
)
from rudeus.science.known_material_shared_site_assignment import (
    deterministic_shared_site_assignment,
)
from rudeus.science.known_material_site_assignment import (
    deterministic_site_assignment,
)


CUBIC_LLZO_WEIGHTED_PLAN_VERSION = "known-material-cubic-llzo-weighted-plan-v1"
WEIGHTING_ASSUMPTION = "independent-marginal-product-no-correlation-claim-v1"


@dataclass(frozen=True, kw_only=True)
class WeightedCubicLlzoRealizationPlan(Record):
    plan_version: str
    member_index: int
    weight_numerator: int
    weight_denominator: int
    weighting_assumption: str
    li1_indices: tuple[int, ...]
    al1_indices: tuple[int, ...]
    li2_indices: tuple[int, ...]
    assignment_hash: str

    @property
    def weight(self) -> Fraction:
        return Fraction(self.weight_numerator, self.weight_denominator)


def build_weighted_cubic_llzo_realization_plans(
) -> tuple[WeightedCubicLlzoRealizationPlan, ...]:
    plans = []
    for pattern in build_exact_weighted_cubic_llzo_count_patterns():
        shared = deterministic_shared_site_assignment(
            site_count=48,
            first_count=pattern.li1_count,
            second_count=pattern.al1_count,
            seed=pattern.member_index,
            namespace="weighted-Li1-Al1",
        )
        li2 = deterministic_site_assignment(
            site_count=192,
            occupied_count=pattern.li2_count,
            seed=pattern.member_index,
            namespace="weighted-Li2",
        )
        payload = (
            f"{CUBIC_LLZO_WEIGHTED_PLAN_VERSION}|{pattern.member_index}|"
            f"{pattern.weight_numerator}/{pattern.weight_denominator}|"
            f"{WEIGHTING_ASSUMPTION}|{shared.assignment_hash}|{li2.assignment_hash}"
        ).encode("utf-8")
        plans.append(
            WeightedCubicLlzoRealizationPlan(
                plan_version=CUBIC_LLZO_WEIGHTED_PLAN_VERSION,
                member_index=pattern.member_index,
                weight_numerator=pattern.weight_numerator,
                weight_denominator=pattern.weight_denominator,
                weighting_assumption=WEIGHTING_ASSUMPTION,
                li1_indices=shared.first_species_indices,
                al1_indices=shared.second_species_indices,
                li2_indices=li2.occupied_site_indices,
                assignment_hash=hashlib.sha256(payload).hexdigest(),
            )
        )
    return tuple(plans)
