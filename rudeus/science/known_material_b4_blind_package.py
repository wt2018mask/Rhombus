"""Materialize B4 blind execution payloads without exposing sealed identity.

The caller supplies a validated B4 identity amendment from sealed external state.
Neither legacy material ids, truth-bundle hashes, nor any commitment over the small
legacy↔opaque permutation are emitted in the visible package.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_b3_split import B3SplitFreeze
from rudeus.science.known_material_b4_blinding_amendment import (
    B4BlindIdentityAmendment,
)
from rudeus.science.known_material_b4_execution_structure import (
    EXECUTION_STRUCTURE_BINDING_VERSION,
    ExecutionStructureBinding,
    ExecutionStructureComponent,
)
from rudeus.science.known_material_b4_ingress import (
    BLIND_INGRESS_VERSION,
    BlindBenchmarkIngress,
    VISIBLE_FIELDS,
)
from rudeus.science.known_material_structure_resolution import (
    ResolutionMode,
    ResolutionStatus,
    StructureResolutionLedger,
)


B4_BLIND_EXECUTION_PACKAGE_VERSION = "known-material-b4-blind-execution-package-v1"


@dataclass(frozen=True, kw_only=True)
class B4BlindExecutionPackage(Record):
    package_version: str
    ingresses: tuple[BlindBenchmarkIngress, ...]

    def validate(self):
        super().validate()
        if self.package_version != B4_BLIND_EXECUTION_PACKAGE_VERSION:
            raise ValueError("unsupported B4 blind execution package version")
        if not self.ingresses:
            raise ValueError("blind execution package requires ingress records")
        ids = tuple(item.benchmark_id for item in self.ingresses)
        if len(ids) != len(set(ids)):
            raise ValueError("blind execution package requires unique opaque ids")
        if ids != tuple(sorted(ids)):
            raise ValueError("blind execution package must be sorted by opaque id")

    @property
    def execution_payloads(self) -> tuple[Mapping[str, str], ...]:
        payloads = tuple(item.execution_payload for item in self.ingresses)
        if any(tuple(payload) != VISIBLE_FIELDS for payload in payloads):
            raise ValueError("blind package payload schema drift")
        return payloads


def _phase_set_visible_hash(case) -> str:
    mapping = case.reference_conditions.get("phase_condition_mapping")
    if not isinstance(mapping, Mapping):
        raise ValueError("PHASE_SET case requires phase-condition mapping")

    hash_by_key = dict(zip(case.retained_artifact_keys, case.artifact_hashes))
    components = []
    for label in sorted(mapping):
        value = mapping[label]
        if not isinstance(value, Mapping):
            raise ValueError("phase-condition mapping entry must be a mapping")
        artifact_key = str(value.get("artifact_key"))
        try:
            artifact_hash = hash_by_key[artifact_key]
        except KeyError as exc:
            raise ValueError("phase-set component is not retained") from exc
        components.append(
            ExecutionStructureComponent(
                label=str(label),
                structure_hash=artifact_hash,
            )
        )
    return ExecutionStructureBinding(
        binding_version=EXECUTION_STRUCTURE_BINDING_VERSION,
        mode=ResolutionMode.PHASE_SET.value,
        components=tuple(components),
    ).visible_structure_hash


def _ensemble_visible_hash(case) -> str:
    execution = case.reference_conditions.get("ensemble_execution")
    if not isinstance(execution, Mapping):
        raise ValueError("ENSEMBLE case requires ensemble_execution metadata")
    value = str(execution.get("execution_structure_hash", ""))
    require_hash(value)
    return value


def visible_structure_hash(case) -> str:
    if case.status != ResolutionStatus.READY.value:
        raise ValueError("blind package requires READY structure cases")
    mode = ResolutionMode(case.mode)
    if mode == ResolutionMode.DIRECT:
        if len(case.artifact_hashes) != 1:
            raise ValueError("DIRECT case requires one retained structure hash")
        return case.artifact_hashes[0]
    if mode == ResolutionMode.PHASE_SET:
        return _phase_set_visible_hash(case)
    if mode == ResolutionMode.ENSEMBLE:
        return _ensemble_visible_hash(case)
    raise ValueError("UNREPRESENTABLE case cannot enter blind execution")


def build_b4_blind_execution_package(
    split_freeze: B3SplitFreeze,
    amendment: B4BlindIdentityAmendment,
    structure_ledger: StructureResolutionLedger,
) -> B4BlindExecutionPackage:
    if amendment.split_freeze_hash != split_freeze.content_hash:
        raise ValueError("blind identity amendment does not bind this B3 split")

    frozen_by_id = {member.benchmark_id: member for member in split_freeze.members}
    case_by_material = {case.material_key: case for case in structure_ledger.cases}
    bindings_by_legacy = {
        binding.legacy_benchmark_id: binding for binding in amendment.bindings
    }
    if set(bindings_by_legacy) != set(frozen_by_id):
        raise ValueError("blind amendment membership differs from frozen B3 membership")

    ingresses = []
    for legacy_id, frozen in frozen_by_id.items():
        binding = bindings_by_legacy[legacy_id]
        if binding.split != frozen.split:
            raise ValueError("blind amendment changes frozen split membership")
        if binding.truth_bundle_hash != frozen.truth_bundle_hash:
            raise ValueError("blind amendment changes frozen truth-bundle binding")
        try:
            case = case_by_material[legacy_id]
        except KeyError as exc:
            raise ValueError("frozen member lacks structure-resolution case") from exc

        ingresses.append(
            BlindBenchmarkIngress(
                ingress_version=BLIND_INGRESS_VERSION,
                benchmark_id=binding.opaque_benchmark_id,
                split=frozen.split,
                structure_hash=visible_structure_hash(case),
                benchmark_protocol_hash=amendment.benchmark_protocol_hash,
            )
        )

    package = B4BlindExecutionPackage(
        package_version=B4_BLIND_EXECUTION_PACKAGE_VERSION,
        ingresses=tuple(sorted(ingresses, key=lambda item: item.benchmark_id)),
    )
    package.validate()
    return package
