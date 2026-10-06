import json
from pathlib import Path


def test_b5_p2_ase_units_diagnostic_invalidates_old_material_fail():
    path = Path(
        "data/benchmarks/known_material/b5_p2_ase_units_diagnostic_v1.json"
    )
    row = json.loads(path.read_text(encoding="utf-8"))

    assert row["schema_version"] == "known-material-b5-p2-ase-units-diagnostic-v1"
    assert row["source_execution"]["workflow_run_id"] == 37536303651
    assert row["source_execution"]["old_p2_config_hash"] == "37f72f8f79f25740"
    assert row["interpretation"]["classification"] == "INVALID_PROTOCOL_EXECUTION"
    assert row["interpretation"]["material_fail_authorized"] is False
    assert row["interpretation"]["threshold_recalibration_authorized"] is False
    assert row["interpretation"]["rerun_required"] is True
    assert row["interpretation"]["corrected_protocol_version"] == (
        "p2-adaptive-v3-ase-units-fixcom-provisional"
    )

    units = row["unit_contract"]
    assert units["configured_timestep_fs"] == 1.0
    assert units["previous_effective_timestep_fs_approx"] > 10.0
    assert units["corrected_mapping"]["timestep"] == (
        "timestep_fs * ase.units.fs"
    )
    assert units["corrected_mapping"]["friction"] == (
        "friction_fs_inv / ase.units.fs"
    )


def test_corrected_gamma_p2_pilot_is_bound_as_stability_only():
    path = Path(
        "data/benchmarks/known_material/b5_p2_corrected_pilot_evidence_v1.json"
    )
    row = json.loads(path.read_text(encoding="utf-8"))

    assert row["protocol_version"] == (
        "p2-adaptive-v3-ase-units-fixcom-provisional"
    )
    assert row["workflow_run_id"] == 37545842461
    assert row["artifact_id"] == 11451027898
    assert row["result"]["dynamic_state"] == "PASS"
    assert row["result"]["numerical_abort"] is None
    assert row["result"]["early_stop_reason"] == "clear_pass"
    assert row["result"]["production_steps_completed"] == 1000
    assert row["interpretation"]["finite_temperature_stability"] == "PASS"
    assert row["interpretation"]["transport_claim_authorized"] is False
    assert row["interpretation"]["diffusion_claim_authorized"] is False
    assert row["interpretation"]["qualification_claim_authorized"] is False
