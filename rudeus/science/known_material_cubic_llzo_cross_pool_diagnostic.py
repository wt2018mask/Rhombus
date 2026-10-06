"""Classify residual Li-Li clashes in correlation-aware cubic Al-LLZO candidates.

Diagnostic only. This module leaves the canonical ensemble and P0 unchanged and
reports residual clash classes by source site pool (LI1 vs LI2).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pymatgen.core import Structure
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
from rudeus.science.known_material_cubic_llzo_correlation_candidate import (
    _li2_pairs,
    _select_li2_indices,
)


DIAGNOSTIC_VERSION = "known-material-cubic-llzo-cross-pool-clash-diagnostic-v1"
LI_LI_MIN_ALLOWED = 1.74


@dataclass(frozen=True, kw_only=True)
class CrossPoolClashDiagnostic(Record):
    diagnostic_version: str
    member_index: int
    residual_clash_count: int
    residual_clash_classes: dict[str, int]
    minimum_distance: float
    minimum_distance_class: str


def _coord(values):
    return tuple(float(v) for v in values)


def _host_sites(structure: Structure):
    hosts = []
    for site in structure:
        if site.is_ordered and site.specie.symbol in {"La", "Zr", "O"}:
            hosts.append((site.specie.symbol, tuple(float(v) % 1.0 for v in site.frac_coords)))
    return tuple(sorted(hosts, key=lambda x: (x[0], x[1])))


def _build_member(cif_path: Path, member_index: int):
    parsed = CifParser(str(cif_path)).parse_structures(primitive=False)
    if len(parsed) != 1:
        raise ValueError("cubic LLZO CIF must contain exactly one structure")
    source = parsed[0]
    source.make_supercell([2, 1, 1])
    hosts = _host_sites(source)
    shared_pool, li2_pool = extract_cubic_llzo_two_cell_coordinate_pools(cif_path)
    patterns = build_exact_weighted_cubic_llzo_count_patterns()
    plans = build_weighted_cubic_llzo_realization_plans()
    pattern = patterns[member_index]
    plan = plans[member_index]

    pairs = _li2_pairs(source.lattice, li2_pool.fractional_coordinates)
    li2_indices = _select_li2_indices(
        pairs, occupied_count=pattern.li2_count, seed=pattern.member_index
    )

    species = [symbol for symbol, _ in hosts]
    coords = [coord for _, coord in hosts]
    labels = ["HOST"] * len(hosts)
    for index in plan.li1_indices:
        species.append("Li")
        coords.append(_coord(shared_pool.fractional_coordinates[index]))
        labels.append("LI1")
    for index in plan.al1_indices:
        species.append("Al")
        coords.append(_coord(shared_pool.fractional_coordinates[index]))
        labels.append("AL1")
    for index in li2_indices:
        species.append("Li")
        coords.append(_coord(li2_pool.fractional_coordinates[index]))
        labels.append("LI2")

    structure = Structure(
        lattice=source.lattice,
        species=species,
        coords=coords,
        coords_are_cartesian=False,
        to_unit_cell=True,
    )
    return structure, labels


def build_cross_pool_clash_diagnostics(cif_path: Path):
    rows = []
    for member_index in range(8):
        structure, labels = _build_member(cif_path, member_index)
        li_indices = [
            i for i, site in enumerate(structure)
            if site.is_ordered and site.specie.symbol == "Li"
        ]
        dm = structure.distance_matrix
        counts = Counter()
        minimum = float("inf")
        minimum_class = ""
        for offset, i in enumerate(li_indices):
            for j in li_indices[offset + 1:]:
                distance = float(dm[i, j])
                if distance < LI_LI_MIN_ALLOWED:
                    pair_class = "-".join(sorted((labels[i], labels[j])))
                    counts[pair_class] += 1
                    if distance < minimum:
                        minimum = distance
                        minimum_class = pair_class
        rows.append(
            CrossPoolClashDiagnostic(
                diagnostic_version=DIAGNOSTIC_VERSION,
                member_index=member_index,
                residual_clash_count=sum(counts.values()),
                residual_clash_classes=dict(sorted(counts.items())),
                minimum_distance=minimum,
                minimum_distance_class=minimum_class,
            )
        )
    return tuple(rows)
