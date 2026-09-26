import copy

import pytest

from rudeus.science.contracts import digest
from rudeus.science.x_mattersim_observation import (
    comparison_ready,
    mattersim_observation,
)
from rudeus.science.x_mattersim_protocol import MatterSimXProtocol
from rudeus.science.x_mattersim_scientific import MatterSimXExecutionSpec
from rudeus.science.x_primary_observation import primary_p3_observation
from rudeus.science.xcheck import XModelIdentity


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


def primary_model():
    return XModelIdentity(
        model_name="MACE-primary",
        model_family="MACE",
        checkpoint_sha256=digest("mace-checkpoint"),
        code_revision=digest("primary-code"),
        implementation_id="rudeus.science.p3",
        training_data_id="mace-mp-training-v1",
    )


def p3_payload():
    a = admission()
    return {
        "p3_scientific_record": {
            "observation": {
                "quantity": "D_self",
                "units": "m2/s",
                "value": 2.0e-10,
                "conditions": {
                    "temperature_K": 550.0,
                    "candidate_id": "candidate",
                    "species": ["Li"],
                    "reference_frame": "simulation_cell",
                },
                "estimator": "free_intercept_OLS_MSD",
                "protocol_hash": a.p3_protocol_hash,
                "artifact_hashes": [a.trajectory_sha256],
            }
        },
        "p3_provenance": {
            "p3_config_hash": a.p3_protocol_hash,
            "trajectory_sha256": a.trajectory_sha256,
        },
    }


def x_protocol():
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


def cross_transport():
    return {
        "quantity": "D_self",
        "units": "m2/s",
        "value": 1.8e-10,
        "estimator_id": "free_intercept_OLS_MSD",
        "trajectory_sha256": digest("cross-traj"),
        "scientific_verdict_changed": False,
    }


def test_primary_and_mattersim_bind_to_same_scientific_scope():
    a = admission()
    primary_binding, primary_obs = primary_p3_observation(
        p3_payload=p3_payload(),
        admission=a,
        primary_model=primary_model(),
    )
    _, cross_binding, cross_obs = mattersim_observation(
        admission=a,
        protocol=x_protocol(),
        transport_result=cross_transport(),
        code_revision=digest("cross-code"),
    )

    assert primary_binding == cross_binding
    assert comparison_ready(
        primary_binding=primary_binding,
        cross_binding=cross_binding,
    )["status"] == "READY"
    assert primary_obs.input_binding_hash == cross_obs.input_binding_hash


@pytest.mark.parametrize(
    "damage,match",
    [
        ("candidate", "candidate mismatch"),
        ("temperature", "temperature mismatch"),
        ("species", "species mismatch"),
        ("protocol", "protocol binding mismatch"),
        ("trajectory", "trajectory evidence mismatch"),
    ],
)
def test_primary_adapter_rejects_rebinding(damage, match):
    payload = copy.deepcopy(p3_payload())
    a = admission()
    if damage == "candidate":
        payload["p3_scientific_record"]["observation"]["conditions"]["candidate_id"] = "other"
    elif damage == "temperature":
        payload["p3_scientific_record"]["observation"]["conditions"]["temperature_K"] = 600.0
    elif damage == "species":
        payload["p3_scientific_record"]["observation"]["conditions"]["species"] = ["Na"]
    elif damage == "protocol":
        payload["p3_scientific_record"]["observation"]["protocol_hash"] = digest("other")
    elif damage == "trajectory":
        payload["p3_scientific_record"]["observation"]["artifact_hashes"] = [digest("other")]

    with pytest.raises(ValueError, match=match):
        primary_p3_observation(
            p3_payload=payload,
            admission=a,
            primary_model=primary_model(),
        )
