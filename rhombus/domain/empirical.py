"""Empirical error-distance calibration readiness contracts.

This module deliberately does not fabricate calibration thresholds. It checks
whether an independently sourced error-distance dataset is scientifically
eligible to support later domain calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ErrorDistanceObservation:
    observation_id: str
    material_id: str
    group_id: str
    structural_distance: float
    error_value: float
    error_metric: str
    reference_source_id: str
    model_checkpoint_sha256: str
    training_membership: str

    def __post_init__(self) -> None:
        for name, value in (
            ("observation_id", self.observation_id),
            ("material_id", self.material_id),
            ("group_id", self.group_id),
            ("error_metric", self.error_metric),
            ("reference_source_id", self.reference_source_id),
            ("model_checkpoint_sha256", self.model_checkpoint_sha256),
            ("training_membership", self.training_membership),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.structural_distance < 0:
            raise ValueError("structural_distance must be non-negative")
        if self.error_value < 0:
            raise ValueError("error_value must be non-negative")


@dataclass(frozen=True)
class CalibrationReadiness:
    ready: bool
    observation_count: int
    material_count: int
    group_count: int
    blockers: tuple[str, ...]


def assess_calibration_readiness(
    observations: Iterable[ErrorDistanceObservation],
    *,
    min_observations: int = 12,
    min_materials: int = 6,
    min_groups: int = 3,
    require_resolved_training_membership: bool = True,
) -> CalibrationReadiness:
    rows = tuple(observations)
    if min_observations <= 0 or min_materials <= 0 or min_groups <= 0:
        raise ValueError("minimum calibration counts must be positive")

    blockers: list[str] = []
    material_count = len({row.material_id for row in rows})
    group_count = len({row.group_id for row in rows})

    if len(rows) < min_observations:
        blockers.append(
            f"insufficient independent observations ({len(rows)} < {min_observations})"
        )
    if material_count < min_materials:
        blockers.append(
            f"insufficient independent materials ({material_count} < {min_materials})"
        )
    if group_count < min_groups:
        blockers.append(
            f"insufficient leave-group-out groups ({group_count} < {min_groups})"
        )

    metrics = {row.error_metric for row in rows}
    if len(metrics) > 1:
        blockers.append("mixed error metrics require separate calibration contracts")

    checkpoints = {row.model_checkpoint_sha256 for row in rows}
    if len(checkpoints) > 1:
        blockers.append("mixed model checkpoints require separate calibration contracts")

    if require_resolved_training_membership and any(
        row.training_membership == "UNRESOLVED_EXACT_MEMBERSHIP" for row in rows
    ):
        blockers.append(
            "exact foundation-model training membership is unresolved for one or more materials"
        )

    source_ids = {row.reference_source_id for row in rows}
    if len(source_ids) < min(2, len(rows)) and rows:
        blockers.append("reference errors lack source diversity")

    return CalibrationReadiness(
        ready=not blockers,
        observation_count=len(rows),
        material_count=material_count,
        group_count=group_count,
        blockers=tuple(blockers),
    )
