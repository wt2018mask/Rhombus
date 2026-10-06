from pathlib import Path

from rudeus.science.known_material_cubic_llzo_cross_pool_feasibility import (
    build_cross_pool_feasibility_diagnostics,
)

CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")

def test_cross_pool_feasibility_accounts_for_every_li2_pair():
    rows = build_cross_pool_feasibility_diagnostics(CIF)
    assert len(rows) == 8
    assert tuple(row.member_index for row in rows) == tuple(range(8))
    for row in rows:
        assert row.li2_pair_count == 96
        assert (
            row.pairs_with_two_allowed_endpoints
            + row.pairs_with_one_allowed_endpoint
            + row.pairs_with_zero_allowed_endpoints
            == 96
        )
        assert 0 <= row.maximum_pair_constrained_li2_count <= 96
