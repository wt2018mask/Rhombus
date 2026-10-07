import json
from pathlib import Path


def test_remaining_libh4_p2_evidence_preserves_raw_verdicts_and_conflict():
    row = json.loads(Path(
        "data/benchmarks/known_material/b5_p2_remaining_libh4_evidence_v1.json"
    ).read_text(encoding="utf-8"))

    assert row["protocol_version"] == (
        "p2-adaptive-v3-ase-units-fixcom-provisional"
    )
    assert row["workflow_run_id"] == 37549230924
    assert row["p2_config_hash"] == "ccca8860d4814232"

    by_phase = {r["component_label"]: r for r in row["results"]}
    assert set(by_phase) == {"hexagonal", "orthorhombic"}

    hex_row = by_phase["hexagonal"]
    assert hex_row["raw_result"]["dynamic_state"] == "INDETERMINATE"
    assert hex_row["raw_result"]["n_mobile"] == 2
    assert hex_row["raw_result"]["host_rmsd_max_A"] > 2.0
    assert hex_row["raw_result"]["lindemann_provisional"] > 1.0
    assert hex_row["interpretation"]["classification"] == "SEMANTIC_GATE_CONFLICT"
    assert hex_row["interpretation"]["authoritative_stability_verdict"] is False
    assert hex_row["interpretation"]["rerun_or_reanalysis_required"] is True

    ortho = by_phase["orthorhombic"]
    assert ortho["raw_result"]["dynamic_state"] == "FAIL"
    assert ortho["raw_result"]["numerical_abort"] is None
    assert ortho["interpretation"]["classification"] == (
        "FINITE_TEMPERATURE_STABILITY_FAIL"
    )
    assert ortho["interpretation"]["transport_claim_authorized"] is False
