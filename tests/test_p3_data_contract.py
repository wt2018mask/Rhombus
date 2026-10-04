"""Estimator/data correctness only; no scientific qualification or cutoffs."""
from dataclasses import replace
import copy

import numpy as np
import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.mlip.p2_traj import verify_traj_artifact, write_traj_artifact
from rudeus.science.contracts import UNRESOLVED, canonical_bytes
from rudeus.science.p3 import P3Protocol, analyze_p3
from rudeus.science.statistics import (joint_origin_bootstrap, COMMON_ORIGIN_BLOCKS_V1)
from rudeus.science.trajectory import recorded_times, reconstruct_fixed_cell, validate_schedule
from rudeus.science.transport import displacement_moments, analyze_trajectory
from tests.test_p3_scientific_slice import protocol
from tests.test_scientific_transport import bound_inputs, trajectory, kwargs


DECLARATION = {"coordinate_convention": "wrapped_cartesian_primary_cell",
               "periodic_directions": [True, True, True], "cell_origin_A": [0, 0, 0]}


def artifact():
    return {"positions": np.array([[[9., 1., 2.]], [[1., 1., 2.]], [[3., 1., 2.]]]),
            "cell": np.eye(3)*10, "cell_mode": "fixed", "species": ["Li"],
            "n_production_frames": 3, "frame_steps": np.array([7, 17, 27]),
            "timestep_fs": 2., "sample_interval_steps": 10,
            "equil_steps": 3, "production_steps_completed": 30}


def test_actual_time_and_integration_saved_spacing_distinction():
    a = artifact()
    sampling = validate_schedule(a, {})
    assert sampling["integration_timestep_fs"] == 2
    assert sampling["saved_frame_spacing_ps"] == .02
    assert sampling["saved_span_ps"] == .04
    moments = displacement_moments(a["positions"], a["species"], a["frame_steps"], 2, [1, 2],
                                   selected_species=("Li",))
    assert moments["time_ps"].tolist() == [.02, .04]
    shifted = displacement_moments(a["positions"], a["species"], a["frame_steps"]+1000, 2, [1, 2],
                                   selected_species=("Li",))
    assert np.array_equal(shifted["time_ps"], moments["time_ps"])


@pytest.mark.parametrize("steps", [[1, 1, 3], [3, 2, 1], [1, 2, 4], [1., 2., 3.],
                                   [1, 2.5, 3], [True, False, True], [True, 2, 3], [-1, 0, 1]])
def test_invalid_time_axis_rejected(steps):
    with pytest.raises(ValueError):
        recorded_times(steps, 1, n_frames=3)


@pytest.mark.parametrize("dt", [0, -1, float("nan"), float("inf"), True, "2"])
def test_invalid_timestep_rejected(dt):
    with pytest.raises(ValueError):
        recorded_times([1, 2, 3], dt, n_frames=3)


@pytest.mark.parametrize("steps", [[7, 27], [17, 27], [7, 17], [8, 18, 28]])
def test_schedule_rejects_missing_and_shifted_frames_even_when_regular(steps):
    a = artifact()
    a.update(frame_steps=np.array(steps), n_production_frames=len(steps))
    with pytest.raises(ValueError, match="schedule"):
        validate_schedule(a, {})


def test_inconsistent_declared_schedule():
    with pytest.raises(ValueError, match="disagree"):
        validate_schedule(artifact(), {"timestep_fs": 1})
    a = artifact()
    a["sample_interval_steps"] = 0
    with pytest.raises(ValueError):
        validate_schedule(a, {})


def test_reconstruction_retains_algorithm_and_exposes_unresolved_images():
    a = artifact()
    before = a["positions"].copy()
    reconstructed, info = reconstruct_fixed_cell(a, DECLARATION)
    assert reconstructed[:, 0, 0].tolist() == pytest.approx([9, 11, 13])
    assert np.array_equal(a["positions"], before)
    assert info["sampling_aliasing"] == "UNKNOWN"
    assert info["applicability"] == UNRESOLVED
    assert not info["drift_subtraction"] and not info["recentering"] and not info["time_dependent_rotation"]


@pytest.mark.parametrize("damage", ["singular", "skew", "nonfinite", "variable", "cell_series",
                                    "convention", "outside", "periodic", "missing", "half_cell"])
def test_unsupported_reconstruction_fails_explicitly(damage):
    a, declaration = artifact(), copy.deepcopy(DECLARATION)
    if damage == "singular":
        a["cell"][2] = 0
    elif damage == "skew":
        a["cell"][0, 1] = 2
    elif damage == "nonfinite":
        a["cell"][0, 0] = float("nan")
    elif damage == "variable":
        a["cell_mode"] = "variable"
    elif damage == "cell_series":
        a["cell"] = np.tile(a["cell"], (3, 1, 1))
    elif damage == "convention":
        declaration["coordinate_convention"] = "continuous_unwrapped_cartesian"
    elif damage == "outside":
        a["positions"][1, 0, 0] = 11
    elif damage == "periodic":
        declaration["periodic_directions"] = [True, True, False]
    elif damage == "missing":
        declaration = None
    else:
        a["positions"][1, 0, 0] = 4
    with pytest.raises(ValueError):
        reconstruct_fixed_cell(a, declaration)


def test_sparse_aliasing_cannot_be_certified_from_wrapped_samples():
    a = artifact()
    a["positions"][:, 0, 0] = [0, 2.5, 5]
    slow = a["positions"].copy()
    fast = slow.copy()
    fast[:, 0, 0] += [0, 10, 20]
    assert np.array_equal(np.mod(fast, 10), np.mod(slow, 10))
    reconstructed, info = reconstruct_fixed_cell(a, DECLARATION)
    assert not np.allclose(reconstructed, fast)
    assert info["sampling_aliasing"] == "UNKNOWN"
    assert "unobserved_whole_cell_crossings_not_excluded" in info["unresolved_requirements"]


def test_reconstruction_translation_and_rotation():
    a = artifact()
    expected, _ = reconstruct_fixed_cell(a, DECLARATION)
    angle = .37
    rotation = np.array([[np.cos(angle), -np.sin(angle), 0],
                         [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
    shift = np.array([12., -3., 7.])
    a["positions"] = a["positions"] @ rotation.T + shift
    a["cell"] = a["cell"] @ rotation.T
    actual, _ = reconstruct_fixed_cell(a, {**DECLARATION, "cell_origin_A": shift.tolist()})
    assert np.allclose(actual, expected @ rotation.T + shift)


def test_species_order_and_full_population_with_framework_diagnostics():
    pos = np.zeros((5, 3, 3))
    pos[:, 0, 0] = np.arange(5)
    pos[:, 1, 1] = 2*np.arange(5)
    labels = ["Li", "O", "Li"]  # stationary Li must not be filtered out
    before = pos.copy()
    moments = displacement_moments(pos, labels, np.arange(5)*10, 2, [1, 2], selected_species=("Li",))
    assert moments["counts"] == {"Li": 2}
    assert moments["origin_population"]["species_indices"] == {"Li": [0, 2]}
    assert moments["origin_indices"] == [[0, 1, 2, 3], [0, 1, 2]]
    assert moments["mean_displacement_A"]["Li"] == [[.5, 0, 0], [1., 0, 0]]
    assert moments["unselected_atom_indices"] == [1]
    assert moments["unselected_atoms_mean_displacement_A"] == [[0, 2., 0], [0, 4., 0]]
    assert np.array_equal(pos, before) and labels == ["Li", "O", "Li"]
    perm = [1, 2, 0]
    other = displacement_moments(pos[:, perm], [labels[i] for i in perm], np.arange(5)*10, 2,
                                  [1, 2], selected_species=("Li",))
    assert np.array_equal(other["self_tensors_A2"]["Li"], moments["self_tensors_A2"]["Li"])
    assert other["origin_population"]["species_indices"] == {"Li": [1, 2]}
    with pytest.raises(ValueError, match="ordered vector"):
        displacement_moments(pos, [labels]*5, np.arange(5)*10, 2, [1, 2], selected_species=("Li",))


def test_tensor_covariance_trace_and_translation():
    pos = trajectory()
    rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    def estimate(p):
        return analyze_trajectory(p, ["Li"]*2, np.arange(80)*10, 10, range(1, 9),
                                  **kwargs())["self_diffusion_by_species"]["Li"]
    original, transformed = estimate(pos), estimate(pos @ rotation.T + [3, -5, 2])
    assert np.allclose(transformed["D_tensor_m2_per_s"],
                       rotation @ np.array(original["D_tensor_m2_per_s"]) @ rotation.T,
                       rtol=1e-12, atol=1e-24)  # arithmetic comparison only, not scientific tolerance
    assert transformed["D_m2_per_s"] == pytest.approx(original["D_m2_per_s"], rel=1e-12)


def test_common_pool_cannot_be_attached_to_primary_population():
    pos = trajectory()
    moments = displacement_moments(pos, ["Li"]*2, np.arange(80), 100, range(1, 9),
                                   selected_species=("Li",))
    assert moments["origin_indices"] == [list(range(80-k)) for k in range(1, 9)]
    with pytest.raises(ValueError, match="population differs"):
        joint_origin_bootstrap(pos, ["Li"]*2, np.arange(80), 100, range(1, 9),
            spec=replace(protocol().resampling, method=COMMON_ORIGIN_BLOCKS_V1),
            expected_population_hash=moments["origin_population_hash"], **kwargs())


def test_integrated_declarations_and_uncertainty_remain_unqualified(tmp_path):
    p2, p25 = bound_inputs(tmp_path)
    before = canonical_bytes([p2, p25])
    result = analyze_p3(p2, p25, protocol(), artifact_root=tmp_path, timestamp="fixed")
    record = result["p3_scientific_record"]
    assert record["uncertainty"]["bounds"] is None
    assert record["uncertainty"]["block_scheme"]["population_match"] is True
    assert record["observation"]["data_support"]["origin_ranges"] == [[0, 80-k, 1] for k in range(1, 9)]
    assert record["observation"]["data_support"]["sampling"]["saved_frame_spacing_ps"] == .1
    assert record["assessment"]["verdict"] == "UNKNOWN"
    assert canonical_bytes([p2, p25]) == before
    legacy = replace(protocol(), reconstruction=None)
    assert "reconstruction" not in legacy.to_dict()
    assert P3Protocol.from_dict(legacy.to_dict()) == legacy
    unavailable = analyze_p3(p2, p25, legacy, artifact_root=tmp_path, timestamp="fixed")
    assert unavailable["p3_scientific_record"]["observation"] is None
    assert "reconstruction_declaration_unresolved" in unavailable["p3_assessment"]["reason_codes"]


def test_integrated_missing_frame_is_rejected_despite_rehashed_artifact(tmp_path):
    p2, p25 = bound_inputs(tmp_path)
    path = tmp_path/"trajectory.npz"
    a = verify_traj_artifact(path, p2["result"]["trajectory_artifact"]["sha256"])
    a["positions"], a["frame_steps"] = a["positions"][::2], a["frame_steps"][::2]
    a["n_production_frames"] = len(a["frame_steps"])
    identity = write_traj_artifact(path, a)
    p2["result"]["trajectory_artifact"]["sha256"] = identity
    p25["result"]["provenance"]["trajectory_artifact_sha256"] = identity
    with pytest.raises(ExecutionError, match="schedule") as exc:
        analyze_p3(p2, p25, protocol(), artifact_root=tmp_path, timestamp="fixed")
    assert exc.value.failure_class.value == "UNSUPPORTED_INPUT"


def test_stored_float_steps_cannot_hide_behind_legacy_integer_coercion(tmp_path):
    p2, p25 = bound_inputs(tmp_path)
    path = tmp_path/"trajectory.npz"
    with np.load(path, allow_pickle=False) as data:
        arrays = {key: data[key] for key in data.files}
    arrays["frame_steps"] = arrays["frame_steps"].astype(float)
    np.savez_compressed(path, **arrays)
    with pytest.raises(ExecutionError, match="stored frame steps") as exc:
        analyze_p3(p2, p25, protocol(), artifact_root=tmp_path, timestamp="fixed")
    assert exc.value.failure_class.value == "INTEGRITY"


def test_integrated_skew_cell_reports_unsupported_not_material_failure(tmp_path):
    p2, p25 = bound_inputs(tmp_path)
    path = tmp_path/"trajectory.npz"
    a = verify_traj_artifact(path, p2["result"]["trajectory_artifact"]["sha256"])
    a["cell"][0, 1] = 2
    identity = write_traj_artifact(path, a)
    p2["result"]["trajectory_artifact"]["sha256"] = identity
    p25["result"]["provenance"]["trajectory_artifact_sha256"] = identity
    before = canonical_bytes([p2, p25])
    with pytest.raises(ExecutionError, match="skew cell") as exc:
        analyze_p3(p2, p25, protocol(), artifact_root=tmp_path, timestamp="fixed")
    assert exc.value.failure_class.value == "UNSUPPORTED_INPUT"
    assert canonical_bytes([p2, p25]) == before
