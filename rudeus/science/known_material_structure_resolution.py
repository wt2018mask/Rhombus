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
                raise ValueError(
                    "unrepresentable resolution cannot claim executable artifacts"
                )
            if not self.scientific_blockers:
                raise ValueError(
                    "unrepresentable resolution requires explicit scientific blockers"
                )
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
    requested_artifact_keys: tuple[str, ...]
    retained_artifact_keys: tuple[str, ...]
    artifact_hashes: tuple[str, ...]
    missing_artifact_keys: tuple[str, ...]
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
        mode = ResolutionMode(self.mode)
        status = ResolutionStatus(self.status)

        requested = self.requested_artifact_keys
        retained = self.retained_artifact_keys
        missing = self.missing_artifact_keys
        if len(requested) != len(set(requested)):
            raise ValueError("resolved case contains duplicate requested artifacts")
        if len(retained) != len(set(retained)):
            raise ValueError("resolved case contains duplicate retained artifacts")
        if len(missing) != len(set(missing)):
            raise ValueError("resolved case contains duplicate missing artifacts")
        if len(retained) != len(self.artifact_hashes):
            raise ValueError("retained artifact hashes must align with retained keys")
        if set(retained) & set(missing):
            raise ValueError("artifact cannot be both retained and missing")
        if set(retained) | set(missing) != set(requested):
            raise ValueError("retained and missing artifacts must partition requested artifacts")
        for digest in self.artifact_hashes:
            require_hash(digest)

        if status == ResolutionStatus.READY:
            if (
                mode == ResolutionMode.UNREPRESENTABLE
                or not requested
                or missing
                or retained != requested
                or self.unresolved_requirements
                or self.scientific_blockers
            ):
                raise ValueError("ready structure case must be fully resolved")

        if status == ResolutionStatus.BLOCKED_MISSING_ARTIFACT:
            if mode == ResolutionMode.UNREPRESENTABLE or not missing:
                raise ValueError("missing-artifact status requires missing artifacts")

        if status == ResolutionStatus.BLOCKED_POLICY:
            if (
                mode == ResolutionMode.UNREPRESENTABLE
                or not requested
                or missing
                or retained != requested
                or not (self.unresolved_requirements or self.scientific_blockers)
            ):
                raise ValueError("policy-blocked case must have all artifacts and a blocker")

        if status == ResolutionStatus.UNREPRESENTABLE:
            if (
                mode != ResolutionMode.UNREPRESENTABLE
                or requested
                or retained
                or missing
                or self.artifact_hashes
                or not self.scientific_blockers
            ):
                raise ValueError(
                    "unrepresentable case must remain artifact-free and blocked"
                )


def resolve_structure_case(
    spec: StructureResolutionSpec,
    registry: ArtifactRegistry,
    retention_index: ArtifactRetentionIndex,
    *,
    satisfied_policy_inputs: tuple[str, ...] = (),
) -> ResolvedStructureCase:
    registry_by_key = {entry.artifact_key: entry for entry in registry.entries}
    receipts_by_key = {
        receipt.artifact_key: receipt for receipt in retention_index.receipts
    }

    if spec.mode == ResolutionMode.UNREPRESENTABLE.value:
        return ResolvedStructureCase(
            structure_resolution_version=STRUCTURE_RESOLUTION_VERSION,
            resolution_key=spec.resolution_key,
            material_key=spec.material_key,
            mode=spec.mode,
            status=ResolutionStatus.UNREPRESENTABLE.value,
            requested_artifact_keys=(),
            retained_artifact_keys=(),
            artifact_hashes=(),
            missing_artifact_keys=(),
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
        raise ValueError(
            "structure resolution cross-binds artifacts from another material"
        )

    retained_keys = tuple(
        key for key in spec.artifact_keys if key in receipts_by_key
    )
    missing_keys = tuple(
        key for key in spec.artifact_keys if key not in receipts_by_key
    )
    retained_hashes = tuple(
        receipts_by_key[key].artifact_sha256 for key in retained_keys
    )

    if missing_keys:
        return ResolvedStructureCase(
            structure_resolution_version=STRUCTURE_RESOLUTION_VERSION,
            resolution_key=spec.resolution_key,
            material_key=spec.material_key,
            mode=spec.mode,
            status=ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value,
            requested_artifact_keys=spec.artifact_keys,
            retained_artifact_keys=retained_keys,
            artifact_hashes=retained_hashes,
            missing_artifact_keys=missing_keys,
            phase_identity=spec.phase_identity,
            composition_identity=spec.composition_identity,
            representation_policy_id=spec.representation_policy_id,
            reference_conditions=spec.reference_conditions,
            unresolved_requirements=(),
            scientific_blockers=spec.scientific_blockers,
        )

    supplied = set(satisfied_policy_inputs)
    missing_policy = tuple(
        item for item in spec.required_policy_inputs if item not in supplied
    )
    blockers = tuple(spec.scientific_blockers)
    if missing_policy or blockers:
        return ResolvedStructureCase(
            structure_resolution_version=STRUCTURE_RESOLUTION_VERSION,
            resolution_key=spec.resolution_key,
            material_key=spec.material_key,
            mode=spec.mode,
            status=ResolutionStatus.BLOCKED_POLICY.value,
            requested_artifact_keys=spec.artifact_keys,
            retained_artifact_keys=retained_keys,
            artifact_hashes=retained_hashes,
            missing_artifact_keys=(),
            phase_identity=spec.phase_identity,
            composition_identity=spec.composition_identity,
            representation_policy_id=spec.representation_policy_id,
            reference_conditions=spec.reference_conditions,
            unresolved_requirements=missing_policy,
            scientific_blockers=blockers,
        )

    return ResolvedStructureCase(
        structure_resolution_version=STRUCTURE_RESOLUTION_VERSION,
        resolution_key=spec.resolution_key,
        material_key=spec.material_key,
        mode=spec.mode,
        status=ResolutionStatus.READY.value,
        requested_artifact_keys=spec.artifact_keys,
        retained_artifact_keys=retained_keys,
        artifact_hashes=retained_hashes,
        missing_artifact_keys=(),
        phase_identity=spec.phase_identity,
        composition_identity=spec.composition_identity,
        representation_policy_id=spec.representation_policy_id,
        reference_conditions=spec.reference_conditions,
    )
