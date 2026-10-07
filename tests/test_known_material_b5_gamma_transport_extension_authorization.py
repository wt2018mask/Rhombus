import json
from pathlib import Path

from rhombus.transport import assess_transport_evidence_extension_admission
from rudeus.mlip.p25_extension import extension_protocol_hash


def test_gamma_extension_authorization_binds_exact_source_and_protocol():
    row = json.loads(Path(
        "data/benchmarks/known_material/"
        "b5_gamma_transport_extension_authorization_v1.json"
    ).read_text(encoding="utf-8"))

    assert row["capability"] == "extend_transport_evidence"
    assert row["authorization_version"] == (
        "transport-evidence-extension-authorization-v1"
    )
    assert row["one_shot"] is True

    candidate = row["candidate"]
    assert candidate["batch_id"] == "df4431260652d2ea"
    assert candidate["source_transport_state"] == "INDETERMINATE"
    assert candidate["source_uncertainty_status"] == "insufficient"
    assert candidate["source_uncertainty_reason"] == "fewer_blocks_than_minimum"
    assert candidate["source_origin_blocks"] == 2
    assert candidate["required_origin_blocks"] == 4
    assert candidate["source_p2_seed"] == 3745788748
    assert candidate["source_trajectory_sha256"] == (
        "b68c805b8f69bb2346ad3f5337cf5df64d9dd0c882af74bed397dcc00af34f02"
    )

    transition = row["transition"]
    assert transition["protocol_hash"] == extension_protocol_hash()
    assert transition["protocol_version"] == (
        "p2-p25-evidence-extension-v1-fixcom-constraint-provisional"
    )
    assert transition["production_steps"] == 8000
    assert transition["force_full_production_for_transport"] is True

    claims = row["claims"]
    assert claims["transport_claim_authorized"] is False
    assert claims["conductivity_claim_authorized"] is False

    execution = row["execution"]
    assert execution["preferred_backend"] == "kaggle"
    assert execution["github_cpu_primary"] is False


def test_gamma_source_is_eligible_under_generic_extension_predicate():
    evidence = json.loads(Path(
        "data/benchmarks/known_material/"
        "b5_gamma_transport_regime_evidence_v1.json"
    ).read_text(encoding="utf-8"))

    decision = assess_transport_evidence_extension_admission(evidence)
    assert decision["admission_status"] == "ELIGIBLE"
    assert decision["capability"] == "extend_transport_evidence"
    assert decision["one_shot"] is True
    assert decision["scientific_claim"] is None
    assert decision["transition_protocol_hash"] == extension_protocol_hash()


def test_extension_predicate_rejects_authoritative_or_wrong_insufficiency():
    evidence = json.loads(Path(
        "data/benchmarks/known_material/"
        "b5_gamma_transport_regime_evidence_v1.json"
    ).read_text(encoding="utf-8"))

    decisive = json.loads(json.dumps(evidence))
    decisive["result"]["transport_state"] = "NONDIFFUSIVE"
    assert assess_transport_evidence_extension_admission(
        decisive
    )["admission_status"] == "NOT_ELIGIBLE"

    wrong_reason = json.loads(json.dumps(evidence))
    wrong_reason["result"]["uncertainty_reason"] = "other_reason"
    assert assess_transport_evidence_extension_admission(
        wrong_reason
    )["admission_status"] == "NOT_ELIGIBLE"
