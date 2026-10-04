"""Frozen S2 v2 prospective population inventories (Stage-B prerequisite).

Explicit committed DEV-A / DEV-B / HELD_OUT replicate inventories: stable
IDs bound one-to-one to explicit integer seeds. Freeze-only: no execution,
no trajectories, no scores, no learned quantile, no calibration package, no
qualification state, no populated production uncertainty bounds.

Design notes (prospective, never tuned from outcomes):
- Seed ranges are the smallest contiguous blocks after the highest
  previously consumed/reserved seed (264): DEV-A 265..363 (99), DEV-B
  364..477 (114), HELD_OUT 478..856 (379). Explicit committed ranges, never
  random, never derived at execution time.
- ID style ``s2v2-<pop>-<NNN>`` extends the repository ``s2-dev-<NN>``
  convention to three-digit zero padding (required: HELD_OUT needs 379
  IDs) with an ``s2v2-`` prefix so v2 IDs can never collide with, or be
  mistaken for, v1 ``s2-dev-*`` / S1 ``s1-*`` IDs. Zero padding keeps
  lexicographic order identical to numeric order.
- This module is deliberately separate from calibration_s2v2.py so that
  method-policy identity, population-inventory identity, and the future
  learned calibration package remain conceptually and hash-distinct. The
  inventories bind S2V2_METHOD_HASH by value; they never alter it.

Two-stage boundary reminder:
    PRE-DEV METHOD IDENTITY (calibration_s2v2.S2V2_METHOD_HASH)
    + THESE inventories -> COMPLETE PRE-HELD_OUT IDENTITY (later)
    -> blind HELD_OUT once. DEV-B is never pooled into DEV-A after
  inspection; any redesign needs a new procedure version with fresh data.
"""

from __future__ import annotations

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration_s1 import S1_TRUTH_D_M2_PER_S
from rudeus.science.calibration_s2v2 import S2V2_METHOD_HASH
from rudeus.science.contracts import digest

# Previously consumed/reserved seeds: S1 DEV {11, 12}, S1 HELD_OUT {21, 22},
# S2 pilot {101..108}, S2 v1 DEV {201..264}. Structured exclusion set so the
# disjointness requirement is enforced, not merely documented.
S2V2_EXCLUDED_SEEDS = frozenset(
    {11, 12, 21, 22} | set(range(101, 109)) | set(range(201, 265)))

# Frozen population shapes: (id prefix, first seed, count, split, role). ----
S2V2_DEV_A_COUNT = 99
S2V2_DEV_B_COUNT = 114
S2V2_HELDOUT_COUNT = 379

S2V2_DEV_A_SEED_FIRST = 265
S2V2_DEV_B_SEED_FIRST = 364
S2V2_HELDOUT_SEED_FIRST = 478

S2V2_DEV_A_ROLE = "calibration-only-derive-q-hat-never-qualification"
S2V2_DEV_B_ROLE = "independent-descriptive-validation-never-qualification"
S2V2_HELDOUT_ROLE = "single-blind-confirmation-never-tuning"

S2V2_DEV_A_SPLIT = "DEV"
S2V2_DEV_B_SPLIT = "DEV"
S2V2_HELDOUT_SPLIT = "HELD_OUT"


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _build_mapping(prefix, seed_first, count):
    """Deterministic one-to-one id <-> seed mapping over an explicit range."""
    return {f"{prefix}-{index:03d}": seed_first + index - 1
            for index in range(1, count + 1)}


S2V2_DEV_A_SEEDS = _build_mapping("s2v2-dev-a", S2V2_DEV_A_SEED_FIRST, S2V2_DEV_A_COUNT)
S2V2_DEV_B_SEEDS = _build_mapping("s2v2-dev-b", S2V2_DEV_B_SEED_FIRST, S2V2_DEV_B_COUNT)
S2V2_HELDOUT_SEEDS = _build_mapping("s2v2-heldout", S2V2_HELDOUT_SEED_FIRST,
                                     S2V2_HELDOUT_COUNT)


def build_s2v2_population_record(*, role, split, seeds, method_hash=S2V2_METHOD_HASH):
    """Canonical inventory record binding role/ids/seeds to the v2 method.

    Contains scheduling identity only: no outcome, result, interval, score,
    quantile, or evaluation fields may ever appear here.
    """
    ordered_ids = tuple(sorted(seeds))
    return {
        "version": "s2-v2-population-v1",
        "role": role,
        "split": split,
        "replicate_ids": ordered_ids,
        "seeds": {replicate_id: seeds[replicate_id] for replicate_id in ordered_ids},
        "count": len(ordered_ids),
        "method_hash": method_hash,
        "calibration_class": "isotropic_brownian",
        "parameter_cell": "cell-a",
        "generator": "brownian",
        "generator_version": "synthetic-v1",
        "scope": "S1-isotropic-Brownian-scope-verbatim",
        "truth": {"type": "ANALYTICAL", "value": {"D_m2_per_s": S1_TRUTH_D_M2_PER_S},
                  "units": "m2/s"},
    }


S2V2_DEV_A_RECORD = build_s2v2_population_record(
    role=S2V2_DEV_A_ROLE, split=S2V2_DEV_A_SPLIT, seeds=S2V2_DEV_A_SEEDS)
S2V2_DEV_B_RECORD = build_s2v2_population_record(
    role=S2V2_DEV_B_ROLE, split=S2V2_DEV_B_SPLIT, seeds=S2V2_DEV_B_SEEDS)
S2V2_HELDOUT_RECORD = build_s2v2_population_record(
    role=S2V2_HELDOUT_ROLE, split=S2V2_HELDOUT_SPLIT, seeds=S2V2_HELDOUT_SEEDS)

S2V2_DEV_A_HASH = digest(S2V2_DEV_A_RECORD)
S2V2_DEV_B_HASH = digest(S2V2_DEV_B_RECORD)
S2V2_HELDOUT_HASH = digest(S2V2_HELDOUT_RECORD)

S2V2_POPULATIONS = {
    "version": "s2-v2-populations-v1",
    "method_hash": S2V2_METHOD_HASH,
    "dev_a": S2V2_DEV_A_HASH,
    "dev_b": S2V2_DEV_B_HASH,
    "heldout": S2V2_HELDOUT_HASH,
}
S2V2_POPULATIONS_HASH = digest(S2V2_POPULATIONS)


def assert_frozen_v2_populations():
    """Verify frozen inventory counts, disjointness, roles, and bindings."""
    populations = {"DEV-A": (S2V2_DEV_A_SEEDS, S2V2_DEV_A_COUNT, S2V2_DEV_A_ROLE,
                             S2V2_DEV_A_RECORD, S2V2_DEV_A_HASH),
                   "DEV-B": (S2V2_DEV_B_SEEDS, S2V2_DEV_B_COUNT, S2V2_DEV_B_ROLE,
                             S2V2_DEV_B_RECORD, S2V2_DEV_B_HASH),
                   "HELD_OUT": (S2V2_HELDOUT_SEEDS, S2V2_HELDOUT_COUNT,
                                S2V2_HELDOUT_ROLE, S2V2_HELDOUT_RECORD,
                                S2V2_HELDOUT_HASH)}
    for name, (seeds, count, role, record, identity) in populations.items():
        if len(seeds) != count:
            _fail(f"S2 v2 {name} inventory count is not frozen")
        if len(set(seeds)) != count or len(set(seeds.values())) != count:
            _fail(f"S2 v2 {name} id/seed mapping is not one-to-one")
        if list(seeds) != sorted(seeds):
            _fail(f"S2 v2 {name} inventory order is not deterministic")
        if record["role"] != role or record["count"] != count:
            _fail(f"S2 v2 {name} record role/count mismatch")
        if record["method_hash"] != S2V2_METHOD_HASH:
            _fail(f"S2 v2 {name} record is not bound to the frozen method")
        if digest(record) != identity:
            _fail(f"S2 v2 {name} inventory hash mismatch")
        if set(seeds.values()) & S2V2_EXCLUDED_SEEDS:
            _fail(f"S2 v2 {name} seeds overlap historical reserved seeds")
    seed_sets = [set(seeds.values()) for seeds, _, _, _, _ in populations.values()]
    id_sets = [set(seeds) for seeds, _, _, _, _ in populations.values()]
    for left in range(3):
        for right in range(left + 1, 3):
            if seed_sets[left] & seed_sets[right]:
                _fail("S2 v2 populations are not seed-disjoint")
            if id_sets[left] & id_sets[right]:
                _fail("S2 v2 populations are not ID-disjoint")
    if digest(S2V2_POPULATIONS) != S2V2_POPULATIONS_HASH:
        _fail("S2 v2 combined populations hash mismatch")


__all__ = [
    "S2V2_EXCLUDED_SEEDS",
    "S2V2_DEV_A_COUNT", "S2V2_DEV_B_COUNT", "S2V2_HELDOUT_COUNT",
    "S2V2_DEV_A_SEED_FIRST", "S2V2_DEV_B_SEED_FIRST", "S2V2_HELDOUT_SEED_FIRST",
    "S2V2_DEV_A_ROLE", "S2V2_DEV_B_ROLE", "S2V2_HELDOUT_ROLE",
    "S2V2_DEV_A_SPLIT", "S2V2_DEV_B_SPLIT", "S2V2_HELDOUT_SPLIT",
    "S2V2_DEV_A_SEEDS", "S2V2_DEV_B_SEEDS", "S2V2_HELDOUT_SEEDS",
    "S2V2_DEV_A_RECORD", "S2V2_DEV_B_RECORD", "S2V2_HELDOUT_RECORD",
    "S2V2_DEV_A_HASH", "S2V2_DEV_B_HASH", "S2V2_HELDOUT_HASH",
    "S2V2_POPULATIONS", "S2V2_POPULATIONS_HASH",
    "assert_frozen_v2_populations", "build_s2v2_population_record",
]
