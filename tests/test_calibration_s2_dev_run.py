"""Frozen S2 DEV coverage-run configuration (freeze only, no execution).

This file freezes the run configuration for the first real S2 DEV coverage
evidence run. It executes nothing: no materialization, no estimation, no
intervals, no coverage run, no qualification. It imports the frozen S2
procedure identity and pins the 64-seed DEV inventory plus the disjointness
policy against every previously reserved seed set.
"""
import re

from rudeus.science.calibration_s2 import (
    S1_DEV_SEEDS_RESERVED,
    S1_HELDOUT_SEEDS_RESERVED,
    S2_DEV_REPLICATES,
    S2_DEV_SEEDS,
    S2_PILOT_SEEDS_RESERVED,
    S2_PROCEDURE,
    S2_PROCEDURE_HASH,
)


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
