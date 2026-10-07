"""AI-first adapter for transport-regime classification.

This module wraps the legacy P2.5 implementation without changing its
scientific gates. The public v2 name describes intent directly:
`classify_transport_regime`.

The adapter is intentionally narrow:
- input must already be admitted by `assess_transport_regime_admission`;
- legacy P2/P2.5 stage names are not exposed to callers;
- diffusion/conductivity claims remain out of scope.
"""

from __future__ import annotations

from typing import Any, Mapping

from rudeus.mlip.p25 import P25_DEFAULTS, analyze_p25

from .admission import assess_transport_regime_admission


def classify_transport_regime(
    *,
    stability_payload: Mapping[str, Any],
    worker_info: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify the mobile-ion transport regime from bound stability evidence.

    Returns the legacy classifier result with an additive AI-first capability
    envelope. Scientific thresholds are delegated unchanged to the legacy
    qualified implementation during migration.
    """
    payload = dict(stability_payload)
    result = payload.get("result") or {}

    decision = assess_transport_regime_admission(
        finite_temperature_stability_verdict=str(
            result.get("p2_verdict", "")
        ),
        authoritative_stability_verdict=(
            result.get("p2_verdict") == "PASS"
            and result.get("dynamic_state") == "PASS"
        ),
        trajectory_sha256=(
            (result.get("trajectory_artifact") or {}).get("sha256")
        ),
        numerical_abort=result.get("numerical_abort"),
    )
    if decision["admission_status"] != "ELIGIBLE":
        return {
            "capability": "classify_transport_regime",
            "operational_status": "SUCCEEDED",
            "scientific_verdict": "INDETERMINATE",
            "transport_state": None,
            "admission": decision,
            "legacy_result": None,
        }

    legacy = analyze_p25(
        payload,
        dict(P25_DEFAULTS),
        dict(worker_info or {}),
        p2_result_path="",
    )
    return {
        "capability": "classify_transport_regime",
        "operational_status": "SUCCEEDED",
        "scientific_verdict": legacy.get("transport_state"),
        "transport_state": legacy.get("transport_state"),
        "admission": decision,
        "legacy_result": legacy,
    }
