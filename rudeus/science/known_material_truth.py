"""Source-bound truth contracts for the blind known-material benchmark.

B1 defines how literature/reference evidence becomes immutable stage-specific
truth records. It selects no real material and assigns no DEV/HELD_OUT split.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from rudeus.science.contracts import Record, Verdict, require_hash
from rudeus.science.known_material_benchmark import (
    STAGES,
    TruthClass,
    TruthEvidenceClass,
)


TRUTH_RECORD_VERSION = "known-material-truth-record-v1"


class SourceKind(str, Enum):
    PEER_REVIEWED_ARTICLE = "PEER_REVIEWED_ARTICLE"
    PRIMARY_DATASET = "PRIMARY_DATASET"
    CURATED_DATABASE = "CURATED_DATABASE"
    REVIEW_OR_STANDARD = "REVIEW_OR_STANDARD"
    REFERENCE_COMPUTATION = "REFERENCE_COMPUTATION"


class EvidenceQuantityKind(str, Enum):
    CATEGORICAL = "CATEGORICAL"
    STRUCTURE = "STRUCTURE"
    ENERGETIC_STABILITY = "ENERGETIC_STABILITY"
    DYNAMIC_STABILITY = "DYNAMIC_STABILITY"
    SELF_DIFFUSION = "SELF_DIFFUSION"
    IONIC_CONDUCTIVITY = "IONIC_CONDUCTIVITY"
    ACTIVATION_ENERGY = "ACTIVATION_ENERGY"
    MODEL_AGREEMENT = "MODEL_AGREEMENT"
    NOVELTY_IDENTITY = "NOVELTY_IDENTITY"
    SYNTHESIS = "SYNTHESIS"
    APPLICATION = "APPLICATION"


class TruthDisposition(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, kw_only=True)
class ReferenceSource(Record):
    """Persistent bibliographic/data identity plus retained audit artifacts."""

    source_id: str
    source_kind: str
    locator: str
    citation: str
    version_or_date: str
    retained_artifact_hashes: tuple[str, ...]
    provenance_notes: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        SourceKind(self.source_kind)
        if not all((self.source_id, self.locator, self.citation, self.version_or_date)):
            raise ValueError("reference source identity is incomplete")
        if not self.retained_artifact_hashes:
            raise ValueError("source requires retained audit evidence")
        for value in self.retained_artifact_hashes:
            require_hash(value)


@dataclass(frozen=True, kw_only=True)
class EvidenceAtom(Record):
    """One source-bound scientific statement; publication count is not independence."""

    source_hash: str
    evidence_class: str
    evidence_family_id: str
    quantity_kind: str
    claim_dimension: str
    phase_identity: str
    species: tuple[str, ...]
    conditions: Mapping[str, Any]
    reported_value: Any
    units: str
    retained_artifact_hashes: tuple[str, ...]
    evidence_scope: str
    uncertainty: Mapping[str, Any] | None = None
    limitations: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        require_hash(self.source_hash)
        TruthEvidenceClass(self.evidence_class)
        EvidenceQuantityKind(self.quantity_kind)
        if not all((self.evidence_family_id, self.claim_dimension, self.phase_identity,
                    self.units, self.evidence_scope)):
            raise ValueError("evidence atom scope or lineage is incomplete")
        if not self.retained_artifact_hashes:
            raise ValueError("evidence atom requires retained evidence")
        for value in self.retained_artifact_hashes:
            require_hash(value)
        if any(not item for item in self.species):
            raise ValueError("species entries must be nonempty")


@dataclass(frozen=True, kw_only=True)
class ReferenceStructure(Record):
    """Exact phase/structure identity used by the benchmark, not a composition proxy."""

    material_identity: str
    composition: str
    phase_identity: str
    structure_hash: str
    structure_format: str
    source_evidence_hashes: tuple[str, ...]
    mobile_species: tuple[str, ...]
    chemistry_family: str
    reference_conditions: Mapping[str, Any] = field(default_factory=dict)

    def validate(self):
        super().validate()
        if not all((self.material_identity, self.composition, self.phase_identity,
                    self.structure_format, self.chemistry_family)):
            raise ValueError("reference structure identity is incomplete")
        require_hash(self.structure_hash)
        if not self.source_evidence_hashes:
            raise ValueError("reference structure requires source-bound evidence")
        for value in self.source_evidence_hashes:
            require_hash(value)
        if not self.mobile_species or any(not item for item in self.mobile_species):
            raise ValueError("reference structure requires explicit mobile species")


@dataclass(frozen=True, kw_only=True)
class StageTruthRecord(Record):
    """Stage-specific truth and what would count as falsification after unblinding."""

    stage: str
    material_reference_hash: str
    truth_statement: str
    truth_value: Any
    disposition: str
    scope: Mapping[str, Any]
    evidence_hashes: tuple[str, ...]
    required_quantity_kinds: tuple[str, ...]
    permitted_pipeline_verdicts: tuple[str, ...]
    falsifying_pipeline_verdicts: tuple[str, ...]
    scorable: bool
    reason_codes: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        if self.stage not in STAGES:
            raise ValueError("unknown truth-record stage")
        require_hash(self.material_reference_hash)
        TruthDisposition(self.disposition)
        if not self.truth_statement or not self.scope:
            raise ValueError("stage truth requires a scoped statement")
        kinds = tuple(EvidenceQuantityKind(v).value for v in self.required_quantity_kinds)
        if len(set(kinds)) != len(kinds):
            raise ValueError("duplicate required evidence quantity")
        permitted = tuple(Verdict(v).value for v in self.permitted_pipeline_verdicts)
        falsifying = tuple(Verdict(v).value for v in self.falsifying_pipeline_verdicts)
        if set(permitted) & set(falsifying):
            raise ValueError("pipeline verdict cannot be both permitted and falsifying")
        supported = self.disposition == TruthDisposition.SUPPORTED.value
        if supported:
            if self.scorable is not True or not self.evidence_hashes or not kinds:
                raise ValueError("supported truth must be source-bound and scorable")
            if not permitted or not falsifying:
                raise ValueError("scorable supported truth requires permitted and falsifying verdicts")
        else:
            if self.scorable is not False:
                raise ValueError("conflicting/insufficient/inapplicable truth is not scoreable")
            if self.falsifying_pipeline_verdicts:
                raise ValueError("unresolved truth cannot falsify pipeline behavior")
        for value in self.evidence_hashes:
            require_hash(value)


@dataclass(frozen=True, kw_only=True)
class KnownMaterialTruthBundle(Record):
    """Complete sealed truth bundle for one reference material before B3 splitting."""

    truth_record_version: str
    benchmark_protocol_hash: str
    benchmark_role: str
    reference: ReferenceStructure
    sources: tuple[ReferenceSource, ...]
    evidence: tuple[EvidenceAtom, ...]
    stage_truths: tuple[StageTruthRecord, ...]
    curation_state: str = "DRAFT"

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["reference"] = ReferenceStructure.from_dict(value["reference"])
        value["sources"] = tuple(ReferenceSource.from_dict(v) for v in value["sources"])
        value["evidence"] = tuple(EvidenceAtom.from_dict(v) for v in value["evidence"])
        value["stage_truths"] = tuple(StageTruthRecord.from_dict(v) for v in value["stage_truths"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.truth_record_version != TRUTH_RECORD_VERSION:
            raise ValueError("unsupported known-material truth record version")
        require_hash(self.benchmark_protocol_hash)
        TruthClass(self.benchmark_role)
        if not isinstance(self.reference, ReferenceStructure):
            raise ValueError("typed reference structure required")
        if self.curation_state not in ("DRAFT", "CURATED_FOR_B2"):
            raise ValueError("invalid truth-bundle curation state")
        if not self.sources or not self.evidence:
            raise ValueError("truth bundle requires source-bound evidence")

        source_map = {item.content_hash: item for item in self.sources}
        evidence_map = {item.content_hash: item for item in self.evidence}
        if len(source_map) != len(self.sources):
            raise ValueError("duplicate reference source")
        if len(evidence_map) != len(self.evidence):
            raise ValueError("duplicate evidence atom")
        if any(item.source_hash not in source_map for item in self.evidence):
            raise ValueError("evidence atom references a source outside the bundle")
        if any(value not in evidence_map for value in self.reference.source_evidence_hashes):
            raise ValueError("reference structure evidence is not retained in bundle")

        if tuple(item.stage for item in self.stage_truths) != STAGES:
            raise ValueError("truth bundle must explicitly account for every benchmark stage")
        if len({item.content_hash for item in self.stage_truths}) != len(self.stage_truths):
            raise ValueError("duplicate stage truth")
        for truth in self.stage_truths:
            if truth.material_reference_hash != self.reference.content_hash:
                raise ValueError("stage truth is bound to a different reference material")
            if any(value not in evidence_map for value in truth.evidence_hashes):
                raise ValueError("stage truth references evidence outside the bundle")
            if truth.disposition == TruthDisposition.SUPPORTED.value:
                available = {evidence_map[value].quantity_kind for value in truth.evidence_hashes}
                if not set(truth.required_quantity_kinds).issubset(available):
                    raise ValueError("stage truth lacks evidence of the required quantity kind")

        # Distinct publications derived from one underlying dataset remain one
        # evidence family for later independence accounting.
        if any(not atom.evidence_family_id for atom in self.evidence):
            raise ValueError("all evidence requires a lineage family")
