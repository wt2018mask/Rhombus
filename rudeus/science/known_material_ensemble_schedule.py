"""Deterministic integer-count schedules for small-cell occupancy ensembles."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from rudeus.science.contracts import Record


ENSEMBLE_COUNT_SCHEDULE_VERSION = "known-material-ensemble-count-schedule-v1"


@dataclass(frozen=True, kw_only=True)
class EnsembleCountSchedule(Record):
    schedule_version: str
    namespace: str
    realization_count: int
    lower_count: int
    upper_count: int
    upper_member_indices: tuple[int, ...]


def deterministic_count_schedule(
    *,
    namespace: str,
    realization_count: int,
    lower_count: int,
    upper_count: int,
    upper_member_count: int,
) -> EnsembleCountSchedule:
    if not namespace or realization_count < 2:
        raise ValueError("count schedule requires namespace and at least two members")
    if lower_count < 0 or upper_count < lower_count:
        raise ValueError("invalid lower/upper integer counts")
    if upper_count - lower_count > 1:
        raise ValueError("count schedule only supports adjacent integer counts")
    if not 0 <= upper_member_count <= realization_count:
        raise ValueError("upper_member_count outside ensemble")
    ranked = []
    for index in range(realization_count):
        token = (
            f"{ENSEMBLE_COUNT_SCHEDULE_VERSION}|{namespace}|{index}"
        ).encode("utf-8")
        ranked.append((hashlib.sha256(token).digest(), index))
    selected = tuple(sorted(index for _, index in sorted(ranked)[:upper_member_count]))
    return EnsembleCountSchedule(
        schedule_version=ENSEMBLE_COUNT_SCHEDULE_VERSION,
        namespace=namespace,
        realization_count=realization_count,
        lower_count=lower_count,
        upper_count=upper_count,
        upper_member_indices=selected,
    )


def count_for_member(schedule: EnsembleCountSchedule, member_index: int) -> int:
    if not 0 <= member_index < schedule.realization_count:
        raise ValueError("member index outside ensemble")
    return (
        schedule.upper_count
        if member_index in schedule.upper_member_indices
        else schedule.lower_count
    )
