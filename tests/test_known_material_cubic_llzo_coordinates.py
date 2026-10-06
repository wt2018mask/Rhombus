"""Coordinate-pool extraction tests for retained cubic Al-LLZO."""
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_coordinates import (
    extract_cubic_llzo_two_cell_coordinate_pools,
)


CIF = Path(
    "data/benchmarks/known_material/structures/cod/7215448-r176453.cif"
)


def test_retained_cubic_llzo_expands_to_expected_two_cell_site_pools():
    shared, li2 = extract_cubic_llzo_two_cell_coordinate_pools(CIF)

    assert shared.pool_id == "Li1-Al1"
    assert li2.pool_id == "Li2"
    assert len(shared.fractional_coordinates) == 48
    assert len(li2.fractional_coordinates) == 192
    assert len(set(shared.fractional_coordinates)) == 48
    assert len(set(li2.fractional_coordinates)) == 192
    assert shared.coordinate_hash != li2.coordinate_hash


def test_retained_cubic_llzo_coordinate_pool_hashes_are_reproducible():
    first = extract_cubic_llzo_two_cell_coordinate_pools(CIF)
    second = extract_cubic_llzo_two_cell_coordinate_pools(CIF)
    assert first == second
