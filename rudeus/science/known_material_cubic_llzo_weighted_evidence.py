"""Source-bound evidence bundle for the exact-weighted cubic Al-LLZO ensemble."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_cubic_llzo_weighted_ordered import (
    build_weighted_cubic_llzo_ordered_structures,
)
from rudeus.science.known_material_cubic_llzo_weighted_plan import (
    WEIGHTING_ASSUMPTION,
)


CUBIC_LLZO_WEIGHTED_EVIDENCE_VERSION = (
    "known-material-cubic-llzo-weighted-representation-evidence-v1"
)
CORRELATION_SCOPE = "MARGINAL_OCCUPANCIES_ONLY_SOURCE_DOES_NOT_RESOLVE_CORRELATIONS"


@dataclass(frozen=True, kw_only=True)
class WeightedRealizationBinding(Record):
    member_index: int
    weight_numerator: int
    weight_denominator: int
    assignment_hash: str
    structure_hash: str

    @property
    def weight(self) -> Fraction:
        return Fraction(self.weight_numerator, self.weight_denominator)

    def validate(self):
        super().validate()
        if self.member_index < 0 or self.weight_numerator <= 0 or self.weight_denominator <= 0:
            raise ValueError("invalid weighted realization identity")
        require_hash(self.assignment_hash)
        require_hash(self.structure_hash)


@dataclass(frozen=True, kw_only=True)
class CubicLlzoWeightedRepresentationEvidence(Record):
    evidence_version: str
    source_artifact_hash: str
    weighting_assumption: str
    correlation_scope: str
    declared_li1_occupancy: str
    declared_al1_occupancy: str
    declared_li2_occupancy: str
    weighted_li_formula: str
    weighted_al_formula: str
    reported_li_formula: str
    reported_al_formula: str
    bindings: tuple[WeightedRealizationBinding, ...]

    def validate(self):
        super().validate()
        if self.evidence_version != CUBIC_LLZO_WEIGHTED_EVIDENCE_VERSION:
            raise ValueError("unsupported weighted representation evidence version")
        require_hash(self.source_artifact_hash)
        if self.weighting_assumption != WEIGHTING_ASSUMPTION:
            raise ValueError("unexpected weighted ensemble assumption")
        if self.correlation_scope != CORRELATION_SCOPE:
            raise ValueError("weighted evidence must preserve correlation-scope caveat")
        if len(self.bindings) != 8:
            raise ValueError("weighted evidence requires eight realizations")
        if tuple(item.member_index for item in self.bindings) != tuple(range(8)):
            raise ValueError("weighted realization member indices must be canonical")
        if sum((item.weight for item in self.bindings), Fraction(0, 1)) != 1:
            raise ValueError("weighted realization weights must sum exactly to one")
        if len({item.assignment_hash for item in self.bindings}) != 8:
            raise ValueError("weighted evidence requires unique assignment hashes")
        if len({item.structure_hash for item in self.bindings}) != 8:
            raise ValueError("weighted evidence requires unique structure hashes")
        if (
            self.declared_li1_occupancy,
            self.declared_al1_occupancy,
            self.declared_li2_occupancy,
        ) != ("0.54", "0.06530", "0.37"):
            raise ValueError("weighted evidence must bind the retained refined occupancies")
        if self.weighted_li_formula != "6.06":
            raise ValueError("weighted ensemble must preserve Li6.06 exactly")
        if self.weighted_al_formula != "0.1959":
            raise ValueError("weighted ensemble must preserve the occupancy-derived Al formula")
        if self.reported_li_formula != "6.060" or self.reported_al_formula != "0.196":
            raise ValueError("weighted evidence must retain the reported formula identity")


def build_cubic_llzo_weighted_representation_evidence(
    cif_path: Path,
    *,
    source_artifact_hash: str,
) -> CubicLlzoWeightedRepresentationEvidence:
    require_hash(source_artifact_hash)
    members = build_weighted_cubic_llzo_ordered_structures(cif_path)
    bindings = tuple(
        WeightedRealizationBinding(
            member_index=item.member_index,
            weight_numerator=item.weight_numerator,
            weight_denominator=item.weight_denominator,
            assignment_hash=item.assignment_hash,
            structure_hash=item.structure_hash,
        )
        for item in members
    )
    return CubicLlzoWeightedRepresentationEvidence(
        evidence_version=CUBIC_LLZO_WEIGHTED_EVIDENCE_VERSION,
        source_artifact_hash=source_artifact_hash,
        weighting_assumption=WEIGHTING_ASSUMPTION,
        correlation_scope=CORRELATION_SCOPE,
        declared_li1_occupancy="0.54",
        declared_al1_occupancy="0.06530",
        declared_li2_occupancy="0.37",
        weighted_li_formula="6.06",
        weighted_al_formula="0.1959",
        reported_li_formula="6.060",
        reported_al_formula="0.196",
        bindings=bindings,
    )
