"""Cubic Al-LLZO occupancy rationalization frontier tests."""
from rudeus.science.known_material_occupancy_frontier import (
    nearest_integer_occupancy_frontier,
)
from rudeus.science.known_material_occupancy_integrality import OccupancySiteConstraint


def test_cubic_al_llzo_small_replica_error_frontier():
    constraints = (
        OccupancySiteConstraint(site_id="Li1", multiplicity=24, occupancy_decimal="0.54"),
        OccupancySiteConstraint(site_id="Al1", multiplicity=24, occupancy_decimal="0.06530"),
        OccupancySiteConstraint(site_id="Li2", multiplicity=96, occupancy_decimal="0.37"),
    )
    frontier = nearest_integer_occupancy_frontier(
        constraints, (1, 2, 4, 8, 16, 32)
    )
    assert tuple(point.replicas for point in frontier) == (1, 2, 4, 8, 16, 32)
    assert tuple(point.max_absolute_error for point in frontier) == (
        "0.01803333333333333333333333333",
        "0.00280",
        "0.00280",
        "0.00240833333333333333333333333",
        "0.0009375",
        "0.0003645833333333333333333333",
    )
    al_counts = tuple(
        point.approximations[1].integer_count for point in frontier
    )
    assert al_counts == (2, 3, 6, 13, 25, 50)
