"""AI-first admission contract for transport-regime classification.

Finite-temperature stability is upstream evidence. Transport admission is
fail-closed: only an authoritative stability PASS with a bound trajectory and
no numerical abort may proceed. Admission itself is not a diffusion claim.
"""

from __future__ import annotations

from typing import Any, Mapping

TRANSPORT_REGIME_CAPABILITY = "classify_transport_regime"
ADMISSION_CONTRACT_VERSION = "transport-regime-admission-v1"


def assess_transport_regime_admission(
    *,
    finite_temperature_stability_verdict: str,
    authoritative_stability_verdict: bool,
    trajectory_sha256: str | None,
    numerical_abort: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a structured, transport-neutral admission decision.

    The caller must supply an explicit upstream authoritative flag rather than
    letting this layer infer authority from a historical stage code.
    """
    reasons: list[str] = []

    if not authoritative_stability_verdict:
        reasons.append("stability_verdict_not_authoritative")
    if finite_temperature_stability_verdict != "PASS":
        reasons.append(
            "finite_temperature_stability_not_pass"
        )
    if numerical_abort is not None:
        reasons.append("numerical_abort_present")
    if not trajectory_sha256:
        reasons.append("trajectory_evidence_missing")

    eligible = not reasons
    return {
        "contract_version": ADMISSION_CONTRACT_VERSION,
        "capability": TRANSPORT_REGIME_CAPABILITY,
        "admission_status": "ELIGIBLE" if eligible else "NOT_ELIGIBLE",
        "scientific_claim": None,
        "transport_state": None,
        "reasons": reasons,
        "trajectory_sha256": trajectory_sha256,
    }
