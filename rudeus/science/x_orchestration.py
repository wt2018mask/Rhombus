"""Production orchestration for primary-vs-MatterSim X comparison.

This module assembles an X record only from already-bound observations and an
explicit XComparisonSpec. It never invents tolerances or silently harmonizes
scope. Absence of an explicit comparison spec is a hard stop.
"""

from __future__ import annotations

from typing import Any, Mapping

from rudeus.science.xcheck import (
    XComparisonSpec,
    XInputBinding,
    XModelIdentity,
    XObservation,
    x_record,
)


class XComparisonOrchestrationError(RuntimeError):
    pass


def build_x_comparison_record(
    *,
    primary_model: XModelIdentity,
    cross_model: XModelIdentity,
    primary_binding: XInputBinding,
    cross_binding: XInputBinding,
    primary_observation: XObservation,
    cross_observation: XObservation,
    comparison: XComparisonSpec | None,
) -> dict:
    """Build a replay-verifiable X record only with an explicit comparison spec."""
    if comparison is None:
        raise XComparisonOrchestrationError(
            "explicit X comparison spec is required; refusing to invent tolerance"
        )

    if primary_binding != cross_binding:
        raise XComparisonOrchestrationError(
            "primary and cross observations are not bound to identical scientific scope"
        )

    if comparison.quantity != primary_binding.quantity:
        raise XComparisonOrchestrationError("comparison quantity does not match X binding")
    if comparison.units != primary_binding.units:
        raise XComparisonOrchestrationError("comparison units do not match X binding")

    return x_record(
        primary_model=primary_model,
        cross_model=cross_model,
        primary_binding=primary_binding,
        cross_binding=cross_binding,
        comparison=comparison,
        primary_observation=primary_observation,
        cross_observation=cross_observation,
    )


def comparison_spec_from_mapping(value: Mapping[str, Any] | None) -> XComparisonSpec:
    """Parse a caller-supplied comparison mapping; never supply defaults."""
    if value is None:
        raise XComparisonOrchestrationError(
            "comparison mapping missing; no default tolerance is permitted"
        )
    allowed = {
        "quantity",
        "units",
        "absolute_tolerance",
        "relative_tolerance",
        "justification",
        "status",
    }
    extra = set(value) - allowed
    if extra:
        raise XComparisonOrchestrationError(
            f"unexpected comparison fields: {sorted(extra)}"
        )
    try:
        return XComparisonSpec.from_dict(dict(value))
    except (TypeError, ValueError) as exc:
        raise XComparisonOrchestrationError(
            f"invalid explicit X comparison spec: {exc}"
        ) from exc
