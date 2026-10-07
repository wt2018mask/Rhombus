"""Deterministic low-cost structural descriptor and distance baseline."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Mapping

from .descriptors import CompositionDescriptor


@dataclass(frozen=True)
class StructuralDescriptor:
    composition: CompositionDescriptor
    cell_lengths: tuple[float, float, float]
    cell_angles_deg: tuple[float, float, float]
    volume_per_atom: float

    def __post_init__(self) -> None:
        if any(value <= 0 for value in self.cell_lengths):
            raise ValueError("cell_lengths must be positive")
        if any(value <= 0 or value >= 180 for value in self.cell_angles_deg):
            raise ValueError("cell_angles_deg must be in (0, 180)")
        if self.volume_per_atom <= 0:
            raise ValueError("volume_per_atom must be positive")


def _composition_l1(
    left: CompositionDescriptor,
    right: CompositionDescriptor,
) -> float:
    lf = dict(left.fractions())
    rf = dict(right.fractions())
    keys = set(lf) | set(rf)
    return sum(abs(lf.get(key, 0.0) - rf.get(key, 0.0)) for key in keys) / 2.0


@dataclass(frozen=True)
class StructuralDistance:
    composition_distance: float
    lattice_length_distance: float
    lattice_angle_distance: float
    volume_per_atom_distance: float
    combined_distance: float


def structural_distance(
    left: StructuralDescriptor,
    right: StructuralDescriptor,
    *,
    weights: Mapping[str, float] | None = None,
) -> StructuralDistance:
    """Compute a transparent baseline distance without claiming calibrated OOD."""

    selected = {
        "composition": 1.0,
        "cell_lengths": 1.0,
        "cell_angles": 1.0,
        "volume_per_atom": 1.0,
    }
    if weights is not None:
        for key, value in weights.items():
            if key not in selected:
                raise ValueError(f"unknown structural distance weight: {key}")
            if value < 0:
                raise ValueError("structural distance weights must be non-negative")
            selected[key] = float(value)
    if sum(selected.values()) <= 0:
        raise ValueError("at least one structural distance weight must be positive")

    composition = _composition_l1(left.composition, right.composition)
    lengths = sqrt(
        sum(
            ((a - b) / max(abs(a), abs(b))) ** 2
            for a, b in zip(left.cell_lengths, right.cell_lengths)
        )
        / 3.0
    )
    angles = sqrt(
        sum(
            ((a - b) / 180.0) ** 2
            for a, b in zip(left.cell_angles_deg, right.cell_angles_deg)
        )
        / 3.0
    )
    volume = abs(left.volume_per_atom - right.volume_per_atom) / max(
        left.volume_per_atom,
        right.volume_per_atom,
    )

    components = {
        "composition": composition,
        "cell_lengths": lengths,
        "cell_angles": angles,
        "volume_per_atom": volume,
    }
    total_weight = sum(selected.values())
    combined = sum(selected[key] * components[key] for key in selected) / total_weight
    return StructuralDistance(
        composition_distance=composition,
        lattice_length_distance=lengths,
        lattice_angle_distance=angles,
        volume_per_atom_distance=volume,
        combined_distance=combined,
    )
