"""Deterministic mutually-exclusive assignment for species sharing one site pool."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from rudeus.science.contracts import Record
from rudeus.science.known_material_site_assignment import SITE_ASSIGNMENT_GENERATOR_VERSION


@dataclass(frozen=True, kw_only=True)
class SharedSiteAssignment(Record):
    generator_version: str
    seed: int
    first_species_indices: tuple[int, ...]
    second_species_indices: tuple[int, ...]
    assignment_hash: str


def deterministic_shared_site_assignment(
    *,
    site_count: int,
    first_count: int,
    second_count: int,
    seed: int,
    namespace: str,
) -> SharedSiteAssignment:
    if site_count <= 0 or first_count < 0 or second_count < 0:
        raise ValueError("shared-site counts must be non-negative with positive site_count")
    if first_count + second_count > site_count:
        raise ValueError("shared-site species counts exceed available sites")
    if seed < 0 or not namespace:
        raise ValueError("shared-site assignment requires seed and namespace")
    ranked = []
    for index in range(site_count):
        token = (
            f"{SITE_ASSIGNMENT_GENERATOR_VERSION}|shared|{namespace}|{seed}|{index}"
        ).encode("utf-8")
        ranked.append((hashlib.sha256(token).digest(), index))
    order = tuple(index for _, index in sorted(ranked))
    first = tuple(sorted(order[:first_count]))
    second = tuple(sorted(order[first_count:first_count + second_count]))
    payload = (
        f"{SITE_ASSIGNMENT_GENERATOR_VERSION}|shared|{namespace}|{seed}|"
        f"first={','.join(map(str, first))}|second={','.join(map(str, second))}"
    ).encode("utf-8")
    return SharedSiteAssignment(
        generator_version=SITE_ASSIGNMENT_GENERATOR_VERSION,
        seed=seed,
        first_species_indices=first,
        second_species_indices=second,
        assignment_hash=hashlib.sha256(payload).hexdigest(),
    )
