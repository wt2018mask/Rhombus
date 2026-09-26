import copy

import numpy as np
import pytest

from rudeus.science.contracts import digest
from rudeus.science.x_mattersim_protocol import MatterSimXProtocol
from rudeus.science.x_mattersim_scientific import MatterSimXExecutionSpec
from rudeus.science.x_mattersim_transport import (
    MatterSimXArtifactError,
    build_x_traj_payload,
    estimate_x_d_self,
    load_x_traj_artifact,
    write_x_traj_artifact,
    x_traj_sha256,
)


def admission():
    return MatterSimXExecutionSpec(
        candidate_id="candidate",
        batch_id="batch",
        target_species="Li",
        temperature_K=550.0,
        source_p2_hash=digest("p2"),
        source_p25_hash=digest("p25"),
        p3_protocol_hash=digest("p3"),
        trajectory_sha256=digest("primary-traj"),
        start_structure_sha256=digest("relaxed"),
    )


def protocol():
    return MatterSimXProtocol(
        target_species="Li",
        temperature_K=550.0,
        timestep_fs=1.0,
        equilibration_steps=10,
        production_steps=100,
        sample_interval_steps=10,
        thermostat="langevin",
        friction_fs_inv=0.02,
        fix_center_of_mass=True,
        ensemble="NVT",
        cell_mode="fixed",
        reference_frame="simulation_cell",
        lag_steps=(1, 2, 3, 4),
        fit_window_ps=(0.01, 0.04),
        estimator_id="free_intercept_OLS_MSD",
        seed=61001,
        source_p3_protocol_hash=digest("p3"),
    )


def execution():
    frames = []
    for i in range(1, 11):
        x = 0.05 * i
        frames.append({
            "phase": "production",
            "positions": np.array([[x, 0.0, 0.0], [0.0, x, 0.0]]),
            "md_step": 10 + i * 10,
        })
    return {
        "scientific_x_evidence": False,
        "start_structure_sha256": digest("relaxed"),
        "model_checkpoint_sha256": admission().checkpoint_sha256,
        "record": {
            "completed": True,
            "species": ["Li", "Li"],
            "cell": np.eye(3) * 10.0,
            "frames": frames,
        },
    }


def test_x_trajectory_roundtrip_and_hash(tmp_path):
    p = build_x_traj_payload(execution(), admission(), protocol())
    sha = x_traj_sha256(p)
    path = tmp_path / "x.npz"
    assert write_x_traj_artifact(path, p) == sha
    loaded = load_x_traj_artifact(path)
    assert x_traj_sha256(loaded) == sha


def test_x_trajectory_refuses_different_overwrite(tmp_path):
    p = build_x_traj_payload(execution(), admission(), protocol())
    path = tmp_path / "x.npz"
    write_x_traj_artifact(path, p)
    changed = copy.deepcopy(p)
    changed["positions"] = np.array(changed["positions"], copy=True)
    changed["positions"][0, 0, 0] += 0.1
    with pytest.raises(MatterSimXArtifactError, match="refusing to overwrite"):
        write_x_traj_artifact(path, changed)


def test_x_trajectory_requires_completed_execution():
    e = execution()
    e["record"]["completed"] = False
    with pytest.raises(MatterSimXArtifactError, match="incomplete"):
        build_x_traj_payload(e, admission(), protocol())


def test_x_d_self_is_derived_without_verdict_change():
    p = build_x_traj_payload(execution(), admission(), protocol())
    obs = estimate_x_d_self(p, protocol())
    assert obs["quantity"] == "D_self"
    assert obs["units"] == "m2/s"
    assert np.isfinite(obs["value"])
    assert obs["trajectory_sha256"] == x_traj_sha256(p)
    assert obs["scientific_verdict_changed"] is False


def test_x_d_self_rejects_protocol_rebinding():
    p = build_x_traj_payload(execution(), admission(), protocol())
    other = protocol()
    other = type(other)(**{**other.to_dict(), "seed": other.seed + 1})
    with pytest.raises(MatterSimXArtifactError, match="protocol mismatch"):
        estimate_x_d_self(p, other)
