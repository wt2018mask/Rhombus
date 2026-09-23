"""Frozen S2 DEV coverage-run configuration (freeze only, no execution).

This file freezes the run configuration for the first real S2 DEV coverage
evidence run. It executes nothing: no materialization, no estimation, no
intervals, no coverage run, no qualification. It imports the frozen S2
procedure identity and pins the 64-seed DEV inventory plus the disjointness
policy against every previously reserved seed set.
"""
import re

from tests.test_calibration_s2_coverage import S2_PROCEDURE, S2_PROCEDURE_HASH

# Frozen DEV inventory: 64 explicit integer seeds, committed content. -------
S2_DEV_REPLICATES = tuple(f"s2-dev-{i:02d}" for i in range(1, 65))
S2_DEV_SEEDS = {f"s2-dev-{i:02d}": seed for i, seed in enumerate(range(201, 265), start=1)}

# Previously reserved seeds (S1 DEV, S1 HELD_OUT, S2 pilot). -----------------
S1_DEV_SEEDS_RESERVED = {11, 12}
S1_HELDOUT_SEEDS_RESERVED = {21, 22}
S2_PILOT_SEEDS_RESERVED = {101, 102, 103, 104, 105, 106, 107, 108}


def test_s2_dev_inventory_frozen():
    assert len(S2_DEV_SEEDS) == 64
    assert set(S2_DEV_SEEDS.values()) == set(range(201, 265))
    assert tuple(S2_DEV_SEEDS) == S2_DEV_REPLICATES
    assert len(set(S2_DEV_REPLICATES)) == 64
    assert all(isinstance(seed, int) for seed in S2_DEV_SEEDS.values())


def test_s2_dev_disjoint_from_reserved():
    assert set(S2_DEV_SEEDS.values()).isdisjoint(S1_HELDOUT_SEEDS_RESERVED)
    assert set(S2_DEV_SEEDS.values()).isdisjoint(
        S1_DEV_SEEDS_RESERVED | S1_HELDOUT_SEEDS_RESERVED | S2_PILOT_SEEDS_RESERVED)


def test_s2_procedure_identity():
    assert re.fullmatch(r"[0-9a-f]{64}", S2_PROCEDURE_HASH)
    assert S2_PROCEDURE["version"] == "s2-interval-procedure-v1"
    assert S2_PROCEDURE["nominal_coverage"] == 0.68
