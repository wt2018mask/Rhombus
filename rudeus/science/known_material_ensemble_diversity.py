"""Fail-closed diversity contract for fractional-occupancy realization ensembles."""
from __future__ import annotations

from dataclasses import dataclass

from rudeus.science.contracts import Record, require_hash


ENSEMBLE_DIVERSITY_VERSION = "known-material-ensemble-diversity-v1"


@dataclass(frozen=True, kw_only=True)
class EnsembleRealizationEvidence(Record):
    realization_hash: str
    site_assignment_hash: str
    generation_seed: int
    generator_version: str

    def validate(self):
        super().validate()
        require_hash(self.realization_hash)
        require_hash(self.site_assignment_hash)
        if self.generation_seed < 0:
            raise ValueError("generation seed must be non-negative")
        if not self.generator_version:
            raise ValueError("generator version is required")


@dataclass(frozen=True, kw_only=True)
class EnsembleDiversityEvidence(Record):
    evidence_version: str
    realizations: tuple[EnsembleRealizationEvidence, ...]
    source_structure_hash: str
    generation_policy_hash: str

    def validate(self):
        super().validate()
        if self.evidence_version != ENSEMBLE_DIVERSITY_VERSION:
            raise ValueError("unsupported ensemble diversity evidence version")
        require_hash(self.source_structure_hash)
        require_hash(self.generation_policy_hash)
        if len(self.realizations) < 2:
            raise ValueError("ensemble diversity requires at least two realizations")
        structure_hashes = tuple(x.realization_hash for x in self.realizations)
        assignment_hashes = tuple(x.site_assignment_hash for x in self.realizations)
        seeds = tuple(x.generation_seed for x in self.realizations)
        if len(set(structure_hashes)) != len(structure_hashes):
            raise ValueError("ensemble realization structures must be unique")
        if len(set(assignment_hashes)) != len(assignment_hashes):
            raise ValueError("ensemble site assignments must be unique")
        if len(set(seeds)) != len(seeds):
            raise ValueError("ensemble generation seeds must be unique")
