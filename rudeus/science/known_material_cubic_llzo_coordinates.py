"""Coordinate-pool extraction for the retained cubic Al-LLZO reference."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from pymatgen.io.cif import CifParser

from rudeus.science.contracts import Record


CUBIC_LLZO_COORDINATE_POOL_VERSION = "known-material-cubic-llzo-coordinate-pools-v1"


@dataclass(frozen=True, kw_only=True)
class CoordinateSitePool(Record):
    pool_version: str
    pool_id: str
    fractional_coordinates: tuple[tuple[str, str, str], ...]
    coordinate_hash: str


def _coord_key(values) -> tuple[str, str, str]:
    rounded = tuple((float(value) % 1.0) for value in values)
    return tuple(f"{value:.12f}" for value in rounded)


def _species_amounts(site) -> dict[str, float]:
    return {str(specie): float(amount) for specie, amount in site.species.items()}


def _matches(amounts: dict[str, float], expected: dict[str, float]) -> bool:
    return set(amounts) == set(expected) and all(
        abs(amounts[key] - value) <= 1e-8 for key, value in expected.items()
    )


def _pool(pool_id: str, coordinates) -> CoordinateSitePool:
    coords = tuple(sorted(_coord_key(values) for values in coordinates))
    payload = (
        f"{CUBIC_LLZO_COORDINATE_POOL_VERSION}|{pool_id}|"
        + "|".join(",".join(values) for values in coords)
    ).encode("utf-8")
    return CoordinateSitePool(
        pool_version=CUBIC_LLZO_COORDINATE_POOL_VERSION,
        pool_id=pool_id,
        fractional_coordinates=coords,
        coordinate_hash=hashlib.sha256(payload).hexdigest(),
    )


def extract_cubic_llzo_two_cell_coordinate_pools(
    cif_path: Path,
) -> tuple[CoordinateSitePool, CoordinateSitePool]:
    structures = CifParser(str(cif_path)).parse_structures(primitive=False)
    if len(structures) != 1:
        raise ValueError("cubic LLZO CIF must contain exactly one structure")
    structure = structures[0]
    structure.make_supercell([2, 1, 1])

    shared = []
    li2 = []
    for site in structure:
        amounts = _species_amounts(site)
        if _matches(amounts, {"Li": 0.54, "Al": 0.0653}):
            shared.append(site.frac_coords)
        elif _matches(amounts, {"Li": 0.37}):
            li2.append(site.frac_coords)

    shared_pool = _pool("Li1-Al1", shared)
    li2_pool = _pool("Li2", li2)
    if len(shared_pool.fractional_coordinates) != 48:
        raise ValueError("cubic LLZO 2-cell shared Li1/Al1 pool must contain 48 sites")
    if len(li2_pool.fractional_coordinates) != 192:
        raise ValueError("cubic LLZO 2-cell Li2 pool must contain 192 sites")
    return shared_pool, li2_pool
