"""Cross-pool occupancy feasibility for cubic Al-LLZO.

Diagnostic only. For each weighted member, keep the canonical Li1/Al1 assignment
fixed and ask whether enough Li2 incompatibility pairs retain at least one
endpoint that is farther than the current P0 Li-Li cutoff from every occupied
Li1 site. This proves or falsifies feasibility without changing the ensemble.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pymatgen.io.cif import CifParser

from rudeus.science.contracts import Record
from rudeus.science.known_material_cubic_llzo_coordinates import (
    extract_cubic_llzo_two_cell_coordinate_pools,
)
from rudeus.science.known_material_cubic_llzo_weighted_ensemble import (
    build_exact_weighted_cubic_llzo_count_patterns,
)
from rudeus.science.known_material_cubic_llzo_weighted_plan import (
    build_weighted_cubic_llzo_realization_plans,
)
from rudeus.science.known_material_cubic_llzo_correlation_candidate import _li2_pairs


DIAGNOSTIC_VERSION = "known-material-cubic-llzo-cross-pool-feasibility-v1"
LI_LI_MIN_ALLOWED = 1.74


@dataclass(frozen=True, kw_only=True)
class CrossPoolFeasibilityDiagnostic(Record):
    diagnostic_version: str
    member_index: int
    li1_count: int
    li2_required_count: int
    li2_pair_count: int
    pairs_with_two_allowed_endpoints: int
    pairs_with_one_allowed_endpoint: int
    pairs_with_zero_allowed_endpoints: int
    maximum_pair_constrained_li2_count: int
    feasible_with_fixed_li1_assignment: bool


def _distance(lattice, a, b) -> float:
    distance, _ = lattice.get_distance_and_image(
        [float(x) for x in a], [float(x) for x in b]
    )
    return float(distance)


def build_cross_pool_feasibility_diagnostics(cif_path: Path):
    parsed = CifParser(str(cif_path)).parse_structures(primitive=False)
    if len(parsed) != 1:
        raise ValueError("cubic LLZO CIF must contain exactly one structure")
    source = parsed[0]
    source.make_supercell([2, 1, 1])

    shared_pool, li2_pool = extract_cubic_llzo_two_cell_coordinate_pools(cif_path)
    pairs = _li2_pairs(source.lattice, li2_pool.fractional_coordinates)
    plans = build_weighted_cubic_llzo_realization_plans()
    patterns = build_exact_weighted_cubic_llzo_count_patterns()

    rows = []
    for plan, pattern in zip(plans, patterns):
        li1_coords = [
            shared_pool.fractional_coordinates[index]
            for index in plan.li1_indices
        ]
        endpoint_counts = []
        for a, b in pairs:
            allowed = 0
            for endpoint in (a, b):
                coord = li2_pool.fractional_coordinates[endpoint]
                if all(
                    _distance(source.lattice, coord, li1) >= LI_LI_MIN_ALLOWED
                    for li1 in li1_coords
                ):
                    allowed += 1
            endpoint_counts.append(allowed)

        maximum = sum(count > 0 for count in endpoint_counts)
        rows.append(
            CrossPoolFeasibilityDiagnostic(
                diagnostic_version=DIAGNOSTIC_VERSION,
                member_index=pattern.member_index,
                li1_count=pattern.li1_count,
                li2_required_count=pattern.li2_count,
                li2_pair_count=len(pairs),
                pairs_with_two_allowed_endpoints=sum(c == 2 for c in endpoint_counts),
                pairs_with_one_allowed_endpoint=sum(c == 1 for c in endpoint_counts),
                pairs_with_zero_allowed_endpoints=sum(c == 0 for c in endpoint_counts),
                maximum_pair_constrained_li2_count=maximum,
                feasible_with_fixed_li1_assignment=maximum >= pattern.li2_count,
            )
        )
    return tuple(rows)
