"""S2 single-point DEV coverage pilot (measurement loop only, no qualification).

Frozen S2 interval-procedure contract + ONE small DEV pilot through the
existing `coverage_experiment` harness. Every number below is a frozen
measurement-loop parameter with NO scientific-validity claim:
- `nominal_coverage_provisional` is a requested interval level, NOT validated coverage.
- `block_origins` is a selected procedural input, NOT a qualified block-length rule.
- S1 truth is long-time ensemble Brownian truth; the estimator's finite-window
  result is compared to it descriptively; no equivalence is assumed.
This pilot produces no qualification evidence and cannot populate P3
uncertainty bounds.
"""
import numpy as np

from rudeus.science.contracts import UNRESOLVED, digest
from rudeus.science.statistics import (
    MATCHED_ORIGIN_BLOCKS_V2,
    ResamplingSpec,
    coverage_experiment,
    matched_origin_block_bootstrap,
)
from rudeus.science.synthetic import brownian
from rudeus.science.transport import analyze_trajectory
from rudeus.science.calibration_s1 import (
    S1_CODE_REVISION,
    S1_DEV_SEEDS,
    S1_ESTIMATOR_CONFIG,
    S1_HELDOUT_SEEDS,
    S1_TRUTH_D_M2_PER_S,
)
from rudeus.science.calibration_s2 import (
    S2_BLOCK_ORIGINS,
    S2_MONTE_CARLO_CONFIDENCE,
    S2_N_RESAMPLES,
    S2_NOMINAL_COVERAGE,
    S2_PILOT_SEEDS,
    S2_PROCEDURE,
    S2_PROCEDURE_HASH,
    S2_RESAMPLING_SEED,
)


def _s2_spec(seed):
    return ResamplingSpec(
        block_origins=S2_BLOCK_ORIGINS,
        min_blocks_provisional=1,
        n_resamples=S2_N_RESAMPLES,
        nominal_coverage_provisional=S2_NOMINAL_COVERAGE,
        seed=seed,
        replica_scheme="single_trajectory_no_replica_resampling",
        joint_quantities=("D:Li",),
        method=MATCHED_ORIGIN_BLOCKS_V2,
    )


def _s2_generate(seed):
    return brownian(
        n_frames=8,
        n_ions=2,
        diffusion_tensor=(0.1 * np.eye(3)).tolist(),
        dt_ps=1.0,
        seed=seed,
    )


def _s2_estimate(positions):
    point = analyze_trajectory(
        positions,
        ["Li"] * 2,
        np.arange(8),
        1000,
        (1, 2),
        **S1_ESTIMATOR_CONFIG,
    )
    population_hash = point["self_diffusion_by_species"]["Li"]["origin_population_hash"]
    resampled = matched_origin_block_bootstrap(
        positions,
        ["Li"] * 2,
        np.arange(8),
        1000,
        (1, 2),
        spec=_s2_spec(S2_RESAMPLING_SEED),
        expected_population_hash=population_hash,
        **S1_ESTIMATOR_CONFIG,
    )
    return {
        "estimate": point["self_diffusion_by_species"]["Li"]["D_m2_per_s"],
        "interval": resampled["intervals"]["D:Li"],
    }


def _s2_run():
    return coverage_experiment(
        _s2_generate,
        _s2_estimate,
        seeds=list(S2_PILOT_SEEDS),
        truth=S1_TRUTH_D_M2_PER_S,
        nominal_coverage=S2_NOMINAL_COVERAGE,
        monte_carlo_confidence=S2_MONTE_CARLO_CONFIDENCE,
        generating_protocol={
            "scope": "S1 isotropic-Brownian scope verbatim",
            "procedure_hash": S2_PROCEDURE_HASH,
        },
    )


def test_s2_procedure_hash():
    assert S2_PROCEDURE_HASH == digest(S2_PROCEDURE)
    assert digest(S2_PROCEDURE) == digest(dict(S2_PROCEDURE))


def test_s2_frozen_content():
    assert S2_PROCEDURE["version"] == "s2-interval-procedure-v1"
    assert S2_PROCEDURE["estimator"] == "free_intercept_OLS_MSD"
    assert S2_PROCEDURE["estimator_config"] == S1_ESTIMATOR_CONFIG
    assert S2_PROCEDURE["resampling_method"] == MATCHED_ORIGIN_BLOCKS_V2
    assert S2_PROCEDURE["nominal_coverage"] == S2_NOMINAL_COVERAGE
    assert S2_PROCEDURE["resampling_spec"]["nominal_coverage_provisional"] == \
        S2_NOMINAL_COVERAGE
    assert S2_PROCEDURE["truth"] == {
        "type": "ANALYTICAL",
        "interpretation": "ensemble/long-time/bulk",
        "value": S1_TRUTH_D_M2_PER_S,
        "units": "m2/s",
    }
    assert S2_PROCEDURE["scope"] == "S1 isotropic-Brownian scope verbatim"
    assert S2_PROCEDURE["code_revision"] == S1_CODE_REVISION


def test_s2_pilot_coverage_run():
    result = _s2_run()
    assert len(result["records"]) == len(S2_PILOT_SEEDS)
    assert [r["seed"] for r in result["records"]] == list(S2_PILOT_SEEDS)
    assert 0.0 <= result["coverage_unconditional"] <= 1.0
    assert "abstention_rate" in result
    for record in result["records"]:
        assert set(record) >= {"seed", "estimate", "interval", "error"}
        if record["interval"] is not None:
            lo, hi = record["interval"]
            assert lo <= hi
    assert result["truth"] == S1_TRUTH_D_M2_PER_S
    assert result["nominal_coverage"] == S2_NOMINAL_COVERAGE
    assert result["scientific_qualification"] == UNRESOLVED


def test_s2_deterministic_rerun():
    first = _s2_run()
    second = _s2_run()
    assert first == second


def test_s2_seed_disjointness():
    assert len(set(S2_PILOT_SEEDS)) == len(S2_PILOT_SEEDS)
    s1_used = set(S1_DEV_SEEDS.values()) | set(S1_HELDOUT_SEEDS.values())
    assert set(S2_PILOT_SEEDS).isdisjoint(s1_used)


def test_s2_no_qualification():
    result = _s2_run()
    assert "QualificationRecord" not in str(type(result))
    assert result["scientific_qualification"] == UNRESOLVED
    assert "PASS" not in result and "FAIL" not in result
    assert result["registered_criteria"] is None
