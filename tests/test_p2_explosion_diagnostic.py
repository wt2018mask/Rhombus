import numpy as np

from rudeus.mlip.cuda_force_diagnostic import diagnostic_termination
from rudeus.mlip.p2 import explosion_diagnostic


def test_explosion_diagnostic_records_existing_guard_state():
    positions = np.array(
        [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
        dtype=float,
    )
    cell = np.eye(3) * 10.0

    record = explosion_diagnostic(
        phase="equil",
        md_step=1200,
        step_jump_A=3.25,
        threshold_A=3.0,
        temperature_K=812.5,
        energy_eV=-123.4,
        max_force_eV_A=17.8,
        positions=positions,
        cell=cell,
        finite=True,
        previous_positions=np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=float
        ),
        species=["Li", "O"],
        forces=np.array([[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]], dtype=float),
    )

    assert record["local_environment"]["atom_index"] == 1
    assert record["local_environment"]["atom_species"] == "O"
    assert record["local_environment"]["initial_force_eV_A"] == 1.0
    assert record["local_environment"]["explosion_force_eV_A"] == 2.0
    assert record["local_environment"]["initial_nearest_neighbor_A"] == 1.0
    assert record["local_environment"]["explosion_nearest_neighbor_A"] == 1.0
    assert record == {
        "phase": "equil",
        "md_step": 1200,
        "step_jump_A": 3.25,
        "threshold_A": 3.0,
        "temperature_K": 812.5,
        "energy_eV": -123.4,
        "max_force_eV_A": 17.8,
        "max_atom_displacement_A": 1.0,
        "max_atom_index": 1,
        "max_atom_species": "O",
        "max_atom_force_eV_A": 2.0,
        "local_environment": {
            "atom_index": 1,
            "atom_species": "O",
            "initial_position_A": [2.0, 0.0, 0.0],
            "explosion_position_A": [2.0, 0.0, 0.0],
            "initial_force_eV_A": 2.0,
            "explosion_force_eV_A": 2.0,
            "force_change_eV_A": 0.0,
            "initial_neighbors": [
                {"index": 0, "species": "Li", "distance_A": 1.0},
            ],
            "explosion_neighbors": [
                {"index": 0, "species": "Li", "distance_A": 1.0},
            ],
            "initial_nearest_neighbor_A": 1.0,
            "explosion_nearest_neighbor_A": 1.0,
        },
        "min_distance_A": 2.0,
        "finite": True,
    }


def test_explosion_diagnostic_preserves_nonfinite_abort_without_fake_distance():
    record = explosion_diagnostic(
        phase="production",
        md_step=7,
        step_jump_A=0.0,
        threshold_A=3.0,
        temperature_K=float("nan"),
        energy_eV=None,
        max_force_eV_A=None,
        positions=None,
        cell=None,
        finite=False,
    )

    assert record["phase"] == "production"
    assert record["md_step"] == 7
    assert record["step_jump_A"] == 0.0
    assert record["threshold_A"] == 3.0
    assert np.isnan(record["temperature_K"])
    assert record["energy_eV"] is None
    assert record["max_force_eV_A"] is None
    assert record["min_distance_A"] is None
    assert record["finite"] is False


def test_state_diagnostic_preserves_termination_diagnostic():
    record = {
        "termination_diagnostic": {
            "phase": "equil",
            "md_step": 1200,
            "step_jump_A": 3.41,
            "threshold_A": 3.0,
            "temperature_K": 823.0,
            "energy_eV": -10.5,
            "max_force_eV_A": 21.0,
            "min_distance_A": 0.72,
            "finite": True,
        }
    }

    assert diagnostic_termination(record) == record["termination_diagnostic"]
    assert diagnostic_termination({"termination_diagnostic": None}) is None
