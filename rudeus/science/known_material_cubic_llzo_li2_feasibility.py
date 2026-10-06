"""Feasibility diagnostics for correlation-aware cubic Al-LLZO Li2 occupancy.

Diagnostic only: this module does not change the canonical ensemble or any P0
threshold. It asks whether the retained Li2 coordinate pool can support the
required 71/72 occupied sites without any Li-Li pair falling below the current
P0 provisional 1.74 A cutoff.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pymatgen.core import Lattice

from rudeus.science.contracts import Record
from rudeus.science.known_material_cubic_llzo_coordinates import (
    extract_cubic_llzo_two_cell_coordinate_pools,
)
from rudeus.science.known_material_cubic_llzo_weighted_ensemble import (
    build_exact_weighted_cubic_llzo_count_patterns,
)


DIAGNOSTIC_VERSION = "known-material-cubic-llzo-li2-correlation-feasibility-v1"
LI_LI_MIN_ALLOWED = 1.74


@dataclass(frozen=True, kw_only=True)
class CubicLlzoLi2CorrelationFeasibility(Record):
    diagnostic_version: str
    site_count: int
    incompatibility_edge_count: int
    connected_component_sizes: tuple[int, ...]
    all_components_cliques: bool
    greedy_independent_set_size: int
    required_li2_counts: tuple[int, ...]
    greedy_supports_all_required_counts: bool


def _load_two_cell_lattice(cif_path: Path) -> Lattice:
    from pymatgen.io.cif import CifParser

    structures = CifParser(str(cif_path)).parse_structures(primitive=False)
    if len(structures) != 1:
        raise ValueError("cubic LLZO CIF must contain exactly one structure")
    structure = structures[0]
    structure.make_supercell([2, 1, 1])
    return structure.lattice


def _edges(lattice: Lattice, coordinates):
    edges = set()
    for i in range(len(coordinates)):
        a = [float(x) for x in coordinates[i]]
        for j in range(i + 1, len(coordinates)):
            b = [float(x) for x in coordinates[j]]
            distance, _ = lattice.get_distance_and_image(a, b)
            if float(distance) < LI_LI_MIN_ALLOWED:
                edges.add((i, j))
    return edges


def _components(site_count: int, edges):
    adjacency = [set() for _ in range(site_count)]
    for i, j in edges:
        adjacency[i].add(j)
        adjacency[j].add(i)
    seen = set()
    components = []
    for start in range(site_count):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        comp = []
        while stack:
            node = stack.pop()
            comp.append(node)
            for nxt in sorted(adjacency[node], reverse=True):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        components.append(tuple(sorted(comp)))
    return tuple(components), tuple(adjacency)


def _is_clique(component, adjacency) -> bool:
    n = len(component)
    if n <= 1:
        return True
    return all(
        len(adjacency[node].intersection(component)) == n - 1
        for node in component
    )


def _greedy_independent_set(adjacency):
    # Deterministic minimum-degree-first elimination. This is a lower bound,
    # not a maximum-independent-set claim.
    remaining = set(range(len(adjacency)))
    selected = []
    while remaining:
        node = min(
            remaining,
            key=lambda idx: (len(adjacency[idx].intersection(remaining)), idx),
        )
        selected.append(node)
        blocked = {node} | adjacency[node]
        remaining.difference_update(blocked)
    return tuple(selected)


def build_cubic_llzo_li2_correlation_feasibility(cif_path: Path):
    _, li2_pool = extract_cubic_llzo_two_cell_coordinate_pools(cif_path)
    coords = li2_pool.fractional_coordinates
    lattice = _load_two_cell_lattice(cif_path)
    edges = _edges(lattice, coords)
    components, adjacency = _components(len(coords), edges)
    greedy = _greedy_independent_set(adjacency)
    required = tuple(sorted({
        pattern.li2_count
        for pattern in build_exact_weighted_cubic_llzo_count_patterns()
    }))
    result = CubicLlzoLi2CorrelationFeasibility(
        diagnostic_version=DIAGNOSTIC_VERSION,
        site_count=len(coords),
        incompatibility_edge_count=len(edges),
        connected_component_sizes=tuple(sorted(len(comp) for comp in components)),
        all_components_cliques=all(_is_clique(comp, adjacency) for comp in components),
        greedy_independent_set_size=len(greedy),
        required_li2_counts=required,
        greedy_supports_all_required_counts=all(len(greedy) >= n for n in required),
    )
    result.validate()
    return result
