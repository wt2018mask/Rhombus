"""Constructive joint occupancy feasibility for cubic Al-LLZO.

Diagnostic only. This searches Li1 selections jointly with the established Li2
pair exclusions. It is constructive: success proves a clash-free candidate
exists under the current distance constraints; failure is not a proof of
infeasibility.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from pymatgen.core import Structure
from pymatgen.io.cif import CifParser

from rudeus.filters.p0 import check_geometry_clash
from rudeus.science.contracts import Record
from rudeus.science.known_material_cubic_llzo_coordinates import (
    extract_cubic_llzo_two_cell_coordinate_pools,
)
from rudeus.science.known_material_cubic_llzo_weighted_ensemble import (
    build_exact_weighted_cubic_llzo_count_patterns,
)
from rudeus.science.known_material_cubic_llzo_correlation_candidate import _li2_pairs


DIAGNOSTIC_VERSION = "known-material-cubic-llzo-joint-occupancy-feasibility-v1"
LI_LI_MIN_ALLOWED = 1.74


@dataclass(frozen=True, kw_only=True)
class JointOccupancyFeasibilityDiagnostic(Record):
    diagnostic_version: str
    member_index: int
    li1_required_count: int
    al1_required_count: int
    li2_required_count: int
    available_li2_pairs_after_li1: int
    constructive_assignment_found: bool
    geometry_ok: bool | None
    geometry_details: dict
    li1_indices: tuple[int, ...]
    al1_indices: tuple[int, ...]
    li2_indices: tuple[int, ...]


def _distance(lattice, a, b) -> float:
    d, _ = lattice.get_distance_and_image(
        [float(x) for x in a], [float(x) for x in b]
    )
    return float(d)


def _host_sites(structure: Structure):
    hosts = []
    for site in structure:
        if site.is_ordered and site.specie.symbol in {"La", "Zr", "O"}:
            hosts.append((site.specie.symbol, tuple(float(v) % 1.0 for v in site.frac_coords)))
    return tuple(sorted(hosts, key=lambda x: (x[0], x[1])))


def _blocked_pairs_by_shared_site(lattice, shared_coords, li2_coords, pairs):
    result = []
    for shared in shared_coords:
        blocked = set()
        for pair_index, (a, b) in enumerate(pairs):
            a_bad = _distance(lattice, shared, li2_coords[a]) < LI_LI_MIN_ALLOWED
            b_bad = _distance(lattice, shared, li2_coords[b]) < LI_LI_MIN_ALLOWED
            if a_bad and b_bad:
                blocked.add(pair_index)
        result.append(frozenset(blocked))
    return tuple(result)


def _rank(seed: int, namespace: str, index: int):
    return hashlib.sha256(
        f"{DIAGNOSTIC_VERSION}|{namespace}|{seed}|{index}".encode()
    ).digest()


def _select_li1(blocked_by_site, count: int, seed: int):
    selected = []
    blocked_union = set()
    remaining = set(range(len(blocked_by_site)))
    while len(selected) < count:
        choice = min(
            remaining,
            key=lambda idx: (
                len(blocked_union | set(blocked_by_site[idx])),
                _rank(seed, "li1", idx),
                idx,
            ),
        )
        selected.append(choice)
        blocked_union.update(blocked_by_site[choice])
        remaining.remove(choice)

    # Deterministic one-swap hill climb to reduce union-blocked Li2 pairs.
    improved = True
    while improved:
        improved = False
        current = set(selected)
        current_union = set().union(*(blocked_by_site[i] for i in current))
        best = (len(current_union), tuple(sorted(current)))
        best_set = current
        for out_idx in sorted(current):
            for in_idx in sorted(set(range(len(blocked_by_site))) - current):
                candidate = (current - {out_idx}) | {in_idx}
                union = set().union(*(blocked_by_site[i] for i in candidate))
                score = (len(union), tuple(sorted(candidate)))
                if score < best:
                    best = score
                    best_set = candidate
        if best_set != current:
            selected = sorted(best_set)
            improved = True
    return tuple(sorted(selected))


def _allowed_pair_endpoints(lattice, li1_coords, li2_coords, pairs):
    result = []
    for a, b in pairs:
        allowed = []
        for endpoint in (a, b):
            coord = li2_coords[endpoint]
            if all(_distance(lattice, coord, li1) >= LI_LI_MIN_ALLOWED for li1 in li1_coords):
                allowed.append(endpoint)
        result.append(tuple(allowed))
    return tuple(result)


def _select_al1(shared_count: int, li1_indices, al1_count: int, seed: int):
    remaining = [i for i in range(shared_count) if i not in set(li1_indices)]
    ranked = sorted(remaining, key=lambda i: (_rank(seed, "al1", i), i))
    return tuple(sorted(ranked[:al1_count]))


def _coord(values):
    return tuple(float(v) for v in values)


def build_joint_occupancy_feasibility_diagnostics(cif_path: Path):
    parsed = CifParser(str(cif_path)).parse_structures(primitive=False)
    if len(parsed) != 1:
        raise ValueError("cubic LLZO CIF must contain exactly one structure")
    source = parsed[0]
    source.make_supercell([2, 1, 1])
    hosts = _host_sites(source)
    shared_pool, li2_pool = extract_cubic_llzo_two_cell_coordinate_pools(cif_path)
    pairs = _li2_pairs(source.lattice, li2_pool.fractional_coordinates)
    blocked = _blocked_pairs_by_shared_site(
        source.lattice,
        shared_pool.fractional_coordinates,
        li2_pool.fractional_coordinates,
        pairs,
    )

    rows = []
    for pattern in build_exact_weighted_cubic_llzo_count_patterns():
        li1 = _select_li1(blocked, pattern.li1_count, pattern.member_index)
        li1_coords = [shared_pool.fractional_coordinates[i] for i in li1]
        allowed = _allowed_pair_endpoints(
            source.lattice,
            li1_coords,
            li2_pool.fractional_coordinates,
            pairs,
        )
        available_pair_indices = [i for i, endpoints in enumerate(allowed) if endpoints]
        found = len(available_pair_indices) >= pattern.li2_count

        li2 = ()
        geometry_ok = None
        geometry_details = {"not_run": "constructive_assignment_not_found"}
        al1 = _select_al1(
            len(shared_pool.fractional_coordinates),
            li1,
            pattern.al1_count,
            pattern.member_index,
        )
        if found:
            ranked_pairs = sorted(
                available_pair_indices,
                key=lambda i: (_rank(pattern.member_index, "li2-pair", i), i),
            )[:pattern.li2_count]
            chosen = []
            for pair_index in ranked_pairs:
                endpoints = allowed[pair_index]
                endpoint = min(
                    endpoints,
                    key=lambda i: (_rank(pattern.member_index, "li2-endpoint", i), i),
                )
                chosen.append(endpoint)
            li2 = tuple(sorted(chosen))

            species = [symbol for symbol, _ in hosts]
            coords = [coord for _, coord in hosts]
            for index in li1:
                species.append("Li")
                coords.append(_coord(shared_pool.fractional_coordinates[index]))
            for index in al1:
                species.append("Al")
                coords.append(_coord(shared_pool.fractional_coordinates[index]))
            for index in li2:
                species.append("Li")
                coords.append(_coord(li2_pool.fractional_coordinates[index]))
            structure = Structure(
                lattice=source.lattice,
                species=species,
                coords=coords,
                coords_are_cartesian=False,
                to_unit_cell=True,
            )
            geometry_ok, geometry_details = check_geometry_clash(structure)

        rows.append(
            JointOccupancyFeasibilityDiagnostic(
                diagnostic_version=DIAGNOSTIC_VERSION,
                member_index=pattern.member_index,
                li1_required_count=pattern.li1_count,
                al1_required_count=pattern.al1_count,
                li2_required_count=pattern.li2_count,
                available_li2_pairs_after_li1=len(available_pair_indices),
                constructive_assignment_found=found,
                geometry_ok=geometry_ok,
                geometry_details=geometry_details,
                li1_indices=li1,
                al1_indices=al1,
                li2_indices=li2,
            )
        )
    return tuple(rows)
