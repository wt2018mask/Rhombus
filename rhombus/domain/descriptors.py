"""Low-cost Rhombus 2.0 domain descriptor primitives.

Phase 3 starts with descriptors that can be computed without learned models or
new scientific execution. These descriptors are evidence inputs, not sufficient
by themselves for strong IN_DOMAIN claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CompositionDescriptor:
    element_counts: tuple[tuple[int, int], ...]
    total_atoms: int
    element_count: int
    atomic_number_min: int
    atomic_number_max: int

    @classmethod
    def from_atomic_numbers(
        cls, atomic_numbers: list[int] | tuple[int, ...]
    ) -> "CompositionDescriptor":
        if not atomic_numbers:
            raise ValueError("atomic_numbers must be non-empty")
        if any((not isinstance(z, int)) or z < 1 or z > 118 for z in atomic_numbers):
            raise ValueError("atomic_numbers must contain integers in [1, 118]")

        counts: dict[int, int] = {}
        for z in atomic_numbers:
            counts[z] = counts.get(z, 0) + 1
        ordered = tuple(sorted(counts.items()))
        return cls(
            element_counts=ordered,
            total_atoms=len(atomic_numbers),
            element_count=len(ordered),
            atomic_number_min=min(counts),
            atomic_number_max=max(counts),
        )

    @classmethod
    def from_count_mapping(cls, counts: Mapping[int, int]) -> "CompositionDescriptor":
        if not counts:
            raise ValueError("counts must be non-empty")
        expanded: list[int] = []
        for atomic_number, count in counts.items():
            if not isinstance(atomic_number, int) or not isinstance(count, int):
                raise ValueError("counts must map integer atomic numbers to integers")
            if atomic_number < 1 or atomic_number > 118 or count <= 0:
                raise ValueError("atomic numbers must be in [1, 118] and counts positive")
            expanded.extend([atomic_number] * count)
        return cls.from_atomic_numbers(expanded)

    @property
    def atomic_numbers(self) -> tuple[int, ...]:
        return tuple(z for z, _ in self.element_counts)

    def fractions(self) -> tuple[tuple[int, float], ...]:
        return tuple(
            (z, count / self.total_atoms) for z, count in self.element_counts
        )
