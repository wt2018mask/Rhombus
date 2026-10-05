"""B2 exact-structure binding ledger.

This layer separates "a paper reports a structure" from "Rhombus has a lawful,
phase-matched, retained and hashed executable structure artifact".  It remains
pre-B3 and grants no benchmark execution or production-search authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_benchmark import build_known_material_benchmark_protocol
from rudeus.science.known_material_truth import TRUTH_RECORD_VERSION
from rudeus.science.known_material_universe import UNIVERSE_VERSION


STRUCTURE_BINDING_VERSION = "known-material-structure-binding-v1"


class StructureArtifactState(str, Enum):
    SOURCE_IDENTIFIED = "SOURCE_IDENTIFIED"
    ARTIFACT_RETAINED = "ARTIFACT_RETAINED"
    HASHED_AND_VALIDATED = "HASHED_AND_VALIDATED"
    REJECTED = "REJECTED"


class StructureSourceKind(str, Enum):
    JOURNAL_SUPPLEMENT = "JOURNAL_SUPPLEMENT"
    PUBLIC_DOMAIN_DATABASE = "PUBLIC_DOMAIN_DATABASE"
    PRIMARY_DATA_REPOSITORY = "PRIMARY_DATA_REPOSITORY"
    CURATED_DATABASE = "CURATED_DATABASE"


class LicenseDisposition(str, Enum):
    VERIFIED_REDISTRIBUTABLE = "VERIFIED_REDISTRIBUTABLE"
    REMOTE_ONLY_UNVERIFIED = "REMOTE_ONLY_UNVERIFIED"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, kw_only=True)
class StructureArtifactBinding(Record):
    material_key: str
    phase_identity: str
    composition_identity: str
    source_id: str
    source_kind: str
    artifact_locator: str
    expected_format: str
    license_disposition: str
    artifact_state: str
    disorder_representation: str
    artifact_sha256: str | None = None
    retained_path: str | None = None
    blockers: tuple[str, ...] = ()
    provenance_notes: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        StructureSourceKind(self.source_kind)
        LicenseDisposition(self.license_disposition)
        StructureArtifactState(self.artifact_state)
        if not all((self.material_key, self.phase_identity, self.composition_identity,
                    self.source_id, self.artifact_locator, self.expected_format,
                    self.disorder_representation)):
            raise ValueError("structure binding identity incomplete")

        state = StructureArtifactState(self.artifact_state)
        if state == StructureArtifactState.HASHED_AND_VALIDATED:
            if self.artifact_sha256 is None or self.retained_path is None:
                raise ValueError("validated structure requires retained artifact and SHA256")
            require_hash(self.artifact_sha256)
            if self.license_disposition != LicenseDisposition.VERIFIED_REDISTRIBUTABLE.value:
                raise ValueError("repo-retained structure requires verified redistribution rights")
            if self.blockers:
                raise ValueError("validated structure cannot retain blockers")
        else:
            if self.artifact_sha256 is not None:
                require_hash(self.artifact_sha256)
            if self.retained_path is not None and state == StructureArtifactState.SOURCE_IDENTIFIED:
                raise ValueError("source-identified artifact cannot claim retained path")

        if self.license_disposition == LicenseDisposition.REMOTE_ONLY_UNVERIFIED.value:
            if self.retained_path is not None:
                raise ValueError("unverified remote artifact cannot be retained in repository")


@dataclass(frozen=True, kw_only=True)
class StructureBindingLedger(Record):
    structure_binding_version: str
    universe_version: str
    truth_record_version: str
    benchmark_protocol_hash: str
    entries: tuple[StructureArtifactBinding, ...]
    b2_structure_closure_authorized: bool = False
    dev_held_out_assignment_authorized: bool = False
    pipeline_execution_authorized: bool = False
    production_search_authorized: bool = False

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["entries"] = tuple(StructureArtifactBinding.from_dict(v) for v in value["entries"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.structure_binding_version != STRUCTURE_BINDING_VERSION:
            raise ValueError("unsupported structure-binding version")
        if self.universe_version != UNIVERSE_VERSION:
            raise ValueError("structure ledger must bind exact B2 universe version")
        if self.truth_record_version != TRUTH_RECORD_VERSION:
            raise ValueError("structure ledger must bind exact B1 truth-record version")
        expected_protocol = build_known_material_benchmark_protocol().content_hash
        if self.benchmark_protocol_hash != expected_protocol:
            raise ValueError("structure ledger must bind exact B0 protocol")
        keys = [entry.material_key for entry in self.entries]
        if not keys or len(keys) != len(set(keys)):
            raise ValueError("structure ledger requires unique material bindings")

        all_validated = all(
            entry.artifact_state == StructureArtifactState.HASHED_AND_VALIDATED.value
            for entry in self.entries
        )
        if self.b2_structure_closure_authorized != all_validated:
            raise ValueError("B2 structure closure flag must reflect every binding state")
        if any((self.dev_held_out_assignment_authorized,
                self.pipeline_execution_authorized,
                self.production_search_authorized)):
            raise ValueError("structure binding grants no split, execution, or production authorization")
