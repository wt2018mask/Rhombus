"""Weighted cubic Al-LLZO realization-plan tests."""
from fractions import Fraction

from rudeus.science.known_material_cubic_llzo_weighted_plan import (
    WEIGHTING_ASSUMPTION,
    build_weighted_cubic_llzo_realization_plans,
)


def _weighted_count(plans, field):
    return sum(
        (len(getattr(plan, field)) * plan.weight for plan in plans),
        Fraction(0, 1),
    )


def test_weighted_realization_plans_preserve_exact_marginals():
    plans = build_weighted_cubic_llzo_realization_plans()

    assert len(plans) == 8
    assert sum((plan.weight for plan in plans), Fraction(0, 1)) == 1
    assert _weighted_count(plans, "li1_indices") / 48 == Fraction("0.54")
    assert _weighted_count(plans, "al1_indices") / 48 == Fraction("0.06530")
    assert _weighted_count(plans, "li2_indices") / 192 == Fraction("0.37")


def test_weighted_realization_plans_are_disjoint_unique_and_explicit_about_assumption():
    plans = build_weighted_cubic_llzo_realization_plans()

    assert all(plan.weighting_assumption == WEIGHTING_ASSUMPTION for plan in plans)
    assert len({plan.assignment_hash for plan in plans}) == 8
    for plan in plans:
        assert set(plan.li1_indices).isdisjoint(plan.al1_indices)
        assert len(plan.li1_indices) in (25, 26)
        assert len(plan.al1_indices) in (3, 4)
        assert len(plan.li2_indices) in (71, 72)


def test_weighted_realization_plans_are_reproducible():
    assert (
        build_weighted_cubic_llzo_realization_plans()
        == build_weighted_cubic_llzo_realization_plans()
    )
