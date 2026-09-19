import numpy as np

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
    )

    assert record == {
        "phase": "equil",
        "md_step": 1200,
        "step_jump_A": 3.25,
        "threshold_A": 3.0,
        "temperature_K": 812.5,
        "energy_eV": -123.4,
        "max_force_eV_A": 17.8,
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
