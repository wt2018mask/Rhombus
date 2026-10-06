"""Feasibility diagnostic for correlation-aware cubic Al-LLZO Li2 occupancy."""
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_li2_feasibility import (
    DIAGNOSTIC_VERSION,
    build_cubic_llzo_li2_correlation_feasibility,
)


CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")


def test_li2_correlation_feasibility_is_complete_and_diagnostic_only():
    result = build_cubic_llzo_li2_correlation_feasibility(CIF)

    assert result.diagnostic_version == DIAGNOSTIC_VERSION
    assert result.site_count == 192
    assert result.incompatibility_edge_count > 0
    assert result.required_li2_counts == (71, 72)
    assert 1 <= result.greedy_independent_set_size <= 192
    assert sum(result.connected_component_sizes) == 192
