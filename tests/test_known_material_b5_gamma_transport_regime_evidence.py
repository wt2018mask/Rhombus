import json
from pathlib import Path


def test_gamma_transport_regime_evidence_is_fail_closed_on_uncertainty():
    row = json.loads(Path(
        "data/benchmarks/known_material/b5_gamma_transport_regime_evidence_v1.json"
    ).read_text(encoding="utf-8"))

    assert row["capability"] == "classify_transport_regime"
    assert row["source"]["workflow_run_id"] == 37558945417
    assert row["source"]["artifact_id"] == 11456136679
    assert row["source"]["trajectory_sha256"] == (
        "b68c805b8f69bb2346ad3f5337cf5df64d9dd0c882af74bed397dcc00af34f02"
    )

    result = row["result"]
    assert result["operational_status"] == "SUCCEEDED"
    assert result["transport_state"] == "INDETERMINATE"
    assert result["point_transport_state"] == "NONDIFFUSIVE"
    assert result["n_origin_blocks"] == 2
    assert result["min_origin_blocks"] == 4
    assert result["uncertainty_status"] == "insufficient"
    assert result["uncertainty_reason"] == "fewer_blocks_than_minimum"

    interp = row["interpretation"]
    assert interp["authoritative_transport_regime_verdict"] is False
    assert interp["diffusion_claim_authorized"] is False
    assert interp["nondiffusion_claim_authorized"] is False
    assert interp["conductivity_claim_authorized"] is False
    assert interp["extension_or_more_evidence_required"] is True
