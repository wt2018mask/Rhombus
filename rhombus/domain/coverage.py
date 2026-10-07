"""Reference-coverage primitives for Rhombus 2.0 Phase 3.

Coverage summarizes distances to an explicit reference set. It does not by
itself assign a domain verdict; verdicts require a separately frozen
calibration contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable

from .distance import StructuralDescriptor, StructuralDistance, structural_distance


@dataclass(frozen=True)
class ReferenceStructure:
    reference_id: str
    descriptor: StructuralDescriptor
    group_id: str | None = None

    def __post_init__(self) -> None:
        if not self.reference_id.strip():
            raise ValueError("reference_id must be non-empty")


@dataclass(frozen=True)
class ReferenceCoverage:
    reference_set_id: str
    reference_count: int
    nearest_reference_id: str
    nearest_distance: float
    kth_distance: float
    k: int
    median_distance: float
    maximum_distance: float
    distances: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        if not self.reference_set_id.strip():
            raise ValueError("reference_set_id must be non-empty")
        if self.reference_count <= 0:
            raise ValueError("reference_count must be positive")
        if len(self.distances) != self.reference_count:
            raise ValueError("distances must match reference_count")
        if self.k <= 0 or self.k > self.reference_count:
            raise ValueError("k must be in [1, reference_count]")
        if self.nearest_distance < 0 or self.kth_distance < 0:
            raise ValueError("coverage distances must be non-negative")


def assess_reference_coverage(
    *,
    candidate: StructuralDescriptor,
    references: Iterable[ReferenceStructure],
    reference_set_id: str,
    k: int = 3,
) -> ReferenceCoverage:
    rows = tuple(references)
    if not rows:
        raise ValueError("references must be non-empty")
    if not reference_set_id.strip():
        raise ValueError("reference_set_id must be non-empty")
    if len({row.reference_id for row in rows}) != len(rows):
        raise ValueError("reference ids must be unique")
    if k <= 0 or k > len(rows):
        raise ValueError("k must be in [1, len(references)]")

    measured: list[tuple[str, StructuralDistance]] = [
        (row.reference_id, structural_distance(candidate, row.descriptor))
        for row in rows
    ]
    ordered = tuple(
        sorted(
            (
                (reference_id, result.combined_distance)
                for reference_id, result in measured
            ),
            key=lambda item: (item[1], item[0]),
        )
    )
    values = [distance for _, distance in ordered]
    return ReferenceCoverage(
        reference_set_id=reference_set_id,
        reference_count=len(ordered),
        nearest_reference_id=ordered[0][0],
        nearest_distance=ordered[0][1],
        kth_distance=ordered[k - 1][1],
        k=k,
        median_distance=median(values),
        maximum_distance=max(values),
        distances=ordered,
    )
