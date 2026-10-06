"""Deterministic abstract realization plans for the cubic Al-LLZO ensemble.

This module binds the frozen per-member integer-count schedule to mutually-exclusive
Li1/Al1 shared-site assignment and independent Li2 assignment. It intentionally
stops before coordinates/CIF generation.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from rudeus.science.contracts import Record
from rudeus.science.known_material_ensemble_schedule import (
    count_for_member,
    deterministic_count_schedule,
)
from rudeus.science.known_material_shared_site_assignment import (
    deterministic_shared_site_assignment,
)
from rudeus.science.known_material_site_assignment import (
    deterministic_site_assignment,
)


CUBIC_LLZO_REALIZATION_PLAN_VERSION = "known-material-cubic-llzo-realization-plan-v1"


@dataclass(frozen=True, kw_only=True)
class CubicLlzoRealizationPlan(Record):
    plan_version: str
    member_index: int
    li1_indices: tuple[int, ...]
    al1_indices: tuple[int, ...]
    li2_indices: tuple[int, ...]
    assignment_hash: str


def build_cubic_llzo_realization_plans() -> tuple[CubicLlzoRealizationPlan, ...]:
    realization_count = 16
    li1_schedule = deterministic_count_schedule(
        namespace="Li1",
        realization_count=realization_count,
        lower_count=25,
        upper_count=26,
        upper_member_count=15,
    )
    al1_schedule = deterministic_count_schedule(
        namespace="Al1",
        realization_count=realization_count,
        lower_count=3,
        upper_count=4,
        upper_member_count=2,
    )
    li2_schedule = deterministic_count_schedule(
        namespace="Li2",
        realization_count=realization_count,
        lower_count=71,
        upper_count=72,
        upper_member_count=1,
    )

    plans = []
    for member_index in range(realization_count):
        li1_count = count_for_member(li1_schedule, member_index)
        al1_count = count_for_member(al1_schedule, member_index)
        li2_count = count_for_member(li2_schedule, member_index)

        shared = deterministic_shared_site_assignment(
            site_count=48,
            first_count=li1_count,
            second_count=al1_count,
            seed=member_index,
            namespace="Li1-Al1",
        )
        li2 = deterministic_site_assignment(
            site_count=192,
            occupied_count=li2_count,
            seed=member_index,
            namespace="Li2",
        )
        payload = (
            f"{CUBIC_LLZO_REALIZATION_PLAN_VERSION}|{member_index}|"
            f"{shared.assignment_hash}|{li2.assignment_hash}"
        ).encode("utf-8")
        plans.append(CubicLlzoRealizationPlan(
            plan_version=CUBIC_LLZO_REALIZATION_PLAN_VERSION,
            member_index=member_index,
            li1_indices=shared.first_species_indices,
            al1_indices=shared.second_species_indices,
            li2_indices=li2.occupied_site_indices,
            assignment_hash=hashlib.sha256(payload).hexdigest(),
        ))
    return tuple(plans)
