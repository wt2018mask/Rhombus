"""Generic scientific binding resolution contract for B2 known-material controls.

This layer maps mechanically retained artifacts into scientifically scoped reference
cases. It is data-driven and supports one-to-one structures, phase-resolved sets,
disorder ensembles, and explicitly unrepresentable controls without material-specific
production code.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_artifact_curation import (
    ArtifactRetentionIndex,
    ArtifactRegistry,
)


STRUCTURE_RESOLUTION_VERSION = "known-material-structure-resolution-v1"


class ResolutionMode(str, Enum):
    DIRECT = "DIRECT"
    PHASE_SET = "PHASE_SET"
    ENSEMBLE = "ENSEMBLE"
    UNREPRESENTABLE = "UNREPRESENTABLE"


class ResolutionStatus(str, Enum):
    READY = "READY"
    BLOCKED_MISSING_ARTIFACT = "BLOCKED_MISSING_ARTIFACT"
    BLOCKED_POLICY = "BLOCKED_POLICY"
    UNREPRESENTABLE = "UNREPRESENTABLE"


@dataclass(frozen=True, kw_only=True)
class StructureResolutionSpec(Record):
    resolution_key: str
    material_key: str
    chemistry_family: str
    mode: str
    artifact_keys: tuple[str, ...]
    phase_identity: str
    composition_identity: str
    representation_policy_id: str
    reference_conditions: Mapping[str, Any]
    required_policy_inputs: tuple[str, ...] = ()
    scientific_blockers: tuple[str, ...] = ()
    rationale: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        mode = ResolutionMode(self.mode)
        if not all((
            self.resolution_key,
            self.material_key,
            self.chemistry_family,
            self.phase_identity,
            self.composition_identity,
            self.representation_policy_id,
        )):
            raise ValueError("structure resolution identity is incomplete")
        if len(self.artifact_keys) != len(set(self.artifact_keys)):
            raise ValueError("structure resolution contains duplicate artifact keys")
        if mode == ResolutionMode.UNREPRESENTABLE:
            if self.artifact_keys:
                raise ValueError("unrepresentable resolution cannot claim executable artifacts")
            if not self.scientific_blockers:
                raise ValueError("unrepresentable resolution requires explicit scientific blockers")
        elif not self.artifact_keys:
            raise ValueError("representable resolution requires at least one artifact")
        if mode == ResolutionMode.DIRECT and len(self.artifact_keys) != 1:
            raise ValueError("direct resolution requires exactly one artifact")


@dataclass(frozen=True, kw_only=True)
class StructureResolutionManifest(Record):
    structure_resolution_version: str
    specs: tuple[StructureResolutionSpec, ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["specs"] = tuple(
            StructureResolutionSpec.from_dict(item) for item in value["specs"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.structure_resolution_version != STRUCTURE_RESOLUTION_VERSION:
            raise ValueError("unsupported structure-resolution version")
        keys = [spec.resolution_key for spec in self.specs]
        if not keys or len(keys) != len(set(keys)):
            raise ValueError("structure resolution requires unique resolution keys")


@dataclass(frozen=True, kw_only=True)
class ResolvedStructureCase(Record):
    structure_resolution_version: str
    resolution_key: str
    material_key: str
    mode: str
    status: str
    artifact_keys: tuple[str, ...]
    artifact_hashes: tuple[str, ...]
    phase_identity: str
    composition_identity: str
    representation_policy_id: str
    reference_conditions: Mapping[str, Any]
    unresolved_requirements: tuple[str, ...] = ()
    scientific_blockers: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        if self.structure_resolution_version != STRUCTURE_RESOLUTION_VERSION:
            raise ValueError("unsupported structure-resolution version")
        ResolutionMode(self.mode)
        status = ResolutionStatus(self.status)
        if len(self.artifact_keys) != len(self.artifact_hashes):
            raise ValueError("resolved case artifact hashes must align with artifact keys")
        for digest in self.artifact_hashes:
            require_hash(digest)
        if status == ResolutionStatus.READY:
            if not self.artifact_keys or self.unresolved_requirements or self.scientific_blockers:
                raise ValueError("ready structure case cannot retain unresolved requirements")
        if status == ResolutionStatus.UNREPRESENTABLE:
            if self.artifact_keys or not self.scientific_blockers:
                raise ValueError("unrepresentable case must remain artifact-free and blocked")


def resolve_structure_case(
    spec: StructureResolutionSpec,
    registry: ArtifactRegistry,
    retention_index: ArtifactRetentionIndex,
    *,
    satisfied_policy_inputs: tuple[str, ...] = (),
) -> ResolvedStructureCase:
    registry_by_key = {entry.artifact_key: entry for entry in registry.entries}
    receipts_by_key = {receipt.artifact_key: receipt for receipt in retention_index.receipts}

    if spec.mode == ResolutionMode.UNREPRESENTABLE.value:
        return ResolvedStructureCase(
            structure_resolution_version=STRUCTURE_RESOLUTION_VERSION,
            resolution_key=spec.resolution_key,
            material_key=spec.material_key,
            mode=spec.mode,
            status=ResolutionStatus.UNREPRESENTABLE.value,
            artifact_keys=(),
            artifact_hashes=(),
            phase_identity=spec.phase_identity,
            composition_identity=spec.composition_identity,
            representation_policy_id=spec.representation_policy_id,
            reference_conditions=spec.reference_conditions,
            unresolved_requirements=(),
            scientific_blockers=spec.scientific_blockers,
        )

    unknown = tuple(key for key in spec.artifact_keys if key not in registry_by_key)
    if unknown:
        raise ValueError(
            "structure resolution references artifacts outside registry: "
            + ", ".join(unknown)
        )

    wrong_material = tuple(
        key
        for key in spec.artifact_keys
        if registry_by_key[key].material_key != spec.material_key
    )
    if wrong_material:
        raise ValueError("structure resolution cross-binds artifacts from another material")

    missing = tuple(key for key in spec.artifact_keys if key not in receipts_by_key)
    if missing:
        return ResolvedStructureCase(
            structure_resolution_version=STRUCTURE_RESOLUTION_VERSION,
            resolution_key=spec.resolution_key,
            material_key=spec.material_key,
            mode=spec.mode,
            status=ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value,
            artifact_keys=spec.artifact_keys,
            artifact_hashes=tuple(
                receipts_by_key[key].artifact_sha256
                for key in spec.artifact_keys
                if key in receipts_by_key
            ),
            phase_identity=spec.phase_identity,
            composition_identity=spec.composition_identity,
            representation_policy_id=spec.representation_policy_id,
            reference_conditions=spec.reference_conditions,
            unresolved_requirements=missing,
            scientific_blockers=spec.scientific_blockers,
        )

    supplied = set(satisfied_policy_inputs)
    missing_policy = tuple(
        item for item in spec.required_policy_inputs if item not in supplied
    )
    blockers = tuple(spec.scientific_blockers)
    if missing_policy or blockers:
        unresolved = tuple(missing_policy)
        return ResolvedStructureCase(
            structure_resolution_version=STRUCTURE_RESOLUTION_VERSION,
            resolution_key=spec.resolution_key,
            material_key=spec.material_key,
            mode=spec.mode,
            status=ResolutionStatus.BLOCKED_POLICY.value,
            artifact_keys=spec.artifact_keys,
            artifact_hashes=tuple(
                receipts_by_key[key].artifact_sha256 for key in spec.artifact_keys
            ),
            phase_identity=spec.phase_identity,
            composition_identity=spec.composition_identity,
            representation_policy_id=spec.representation_policy_id,
            reference_conditions=spec.reference_conditions,
            unresolved_requirements=unresolved,
            scientific_blockers=blockers,
        )

    return ResolvedStructureCase(
        structure_resolution_version=STRUCTURE_RESOLUTION_VERSION,
        resolution_key=spec.resolution_key,
        material_key=spec.material_key,
        mode=spec.mode,
        status=ResolutionStatus.READY.value,
        artifact_keys=spec.artifact_keys,
        artifact_hashes=tuple(
            receipts_by_key[key].artifact_sha256 for key in spec.artifact_keys
        ),
        phase_identity=spec.phase_identity,
        composition_identity=spec.composition_identity,
        representation_policy_id=spec.representation_policy_id,
        reference_conditions=spec.reference_conditions,
    )
