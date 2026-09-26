import copy

import pytest

from rudeus.mlip.sharding import structure_dict_sha256
from rudeus.science.contracts import digest
from rudeus.science.x_mattersim_protocol import MatterSimXProtocol
from rudeus.science.x_mattersim_runner import (
    MatterSimXExecutionError,
    execute_mattersim_x_md,
)
from rudeus.science.x_mattersim_scientific import MatterSimXExecutionSpec


def structure():
    return {
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "charge": 0,
        "lattice": {"matrix": [[4, 0, 0], [0, 4, 0], [0, 0, 4]], "pbc": [True, True, True]},
        "properties": {},
        "sites": [
            {
                "species": [{"element": "Li", "occu": 1}],
                "abc": [0.0, 0.0, 0.0],
                "properties": {},
                "label": "Li",
                "xyz": [0.0, 0.0, 0.0],
            }
        ],
    }


def admission(s):
    return MatterSimXExecutionSpec(
        candidate_id="candidate",
        batch_id="batch",
        target_species="Li",
        temperature_K=550.0,
        source_p2_hash=digest("p2"),
        source_p25_hash=digest("p25"),
        p3_protocol_hash=digest("p3"),
        trajectory_sha256=digest("traj"),
        start_structure_sha256=structure_dict_sha256(s),
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
        lag_steps=(1, 2, 5),
        fit_window_ps=(0.01, 0.05),
        estimator_id="free_intercept_OLS_MSD",
        seed=61001,
        source_p3_protocol_hash=digest("p3"),
    )


def p1_payload(s):
    sha = structure_dict_sha256(s)
    return {
        "batch_id": "batch",
        "result": {
            "p1_verdict": "KEEP_FOR_P2",
            "relaxed_structure_dict": s,
            "relaxed_structure_sha256": sha,
        },
    }


def test_runner_verifies_structure_before_calculator_and_executes_without_verdict():
    s = structure()
    seen = {}

    def calculator_factory():
        seen["calculator"] = True
        return object()

    def md_engine(structure_dict, calc, engine_protocol, seed, batch_id=None):
        seen["structure"] = structure_dict
        seen["protocol"] = engine_protocol
        seen["seed"] = seed
        seen["batch_id"] = batch_id
        return {
            "completed": True,
            "species": ["Li"],
            "cell": [[4, 0, 0], [0, 4, 0], [0, 0, 4]],
            "frames": [],
            "timestep_fs": 1.0,
            "sample_interval_steps": 10,
            "equil_steps": 10,
            "production_steps": 100,
            "seed": seed,
        }

    a = admission(s)
    p = protocol()
    out = execute_mattersim_x_md(
        p1_payload=p1_payload(s),
        admission=a,
        protocol=p,
        calculator_factory=calculator_factory,
        md_engine=md_engine,
    )

    assert out["status"] == "EXECUTED"
    assert out["scientific_x_evidence"] is False
    assert out["scientific_verdict_changed"] is False
    assert out["start_structure_sha256"] == a.start_structure_sha256
    assert seen["structure"] == s
    assert seen["protocol"]["friction_fs_inv_provisional"] == 0.02
    assert seen["protocol"]["fix_center_of_mass"] is True
    assert seen["seed"] == p.seed
    assert seen["batch_id"] == a.batch_id


def test_runner_rejects_tampered_structure_before_expensive_init():
    s = structure()
    payload = p1_payload(s)
    payload["result"]["relaxed_structure_dict"]["sites"][0]["abc"] = [0.1, 0.0, 0.0]
    called = {"calculator": False}

    def calculator_factory():
        called["calculator"] = True
        return object()

    with pytest.raises(MatterSimXExecutionError, match="bytes disagree"):
        execute_mattersim_x_md(
            p1_payload=payload,
            admission=admission(s),
            protocol=protocol(),
            calculator_factory=calculator_factory,
            md_engine=lambda *args, **kwargs: {},
        )

    assert called["calculator"] is False


def test_runner_rejects_recorded_structure_hash_rebinding():
    s = structure()
    payload = p1_payload(s)
    payload["result"]["relaxed_structure_sha256"] = digest("other")

    with pytest.raises(MatterSimXExecutionError, match="recorded relaxed-structure SHA"):
        execute_mattersim_x_md(
            p1_payload=payload,
            admission=admission(s),
            protocol=protocol(),
            calculator_factory=lambda: object(),
            md_engine=lambda *args, **kwargs: {},
        )


def test_runner_preserves_inputs():
    s = structure()
    payload = p1_payload(s)
    a = admission(s)
    p = protocol()
    before = copy.deepcopy(payload)

    execute_mattersim_x_md(
        p1_payload=payload,
        admission=a,
        protocol=p,
        calculator_factory=lambda: object(),
        md_engine=lambda *args, **kwargs: {"completed": False},
    )

    assert payload == before
