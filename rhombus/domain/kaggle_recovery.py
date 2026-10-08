"""Fail-closed offline triage of a terminated Phase 3 Kaggle production run.

This evaluator does NOT contact Kaggle, inspect files, or attest source identity.
It takes host-observed status and independently verified artifact facts. No
agent-supplied status can authorize a re-submit or scientific conclusions.
"""
from __future__ import annotations

from typing import Any, Mapping

TERMINAL = frozenset({"COMPLETE", "ERROR", "CANCELLED", "TIMEOUT"})
STATES = TERMINAL | {"RUNNING", "UNKNOWN", "STATUS_QUERY_ERROR"}
REQUIRED_EVIDENCE = frozenset({
    "receipt_verified", "archive_hashes_verified",
    "source_counts_verified", "source_digests_verified",
})


def assess_kaggle_recovery(
    *, provider_state: str, evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Assess verified observables, not an inference from elapsed time or CI.

    No production kernel is submitted/cancelled by this code. A status-query
    exception never becomes a provider ERROR or RUNNING automatically.
    """
    if provider_state not in STATES:
        raise ValueError("unsupported provider state")
    if not isinstance(evidence, Mapping) or set(evidence) != REQUIRED_EVIDENCE:
        raise ValueError("exact verified evidence flags are required")
    if any(type(flag) is not bool for flag in evidence.values()):
        raise ValueError("evidence flags must be host-verified booleans")

    complete = all(evidence.values())
    if provider_state == "COMPLETE" and complete:
        state = "ARTIFACT_VERIFICATION_REPORTED_COMPLETE"
        next_action = "INDEPENDENTLY_REVIEW_VERIFICATION_AND_PROVENANCE"
    elif provider_state in {"ERROR", "CANCELLED", "TIMEOUT"}:
        state = "TERMINAL_INCOMPLETE_OR_UNQUALIFIED"
        next_action = "CAPTURE_SANITIZED_LOGS_AND_VALIDATE_RECOVERABLE_FILES"
    elif provider_state == "COMPLETE":
        state = "COMPLETE_BUT_OUTPUTS_UNVERIFIED"
        next_action = "RETRIEVE_AND_INDEPENDENTLY_VERIFY_OUTPUTS"
    else:
        state = "PROVIDER_NOT_ATTESTED_TERMINAL"
        next_action = "CONTINUE_BOUNDED_READ_ONLY_STATUS_OBSERVATION"

    return {
        "schema_version": "rhombus-phase3-kaggle-recovery-triage-v1",
        "provider_state": provider_state,
        "recovery_state": state,
        "next_action": next_action,
        "verified_evidence_flags": dict(evidence),
        "provider_terminal": provider_state in TERMINAL,
        "resubmission_authorized": False,
        "partial_results_scientifically_qualified": False,
        "scientific_verdict": "UNKNOWN",
        "claim_authorized": False,
        "limitations": [
            "DECLARED_FLAGS_REQUIRE_HOST_INDEPENDENT_ATTESTATION",
            "NO_REMOTE_PROVIDER_CALL_OR_KERNEL_EXECUTION",
            "NO_PARTIAL_OUTPUT_DURABILITY_ASSUMED",
            "STATUS_QUERY_HEARTBEAT_NOT_PROVIDER_STATE",
        ],
    }


__all__ = ["assess_kaggle_recovery"]
