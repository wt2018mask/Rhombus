"""Phase 2 diagnostic resampling contract; no coverage or qualification claims."""
import numpy as np
import pytest

import rudeus.science.statistics as statistics
from rudeus.science.contracts import UNRESOLVED, digest
from rudeus.science.p3 import analyze_p3
from rudeus.science.statistics import (MATCHED_ORIGIN_BLOCKS_V2, ResamplingSpec,
                                       matched_origin_block_bootstrap)
from rudeus.science.transport import analyze_trajectory, displacement_moments
from tests.test_p3_scientific_slice import protocol
from tests.test_scientific_transport import bound_inputs, kwargs, trajectory


def phase2_spec(**changes):
    values = dict(block_origins=9, min_blocks_provisional=999, n_resamples=12,
                  nominal_coverage_provisional=.68, seed=41,
                  replica_scheme="single_trajectory_no_replica_resampling",
                  joint_quantities=("D:Li",), method=MATCHED_ORIGIN_BLOCKS_V2)
    values.update(changes)
    return ResamplingSpec(**values)


def run_phase2(positions=None, **spec_changes):
    positions = trajectory() if positions is None else positions
    lags = tuple(range(1, 9))
    point = analyze_trajectory(positions, ["Li"]*2, np.arange(80), 100, lags, **kwargs())
    population_hash = point["self_diffusion_by_species"]["Li"]["origin_population_hash"]
    return matched_origin_block_bootstrap(
        positions, ["Li"]*2, np.arange(80), 100, lags,
        spec=phase2_spec(**spec_changes), expected_population_hash=population_hash, **kwargs())


def test_unit_weights_reproduce_primary_msd_tensor_and_signed_estimator():
    positions = trajectory()
    lags = tuple(range(1, 9))
    primary = analyze_trajectory(positions, ["Li"]*2, np.arange(80), 100, lags, **kwargs())
    weighted = analyze_trajectory(positions, ["Li"]*2, np.arange(80), 100, lags,
                                  origin_weights=np.ones(79, dtype=int), **kwargs())
    a, b = primary["self_diffusion_by_species"]["Li"], weighted["self_diffusion_by_species"]["Li"]
    assert b["D_m2_per_s"] == pytest.approx(a["D_m2_per_s"])
    assert np.allclose(b["D_tensor_m2_per_s"], a["D_tensor_m2_per_s"])
    assert b["intercept_A2"] == pytest.approx(a["intercept_A2"])
    assert b["origin_counts"] == a["origin_counts"]


def test_full_population_tail_and_lag_specific_support_are_retained():
    result = run_phase2()
    assert result["eligible_origin_union"] == 79
    assert result["block_boundaries"] == [[0, 9], [9, 18], [18, 27], [27, 36],
                                           [36, 45], [45, 54], [54, 63], [63, 72], [72, 79]]
    assert result["tail_block_policy"] == "preserve_short_final_block"
    assert result["lag_support_counts"] == {str(lag): 80-lag for lag in range(1, 9)}
    assert result["lag_block_support_counts"]["8"][-1] == 0
    assert result["effective_independent_blocks"] is None
    assert result["coordinate_joining"] is False


def test_population_mismatch_and_alternate_method_are_rejected():
    with pytest.raises(ValueError, match="population differs"):
        matched_origin_block_bootstrap(
            trajectory(), ["Li"]*2, np.arange(80), 100, range(1, 9),
            spec=phase2_spec(), expected_population_hash=digest("forged"), **kwargs())
    with pytest.raises(ValueError, match="versioned method"):
        matched_origin_block_bootstrap(
            trajectory(), ["Li"]*2, np.arange(80), 100, range(1, 9),
            spec=phase2_spec(method="explicit_common_origin_blocks-v1-unqualified"),
            expected_population_hash=digest("irrelevant"), **kwargs())


def test_integer_block_weights_are_joint_across_atoms_species_lags_and_tensors():
    positions = trajectory()
    positions = np.concatenate([positions[:, :1], positions[:, :1] * np.array([2., 1., -1.])], axis=1)
    labels = ["Li", "Na"]
    lags = (1, 3)
    weights = np.zeros(79, dtype=int)
    weights[:9] = 2
    weights[18:27] = 1
    moments = displacement_moments(positions, labels, np.arange(80), 100, lags,
                                   selected_species=("Li", "Na"), origin_weights=weights)
    for lag_index, lag in enumerate(lags):
        rows = np.arange(80-lag)
        w = weights[:80-lag]
        for species, atom in (("Li", 0), ("Na", 1)):
            delta = positions[rows+lag, atom] - positions[rows, atom]
            expected = np.average(np.einsum("na,nb->nab", delta, delta), axis=0, weights=w)
            assert moments["self_tensors_A2"][species][lag_index] == pytest.approx(expected)
    assert moments["origin_counts"] == [27, 27]
    assert moments["origin_weight_hash"] == digest(weights.tolist())


def test_zero_lag_denominator_is_explicit():
    weights = np.zeros(79, dtype=int)
    weights[72:] = 1
    with pytest.raises(ValueError, match="zero resampling weight for lag 8"):
        displacement_moments(trajectory(), ["Li"]*2, np.arange(80), 100, range(1, 9),
                             selected_species=("Li",), origin_weights=weights)


def test_failed_draw_is_retained_without_retry_and_disables_interval(monkeypatch):
    original = statistics._weighted_analysis
    calls = {"count": 0}
    def fail_first(*args, **kw):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("planned_test_failure")
        return original(*args, **kw)
    monkeypatch.setattr(statistics, "_weighted_analysis", fail_first)
    result = run_phase2(n_resamples=4)
    assert calls["count"] == 4
    assert len(result["draw_records"]) == result["planned_draws"] == 4
    assert result["draw_records"][0]["status"] == "FAILED"
    assert result["failed_draws"] == [{"draw": 0, "reason": "planned_test_failure"}]
    assert result["draws"]["D:Li"][0] is None
    assert result["intervals"]["D:Li"] is None
    assert result["diagnostic_interval_available"] is False


def test_seed_metadata_fixed_window_and_draws_are_reproducible():
    a, b = run_phase2(), run_phase2()
    assert a == b
    assert a["planned_draws"] == len(a["draw_records"]) == 12
    assert a["rng"] == "numpy.random.Generator(PCG64)" and a["seed"] == 41
    assert a["quantile_method"] == "linear"
    assert a["estimator_specification"]["fit_window_ps"] == [.1, .8]
    assert a["estimator_specification"]["forced_zero_intercept"] is False
    assert a["estimator_specification_hash"] == digest(a["estimator_specification"])
    assert a["resampling_spec"]["min_blocks_provisional"] == 999  # recorded, never used as a gate
    assert all(record["status"] == "COMPLETED" for record in a["draw_records"])


def test_negative_resampled_slopes_remain_signed_and_window_is_fixed():
    time = np.arange(80)
    positions = np.zeros((80, 2, 3))
    positions[:, :, 0] = np.sin(2*np.pi*time/8)[:, None]
    lags = tuple(range(1, 9))
    fit_kwargs = {**kwargs(), "fit_window_ps": (.4, .8)}
    point = analyze_trajectory(positions, ["Li"]*2, time, 100, lags, **fit_kwargs)
    population_hash = point["self_diffusion_by_species"]["Li"]["origin_population_hash"]
    result = matched_origin_block_bootstrap(
        positions, ["Li"]*2, time, 100, lags, spec=phase2_spec(),
        expected_population_hash=population_hash, **fit_kwargs)
    assert point["self_diffusion_by_species"]["Li"]["D_m2_per_s"] < 0
    assert all(value < 0 for value in result["draws"]["D:Li"])
    assert result["estimator_specification"]["fit_window_ps"] == [.4, .8]
    assert result["estimator_specification"]["slope_clipping"] is False
    assert result["estimator_specification"]["psd_projection"] is False


def test_translation_invariance_and_tensor_rotation_covariance():
    positions = trajectory()
    rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    original = run_phase2(positions)
    transformed = run_phase2(positions @ rotation.T + [3., -4., 7.])
    assert transformed["draws"]["D:Li"] == pytest.approx(original["draws"]["D:Li"])
    for left, right in zip(original["tensor_draws"]["Li"], transformed["tensor_draws"]["Li"]):
        assert np.array(right) == pytest.approx(rotation @ np.array(left) @ rotation.T, abs=1e-22)


def test_integrated_diagnostic_never_populates_qualified_bounds_or_verdict(tmp_path):
    p2, p25 = bound_inputs(tmp_path)
    result = analyze_p3(p2, p25, protocol(), artifact_root=tmp_path, timestamp="fixed")
    uncertainty = result["p3_scientific_record"]["uncertainty"]
    diagnostic = result["quantitative_transport"]["self_diffusion"]["resampling_diagnostic"]
    assert diagnostic["intervals"]["D:Li"] is not None
    assert uncertainty["bounds"] is None and uncertainty["calibration_reference"] is None
    assert uncertainty["qualification"] == UNRESOLVED
    assert uncertainty["block_scheme"]["effective_independent_blocks"] is None
    assert result["p3_scientific_record"]["assessment"]["verdict"] == "UNKNOWN"
    assert result["p3_assessment"]["qualification"] == UNRESOLVED
