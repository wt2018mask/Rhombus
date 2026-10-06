"""Diagnostics for cubic Al-LLZO raw-P0 failures."""
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_p0_diagnostic import (
    DIAGNOSTIC_VERSION,
    build_cubic_llzo_p0_diagnostics,
)


CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")


def test_cubic_llzo_p0_diagnostic_is_complete_and_non_authoritative():
    diagnostics = build_cubic_llzo_p0_diagnostics(CIF)

    assert len(diagnostics) == 8
    assert tuple(item.member_index for item in diagnostics) == tuple(range(8))
    assert all(item.diagnostic_version == DIAGNOSTIC_VERSION for item in diagnostics)
    assert all(item.min_li_li_distance > 0 for item in diagnostics)
    assert all(item.min_allowed_li_li > 0 for item in diagnostics)
    assert all(item.li_li_clash_pair_count >= 0 for item in diagnostics)
