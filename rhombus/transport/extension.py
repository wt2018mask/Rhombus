"""AI-first transport evidence extension contract.

This module exposes the semantic capability name used by Rhombus 2.0 while
reusing the frozen legacy one-shot extension protocol during migration.
"""

from __future__ import annotations

from typing import Any, Mapping

from rudeus.mlip.p25_extension import (
    ADMISSION_POLICY as LEGACY_ADMISSION_POLICY,
    EXTENSION_POLICY,
    EXTENSION_PROTOCOL_VERSION,
    TRANSITION_VERSION,
    build_extension_protocol,
    extension_protocol_hash,
)

TRANSPORT_EVIDENCE_EXTENSION_CAPABILITY = "extend_transport_evidence"
TRANSPORT_EVIDENCE_EXTENSION_AUTH_VERSION = (
    "transport-evidence-extension-authorization-v1"
)


def assess_transport_evidence_extension_admission(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Return fail-closed one-shot extension eligibility.

    Only statistical insufficiency may be repaired by more trajectory evidence.
    Composition insufficiency, an authoritative transport verdict, or an
    already-extended source are not eligible.
    """
    result = evidence.get("result") or {}
    interpretation = evidence.get("interpretation") or {}
    reasons: list[str] = []

    if result.get("transport_state") != "INDETERMINATE":
        reasons.append("transport_state_not_indeterminate")
    if result.get("uncertainty_status") != "insufficient":
        reasons.append("uncertainty_not_insufficient")
    if result.get("uncertainty_reason") != "fewer_blocks_than_minimum":
        reasons.append("insufficiency_not_origin_block_limited")
    if int(result.get("n_mobile_ions", 0)) < 2:
        reasons.append("nonextendable_mobile_count_insufficiency")
    if interpretation.get("extension_or_more_evidence_required") is not True:
        reasons.append("extension_not_required_by_source_interpretation")
    if evidence.get("source", {}).get("extension_transition_version"):
        reasons.append("extension_is_one_shot")

    eligible = not reasons
    return {
        "authorization_version": TRANSPORT_EVIDENCE_EXTENSION_AUTH_VERSION,
        "capability": TRANSPORT_EVIDENCE_EXTENSION_CAPABILITY,
        "admission_status": "ELIGIBLE" if eligible else "NOT_ELIGIBLE",
        "reasons": reasons,
        "transition_version": TRANSITION_VERSION,
        "legacy_admission_policy": LEGACY_ADMISSION_POLICY,
        "transition_protocol_version": EXTENSION_PROTOCOL_VERSION,
        "transition_policy": EXTENSION_POLICY,
        "transition_protocol_hash": extension_protocol_hash(),
        "transition_protocol": build_extension_protocol(),
        "one_shot": True,
        "scientific_claim": None,
    }
