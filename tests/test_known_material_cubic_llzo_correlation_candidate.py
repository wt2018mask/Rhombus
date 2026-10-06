from pathlib import Path

from rudeus.science.known_material_cubic_llzo_correlation_candidate import (
    build_correlation_aware_candidate_diagnostics,
)


CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")


def test_correlation_aware_candidate_preserves_li2_counts_without_pair_violations():
    rows = build_correlation_aware_candidate_diagnostics(CIF)
    assert len(rows) == 8
    assert tuple(row.member_index for row in rows) == tuple(range(8))
    assert all(row.li2_required_count == row.li2_selected_count for row in rows)
    assert all(row.li2_incompatible_pair_violations == 0 for row in rows)
    assert len({row.structure_hash for row in rows}) == 8
