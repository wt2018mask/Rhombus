from dataclasses import replace
import copy
import numpy as np
import pytest

from rudeus.science.contracts import UNRESOLVED, digest
from rudeus.science.transport import analyze_trajectory, displacement_moments, fit_moments
from rudeus.science.statistics import ResamplingSpec, joint_origin_bootstrap, coverage_experiment
from rudeus.science.synthetic import brownian, caged, hopping, correlated_motion, wrap, temperature_series
from rudeus.science.temperature import TemperaturePoint, analyze_temperature
from rudeus.science.p3 import P3Protocol, analyze_p3
from rudeus.mlip.p2 import unwrap_trajectory
from rudeus.mlip.p25 import analyze_p25, P25_DEFAULTS
from rudeus.mlip.p2_traj import build_traj_payload, write_traj_artifact
from rudeus.execution.contracts import ExecutionError


def trajectory():
    return brownian(n_frames=80, n_ions=2, diffusion_tensor=np.eye(3)*0.01, dt_ps=0.1, seed=5)


def kwargs():
    return dict(selected_species=("Li",), fit_window_ps=(0.1, 0.8), volume_A3=1000,
                temperature_K=500, reference_frame="simulation_cell", charge_numbers={"Li": 1})


def test_physical_time_free_intercept_tensor_and_signed_slope():
    tensors = np.array([np.eye(3)*(2-0.2*t) for t in [1., 2., 3.]])
    moments = dict(time_ps=np.array([1., 2., 3.]), self_tensors_A2={"Li": tensors},
                   n_frames=10, counts={"Li": 2}, origin_policy="all_available_per_lag",
                   origin_counts=[9, 8, 7])
    result = fit_moments(moments, (1., 3.), volume_A3=10, temperature_K=500,
                         reference_frame="simulation_cell")
    sd = result["self_diffusion_by_species"]["Li"]
    assert sd["D_A2_per_ps"] == pytest.approx(-0.1)
    assert sd["intercept_A2"] == pytest.approx(6)
    assert np.trace(sd["D_tensor_m2_per_s"])/3 == pytest.approx(sd["D_m2_per_s"])
    assert not result["conductivity_estimate"]["available"]
    p = trajectory()
    a = displacement_moments(p, ["Li"]*2, np.arange(80)*10, 10, [1, 2], selected_species=("Li",))
    assert a["time_ps"].tolist() == pytest.approx([0.1, 0.2])
    with pytest.raises(ValueError, match="irregular"):
        displacement_moments(p, ["Li"]*2, [0, 11, *range(20, 800, 10)], 10, [1, 2], selected_species=("Li",))


def test_collective_cancellation_cross_species_and_no_center_of_mass_removal():
    single = trajectory()[:, :1]
    opposite = np.concatenate([single, -single], axis=1)
    result = analyze_trajectory(opposite, ["Li", "Na"], np.arange(80), 100, range(1, 9),
                                **{**kwargs(), "selected_species": ("Li", "Na"),
                                   "charge_numbers": {"Li": 1, "Na": 1}})
    assert result["conductivity_estimate"]["value_S_per_m"] > 0
    assert result["collective_transport"]["sigma_S_per_m"] == pytest.approx(0, abs=1e-15)
    assert result["collective_transport"]["correlation"]["factor"] == pytest.approx(0, abs=1e-15)
    same = np.concatenate([single, single], axis=1)
    co = analyze_trajectory(same, ["Li"]*2, np.arange(80), 100, range(1, 9), **kwargs())
    assert co["collective_transport"]["correlation"]["factor"] == pytest.approx(2)


def test_joint_bootstrap_bookkeeping_and_reproducibility():
    spec = ResamplingSpec(block_origins=9, min_blocks_provisional=2, n_resamples=12,
                          nominal_coverage_provisional=0.68, seed=41,
                          replica_scheme="single_trajectory_no_replica_resampling",
                          joint_quantities=("D:Li", "sigma_NE", "sigma_collective", "correlation"))
    args = (trajectory(), ["Li"]*2, np.arange(80), 100, range(1, 8))
    a = joint_origin_bootstrap(*args, spec=spec, **kwargs())
    b = joint_origin_bootstrap(*args, spec=spec, **kwargs())
    assert a == b
    assert a["used_origins"]+a["discarded_origins"] == 73
    assert a["discarded_origins"] == 1
    assert a["effective_independent_blocks"] is None
    assert a["scientific_qualification"] == UNRESOLVED
    tiny = joint_origin_bootstrap(*args, spec=replace(spec, min_blocks_provisional=99), **kwargs())
    assert tiny["status"] == "INSUFFICIENT"


def test_generators_and_coverage_abstention_are_not_qualification():
    cages = caged(n_frames=20, n_ions=2, retention=.5, stationary_std_A=.1, seed=3)
    hops = hopping(n_frames=20, n_ions=2, jump_length_A=1, rate_per_ps=2, dt_ps=.1, seed=3)
    corr = correlated_motion(n_frames=20, n_ions=2, spatial_covariance=np.eye(6)*.01,
                             retention=.7, dt_ps=.1, seed=3)
    assert cages.shape == hops.shape == corr.shape == (20, 2, 3)
    p = trajectory()
    assert np.allclose(unwrap_trajectory(wrap(p, np.eye(3)*10), np.eye(3)*10), p)
    report = coverage_experiment(lambda seed: seed, lambda value: {"estimate": 1,
                                 "interval": None if value == 1 else [0, 2]},
                                 seeds=[1, 2, 3], truth=1, nominal_coverage=.9,
                                 monte_carlo_confidence=.9, generating_protocol={"test": "known intervals"})
    assert report["coverage_unconditional"] == 2/3
    assert report["coverage_conditional"] == 1
    assert report["abstention_rate"] == 1/3
    assert report["scientific_qualification"] == UNRESOLVED


def points():
    temps = [500., 600., 700.]
    values = temperature_series(temperatures_K=temps, prefactor=1e-5,
                                activation_energy_eV=.2, log_noise_std=0, seed=1)
    return [TemperaturePoint(candidate_id="a", phase_id="phase", comparison_scope_hash=digest("scope"),
                             temperature_K=t, quantity="D_self", units="m2/s", value=float(v),
                             source_artifacts=(digest(t),), protocol_hash=digest(["protocol", t]),
                             replica_id="0") for t, v in zip(temps, values)]


def test_temperature_diagnostics_uncertainty_extrapolation_and_unresolved_points():
    ps = points()
    fit = analyze_temperature(ps, fit_quantity="D_self", target_temperature_K=300,
                              joint_draws=[[p.value*.9 for p in ps], [p.value*1.1 for p in ps]],
                              nominal_coverage=.68, resampling_provenance={"method": "test"})
    assert fit["fit"]["activation_energy_eV"] == pytest.approx(.2)
    assert fit["prediction"]["status"] == "EXTRAPOLATED"
    assert fit["prediction"]["inverse_temperature_distance_per_K"] == pytest.approx(1/300-1/500)
    assert fit["prediction"]["parameter_only_interval"] is not None
    assert fit["model_discrepancy_uncertainty"] is None
    assert fit["scientific_qualification"] == UNRESOLVED
    ps[1] = replace(ps[1], value=None, status="FAILED")
    bad = analyze_temperature(ps, fit_quantity="D_self")
    assert len(bad["points"]) == 3 and not bad["fit"]["available"]


def bound_inputs(tmp_path):
    p = trajectory()
    protocol = {"p2_protocol_version": "test-v1"}
    job = {"batch_id": "batch", "p2_config_hash": "legacy-config", "p2_protocol": protocol}
    record = {"species": ["Li"]*2, "cell": np.eye(3)*10, "timestep_fs": 10,
              "sample_interval_steps": 10, "equil_steps": 0, "production_steps": 800,
              "seed": 1, "frames": [{"phase": "production", "positions": frame,
                                      "md_step": (i+1)*10} for i, frame in enumerate(wrap(p, np.eye(3)*10))]}
    artifact = build_traj_payload(record, job)
    sha = write_traj_artifact(tmp_path/"trajectory.npz", artifact)
    p2 = {"batch_id": "batch", "result": {"candidate_material_id": "candidate", "parent_id": "parent",
          "p2_config_hash": "legacy-config", "p2_protocol_version": "test-v1", "seed": 1,
          "temperature_K": 500., "dynamic_state": "PASS", "p2_verdict": "PASS",
          "trajectory_artifact": {"path": str(tmp_path/"trajectory.npz"), "sha256": sha,
                                  "format_version": "p2-traj-v1"}, "provenance": {}}}
    p25 = {"result": analyze_p25(p2, dict(P25_DEFAULTS), p2_result_path="p2.json")}
    p2["result"]["trajectory_artifact"]["path"] = "trajectory.npz"
    return p2, p25


def test_p2_p25_p3_integration_preserves_history_and_never_reruns(tmp_path):
    p2, p25 = bound_inputs(tmp_path)
    before = copy.deepcopy(p25)
    proto = P3Protocol(target_species="Li", lag_steps=tuple(range(1, 9)),
                       fit_window_ps=(.1, .8), reference_frame="simulation_cell")
    out = analyze_p3(p2, p25, proto, artifact_root=tmp_path, timestamp="2026-09-20T00:00:00Z")
    assert p25 == before
    for key, value in p25["result"].items():
        assert out[key] == value
    assert set(out["quantitative_transport"]) == {"self_diffusion", "conductivity_estimate",
                                                 "collective_transport", "temperature_dependence", "extrapolation"}
    assert out["p3_assessment"]["verdict"] == "UNKNOWN"
    assert not out["quantitative_transport"]["collective_transport"]["available"]
    assert out == analyze_p3(p2, p25, proto, artifact_root=tmp_path, timestamp="2026-09-20T00:00:00Z")
    unresolved = analyze_p3(p2, p25, P3Protocol(target_species="Li"), artifact_root=tmp_path, timestamp="fixed")
    assert not unresolved["quantitative_transport"]["self_diffusion"]["available"]
    p25["result"]["provenance"]["p2_seed"] = 999
    with pytest.raises(ExecutionError) as exc:
        analyze_p3(p2, p25, proto, artifact_root=tmp_path, timestamp="fixed")
    assert exc.value.failure_class == "INTEGRITY"
