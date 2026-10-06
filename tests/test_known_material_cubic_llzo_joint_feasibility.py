from pathlib import Path

from rudeus.science.known_material_cubic_llzo_joint_feasibility import (
    DIAGNOSTIC_VERSION,
    build_joint_occupancy_feasibility_diagnostics,
)

CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")

def test_joint_occupancy_feasibility_preserves_required_counts_when_constructed():
    rows = build_joint_occupancy_feasibility_diagnostics(CIF)
    assert len(rows) == 8
    assert tuple(row.member_index for row in rows) == tuple(range(8))
    assert all(row.diagnostic_version == DIAGNOSTIC_VERSION for row in rows)
    for row in rows:
        assert len(row.li1_indices) == row.li1_required_count
        assert len(row.al1_indices) == row.al1_required_count
        assert set(row.li1_indices).isdisjoint(row.al1_indices)
        if row.constructive_assignment_found:
            assert len(row.li2_indices) == row.li2_required_count
            assert row.available_li2_pairs_after_li1 >= row.li2_required_count
