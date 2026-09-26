from dataclasses import replace

import pytest

from rudeus.science.contracts import digest
from rudeus.science.x_mattersim_protocol import MatterSimXProtocol, bind_protocol
from rudeus.science.x_mattersim_scientific import MatterSimXExecutionSpec


def admission():
    return MatterSimXExecutionSpec(
        candidate_id="candidate",
        batch_id="batch",
        target_species="Li",
        temperature_K=550.0,
        source_p2_hash=digest("p2"),
        source_p25_hash=digest("p25"),
        p3_protocol_hash=digest("p3"),
        trajectory_sha256=digest("traj"),
        start_structure_sha256=digest("relaxed-structure"),
    )


def protocol():
    return MatterSimXProtocol(
        target_species="Li",
        temperature_K=550.0,
        timestep_fs=1.0,
        equilibration_steps=1000,
        production_steps=10000,
        sample_interval_steps=10,
        thermostat="langevin",
        friction_fs_inv=0.02,
        fix_center_of_mass=True,
        ensemble="NVT",
        cell_mode="fixed",
        reference_frame="simulation_cell",
        lag_steps=(1, 2, 5, 10, 20, 50, 100),
        fit_window_ps=(1.0, 10.0),
        estimator_id="free_intercept_OLS_MSD",
        seed=61001,
        source_p3_protocol_hash=digest("p3"),
    )


def test_mattersim_x_protocol_binds_exact_admission_scope():
    a = admission()
    p = protocol()
    bound = bind_protocol(a, p)

    assert bound["stage"] == "X"
    assert bound["purpose"] == "independent_transport_crosscheck"
    assert bound["admission_hash"] == a.content_hash
    assert bound["protocol_hash"] == p.content_hash
    assert bound["candidate_id"] == "candidate"
    assert bound["start_structure_sha256"] == digest("relaxed-structure")
    assert bound["scientific_verdict_changed"] is False
    assert MatterSimXProtocol.from_dict(p.to_dict()) == p


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("target_species", "Na", "target species mismatch"),
        ("temperature_K", 600.0, "temperature mismatch"),
        ("source_p3_protocol_hash", digest("other"), "source P3 hash mismatch"),
    ],
)
def test_mattersim_x_protocol_rejects_scope_drift(field, value, match):
    a = admission()
    p = replace(protocol(), **{field: value})
    with pytest.raises(ValueError, match=match):
        bind_protocol(a, p)


@pytest.mark.parametrize(
    "field,value",
    [
        ("timestep_fs", 0.0),
        ("production_steps", 0),
        ("sample_interval_steps", 0),
        ("thermostat", "nose-hoover"),
        ("friction_fs_inv", 0.0),
        ("fix_center_of_mass", "yes"),
        ("ensemble", "NPT"),
        ("cell_mode", "variable"),
        ("reference_frame", "center_of_mass"),
        ("lag_steps", (2, 1)),
        ("fit_window_ps", (10.0, 1.0)),
    ],
)
def test_mattersim_x_protocol_rejects_unsupported_or_invalid_parameters(field, value):
    with pytest.raises(ValueError):
        replace(protocol(), **{field: value})


def test_mattersim_x_protocol_rejects_lag_beyond_available_frames():
    with pytest.raises(ValueError, match="lag exceeds"):
        replace(
            protocol(),
            production_steps=100,
            sample_interval_steps=10,
            lag_steps=(1, 10),
        )


def test_mattersim_x_protocol_hash_changes_with_scientific_parameter():
    p = protocol()
    assert replace(p, seed=p.seed + 1).content_hash != p.content_hash
    assert replace(p, timestep_fs=2.0).content_hash != p.content_hash
    assert replace(p, production_steps=20000).content_hash != p.content_hash
