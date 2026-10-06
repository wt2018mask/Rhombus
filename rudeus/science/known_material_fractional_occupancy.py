"""Fail-closed contract for fractional-occupancy execution strategies.

This contract records what evidence must exist before a disordered crystallographic
average can be converted into executable atomistic realizations.  It deliberately
does not generate configurations or declare any benchmark member READY.
"""
from __future__ import annotations

from dataclasses import dataclass

from rudeus.science.contracts import Record, require_hash


FRACTIONAL_OCCUPANCY_STRATEGY_VERSION = (
    "known-material-fractional-occupancy-strategy-v1"
)


@dataclass(frozen=True, kw_only=True)
class FractionalOccupancyExecutionStrategy(Record):
    strategy_version: str
    source_artifact_hash: str
    realization_hashes: tuple[str, ...]
    realization_weights: tuple[float, ...]
    composition_preserved: bool
    occupancy_statistics_preserved: bool
    deterministic_generation: bool
    generation_method: str
    provenance_refs: tuple[str, ...]
    bias_assessment: tuple[str, ...]

    def validate(self):
        super().validate()
        if self.strategy_version != FRACTIONAL_OCCUPANCY_STRATEGY_VERSION:
            raise ValueError("unsupported fractional-occupancy strategy version")
        require_hash(self.source_artifact_hash)
        if len(self.realization_hashes) < 2:
            raise ValueError("fractional occupancy requires multiple realizations")
        if len(self.realization_hashes) != len(set(self.realization_hashes)):
            raise ValueError("fractional occupancy realizations must be distinct")
        for digest in self.realization_hashes:
            require_hash(digest)
        if len(self.realization_weights) != len(self.realization_hashes):
            raise ValueError("realization weights must align with realizations")
        if any(weight <= 0 for weight in self.realization_weights):
            raise ValueError("realization weights must be positive")
        if abs(sum(self.realization_weights) - 1.0) > 1e-9:
            raise ValueError("realization weights must sum to one")
        if not self.composition_preserved:
            raise ValueError("strategy must preserve benchmark composition")
        if not self.occupancy_statistics_preserved:
            raise ValueError("strategy must preserve declared occupancy statistics")
        if not self.deterministic_generation:
            raise ValueError("strategy generation must be reproducible")
        if not self.generation_method or not self.provenance_refs:
            raise ValueError("strategy requires generation provenance")
        if not self.bias_assessment:
            raise ValueError("strategy requires explicit representation-bias assessment")
