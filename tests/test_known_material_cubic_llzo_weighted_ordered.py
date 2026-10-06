"""Exact-weighted ordered cubic Al-LLZO structure tests."""
from fractions import Fraction
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_weighted_ordered import (
    build_weighted_cubic_llzo_ordered_structures,
)


CIF = Path(
    "data/benchmarks/known_material/structures/cod/7215448-r176453.cif"
)


def test_weighted_ordered_structures_preserve_exact_weighted_composition():
    members = build_weighted_cubic_llzo_ordered_structures(CIF)

    assert len(members) == 8
    assert sum((member.weight for member in members), Fraction(0, 1)) == 1

    weighted_li = Fraction(0, 1)
    weighted_al = Fraction(0, 1)
    for member in members:
        amounts = member.structure.composition.get_el_amt_dict()
        assert amounts["La"] == 48
        assert amounts["Zr"] == 32
        assert amounts["O"] == 192
        assert 371 <= len(member.structure) <= 374
        weighted_li += int(amounts["Li"]) * member.weight
        weighted_al += int(amounts["Al"]) * member.weight

    assert weighted_li / 16 == Fraction(303, 50)  # 6.06
    assert weighted_al / 16 == Fraction(1959, 10000)  # 0.1959


def test_weighted_ordered_structures_are_unique_and_reproducible():
    first = build_weighted_cubic_llzo_ordered_structures(CIF)
    second = build_weighted_cubic_llzo_ordered_structures(CIF)

    assert tuple(
        (m.structure_hash, m.assignment_hash, m.weight)
        for m in first
    ) == tuple(
        (m.structure_hash, m.assignment_hash, m.weight)
        for m in second
    )
    assert len({member.structure_hash for member in first}) == 8
    assert len({member.assignment_hash for member in first}) == 8


def test_weighted_ordered_structures_have_no_duplicate_coordinates():
    for member in build_weighted_cubic_llzo_ordered_structures(CIF):
        coordinates = {
            tuple(f"{float(value) % 1.0:.12f}" for value in site.frac_coords)
            for site in member.structure
        }
        assert len(coordinates) == len(member.structure)
