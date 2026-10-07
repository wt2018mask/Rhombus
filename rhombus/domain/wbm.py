"""Deterministic, outcome-blind WBM sampling contracts for Phase 3."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable


@dataclass(frozen=True)
class WBMSourceContract:
    source_id: str
    dataset_role: str
    expected_structure_count: int
    expected_material_count: int
    ground_truth_field: str
    energy_correction_policy: str
    license_id: str
    exposure_status: str

    def __post_init__(self) -> None:
        for name, value in (
            ("source_id", self.source_id),
            ("dataset_role", self.dataset_role),
            ("ground_truth_field", self.ground_truth_field),
            ("energy_correction_policy", self.energy_correction_policy),
            ("license_id", self.license_id),
            ("exposure_status", self.exposure_status),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.expected_structure_count <= 0 or self.expected_material_count <= 0:
            raise ValueError("expected dataset counts must be positive")


@dataclass(frozen=True)
class WBMSamplingRecord:
    material_id: str
    substitution_step: int
    prototype_group: str

    def __post_init__(self) -> None:
        if not self.material_id.strip():
            raise ValueError("material_id must be non-empty")
        if self.substitution_step not in {1, 2, 3, 4, 5}:
            raise ValueError("substitution_step must be in {1,2,3,4,5}")
        if not self.prototype_group.strip():
            raise ValueError("prototype_group must be non-empty")


def _rank_key(record: WBMSamplingRecord, *, sampling_version: str) -> tuple[str, str]:
    payload = (
        f"{sampling_version}\0{record.substitution_step}\0"
        f"{record.prototype_group}\0{record.material_id}"
    ).encode("utf-8")
    return sha256(payload).hexdigest(), record.material_id


def deterministic_wbm_sample(
    rows: Iterable[WBMSamplingRecord],
    *,
    sample_size: int,
    sampling_version: str,
) -> tuple[WBMSamplingRecord, ...]:
    """Select a deterministic, outcome-blind sample stratified by substitution step.

    Only immutable source metadata participates in ranking. No DFT target,
    model prediction, prediction error, Rhombus verdict, or distance is accepted
    by this API, preventing outcome leakage into cohort selection.
    """

    records = tuple(rows)
    if not sampling_version.strip():
        raise ValueError("sampling_version must be non-empty")
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    if sample_size > len(records):
        raise ValueError("sample_size cannot exceed available records")
    if len({row.material_id for row in records}) != len(records):
        raise ValueError("material_id values must be unique")

    strata: dict[int, list[WBMSamplingRecord]] = {step: [] for step in range(1, 6)}
    for row in records:
        strata[row.substitution_step].append(row)

    active = [step for step, values in strata.items() if values]
    if sample_size < len(active):
        raise ValueError(
            "sample_size must be at least the number of populated substitution-step strata"
        )

    allocation = {step: 1 for step in active}
    remaining = sample_size - len(active)

    ordered_pool = sorted(
        (
            row
            for step in active
            for row in strata[step]
            if row not in ()
        ),
        key=lambda row: _rank_key(row, sampling_version=sampling_version),
    )

    capacity = {step: len(strata[step]) - 1 for step in active}
    while remaining:
        progressed = False
        for row in ordered_pool:
            step = row.substitution_step
            if capacity[step] <= 0:
                continue
            allocation[step] += 1
            capacity[step] -= 1
            remaining -= 1
            progressed = True
            if remaining == 0:
                break
        if not progressed:
            raise ValueError("insufficient stratum capacity for requested sample_size")

    selected: list[WBMSamplingRecord] = []
    for step in active:
        ranked = sorted(
            strata[step],
            key=lambda row: _rank_key(row, sampling_version=sampling_version),
        )
        selected.extend(ranked[: allocation[step]])

    return tuple(
        sorted(
            selected,
            key=lambda row: (
                row.substitution_step,
                _rank_key(row, sampling_version=sampling_version),
            ),
        )
    )
