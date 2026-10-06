"""Ordered cubic Al-LLZO realization tests."""
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_ordered import (
    build_cubic_llzo_ordered_structures,
    ordered_structure_hash,
)


CIF = Path(
    "data/benchmarks/known_material/structures/cod/7215448-r176453.cif"
)


def test_cubic_llzo_ordered_structures_preserve_host_and_ensemble_counts():
    structures = build_cubic_llzo_ordered_structures(CIF)
    assert len(structures) == 16

    li_total = 0
    al_total = 0
    for structure in structures:
        assert structure.is_ordered
        counts = structure.composition.get_el_amt_dict()
        assert counts["La"] == 48
        assert counts["Zr"] == 32
        assert counts["O"] == 192
        li_total += int(counts["Li"])
        al_total += int(counts["Al"])
        assert 371 <= len(structure) <= 374

    assert li_total == 1552
    assert al_total == 50


def test_cubic_llzo_ordered_structures_are_unique_and_reproducible():
    first = build_cubic_llzo_ordered_structures(CIF)
    second = build_cubic_llzo_ordered_structures(CIF)
    first_hashes = tuple(ordered_structure_hash(structure) for structure in first)
    second_hashes = tuple(ordered_structure_hash(structure) for structure in second)

    assert first_hashes == second_hashes
    assert len(set(first_hashes)) == 16


def test_cubic_llzo_ordered_structures_have_no_duplicate_coordinates():
    for structure in build_cubic_llzo_ordered_structures(CIF):
        coordinates = {
            tuple(f"{float(value) % 1.0:.12f}" for value in site.frac_coords)
            for site in structure
        }
        assert len(coordinates) == len(structure)
