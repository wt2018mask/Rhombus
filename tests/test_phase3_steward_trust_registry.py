"""0144 host trust roots: test-only deterministic Ed25519 keys, no real stewards."""
import copy
import hashlib
import json

import pytest

from rhombus.qualification.steward_trust_registry import (
    SCHEMA, MODEL_SHA256, MAX_REGISTRY_BYTES,
    read_host_pinned_steward_registry, review_pinned_external_steward_packet,
)
from tests.test_phase3_steward_envelope_intake import packet


def host_packet():
    claim = packet(scope="EXTERNAL")  # TEST_ONLY keys, never production trust
    policy = {
        "schema_version": SCHEMA,
        "revision": 1,
        "scope": "EXTERNAL",
        "evaluation_id": claim["envelope"]["evaluation_id"],
        "model_sha256": MODEL_SHA256,
        "development_group": claim["envelope"]["development_group"],
        "log_id": "test-ledger-0143",
        "registrations": [
            {
                "issuer": role,
                "role": role,
                "independence_group": "test-independent-" + role,
                "public_key_hex": claim["trusted_issuers"][role].public_key.hex(),
                "status": "ACTIVE",
                "authority_review_sha256": hashlib.sha256(
                    ("TEST_ONLY_unvetted_" + role).encode()
                ).hexdigest(),
            }
            for role in ("steward", "witness")
        ],
    }
    return claim, policy


def raw_and_host_sha(policy):
    raw = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()
    return raw, hashlib.sha256(raw).hexdigest()


def review(claim, policy, *, host_pin=None):
    raw, actual = raw_and_host_sha(policy)
    return review_pinned_external_steward_packet(
        raw_host_registry=raw,
        expected_host_sha256=actual if host_pin is None else host_pin,
        envelope=claim["envelope"],
        study_plan=claim["study_plan"],
        receipts=claim["receipts"],
    )


def test_host_pinned_synthetic_external_mechanics_never_grants_science():
    claim, policy = host_packet()
    result = review(claim, policy)
    assert result["current_unrevoked_host_signers_authenticated"] is True
    assert result["current_distinct_host_role_groups_verified_as_registered"] is True
    assert result["host_registry_revision"] == 1
    assert result["real_world_institutional_approval_independently_verified"] is False
    assert result["scientifically_qualified_independent_material_count"] == 0
    assert result["cohort_material_identity_measurement_and_truth_independently_verified"] is False
    assert result["publisher_selected_training_frame_overlap_audited"] is False
    assert result["P0_01_status"] == result["P0_02_status"] == result["P0_03_status"] == "BLOCKED"
    assert result["scientific_release_authorized"] is False
    assert result["status"] == "HOST_PINNED_CRYPTOGRAPHIC_ASSERTION_ONLY"
    assert result["self_reported_material_counts_are_not_material_evidence"] is True


def test_exact_raw_byte_hash_pinning_fails_reformat_without_operator_reapproval():
    _, policy = host_packet()
    raw, pinned_sha = raw_and_host_sha(policy)
    reformatted = json.dumps(policy, indent=2).encode()
    assert reformatted != raw
    with pytest.raises(ValueError, match="host root mismatch"):
        read_host_pinned_steward_registry(
            raw_registry=reformatted, expected_host_sha256=pinned_sha)


def test_unauthorized_key_rotation_or_revocation_fails_old_host_pin():
    claim, policy = host_packet()
    _, pinned = raw_and_host_sha(policy)
    policy["registrations"][0]["status"] = "REVOKED"
    with pytest.raises(ValueError, match="host root mismatch"):
        review(claim, policy, host_pin=pinned)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(schema_version="other"),
    lambda p: p.update(scope="SYNTHETIC"),
    lambda p: p.update(model_sha256="f"*64),
    lambda p: p.update(revision=0),
    lambda p: p.update(revision=True),
    lambda p: p.update(log_id=""),
    lambda p: p.update(extra_untrusted_roster=["PRIVATE"]),
    lambda p: p.update(registrations=[]),
    lambda p: p["registrations"][0].update(issuer="BAD/NAME"),
    lambda p: p["registrations"][0].update(role="publisher"),
    lambda p: p["registrations"][0].update(status="UNVERIFIED"),
    lambda p: p["registrations"][0].update(authority_review_sha256="nonsense"),
    lambda p: p["registrations"][0].update(public_key_hex="1"*63),
    lambda p: p["registrations"][0].update(public_key_hex="0"*64),
    lambda p: p["registrations"][0].update(extra_secret="DO_NOT_COPY"),
    lambda p: p["registrations"][1].update(public_key_hex=p["registrations"][0]["public_key_hex"]),
    lambda p: p["registrations"][1].update(issuer="steward"),
    lambda p: p["registrations"][1].update(role="steward"),
    lambda p: p["registrations"][1].update(independence_group=p["registrations"][0]["independence_group"]),
    lambda p: p["registrations"][1].update(independence_group=p["development_group"]),
    lambda p: p["registrations"][0].update(status="REVOKED"),
])
def test_unapproved_registry_claims_rejected_even_with_recomputed_hash(mutate):
    _, policy = host_packet()
    mutate(policy)
    raw, pinned = raw_and_host_sha(policy)
    with pytest.raises(ValueError):
        read_host_pinned_steward_registry(raw_registry=raw, expected_host_sha256=pinned)


def test_revoked_old_key_remains_in_audit_record_but_never_authorized():
    claim, policy = host_packet()
    old = copy.deepcopy(policy["registrations"][0])
    old.update(
        issuer="oldsteward", status="REVOKED",
        public_key_hex=hashlib.sha256(b"TEST_ONLY_OLD_KEY").hexdigest(),
    )
    policy["registrations"].append(old)
    raw, pin = raw_and_host_sha(policy)
    observed, active = read_host_pinned_steward_registry(
        raw_registry=raw, expected_host_sha256=pin)
    assert observed["revision"] == 1
    assert set(active) == {"steward", "witness"}
    assert "oldsteward" not in active
    assert review(claim, policy)["scientific_release_authorized"] is False
    claim["receipts"][0]["issuer"] = "oldsteward"
    with pytest.raises(ValueError, match="untrusted independent issuer"):
        review(claim, policy)


def test_revoking_without_replacing_active_witness_fails_even_with_new_pin():
    claim, policy = host_packet()
    policy["registrations"][1]["status"] = "REVOKED"
    with pytest.raises(ValueError, match="one steward and one witness"):
        review(claim, policy)


@pytest.mark.parametrize("change", [
    lambda c: c["envelope"].update(evaluation_id="unknown-cohort"),
    lambda c: c["envelope"].update(scope="SYNTHETIC"),
    lambda c: c["envelope"].update(development_group="different"),
    lambda c: c["envelope"].update(model_sha256="a"*64),
    lambda c: c["receipts"][0].update(signature="f"*128),
    lambda c: c["receipts"][1].update(previous_receipt_sha256="0"*64),
    lambda c: c["receipts"][1].update(issuer="untrusted"),
    lambda c: c["receipts"][1].update(role="steward"),
])
def test_signed_claim_not_bound_to_host_policy_denied(change):
    claim, policy = host_packet()
    change(claim)
    with pytest.raises(ValueError):
        review(claim, policy)


def test_malicious_packet_cannot_provision_its_own_key_or_trust_revision():
    claim, policy = host_packet()
    claim["envelope"]["host_registry_sha256"] = "f"*64
    with pytest.raises(ValueError):
        review(claim, policy)
    del claim["envelope"]["host_registry_sha256"]
    _, original_pin = raw_and_host_sha(policy)
    policy["registrations"][0]["public_key_hex"] = "b"*64
    with pytest.raises(ValueError, match="host root mismatch"):
        review(claim, policy, host_pin=original_pin)


@pytest.mark.parametrize("raw", [
    b'{"revision":1,"revision":2}',
    b'{"revision":NaN}',
    b'{"revision":Infinity}',
    b'\xff',
    b'[]',
    b'',
    b' ' * (MAX_REGISTRY_BYTES + 1),
])
def test_bounded_strict_host_json_rejects_noncanonical_inputs(raw):
    with pytest.raises(ValueError):
        read_host_pinned_steward_registry(
            raw_registry=raw,
            expected_host_sha256=hashlib.sha256(raw).hexdigest())


def test_missing_or_attacker_chosen_pin_is_not_proof_of_external_institution():
    claim, policy = host_packet()
    raw, pin = raw_and_host_sha(policy)
    for wrong in ("ff", pin.upper(), None, False):
        with pytest.raises(ValueError):
            read_host_pinned_steward_registry(
                raw_registry=raw, expected_host_sha256=wrong)
    # A mathematically matching test-only pin proves only this test's bytes.
    report = review(claim, policy, host_pin=pin)
    assert report["cryptographic_trust_policy_requires_out_of_band_owner"] is True
    assert report["real_world_institutional_approval_independently_verified"] is False


def test_returned_aggregate_does_not_expose_roster_signer_names_or_keys():
    claim, policy = host_packet()
    r = review(claim, policy)
    rendered = json.dumps(r)
    assert "test-ledger-0143" not in rendered
    assert "test-independent-steward" not in rendered
    assert "PRIVATE" not in rendered
    assert "signature" not in rendered
    for row in policy["registrations"]:
        assert row["public_key_hex"] not in rendered
