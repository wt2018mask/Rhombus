import math

import pytest

from rudeus.science.contracts import digest
from rudeus.science.x_mattersim_observation import (
    comparison_ready,
    mattersim_observation,
)
from rudeus.science.x_mattersim_protocol import MatterSimXProtocol
from rudeus.science.x_mattersim_scientific import MatterSimXExecutionSpec
from rudeus.science.xcheck import XInputBinding


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
        lag_steps=(1, 2, 3),
        fit_window_ps=(0.01, 0.03),
        estimator_id="free_intercept_OLS_MSD",
        seed=61001,
        source_p3_protocol_hash=digest("p3"),
    )


def transport():
    return {
        "quantity": "D_self",
        "units": "m2/s",
        "value": 1.5e-10,
        "estimator_id": "free_intercept_OLS_MSD",
        "trajectory_sha256": digest("x-traj"),
        "scientific_verdict_changed": False,
    }


def test_mattersim_transport_binds_to_generic_x_observation():
    model, binding, obs = mattersim_observation(
        admission=admission(),
        protocol=protocol(),
        transport_result=transport(),
        code_revision=digest("code"),
    )

    assert binding.candidate_id == "candidate"
    assert binding.structure_sha256 == digest("relaxed")
    assert binding.quantity == "D_self"
    assert binding.units == "m2/s"
    assert obs.model_hash == model.content_hash
    assert obs.input_binding_hash == binding.content_hash
    assert obs.evidence_hash == digest("x-traj")
    assert math.isclose(obs.value, 1.5e-10)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("quantity", "sigma_NE", "quantity mismatch"),
        ("units", "S/m", "units mismatch"),
        ("estimator_id", "other", "estimator mismatch"),
        ("scientific_verdict_changed", True, "must not change verdict"),
    ],
)
def test_mattersim_observation_rejects_rebinding(field, value, match):
    result = transport()
    result[field] = value
    with pytest.raises(ValueError, match=match):
        mattersim_observation(
            admission=admission(),
            protocol=protocol(),
            transport_result=result,
            code_revision=digest("code"),
        )


def test_comparison_ready_requires_identical_binding():
    _, binding, _ = mattersim_observation(
        admission=admission(),
        protocol=protocol(),
        transport_result=transport(),
        code_revision=digest("code"),
    )
    assert comparison_ready(primary_binding=binding, cross_binding=binding)["status"] == "READY"

    other = XInputBinding(
        candidate_id=binding.candidate_id,
        structure_sha256=binding.structure_sha256,
        protocol_hash=digest("other-protocol"),
        quantity=binding.quantity,
        units=binding.units,
        conditions=binding.conditions,
    )
    blocked = comparison_ready(primary_binding=binding, cross_binding=other)
    assert blocked["status"] == "BLOCKED_SCOPE_MISMATCH"
