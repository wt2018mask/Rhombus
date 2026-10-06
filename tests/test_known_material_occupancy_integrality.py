"""Occupancy-integrality tests for the retained cubic Al-LLZO refinement."""
from rudeus.science.known_material_occupancy_integrality import (
    OccupancySiteConstraint,
    analyze_exact_occupancy_integrality,
)


def test_cubic_al_llzo_literal_refined_occupancies_require_1250_cells():
    analysis = analyze_exact_occupancy_integrality((
        OccupancySiteConstraint(
            site_id="Li1", multiplicity=24, occupancy_decimal="0.54"
        ),
        OccupancySiteConstraint(
            site_id="Al1", multiplicity=24, occupancy_decimal="0.06530"
        ),
        OccupancySiteConstraint(
            site_id="Li2", multiplicity=96, occupancy_decimal="0.37"
        ),
    ))
    assert analysis.minimum_conventional_cell_replicas == 1250
    assert analysis.exact_integer_counts == (16200, 1959, 44400)
