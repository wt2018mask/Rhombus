"""Generic deterministic primitives for constraint-aware partial occupancy.

These helpers are chemistry-agnostic. They operate on integer site identifiers
and precomputed incompatibility relations; callers remain responsible for
deriving scientifically justified constraints from source evidence or explicit
geometric rules.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from rudeus.science.contracts import Record


CONSTRAINT_REALIZATION_VERSION = "constraint-aware-partial-occupancy-v1"


@dataclass(frozen=True, kw_only=True)
class PairConstrainedSelection(Record):
    generator_version: str
    seed: int
    occupied_indices: tuple[int, ...]
    assignment_hash: str


def _rank(seed: int, namespace: str, index: int) -> bytes:
    return hashlib.sha256(
        f"{CONSTRAINT_REALIZATION_VERSION}|{namespace}|{seed}|{index}".encode()
    ).digest()


def pair_constrained_selection(
    *,
    incompatible_pairs: tuple[tuple[int, int], ...],
    allowed_indices: tuple[int, ...],
    occupied_count: int,
    seed: int,
    namespace: str,
) -> PairConstrainedSelection:
    """Select at most one endpoint from each incompatible pair.

    Every allowed index must belong to exactly one pair. The function is
    deterministic and fails closed if the requested count exceeds capacity.
    """
    if occupied_count < 0 or seed < 0 or not namespace:
        raise ValueError("invalid pair-constrained selection request")
    allowed = set(allowed_indices)
    pair_members = set()
    available = []
    for a, b in incompatible_pairs:
        if a == b:
            raise ValueError("incompatible pair endpoints must differ")
        if a in pair_members or b in pair_members:
            raise ValueError("incompatible pairs must be disjoint")
        pair_members.update((a, b))
        endpoints = tuple(index for index in (a, b) if index in allowed)
        if endpoints:
            available.append((a, b, endpoints))
    if allowed - pair_members:
        raise ValueError("allowed index is not covered by an incompatible pair")
    if occupied_count > len(available):
        raise ValueError("requested occupancy exceeds constrained capacity")

    ranked_pairs = sorted(
        available,
        key=lambda item: (
            _rank(seed, f"{namespace}:pair", min(item[0], item[1])),
            min(item[0], item[1]),
        ),
    )[:occupied_count]
    selected = []
    for a, b, endpoints in ranked_pairs:
        endpoint = min(
            endpoints,
            key=lambda index: (_rank(seed, f"{namespace}:endpoint", index), index),
        )
        selected.append(endpoint)
    selected_tuple = tuple(sorted(selected))
    payload = (
        f"{CONSTRAINT_REALIZATION_VERSION}|{namespace}|{seed}|"
        + ",".join(map(str, selected_tuple))
    ).encode()
    result = PairConstrainedSelection(
        generator_version=CONSTRAINT_REALIZATION_VERSION,
        seed=seed,
        occupied_indices=selected_tuple,
        assignment_hash=hashlib.sha256(payload).hexdigest(),
    )
    result.validate()
    return result


def endpoint_block_mask(blocked_indices: tuple[int, ...]) -> int:
    mask = 0
    for index in blocked_indices:
        if index < 0:
            raise ValueError("site indices must be non-negative")
        mask |= 1 << index
    return mask


def merge_block_masks(masks) -> int:
    merged = 0
    for mask in masks:
        if mask < 0:
            raise ValueError("block masks must be non-negative")
        merged |= mask
    return merged


def available_pair_count(
    *, blocked_mask: int, incompatible_pairs: tuple[tuple[int, int], ...]
) -> int:
    if blocked_mask < 0:
        raise ValueError("block mask must be non-negative")
    return sum(
        not (((blocked_mask >> a) & 1) and ((blocked_mask >> b) & 1))
        for a, b in incompatible_pairs
    )
