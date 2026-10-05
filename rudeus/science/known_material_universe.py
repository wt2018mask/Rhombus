"""B2 literature-grounded material-universe intake.

B2 records which real materials/phase contexts merit full truth-bundle curation.
It does not assign DEV/HELD_OUT membership, create benchmark IDs, or qualify
Rhombus. Entries remain non-executable until exact structures and B1 truth
bundles are completed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rudeus.science.contracts import Record
from rudeus.science.known_material_benchmark import TruthClass


UNIVERSE_VERSION = "known-material-universe-intake-v1"


class CurationState(str, Enum):
    SOURCE_SCREENED = "SOURCE_SCREENED"
    STRUCTURE_BINDING_REQUIRED = "STRUCTURE_BINDING_REQUIRED"
    TRUTH_BUNDLE_READY = "TRUTH_BUNDLE_READY"


@dataclass(frozen=True, kw_only=True)
class LiteratureSourceStub(Record):
    source_id: str
    locator: str
    title: str
    publication_year: int
    evidence_dimensions: tuple[str, ...]

    def validate(self):
        super().validate()
        if not all((self.source_id, self.locator, self.title)):
            raise ValueError("source stub identity incomplete")
        if self.publication_year < 1900 or self.publication_year > 2100:
            raise ValueError("publication year out of supported range")
        if not self.evidence_dimensions or any(not value for value in self.evidence_dimensions):
            raise ValueError("source stub requires scoped evidence dimensions")


@dataclass(frozen=True, kw_only=True)
class UniverseEntry(Record):
    material_key: str
    material_name: str
    nominal_composition: str
    phase_context: str
    chemistry_family: str
    mobile_species: tuple[str, ...]
    proposed_role: str
    rationale: tuple[str, ...]
    literature_sources: tuple[LiteratureSourceStub, ...]
    curation_state: str
    blockers: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["literature_sources"] = tuple(
            LiteratureSourceStub.from_dict(v) for v in value["literature_sources"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        TruthClass(self.proposed_role)
        CurationState(self.curation_state)
        if not all((self.material_key, self.material_name, self.nominal_composition,
                    self.phase_context, self.chemistry_family)):
            raise ValueError("material-universe identity incomplete")
        if not self.mobile_species or any(not value for value in self.mobile_species):
            raise ValueError("explicit mobile species required")
        if not self.rationale or not self.literature_sources:
            raise ValueError("literature-grounded rationale required")
        source_ids = [item.source_id for item in self.literature_sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("duplicate literature source stub")
        if self.curation_state == CurationState.TRUTH_BUNDLE_READY.value and self.blockers:
            raise ValueError("truth-bundle-ready entry cannot retain blockers")


@dataclass(frozen=True, kw_only=True)
class MaterialUniverseIntake(Record):
    universe_version: str
    benchmark_protocol_hash: str
    truth_record_version: str
    scope: str
    selection_principles: tuple[str, ...]
    entries: tuple[UniverseEntry, ...]
    dev_held_out_assignment_authorized: bool = False
    numeric_qualification_thresholds_authorized: bool = False
    pipeline_execution_authorized: bool = False
    production_search_authorized: bool = False

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["entries"] = tuple(UniverseEntry.from_dict(v) for v in value["entries"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.universe_version != UNIVERSE_VERSION:
            raise ValueError("unsupported material-universe version")
        if not self.benchmark_protocol_hash or len(self.benchmark_protocol_hash) != 64:
            raise ValueError("benchmark protocol hash must be a full SHA256")
        if not self.truth_record_version or not self.scope:
            raise ValueError("universe scope is incomplete")
        if not self.selection_principles or not self.entries:
            raise ValueError("universe requires selection principles and entries")
        keys = [item.material_key for item in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate material key")
        families = {item.chemistry_family for item in self.entries}
        roles = {item.proposed_role for item in self.entries}
        if len(families) < 4:
            raise ValueError("B2 intake must span multiple chemistry families")
        if TruthClass.POSITIVE.value not in roles or TruthClass.NEGATIVE.value not in roles:
            raise ValueError("B2 intake requires both positive and negative controls")
        if any((self.dev_held_out_assignment_authorized,
                self.numeric_qualification_thresholds_authorized,
                self.pipeline_execution_authorized,
                self.production_search_authorized)):
            raise ValueError("B2 intake grants no split, threshold, execution, or production authorization")
