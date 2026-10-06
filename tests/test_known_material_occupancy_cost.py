"""Composition/cost diagnostics for cubic Al-LLZO rationalization."""
from rudeus.science.known_material_occupancy_cost import cubic_al_llzo_cost_point
from rudeus.science.known_material_occupancy_frontier import nearest_integer_occupancy_frontier
from rudeus.science.known_material_occupancy_integrality import OccupancySiteConstraint


def _constraints():
    return (
        OccupancySiteConstraint(site_id="Li1", multiplicity=24, occupancy_decimal="0.54"),
        OccupancySiteConstraint(site_id="Al1", multiplicity=24, occupancy_decimal="0.06530"),
        OccupancySiteConstraint(site_id="Li2", multiplicity=96, occupancy_decimal="0.37"),
    )


def test_cubic_al_llzo_cost_exposes_small_error_large_atom_tradeoff():
    frontier = nearest_integer_occupancy_frontier(_constraints(), (1, 2, 16))
    costs = tuple(cubic_al_llzo_cost_point(point) for point in frontier)

    assert tuple(cost.total_atom_count for cost in costs) == (201, 401, 3205)
    assert costs[0].formula_li == "6"
    assert costs[0].formula_al == "0.25"
    assert costs[1].formula_li == "6.0625"
    assert costs[1].formula_al == "0.1875"
    assert costs[16 // 16 + 1].formula_li == "6.0625"
    assert costs[2].formula_al == "0.1953125"
    assert costs[2].formula_li_absolute_error == "0.0025"
    assert costs[2].formula_al_absolute_error == "0.0006875"
