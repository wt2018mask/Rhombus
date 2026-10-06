"""Constructive joint occupancy feasibility for cubic Al-LLZO.

Diagnostic only. This searches Li1 selections jointly with the established Li2
pair exclusions. It is constructive: success proves a clash-free candidate
exists under the current distance constraints; failure is not a proof of
infeasibility.

v2 scoring fixes the v1 objective bug: Li1 selection is now scored by the
number of Li2 incompatibility pairs that retain at least one allowed endpoint
after the full selected Li1 set is applied. This captures cross-site endpoint
blocking that v1 ignored.
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


DIAGNOSTIC_VERSION = "known-material-cubic-llzo-joint-occupancy-feasibility-v2"
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


def _rank(seed: int, namespace: str, index: int):
    return hashlib.sha256(
        f"{DIAGNOSTIC_VERSION}|{namespace}|{seed}|{index}".encode()
    ).digest()


def _allowed_pair_endpoints(lattice, li1_indices, shared_coords, li2_coords, pairs):
    li1_coords = [shared_coords[i] for i in li1_indices]
    result = []
    for a, b in pairs:
        allowed = []
        for endpoint in (a, b):
            coord = li2_coords[endpoint]
            if all(
                _distance(lattice, coord, li1) >= LI_LI_MIN_ALLOWED
                for li1 in li1_coords
            ):
                allowed.append(endpoint)
        result.append(tuple(allowed))
    return tuple(result)


def _available_pair_count(lattice, li1_indices, shared_coords, li2_coords, pairs) -> int:
    return sum(
        bool(endpoints)
        for endpoints in _allowed_pair_endpoints(
            lattice, li1_indices, shared_coords, li2_coords, pairs
        )
    )


def _select_li1(
    *,
    lattice,
    shared_coords,
    li2_coords,
    pairs,
    count: int,
    seed: int,
):
    selected: list[int] = []
    remaining = set(range(len(shared_coords)))

    # Greedy construction using the real objective: maximize Li2 pairs that
    # retain at least one allowed endpoint after the full selected Li1 set.
    while len(selected) < count:
        choice = max(
            remaining,
            key=lambda idx: (
                _available_pair_count(
                    lattice,
                    tuple(sorted((*selected, idx))),
                    shared_coords,
                    li2_coords,
                    pairs,
                ),
                bytes(255 - b for b in _rank(seed, "li1", idx)),
                -idx,
            ),
        )
        selected.append(choice)
        remaining.remove(choice)

    # Deterministic one-swap hill climb on the same exact objective.
    improved = True
    while improved:
        improved = False
        current = set(selected)
        current_score = _available_pair_count(
            lattice,
            tuple(sorted(current)),
            shared_coords,
            li2_coords,
            pairs,
        )
        best_score = current_score
        best_key = tuple(sorted(current))
        best_set = current
        for out_idx in sorted(current):
            for in_idx in sorted(set(range(len(shared_coords))) - current):
                candidate = (current - {out_idx}) | {in_idx}
                score = _available_pair_count(
                    lattice,
                    tuple(sorted(candidate)),
                    shared_coords,
                    li2_coords,
                    pairs,
                )
                key = tuple(sorted(candidate))
                if score > best_score or (score == best_score and key < best_key):
                    best_score = score
                    best_key = key
                    best_set = candidate
        if best_set != current:
            selected = sorted(best_set)
            improved = True

    return tuple(sorted(selected))


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
    shared_coords = shared_pool.fractional_coordinates
    li2_coords = li2_pool.fractional_coordinates
    pairs = _li2_pairs(source.lattice, li2_coords)

    rows = []
    for pattern in build_exact_weighted_cubic_llzo_count_patterns():
        li1 = _select_li1(
            lattice=source.lattice,
            shared_coords=shared_coords,
            li2_coords=li2_coords,
            pairs=pairs,
            count=pattern.li1_count,
            seed=pattern.member_index,
        )
        allowed = _allowed_pair_endpoints(
            source.lattice, li1, shared_coords, li2_coords, pairs
        )
        available_pair_indices = [i for i, endpoints in enumerate(allowed) if endpoints]
        found = len(available_pair_indices) >= pattern.li2_count

        li2 = ()
        geometry_ok = None
        geometry_details = {"not_run": "constructive_assignment_not_found"}
        al1 = _select_al1(
            len(shared_coords),
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
                coords.append(_coord(shared_coords[index]))
            for index in al1:
                species.append("Al")
                coords.append(_coord(shared_coords[index]))
            for index in li2:
                species.append("Li")
                coords.append(_coord(li2_coords[index]))
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
