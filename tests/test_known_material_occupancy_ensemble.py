"""Small-cell ensemble diagnostics for cubic Al-LLZO."""
from decimal import Decimal

from rudeus.science.known_material_occupancy_ensemble import (
    nearest_equal_weight_ensemble_average,
)
from rudeus.science.known_material_occupancy_integrality import OccupancySiteConstraint


CONSTRAINTS = (
    OccupancySiteConstraint(site_id="Li1", multiplicity=24, occupancy_decimal="0.54"),
    OccupancySiteConstraint(site_id="Al1", multiplicity=24, occupancy_decimal="0.06530"),
    OccupancySiteConstraint(site_id="Li2", multiplicity=96, occupancy_decimal="0.37"),
)


def test_two_cell_ensemble_improves_average_occupancy_with_more_realizations():
    max_errors = []
    for count in (2, 4, 8, 16):
        approximations = tuple(
            nearest_equal_weight_ensemble_average(
                item, replicas_per_realization=2, realization_count=count
            )
            for item in CONSTRAINTS
        )
        max_errors.append(max(Decimal(item.absolute_error) for item in approximations))

    assert max_errors == [
        Decimal("0.00280"),
        Decimal("0.00240833333333333333333333333"),
        Decimal("0.0009375"),
        Decimal("0.0003645833333333333333333333"),
    ]


def test_sixteen_member_two_cell_ensemble_keeps_each_realization_small():
    approximations = tuple(
        nearest_equal_weight_ensemble_average(
            item, replicas_per_realization=2, realization_count=16
        )
        for item in CONSTRAINTS
    )
    assert tuple(item.upper_realization_count for item in approximations) == (15, 2, 1)
    assert max(Decimal(item.absolute_error) for item in approximations) == Decimal(
        "0.0003645833333333333333333333"
    )
