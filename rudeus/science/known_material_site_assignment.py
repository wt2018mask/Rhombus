"""Deterministic, count-preserving assignment of species to candidate sites."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from rudeus.science.contracts import Record


SITE_ASSIGNMENT_GENERATOR_VERSION = "known-material-site-assignment-sha256-v1"


@dataclass(frozen=True, kw_only=True)
class SiteAssignment(Record):
    generator_version: str
    seed: int
    occupied_site_indices: tuple[int, ...]
    assignment_hash: str


def deterministic_site_assignment(
    *,
    site_count: int,
    occupied_count: int,
    seed: int,
    namespace: str,
) -> SiteAssignment:
    if site_count <= 0:
        raise ValueError("site_count must be positive")
    if occupied_count < 0 or occupied_count > site_count:
        raise ValueError("occupied_count must lie in [0, site_count]")
    if seed < 0 or not namespace:
        raise ValueError("assignment requires non-negative seed and namespace")

    ranked = []
    for index in range(site_count):
        token = (
            f"{SITE_ASSIGNMENT_GENERATOR_VERSION}|{namespace}|{seed}|{index}"
        ).encode("utf-8")
        ranked.append((hashlib.sha256(token).digest(), index))
    selected = tuple(sorted(index for _, index in sorted(ranked)[:occupied_count]))
    payload = (
        f"{SITE_ASSIGNMENT_GENERATOR_VERSION}|{namespace}|{seed}|"
        + ",".join(map(str, selected))
    ).encode("utf-8")
    return SiteAssignment(
        generator_version=SITE_ASSIGNMENT_GENERATOR_VERSION,
        seed=seed,
        occupied_site_indices=selected,
        assignment_hash=hashlib.sha256(payload).hexdigest(),
    )
