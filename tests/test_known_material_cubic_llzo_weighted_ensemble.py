"""Exact weighted cubic Al-LLZO occupancy-ensemble tests."""
from fractions import Fraction

from rudeus.science.known_material_cubic_llzo_weighted_ensemble import (
    build_exact_weighted_cubic_llzo_count_patterns,
)


def _weighted(patterns, field):
    return sum(
        (getattr(item, field) * item.weight for item in patterns),
        Fraction(0, 1),
    )


def test_weighted_two_cell_ensemble_exactly_preserves_declared_site_occupancies():
    patterns = build_exact_weighted_cubic_llzo_count_patterns()

    assert len(patterns) == 8
    assert sum((item.weight for item in patterns), Fraction(0, 1)) == 1
    assert all(item.weight > 0 for item in patterns)

    assert _weighted(patterns, "li1_count") / 48 == Fraction("0.54")
    assert _weighted(patterns, "al1_count") / 48 == Fraction("0.06530")
    assert _weighted(patterns, "li2_count") / 192 == Fraction("0.37")


def test_weighted_two_cell_ensemble_preserves_refined_formula():
    patterns = build_exact_weighted_cubic_llzo_count_patterns()

    li_per_formula = (
        _weighted(patterns, "li1_count") + _weighted(patterns, "li2_count")
    ) / 16
    al_per_formula = _weighted(patterns, "al1_count") / 16

    assert li_per_formula == Fraction(303, 50)  # 6.06
    assert al_per_formula == Fraction(1959, 10000)  # 0.1959 -> reported 0.196
    assert round(float(al_per_formula), 3) == 0.196


def test_weighted_patterns_remain_small_and_shared_site_safe():
    patterns = build_exact_weighted_cubic_llzo_count_patterns()

    for item in patterns:
        assert item.li1_count in (25, 26)
        assert item.al1_count in (3, 4)
        assert item.li2_count in (71, 72)
        assert item.li1_count + item.al1_count <= 48
        total_atoms = 272 + item.li1_count + item.al1_count + item.li2_count
        assert 371 <= total_atoms <= 374
