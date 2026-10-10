"""Offline Ed25519 verification against host-provisioned external trust anchors.

Keys, permitted roles, independence groups and scope are never taken from an
artifact. A valid signature authenticates an assertion, not its scientific truth.
No keys are generated, no network is contacted, and no qualification is granted.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "rhombus-independent-receipt-v1"
ZERO_SHA256 = "0" * 64
MAX_JSON_BYTES = 8 * 1024 * 1024


def exact_fields(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{label}: unexpected schema")


def digest(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("expected exact lowercase SHA256")
    return value


def bounded_text(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 256 or not value.strip():
        raise ValueError("expected bounded nonempty text")
    return value


def integer(value, low=1, high=100_000_000):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("expected bounded integer")
    return value


def canonical_bytes(value):
    try:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("noncanonical JSON input") from exc
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("JSON evidence exceeds budget")
    return raw


def evidence_sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_evidence_json(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_JSON_BYTES:
        raise ValueError("JSON evidence exceeds budget")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("nonfinite JSON constant")

    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=reject)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid JSON evidence") from exc
    canonical_bytes(value)
    return value


@dataclass(frozen=True)
class TrustedIssuer:
    public_key: bytes
    roles: frozenset[str]
    independence_group: str
    scope: str
    log_id: str

    def __post_init__(self):
        if not isinstance(self.public_key, bytes) or len(self.public_key) != 32:
            raise ValueError("Ed25519 public key must be 32 bytes")
        if not isinstance(self.roles, frozenset) or not self.roles:
            raise ValueError("trusted roles must be a nonempty frozenset")
        for role in self.roles:
            bounded_text(role)
        bounded_text(self.independence_group)
        bounded_text(self.log_id)
        if self.scope not in ("SYNTHETIC", "EXTERNAL"):
            raise ValueError("invalid trust scope")


def verify_evidence_receipt(
    receipt,
    *,
    trusted_issuers: Mapping[str, TrustedIssuer],
    role,
    event,
    subject_sha256,
    context_sha256,
    scope,
):
    exact_fields(
        receipt,
        (
            "schema_version",
            "issuer",
            "role",
            "event",
            "subject_sha256",
            "context_sha256",
            "scope",
            "log_id",
            "sequence",
            "previous_receipt_sha256",
            "signature",
        ),
        "receipt",
    )
    bounded_text(receipt["issuer"])
    issuer = trusted_issuers.get(receipt["issuer"])
    if not isinstance(issuer, TrustedIssuer):
        raise ValueError("untrusted independent issuer")
    if role not in issuer.roles or receipt["role"] != role:
        raise ValueError("receipt role not permitted")
    if (
        receipt["schema_version"] != SCHEMA
        or receipt["scope"] != scope
        or issuer.scope != scope
    ):
        raise ValueError("receipt schema/scope mismatch")
    if receipt["log_id"] != issuer.log_id or receipt["event"] != event:
        raise ValueError("receipt log/event mismatch")
    if receipt["subject_sha256"] != digest(subject_sha256) or receipt[
        "context_sha256"
    ] != digest(context_sha256):
        raise ValueError("receipt subject/context mismatch")
    digest(receipt["previous_receipt_sha256"])
    integer(receipt["sequence"])
    signature = receipt["signature"]
    if not isinstance(signature, str) or not re.fullmatch("[0-9a-f]{128}", signature):
        raise ValueError("invalid Ed25519 signature encoding")
    body = {key: value for key, value in receipt.items() if key != "signature"}
    try:
        Ed25519PublicKey.from_public_bytes(issuer.public_key).verify(
            bytes.fromhex(signature), canonical_bytes(body)
        )
    except InvalidSignature as exc:
        raise ValueError("invalid independent signature") from exc
    return issuer
