"""Diagnostic correlation-aware candidate structures for cubic Al-LLZO.

This does not replace the canonical weighted ensemble. It tests whether a
deterministic one-per-incompatible-Li2-pair assignment removes the severe
Li2-Li2 overlaps while preserving each member's exact Li2 count.
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
from rudeus.science.known_material_cubic_llzo_weighted_plan import (
    build_weighted_cubic_llzo_realization_plans,
)
from rudeus.science.known_material_cubic_llzo_ordered import ordered_structure_hash


DIAGNOSTIC_VERSION = "known-material-cubic-llzo-correlation-aware-candidate-v1"
LI_LI_MIN_ALLOWED = 1.74


@dataclass(frozen=True, kw_only=True)
class CorrelationAwareCandidateDiagnostic(Record):
    diagnostic_version: str
    member_index: int
    li2_required_count: int
    li2_selected_count: int
    li2_incompatible_pair_violations: int
    geometry_ok: bool | None
    geometry_details: dict
    structure_hash: str


def _coord(values):
    return tuple(float(v) for v in values)


def _host_sites(structure: Structure):
    hosts = []
    for site in structure:
        if site.is_ordered and site.specie.symbol in {"La", "Zr", "O"}:
            hosts.append((site.specie.symbol, tuple(float(v) % 1.0 for v in site.frac_coords)))
    return tuple(sorted(hosts, key=lambda x: (x[0], x[1])))


def _li2_pairs(lattice, coordinates):
    adjacency = [set() for _ in range(len(coordinates))]
    for i in range(len(coordinates)):
        a = [float(x) for x in coordinates[i]]
        for j in range(i + 1, len(coordinates)):
            b = [float(x) for x in coordinates[j]]
            distance, _ = lattice.get_distance_and_image(a, b)
            if float(distance) < LI_LI_MIN_ALLOWED:
                adjacency[i].add(j)
                adjacency[j].add(i)
    pairs = []
    seen = set()
    for i in range(len(adjacency)):
        if i in seen:
            continue
        neighbors = adjacency[i]
        if len(neighbors) != 1:
            raise ValueError("Li2 incompatibility graph is no longer disjoint pairs")
        j = next(iter(neighbors))
        if adjacency[j] != {i}:
            raise ValueError("Li2 incompatibility graph is no longer symmetric pairs")
        pairs.append(tuple(sorted((i, j))))
        seen.update((i, j))
    if len(pairs) * 2 != len(coordinates):
        raise ValueError("Li2 pair partition does not cover the retained pool")
    return tuple(sorted(set(pairs)))


def _select_li2_indices(pairs, *, occupied_count: int, seed: int):
    representatives = []
    for a, b in pairs:
        ranked = []
        for index in (a, b):
            token = f"{DIAGNOSTIC_VERSION}|endpoint|{seed}|{a}|{b}|{index}".encode()
            ranked.append((hashlib.sha256(token).digest(), index))
        representatives.append(min(ranked)[1])
    ranked_reps = []
    for index in representatives:
        token = f"{DIAGNOSTIC_VERSION}|rank|{seed}|{index}".encode()
        ranked_reps.append((hashlib.sha256(token).digest(), index))
    if occupied_count > len(ranked_reps):
        raise ValueError("requested Li2 count exceeds pair-constrained capacity")
    return tuple(sorted(index for _, index in sorted(ranked_reps)[:occupied_count]))


def build_correlation_aware_candidate_diagnostics(cif_path: Path):
    parsed = CifParser(str(cif_path)).parse_structures(primitive=False)
    if len(parsed) != 1:
        raise ValueError("cubic LLZO CIF must contain exactly one structure")
    source = parsed[0]
    source.make_supercell([2, 1, 1])
    hosts = _host_sites(source)
    shared_pool, li2_pool = extract_cubic_llzo_two_cell_coordinate_pools(cif_path)
    pairs = _li2_pairs(source.lattice, li2_pool.fractional_coordinates)
    patterns = build_exact_weighted_cubic_llzo_count_patterns()
    plans = build_weighted_cubic_llzo_realization_plans()

    diagnostics = []
    for pattern, plan in zip(patterns, plans):
        li2_indices = _select_li2_indices(
            pairs,
            occupied_count=pattern.li2_count,
            seed=pattern.member_index,
        )
        selected = set(li2_indices)
        violations = sum(a in selected and b in selected for a, b in pairs)

        species = [symbol for symbol, _ in hosts]
        coords = [coord for _, coord in hosts]
        for index in plan.li1_indices:
            species.append("Li")
            coords.append(_coord(shared_pool.fractional_coordinates[index]))
        for index in plan.al1_indices:
            species.append("Al")
            coords.append(_coord(shared_pool.fractional_coordinates[index]))
        for index in li2_indices:
            species.append("Li")
            coords.append(_coord(li2_pool.fractional_coordinates[index]))
        structure = Structure(
            lattice=source.lattice,
            species=species,
            coords=coords,
            coords_are_cartesian=False,
            to_unit_cell=True,
        )
        geometry_ok, details = check_geometry_clash(structure)
        diagnostics.append(
            CorrelationAwareCandidateDiagnostic(
                diagnostic_version=DIAGNOSTIC_VERSION,
                member_index=pattern.member_index,
                li2_required_count=pattern.li2_count,
                li2_selected_count=len(li2_indices),
                li2_incompatible_pair_violations=violations,
                geometry_ok=geometry_ok,
                geometry_details=details,
                structure_hash=ordered_structure_hash(structure),
            )
        )
    return tuple(diagnostics)
