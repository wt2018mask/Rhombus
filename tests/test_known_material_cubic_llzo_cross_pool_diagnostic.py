from pathlib import Path

from rudeus.science.known_material_cubic_llzo_cross_pool_diagnostic import (
    build_cross_pool_clash_diagnostics,
)

CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")

def test_cross_pool_clash_diagnostic_classifies_all_residual_clashes():
    rows = build_cross_pool_clash_diagnostics(CIF)
    assert len(rows) == 8
    assert tuple(row.member_index for row in rows) == tuple(range(8))
    assert all(row.residual_clash_count > 0 for row in rows)
    assert all(sum(row.residual_clash_classes.values()) == row.residual_clash_count for row in rows)
    assert all(row.minimum_distance > 0 for row in rows)
