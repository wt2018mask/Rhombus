"""Tests for fail-closed real-MD S3 calibration admission."""

import json
from pathlib import Path

from rudeus.science.real_md_s3_admission import (
    ADMISSION_BLOCKED,
    ADMISSION_ELIGIBLE,
    ADMISSION_INELIGIBLE,
    BROWNIAN_SYNTHETIC_DOMAIN,
    POPULATION_BLOCKED,
    POPULATION_READY,
    REAL_MD_DOMAIN,
    assess_real_md_s3_admission,
    interim_artifact_allows_final_s3,
    qualification_domain_compatible,
    summarize_real_md_s3_population,
)


def _p2(verdict="PASS", candidate="cand-1", batch="batch-1"):
    return {
        "batch_id": batch,
        "result": {
            "candidate_material_id": candidate,
            "batch_id": batch,
            "p2_verdict": verdict,
        },
    }


def _p25(state="DIFFUSIVE", candidate="cand-1", batch="batch-1"):
    return {
        "batch_id": batch,
        "result": {
            "candidate_material_id": candidate,
            "batch_id": batch,
            "p2_verdict": "PASS",
            "p25_verdict": state,
            "transport_state": state,
        },
    }


def test_diffusive_candidate_is_real_md_s3_eligible():
    decision = assess_real_md_s3_admission(_p2(), _p25())
    assert decision.eligible is True
    assert decision.status == ADMISSION_ELIGIBLE
    assert decision.evidence_role == "calibration_candidate"
    assert decision.reasons == ()


def test_nondiffusive_candidate_is_negative_control_not_calibration_member():
    decision = assess_real_md_s3_admission(_p2(), _p25("NONDIFFUSIVE"))
    assert decision.eligible is False
    assert decision.status == ADMISSION_INELIGIBLE
    assert decision.evidence_role == "negative_control"
    assert "p25_not_diffusive" in decision.reasons


def test_indeterminate_candidate_is_ineligible_not_negative_control():
    decision = assess_real_md_s3_admission(_p2(), _p25("INDETERMINATE"))
    assert decision.eligible is False
    assert decision.status == ADMISSION_INELIGIBLE
    assert decision.evidence_role == "excluded"
    assert "p25_not_diffusive" in decision.reasons


def test_p2_nonpass_never_enters_calibration_population():
    decision = assess_real_md_s3_admission(_p2("FAIL"), _p25("DIFFUSIVE"))
    assert decision.eligible is False
    assert decision.status == ADMISSION_INELIGIBLE
    assert "p2_not_pass" in decision.reasons


def test_integrity_and_execution_failures_are_blocked_not_material_verdicts():
    integrity = assess_real_md_s3_admission(
        _p2(), _p25(), integrity_ok=False
    )
    execution = assess_real_md_s3_admission(
        _p2(), _p25(), execution_ok=False
    )
    assert integrity.status == ADMISSION_BLOCKED
    assert integrity.evidence_role == "excluded"
    assert integrity.reasons == ("integrity_failure",)
    assert execution.status == ADMISSION_BLOCKED
    assert execution.reasons == ("execution_failure",)


def test_cross_document_identity_and_transport_mismatches_fail_closed():
    candidate_mismatch = assess_real_md_s3_admission(
        _p2(candidate="a"), _p25(candidate="b")
    )
    assert candidate_mismatch.status == ADMISSION_BLOCKED
    assert "candidate_identity_mismatch" in candidate_mismatch.reasons

    p25 = _p25("DIFFUSIVE")
    p25["result"]["transport_state"] = "NONDIFFUSIVE"
    state_mismatch = assess_real_md_s3_admission(_p2(), p25)
    assert state_mismatch.status == ADMISSION_BLOCKED
    assert "p25_transport_state_mismatch" in state_mismatch.reasons


def test_brownian_qualification_cannot_authorize_real_md_bounds():
    assert qualification_domain_compatible(REAL_MD_DOMAIN, REAL_MD_DOMAIN)
    assert qualification_domain_compatible(
        BROWNIAN_SYNTHETIC_DOMAIN, REAL_MD_DOMAIN
    ) is False
    assert qualification_domain_compatible(
        REAL_MD_DOMAIN, BROWNIAN_SYNTHETIC_DOMAIN
    ) is False


def test_interim_feasibility_artifact_cannot_become_final_s3():
    interim = {
        "claim_scope": {
            "stage1_final_qualification": False,
            "diffusion_coefficient_qualified": False,
            "uncertainty_transfer_qualified": False,
        }
    }
    assert interim_artifact_allows_final_s3(interim) is False

    missing_scope = {"D_provisional_m2_s": 1.9e-10}
    assert interim_artifact_allows_final_s3(missing_scope) is False

    final = {
        "claim_scope": {
            "stage1_final_qualification": True,
            "diffusion_coefficient_qualified": True,
            "uncertainty_transfer_qualified": True,
        }
    }
    assert interim_artifact_allows_final_s3(final) is True


def test_population_is_blocked_until_at_least_one_diffusive_candidate_exists():
    blocked = summarize_real_md_s3_population([
        (_p2(candidate="n1"), _p25("NONDIFFUSIVE", candidate="n1")),
        (_p2(candidate="n2"), _p25("INDETERMINATE", candidate="n2")),
    ])
    assert blocked["status"] == POPULATION_BLOCKED
    assert blocked["n_eligible"] == 0
    assert blocked["n_negative_controls"] == 1

    ready = summarize_real_md_s3_population([
        (_p2(candidate="n1"), _p25("NONDIFFUSIVE", candidate="n1")),
        (_p2(candidate="d1"), _p25("DIFFUSIVE", candidate="d1")),
    ])
    assert ready["status"] == POPULATION_READY
    assert ready["n_eligible"] == 1
    assert ready["eligible_candidate_material_ids"] == ["d1"]


def test_persisted_100ps_pilot_is_interim_negative_evidence_only():
    artifact_dir = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "batches"
        / "audit"
        / "p3_real_md_reference_pilot"
    )
    matches = sorted(artifact_dir.glob(
        "0d4de6bc17174a64_replica61001_100ps_*.json"
    ))
    assert len(matches) == 1
    artifact = json.loads(matches[0].read_text(encoding="utf-8"))
    assert artifact["artifact_format"] == (
        "p3-real-md-reference-feasibility-interim-v1"
    )
    assert artifact["interim_status"] == "NON_QUALIFIED_INTERIM"
    assert artifact["interim_gates"]["log_slope_0p75_to_1p30"] is False
    assert artifact["claim_scope"]["p3_candidate_qualification"] is False
    assert interim_artifact_allows_final_s3(artifact) is False
