import json
from pathlib import Path


def test_hex_libh4_semantic_recheck_is_authoritative_stability_fail():
    row = json.loads(Path(
        "data/benchmarks/known_material/b5_p2_hex_libh4_semantic_recheck_v1.json"
    ).read_text(encoding="utf-8"))

    assert row["protocol_version"] == (
        "p2-adaptive-v3-ase-units-fixcom-provisional"
    )
    assert row["evaluation_policy_version"] == (
        "p2-stability-eval-v2-host-first-mobile-neutral"
    )
    assert row["workflow_run_id"] == 37553573930
    assert row["artifact_id"] == 11453788829
    assert row["trajectory_sha256"] == (
        "527f4845998babfb114147860de70fe21f8ad7b3d3ed3bf1f026f1f80a0b8c59"
    )

    result = row["result"]
    assert result["dynamic_state"] == "FAIL"
    assert result["p2_verdict"] == "FAIL"
    assert result["numerical_abort"] is None
    assert result["early_stop_reason"] == "clear_failure"
    assert result["production_steps_completed"] == 1000
    assert result["n_mobile"] == 2
    assert result["host_rmsd_final_A"] > 1.0
    assert result["lindemann_provisional"] > 0.2

    interpretation = row["interpretation"]
    assert interpretation["authoritative_stability_verdict"] is True
    assert interpretation["mobile_count_masking_resolved"] is True
    assert interpretation["transport_claim_authorized"] is False
    assert interpretation["diffusion_claim_authorized"] is False
