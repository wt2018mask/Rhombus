"""Cubic Al-LLZO abstract realization-plan tests."""
from rudeus.science.known_material_cubic_llzo_realization import (
    build_cubic_llzo_realization_plans,
)


def test_cubic_llzo_realization_plans_are_count_preserving_and_disjoint():
    plans = build_cubic_llzo_realization_plans()
    assert len(plans) == 16
    assert tuple(plan.member_index for plan in plans) == tuple(range(16))
    assert sum(len(plan.li1_indices) for plan in plans) == 415
    assert sum(len(plan.al1_indices) for plan in plans) == 50
    assert sum(len(plan.li2_indices) for plan in plans) == 1137

    for plan in plans:
        assert set(plan.li1_indices).isdisjoint(plan.al1_indices)
        assert all(0 <= index < 48 for index in plan.li1_indices)
        assert all(0 <= index < 48 for index in plan.al1_indices)
        assert all(0 <= index < 192 for index in plan.li2_indices)


def test_cubic_llzo_realization_plans_are_reproducible_and_member_unique():
    first = build_cubic_llzo_realization_plans()
    second = build_cubic_llzo_realization_plans()
    assert first == second
    assert len({plan.assignment_hash for plan in first}) == 16
