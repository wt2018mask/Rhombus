"""Materialize the exact-weighted cubic Al-LLZO realization plans as ordered structures."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from pymatgen.core import Structure
from pymatgen.io.cif import CifParser

from rudeus.science.known_material_cubic_llzo_coordinates import (
    extract_cubic_llzo_two_cell_coordinate_pools,
)
from rudeus.science.known_material_cubic_llzo_ordered import ordered_structure_hash
from rudeus.science.known_material_cubic_llzo_weighted_plan import (
    WEIGHTING_ASSUMPTION,
    build_weighted_cubic_llzo_realization_plans,
)


@dataclass(frozen=True)
class WeightedOrderedCubicLlzo:
    member_index: int
    weight_numerator: int
    weight_denominator: int
    weighting_assumption: str
    assignment_hash: str
    structure_hash: str
    structure: Structure

    @property
    def weight(self) -> Fraction:
        return Fraction(self.weight_numerator, self.weight_denominator)


def _host_sites(structure: Structure):
    hosts = []
    for site in structure:
        if site.is_ordered and site.specie.symbol in {"La", "Zr", "O"}:
            coords = tuple(float(value) % 1.0 for value in site.frac_coords)
            hosts.append((site.specie.symbol, coords))
    return tuple(sorted(hosts, key=lambda item: (item[0], item[1])))


def _coord(values) -> tuple[float, float, float]:
    return tuple(float(value) for value in values)


def build_weighted_cubic_llzo_ordered_structures(
    cif_path: Path,
) -> tuple[WeightedOrderedCubicLlzo, ...]:
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
    members = []
    for plan in build_weighted_cubic_llzo_realization_plans():
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

        structure = Structure(
            lattice=source.lattice,
            species=species,
            coords=coordinates,
            coords_are_cartesian=False,
            to_unit_cell=True,
        )
        if not structure.is_ordered:
            raise ValueError("weighted cubic LLZO realization must be fully ordered")
        members.append(
            WeightedOrderedCubicLlzo(
                member_index=plan.member_index,
                weight_numerator=plan.weight_numerator,
                weight_denominator=plan.weight_denominator,
                weighting_assumption=WEIGHTING_ASSUMPTION,
                assignment_hash=plan.assignment_hash,
                structure_hash=ordered_structure_hash(structure),
                structure=structure,
            )
        )
    return tuple(members)
