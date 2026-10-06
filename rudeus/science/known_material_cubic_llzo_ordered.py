"""Build deterministic ordered cubic Al-LLZO structures from frozen plans."""
from __future__ import annotations

import hashlib
from pathlib import Path

from pymatgen.core import Structure
from pymatgen.io.cif import CifParser

from rudeus.science.known_material_cubic_llzo_coordinates import (
    extract_cubic_llzo_two_cell_coordinate_pools,
)
from rudeus.science.known_material_cubic_llzo_realization import (
    build_cubic_llzo_realization_plans,
)


def _coord(values) -> tuple[float, float, float]:
    return tuple(float(value) for value in values)


def _host_sites(structure: Structure):
    hosts = []
    for site in structure:
        if not site.is_ordered:
            continue
        symbol = site.specie.symbol
        if symbol in {"La", "Zr", "O"}:
            coords = tuple(float(value) % 1.0 for value in site.frac_coords)
            hosts.append((symbol, coords))
    return tuple(sorted(hosts, key=lambda item: (item[0], item[1])))


def build_cubic_llzo_ordered_structures(cif_path: Path) -> tuple[Structure, ...]:
    parsed = CifParser(str(cif_path)).parse_structures(primitive=False)
    if len(parsed) != 1:
        raise ValueError("cubic LLZO CIF must contain exactly one structure")
    source = parsed[0]
    source.make_supercell([2, 1, 1])

    hosts = _host_sites(source)
    host_counts = {
        symbol: sum(1 for host_symbol, _ in hosts if host_symbol == symbol)
        for symbol in ("La", "Zr", "O")
    }
    if host_counts != {"La": 48, "Zr": 32, "O": 192}:
        raise ValueError("unexpected cubic LLZO fixed-host multiplicities")

    shared_pool, li2_pool = extract_cubic_llzo_two_cell_coordinate_pools(cif_path)
    plans = build_cubic_llzo_realization_plans()
    structures = []
    for plan in plans:
        species = [symbol for symbol, _ in hosts]
        coordinates = [coords for _, coords in hosts]

        for index in plan.li1_indices:
            species.append("Li")
            coordinates.append(_coord(shared_pool.fractional_coordinates[index]))
        for index in plan.al1_indices:
            species.append("Al")
            coordinates.append(_coord(shared_pool.fractional_coordinates[index]))
        for index in plan.li2_indices:
            species.append("Li")
            coordinates.append(_coord(li2_pool.fractional_coordinates[index]))

        ordered = Structure(
            lattice=source.lattice,
            species=species,
            coords=coordinates,
            coords_are_cartesian=False,
            to_unit_cell=True,
        )
        if not ordered.is_ordered:
            raise ValueError("generated cubic LLZO realization must be fully ordered")
        structures.append(ordered)
    return tuple(structures)


def ordered_structure_hash(structure: Structure) -> str:
    rows = []
    for site in structure:
        if not site.is_ordered:
            raise ValueError("structure hash requires an ordered structure")
        coords = tuple(float(value) % 1.0 for value in site.frac_coords)
        rows.append(
            (
                site.specie.symbol,
                *(f"{value:.12f}" for value in coords),
            )
        )
    rows.sort()
    lattice = ",".join(f"{value:.12f}" for value in structure.lattice.matrix.flatten())
    payload = lattice + "|" + "|".join(",".join(row) for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
