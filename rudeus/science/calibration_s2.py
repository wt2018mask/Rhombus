"""Frozen S2 interval-procedure contract and DEV run inventory.

Frozen S2 measurement-loop parameters with NO scientific-validity claim:
- `nominal_coverage_provisional` is a requested interval level, NOT validated coverage.
- `block_origins` is a selected procedural input, NOT a qualified block-length rule.
- DEV seed inventory is committed content disjoint from all reserved seed sets.

This module is the canonical home of the S2 frozen content (previously
defined in tests). Values here are committed scientific content: do not
alter them without a new frozen contract.
"""
from rudeus.science.calibration_s1 import (
    S1_CODE_REVISION,
    S1_ESTIMATOR_CONFIG,
    S1_TRUTH_D_M2_PER_S,
)
from rudeus.science.contracts import digest
from rudeus.science.statistics import MATCHED_ORIGIN_BLOCKS_V2

# Frozen S2 procedure: measurement-loop parameters only, no validity claims. --
S2_NOMINAL_COVERAGE = 0.68  # requested interval level only, NOT validated coverage
S2_BLOCK_ORIGINS = 2  # selected procedural input, NOT a qualified block-length rule
S2_N_RESAMPLES = 16  # explicit resample count, NOT a sufficiency claim
S2_MONTE_CARLO_CONFIDENCE = 0.95  # counting uncertainty only, NOT trajectory physics
S2_PILOT_SEEDS = [101, 102, 103, 104, 105, 106, 107, 108]  # pilot-only DEV seeds
S2_RESAMPLING_SEED = 7  # explicit per-trajectory resampling seed

S2_PROCEDURE = {
    "version": "s2-interval-procedure-v1",
    "estimator": "free_intercept_OLS_MSD",
    "estimator_config": dict(S1_ESTIMATOR_CONFIG),
    "resampling_method": MATCHED_ORIGIN_BLOCKS_V2,
    "resampling_spec": {
        "block_origins": S2_BLOCK_ORIGINS,
        "n_resamples": S2_N_RESAMPLES,
        "nominal_coverage_provisional": S2_NOMINAL_COVERAGE,
        "seed_scheme": "explicit per-trajectory seed",
        "joint_quantities": ("D:Li",),
    },
    "nominal_coverage": S2_NOMINAL_COVERAGE,
    "block_origins": S2_BLOCK_ORIGINS,
    "truth": {
        "type": "ANALYTICAL",
        "interpretation": "ensemble/long-time/bulk",
        "value": S1_TRUTH_D_M2_PER_S,
        "units": "m2/s",
    },
    "scope": "S1 isotropic-Brownian scope verbatim",
    "code_revision": S1_CODE_REVISION,
}
S2_PROCEDURE_HASH = digest(S2_PROCEDURE)

# Frozen DEV inventory: 64 explicit integer seeds, committed content. -------
S2_DEV_REPLICATES = tuple(f"s2-dev-{i:02d}" for i in range(1, 65))
S2_DEV_SEEDS = {f"s2-dev-{i:02d}": seed for i, seed in enumerate(range(201, 265), start=1)}

# Previously reserved seeds (S1 DEV, S1 HELD_OUT, S2 pilot). -----------------
S1_DEV_SEEDS_RESERVED = {11, 12}
S1_HELDOUT_SEEDS_RESERVED = {21, 22}
S2_PILOT_SEEDS_RESERVED = {101, 102, 103, 104, 105, 106, 107, 108}
