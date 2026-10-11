"""Host SHA256-pinned external steward trust roots, never artifact-supplied keys.

A SHA256 pin MUST be supplied independently by the host, never copied from an
untrusted envelope, its adjacent policy file or a public development fixture.
A valid signature proves only a claim was signed; never scientific validity.
"""
from __future__ import annotations

import hashlib
import re

from rhombus.evidence.receipts import (
    TrustedIssuer, bounded_text, digest, exact_fields, integer,
    read_evidence_json,
)
from rhombus.qualification.steward_envelope import (
    MODEL_SHA256, verify_steward_preregistration,
)

SCHEMA = "rhombus-host-pinned-steward-trust-registry-0144-v1"
REPORT_SCHEMA = "rhombus-host-pinned-steward-preregistration-review-0144-v1"
MAX_REGISTRY_BYTES = 16_384
MAX_REGISTRATIONS = 24
_ROLES = frozenset(("steward", "witness"))
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_PUBKEY = re.compile(r"^[0-9a-f]{64}$")


def _id(value, label):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("invalid " + label)
    return value


def read_host_pinned_steward_registry(
    *, raw_registry: bytes, expected_host_sha256: str,
) -> tuple[dict, dict[str, TrustedIssuer]]:
    """Return validated policy and ACTIVE trusted keys only.

    Callers are responsible for out-of-band ownership of expected_host_sha256.
    The function cannot verify an actual institutional affiliation or source
    measurement authority. Revocation/rotation changes require a fresh pin.
    """
    digest(expected_host_sha256)
    if (
        not isinstance(raw_registry, bytes)
        or not 1 <= len(raw_registry) <= MAX_REGISTRY_BYTES
    ):
        raise ValueError("host trust registry byte budget invalid")
    if hashlib.sha256(raw_registry).hexdigest() != expected_host_sha256:
        raise ValueError("host root mismatch: unapproved registry or rotation")
    policy = read_evidence_json(raw_registry)
    exact_fields(
        policy,
        (
            "schema_version", "revision", "scope", "evaluation_id",
            "model_sha256", "development_group", "log_id", "registrations",
        ),
        "host registry",
    )
    if policy["schema_version"] != SCHEMA or policy["scope"] != "EXTERNAL":
        raise ValueError("unsupported external host trust policy")
    integer(policy["revision"], high=10_000)
    _id(policy["evaluation_id"], "external evaluation ID")
    _id(policy["development_group"], "developer independence group")
    _id(policy["log_id"], "audit log ID")
    if policy["model_sha256"] != MODEL_SHA256:
        raise ValueError("unrecognized model checkpoint identity in trust root")
    rows = policy["registrations"]
    if not isinstance(rows, list) or not 2 <= len(rows) <= MAX_REGISTRATIONS:
        raise ValueError("incomplete or overlarge host trust registry")
    seen_issuer, seen_keys, active_roles = set(), set(), set()
    trusted: dict[str, TrustedIssuer] = {}
    active_groups = set()
    for row in rows:
        exact_fields(
            row,
            (
                "issuer", "role", "independence_group", "public_key_hex",
                "status", "authority_review_sha256",
            ),
            "host issuer registration",
        )
        issuer = _id(row["issuer"], "issuer")
        group = _id(row["independence_group"], "independence group")
        role, status = row["role"], row["status"]
        if role not in _ROLES or status not in ("ACTIVE", "REVOKED"):
            raise ValueError("unsupported or expired external issuer role/status")
        public_hex = row["public_key_hex"]
        if (
            not isinstance(public_hex, str)
            or not _PUBKEY.fullmatch(public_hex)
            or public_hex == "0" * 64
        ):
            raise ValueError("invalid Ed25519 trust-anchor encoding")
        digest(row["authority_review_sha256"])
        if issuer in seen_issuer or public_hex in seen_keys:
            raise ValueError("duplicated issuer or reused signing public key")
        seen_issuer.add(issuer)
        seen_keys.add(public_hex)
        if status == "ACTIVE":
            if role in active_roles or group in active_groups or (
                group == policy["development_group"]
            ):
                raise ValueError("active issuer role/group conflicts or developer custody")
            active_roles.add(role)
            active_groups.add(group)
            trusted[issuer] = TrustedIssuer(
                public_key=bytes.fromhex(public_hex),
                roles=frozenset((role,)),
                independence_group=group,
                scope="EXTERNAL",
                log_id=policy["log_id"],
            )
    if active_roles != _ROLES or len(trusted) != 2:
        raise ValueError("host must independently activate one steward and one witness")
    return policy, trusted


def review_pinned_external_steward_packet(
    *, raw_host_registry: bytes, expected_host_sha256: str,
    envelope: dict, study_plan: dict, receipts: list,
) -> dict:
    """Use ONLY out-of-band-pinned active issuers, not packet-provided keys."""
    policy, trusted_issuers = read_host_pinned_steward_registry(
        raw_registry=raw_host_registry,
        expected_host_sha256=expected_host_sha256,
    )
    if not isinstance(envelope, dict) or any((
        envelope.get("evaluation_id") != policy["evaluation_id"],
        envelope.get("scope") != "EXTERNAL",
        envelope.get("model_sha256") != policy["model_sha256"],
        envelope.get("development_group") != policy["development_group"],
    )):
        raise ValueError("sealed study is not bound to approved external host policy")
    verified = verify_steward_preregistration(
        envelope=envelope,
        study_plan=study_plan,
        receipts=receipts,
        trusted_issuers=trusted_issuers,
    )
    if not verified["two_role_bound_signatures_cryptographically_verified"]:
        raise ValueError("signed external preregistration did not authenticate")
    # Never output public/private keys, receipt signatures, log/issuer identity,
    # original private cohort identifiers, data rows, measurement or truth.
    return {
        "schema_version": REPORT_SCHEMA,
        "approved_host_registry_exact_bytes_sha256": expected_host_sha256,
        "host_registry_revision": policy["revision"],
        "bound_external_study_commitment_sha256": verified["sealed_envelope_sha256"],
        "bound_prospective_plan_sha256": verified["bound_study_plan_sha256"],
        "bound_model_sha256": MODEL_SHA256,
        "current_unrevoked_host_signers_authenticated": True,
        "current_distinct_host_role_groups_verified_as_registered": True,
        "cryptographic_trust_policy_requires_out_of_band_owner": True,
        "real_world_institutional_approval_independently_verified": False,
        "cohort_material_identity_measurement_and_truth_independently_verified": False,
        "publisher_selected_training_frame_overlap_audited": False,
        "scientifically_qualified_independent_material_count": 0,
        "self_reported_material_counts_are_not_material_evidence": True,
        "scientific_verdict": "INDETERMINATE",
        "P0_01_status": "BLOCKED",
        "P0_02_status": "BLOCKED",
        "P0_03_status": "BLOCKED",
        "scientific_release_authorized": False,
        "status": "HOST_PINNED_CRYPTOGRAPHIC_ASSERTION_ONLY",
    }
