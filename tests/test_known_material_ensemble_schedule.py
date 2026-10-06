"""Ensemble count-schedule tests for cubic Al-LLZO."""
from rudeus.science.known_material_ensemble_schedule import (
    count_for_member,
    deterministic_count_schedule,
)


def test_cubic_llzo_sixteen_member_two_cell_count_schedules():
    li1 = deterministic_count_schedule(
        namespace="Li1", realization_count=16,
        lower_count=25, upper_count=26, upper_member_count=15,
    )
    al1 = deterministic_count_schedule(
        namespace="Al1", realization_count=16,
        lower_count=3, upper_count=4, upper_member_count=2,
    )
    li2 = deterministic_count_schedule(
        namespace="Li2", realization_count=16,
        lower_count=71, upper_count=72, upper_member_count=1,
    )

    assert sum(count_for_member(li1, i) for i in range(16)) == 415
    assert sum(count_for_member(al1, i) for i in range(16)) == 50
    assert sum(count_for_member(li2, i) for i in range(16)) == 1137

    for i in range(16):
        assert count_for_member(li1, i) + count_for_member(al1, i) <= 48


def test_count_schedule_is_deterministic():
    first = deterministic_count_schedule(
        namespace="Li1", realization_count=16,
        lower_count=25, upper_count=26, upper_member_count=15,
    )
    second = deterministic_count_schedule(
        namespace="Li1", realization_count=16,
        lower_count=25, upper_count=26, upper_member_count=15,
    )
    assert first == second
