"""0143 red-team cryptographic only — no real material identities or signing keys."""
import copy
import hashlib

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rhombus.evidence.receipts import (
    TrustedIssuer, canonical_bytes, evidence_sha256, ZERO_SHA256,
)
from rhombus.qualification.steward_envelope import (
    SCHEMA, MODEL_SHA256, IDENTITY_SCHEME, PRIVACY,
    verify_steward_preregistration,
)
from scripts.science.independent_material_study_feasibility import (
    SCHEMA as PLAN_SCHEMA, UNIT, COHORT, IID_DESIGN, NONIID_DESIGN,
    ENDPOINT, plan_independent_material_study,
)

KEYS = {
    role: Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(("TEST_ONLY_0143_" + role).encode()).digest()
    )
    for role in ("steward", "witness")
}


def packet(*, scope="SYNTHETIC"):
    plan = {
        "schema_version": PLAN_SCHEMA,
        "unit": UNIT,
        "cohort_source": COHORT,
        "sampling_design": IID_DESIGN,
        "endpoint": ENDPOINT,
        "confidence_level": 0.95,
        "maximum_wilson_half_width": 0.10,
        "prospective_pre_enrollment_nonacquisition_fraction": 0.20,
        "post_enrollment_failures_count_in_denominator": True,
    }
    envelope = {
        "schema_version": SCHEMA,
        "scope": scope,
        "evaluation_id": "synthetic-0143-only",
        "evaluation_version": "test-v1",
        "model_sha256": MODEL_SHA256,
        "study_plan_sha256":
            plan_independent_material_study(plan)["validated_prospective_plan_sha256"],
        "cohort_commitment_sha256": hashlib.sha256(b"TEST_ONLY_SALTED_COHORT").hexdigest(),
        "identity_scheme": IDENTITY_SCHEME,
        "privacy_policy": PRIVACY,
        "development_group": "test-developer-group",
        "declared_independent_material_count": 93,
        "declared_prospective_recruited_count": 117,
        "outcome_policy": "ALL_ENROLLED_MATERIALS_INCLUDING_FAILED_UNKNOWN_ABSTAINED",
    }
    trusted_issuers = {
        role: TrustedIssuer(
            key.public_key().public_bytes_raw(),
            frozenset((role,)),
            "test-independent-" + role,
            scope,
            "test-ledger-0143",
        )
        for role, key in KEYS.items()
    }
    result = {
        "envelope": envelope,
        "study_plan": plan,
        "trusted_issuers": trusted_issuers,
    }
    resign(result)
    return result


def resign(value):
    envelope_hash = evidence_sha256(value["envelope"])
    previous = ZERO_SHA256
    receipts = []
    for i, (role, event) in enumerate((
        ("steward", "cohort_preregistered"),
        ("witness", "cohort_commitment_witnessed"),
    ), start=1):
        body = {
            "schema_version": "rhombus-independent-receipt-v1",
            "issuer": role,
            "role": role,
            "event": event,
            "subject_sha256": envelope_hash,
            "context_sha256": envelope_hash,
            "scope": value["envelope"]["scope"],
            "log_id": "test-ledger-0143",
            "sequence": i,
            "previous_receipt_sha256": previous,
        }
        signed = {
            **body, "signature": KEYS[role].sign(canonical_bytes(body)).hex(),
        }
        receipts.append(signed)
        previous = evidence_sha256(signed)
    value["receipts"] = receipts


def test_synthetic_sealed_commitment_verifies_signatures_not_science():
    r = verify_steward_preregistration(**packet())
    assert r["two_role_bound_signatures_cryptographically_verified"] is True
    assert r["scope"] == "SYNTHETIC"
    assert r["claimed_material_count_not_independently_verified"] == 93
    assert r["claimed_recruited_count_not_independently_verified"] == 117
    assert r["externally_qualified_independent_material_count"] == 0
    assert not r["new_private_cohort_source_independently_verified"]
    assert not r["physical_material_independence_and_sampling_frame_verified"]
    assert not r["all_actual_material_outcomes_or_blind_truth_received"]
    assert not r["actual_model_predictions_committed_before_truth"]
    assert r["P0_01_status"] == "BLOCKED"
    assert r["P0_02_status"] == "BLOCKED"
    assert r["P0_03_status"] == "BLOCKED"
    assert not r["scientific_release_authorized"]
    assert r["status"] == "SIGNED_PREREGISTRATION_ASSERTION_ONLY"


def test_synthetic_test_scope_cannot_be_elevated_by_editing_scope_only():
    f = packet()
    f["envelope"]["scope"] = "EXTERNAL"
    with pytest.raises(ValueError):
        verify_steward_preregistration(**f)


def test_external_scope_test_key_simulation_still_does_not_authorize_science():
    # Demonstrates mechanics ONLY; TEST_ONLY public keys are NOT real trust anchors.
    f = packet(scope="EXTERNAL")
    r = verify_steward_preregistration(**f)
    assert r["scope"] == "EXTERNAL"
    assert r["external_parties_real_world_independence_verified"] is False
    assert r["externally_qualified_independent_material_count"] == 0
    assert not r["scientific_release_authorized"]


@pytest.mark.parametrize("target,change", [
    ("envelope", lambda x: x.update(model_sha256="1"*64)),
    ("envelope", lambda x: x.update(cohort_commitment_sha256="abc")),
    ("envelope", lambda x: x.update(study_plan_sha256="e"*64)),
    ("envelope", lambda x: x.update(identity_scheme="RAW_PUBLIC_FORMULAE")),
    ("envelope", lambda x: x.update(privacy_policy="PUBLISH_TRUE_LI_CONDUCTIVITY")),
    ("envelope", lambda x: x.update(outcome_policy="DROP_FAILED")),
    ("envelope", lambda x: x.update(declared_independent_material_count=92)),
    ("envelope", lambda x: x.update(declared_prospective_recruited_count=116)),
    ("envelope", lambda x: x.update(declared_independent_material_count=True)),
    ("envelope", lambda x: x.update(cohort_private_truth=["PRIVATE_SAMPLE"])),
    ("envelope", lambda x: x.update(scope="PUBLIC_OBELIX_TEST")),
    ("study_plan", lambda x: x.update(sampling_design=NONIID_DESIGN)),
    ("study_plan", lambda x: x.update(post_enrollment_failures_count_in_denominator=False)),
])
def test_invalid_protocol_claims_fail_even_if_resigned(target, change):
    f = packet()
    change(f[target])
    resign(f)
    with pytest.raises(ValueError):
        verify_steward_preregistration(**f)


@pytest.mark.parametrize("mutation", [
    "modified_envelope_after_signing",
    "modified_signature",
    "wrong_receipt_order",
    "broken_previous_link",
    "untrusted_issuer",
    "self_issued_key_from_packet",
    "duplicate_role",
    "mismatched_event",
    "mismatched_log",
    "wrong_receipt_scope",
    "same_independence_group",
    "developer_controlled_key",
    "wrong_sequence",
    "missing_receipt",
    "missing_host_keys",
    "wrong_signing_context",
])
def test_receipt_chain_red_team_rejections(mutation):
    f = packet()
    if mutation == "modified_envelope_after_signing":
        f["envelope"]["evaluation_version"] = "changed-after-witness"
    elif mutation == "modified_signature":
        f["receipts"][0]["signature"] = "e"*128
    elif mutation == "wrong_receipt_order":
        f["receipts"] = list(reversed(f["receipts"]))
    elif mutation == "broken_previous_link":
        f["receipts"][1]["previous_receipt_sha256"] = ZERO_SHA256
    elif mutation in ("untrusted_issuer", "self_issued_key_from_packet"):
        f["receipts"][0]["issuer"] = "unprovisioned"
        if mutation == "self_issued_key_from_packet":
            f["envelope"]["trusted_issuers_from_packet"] = "FAKE"
    elif mutation == "duplicate_role":
        f["receipts"][1]["role"] = "steward"
    elif mutation == "mismatched_event":
        f["receipts"][0]["event"] = "truth_released_before_prediction"
    elif mutation == "mismatched_log":
        f["receipts"][1]["log_id"] = "other-log"
    elif mutation == "wrong_receipt_scope":
        f["receipts"][0]["scope"] = "EXTERNAL"
    elif mutation == "same_independence_group":
        from dataclasses import replace
        f["trusted_issuers"]["witness"] = replace(
            f["trusted_issuers"]["witness"],
            independence_group=f["trusted_issuers"]["steward"].independence_group)
    elif mutation == "developer_controlled_key":
        from dataclasses import replace
        f["trusted_issuers"]["steward"] = replace(
            f["trusted_issuers"]["steward"],
            independence_group=f["envelope"]["development_group"])
    elif mutation == "wrong_sequence":
        f["receipts"][1]["sequence"] = 1
    elif mutation == "missing_receipt":
        f["receipts"] = f["receipts"][:1]
    elif mutation == "missing_host_keys":
        f["trusted_issuers"] = {}
    elif mutation == "wrong_signing_context":
        f["receipts"][1]["context_sha256"] = "a"*64
    with pytest.raises(ValueError):
        verify_steward_preregistration(**f)


def test_sealed_aggregate_output_has_no_private_identifiers_or_public_issuer_keys():
    import json
    f = packet()
    r = verify_steward_preregistration(**f)
    serialized = json.dumps(r)
    assert "PRIVATE_SAMPLE" not in serialized
    assert "test-independent-steward" not in serialized
    assert "test-ledger-0143" not in serialized
    assert "signature" in serialized
    assert "material_tokens" not in serialized


def test_preregistered_count_is_asserted_not_qualified_or_empirical():
    f = packet()
    f["envelope"]["declared_independent_material_count"] = 1000
    f["envelope"]["declared_prospective_recruited_count"] = 1000
    resign(f)
    r = verify_steward_preregistration(**f)
    assert r["claimed_material_count_not_independently_verified"] == 1000
    assert r["externally_qualified_independent_material_count"] == 0
    assert r["P0_03_status"] == "BLOCKED"
