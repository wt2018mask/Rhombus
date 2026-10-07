import json
from pathlib import Path


def test_phase0_closure_is_conservative_and_complete():
    root = Path(__file__).resolve().parents[1]
    closure = json.loads(
        (root / "data/development/phase0_closure_v1.json").read_text()
    )
    gamma = json.loads(
        (
            root
            / "data/benchmarks/known_material/"
            "b5_gamma_transport_extension_evidence_v1.json"
        ).read_text()
    )

    assert closure["status"] == "CLOSED"
    assert closure["next_phase"] == "R2_PHASE1_ARCHITECTURE_FREEZE"
    assert closure["cohort"]["gamma_lialo2"]["transport_regime"] == "NONDIFFUSIVE"
    assert closure["cohort"]["hex_libh4"]["p2_stability"] == "FAIL"
    assert closure["cohort"]["ortho_libh4"]["p2_stability"] == "FAIL"
    assert closure["cohort"]["cubic_al_llzo"]["p0"] == "INDETERMINATE"

    assert gamma["operational_status"] == "SUCCEEDED"
    assert gamma["stability_verdict"] == "PASS"
    assert gamma["transport_state"] == "NONDIFFUSIVE"
    assert gamma["production_steps_completed"] == 8000
    assert gamma["sufficiency"]["n_origin_blocks"] >= gamma["sufficiency"]["min_blocks"]
    assert gamma["claims"]["nondiffusive_regime_claim_authorized"] is True
    assert gamma["claims"]["conductivity_claim_authorized"] is False
    assert gamma["claims"]["self_diffusion_claim_authorized"] is False
    assert gamma["claims"]["tracer_diffusion_claim_authorized"] is False
    assert gamma["claims"]["qualification_claim_authorized"] is False
