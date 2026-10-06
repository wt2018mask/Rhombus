"""Representation-aware structure units for B5 DEV diagnostic execution.

This expands each canonical DEV material into concrete structure units without
running any scientific stage. DIRECT uses one retained artifact, PHASE_SET uses
each retained phase artifact, and the current ENSEMBLE case is regenerated from
its source-bound deterministic cubic Al-LLZO policy evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_artifact_curation import (
    ArtifactRegistry,
    ArtifactRetentionIndex,
)
from rudeus.science.known_material_b4_blind_package import visible_structure_hash
from rudeus.science.known_material_cubic_llzo_policy_evidence import (
    GENERATION_METHOD,
    build_cubic_llzo_fractional_occupancy_policy_evidence,
)
from rudeus.science.known_material_b5_dev_plan import B5DevDiagnosticPlan
from rudeus.science.known_material_structure_resolution import (
    ResolutionMode,
    StructureResolutionLedger,
)


B5_DEV_STRUCTURE_UNIT_VERSION = "known-material-b5-dev-structure-unit-v1"
B5_DEV_STRUCTURE_UNIT_PLAN_VERSION = "known-material-b5-dev-structure-unit-plan-v1"
RETAINED_ARTIFACT = "RETAINED_ARTIFACT"
DETERMINISTIC_GENERATOR = "DETERMINISTIC_GENERATOR"
STRUCTURE_ROOT = Path("data/benchmarks/known_material/structures")


@dataclass(frozen=True, kw_only=True)
class B5DevStructureUnit(Record):
    unit_version: str
    material_key: str
    split: str
    material_structure_hash: str
    representation_mode: str
    component_label: str
    unit_structure_hash: str
    materialization_kind: str
    source_artifact_key: str
    source_path: str
    condition_scope: Mapping[str, Any]
    generator_id: str | None = None
    weight_numerator: int | None = None
    weight_denominator: int | None = None

    def validate(self):
        super().validate()
        if self.unit_version != B5_DEV_STRUCTURE_UNIT_VERSION:
            raise ValueError("unsupported B5 DEV structure-unit version")
        if not self.material_key or not self.component_label:
            raise ValueError("B5 DEV structure unit identity is incomplete")
        if self.split != "DEV":
            raise ValueError("B5 DEV structure units may contain DEV only")
        require_hash(self.material_structure_hash)
        require_hash(self.unit_structure_hash)
        mode = ResolutionMode(self.representation_mode)
        if mode == ResolutionMode.UNREPRESENTABLE:
            raise ValueError("unrepresentable structure cannot enter B5 DEV")
        if not self.source_artifact_key or not self.source_path:
            raise ValueError("B5 DEV structure unit requires source artifact binding")
        source_path = Path(self.source_path)
        if (
            source_path.is_absolute()
            or ".." in source_path.parts
            or not source_path.is_relative_to(STRUCTURE_ROOT)
        ):
            raise ValueError("B5 DEV source path escapes retained structure root")

        weighted = self.weight_numerator is not None or self.weight_denominator is not None
        if (self.weight_numerator is None) != (self.weight_denominator is None):
            raise ValueError("B5 DEV unit weight requires numerator and denominator")
        if weighted:
            if mode != ResolutionMode.ENSEMBLE:
                raise ValueError("only ENSEMBLE units may carry weights")
            if self.weight_numerator <= 0 or self.weight_denominator <= 0:
                raise ValueError("B5 DEV ENSEMBLE weights must be positive")

        if self.materialization_kind == RETAINED_ARTIFACT:
            if self.generator_id is not None:
                raise ValueError("retained artifact unit cannot declare generator")
            if mode == ResolutionMode.ENSEMBLE:
                raise ValueError("current ENSEMBLE units must use deterministic generator")
        elif self.materialization_kind == DETERMINISTIC_GENERATOR:
            if mode != ResolutionMode.ENSEMBLE or not self.generator_id:
                raise ValueError("generated B5 DEV units require ENSEMBLE generator")
        else:
            raise ValueError("unsupported B5 DEV materialization kind")

        if mode == ResolutionMode.DIRECT:
            if self.material_structure_hash != self.unit_structure_hash:
                raise ValueError("DIRECT unit hash must equal material structure hash")
            if weighted:
                raise ValueError("DIRECT unit cannot carry weight")


@dataclass(frozen=True, kw_only=True)
class B5DevStructureUnitPlan(Record):
    plan_version: str
    dev_diagnostic_plan_hash: str
    units: tuple[B5DevStructureUnit, ...]
    diagnostic_only: bool
    qualification_evidence_authorized: bool = False
    held_out_execution_authorized: bool = False
    production_search_authorized: bool = False

    def validate(self):
        super().validate()
        if self.plan_version != B5_DEV_STRUCTURE_UNIT_PLAN_VERSION:
            raise ValueError("unsupported B5 DEV structure-unit plan version")
        require_hash(self.dev_diagnostic_plan_hash)
        if not self.units:
            raise ValueError("B5 DEV structure-unit plan requires units")
        ordering = tuple(
            (unit.material_key, unit.component_label)
            for unit in self.units
        )
        if ordering != tuple(sorted(ordering)):
            raise ValueError("B5 DEV structure units must be canonically sorted")
        if len(ordering) != len(set(ordering)):
            raise ValueError("B5 DEV structure-unit identities must be unique")
        if any(unit.split != "DEV" for unit in self.units):
            raise ValueError("B5 DEV structure-unit plan may contain DEV only")
        if self.diagnostic_only is not True:
            raise ValueError("B5 DEV structure-unit plan is diagnostic only")
        if any(
            (
                self.qualification_evidence_authorized,
                self.held_out_execution_authorized,
                self.production_search_authorized,
            )
        ):
            raise ValueError("B5 DEV structure units authorize no qualification or production")


def _artifact_binding(
    *,
    artifact_key: str,
    expected_hash: str,
    registry_by_key,
    receipt_by_key,
):
    try:
        entry = registry_by_key[artifact_key]
        receipt = receipt_by_key[artifact_key]
    except KeyError as exc:
        raise ValueError("B5 DEV structure unit lacks retained artifact provenance") from exc
    if entry.retained_path != receipt.retained_path:
        raise ValueError("B5 DEV registry and receipt paths disagree")
    if receipt.artifact_sha256 != expected_hash:
        raise ValueError("B5 DEV retained artifact hash differs from structure ledger")
    return entry


def _retained_unit(
    *,
    material_key: str,
    material_structure_hash: str,
    mode: str,
    label: str,
    artifact_key: str,
    artifact_hash: str,
    condition_scope: Mapping[str, Any],
    registry_by_key,
    receipt_by_key,
) -> B5DevStructureUnit:
    entry = _artifact_binding(
        artifact_key=artifact_key,
        expected_hash=artifact_hash,
        registry_by_key=registry_by_key,
        receipt_by_key=receipt_by_key,
    )
    return B5DevStructureUnit(
        unit_version=B5_DEV_STRUCTURE_UNIT_VERSION,
        material_key=material_key,
        split="DEV",
        material_structure_hash=material_structure_hash,
        representation_mode=mode,
        component_label=label,
        unit_structure_hash=artifact_hash,
        materialization_kind=RETAINED_ARTIFACT,
        source_artifact_key=artifact_key,
        source_path=entry.retained_path,
        condition_scope=condition_scope,
    )


def _expand_ensemble(
    *,
    repo_root: Path,
    material_key: str,
    material_structure_hash: str,
    case,
    registry_by_key,
    receipt_by_key,
) -> tuple[B5DevStructureUnit, ...]:
    if (
        material_key != "llzo-cubic-al-stabilized"
        or case.representation_policy_id != "fractional-occupancy-explicit-v1"
        or len(case.retained_artifact_keys) != 1
        or len(case.artifact_hashes) != 1
    ):
        raise ValueError("B5 DEV has no execution adapter for this ENSEMBLE representation")

    artifact_key = case.retained_artifact_keys[0]
    source_hash = case.artifact_hashes[0]
    entry = _artifact_binding(
        artifact_key=artifact_key,
        expected_hash=source_hash,
        registry_by_key=registry_by_key,
        receipt_by_key=receipt_by_key,
    )
    _, execution, _ = build_cubic_llzo_fractional_occupancy_policy_evidence(
        repo_root / entry.retained_path,
        source_artifact_hash=source_hash,
    )
    if execution.visible_structure_hash != material_structure_hash:
        raise ValueError("B5 DEV ENSEMBLE expansion differs from canonical composite hash")

    return tuple(
        B5DevStructureUnit(
            unit_version=B5_DEV_STRUCTURE_UNIT_VERSION,
            material_key=material_key,
            split="DEV",
            material_structure_hash=material_structure_hash,
            representation_mode=ResolutionMode.ENSEMBLE.value,
            component_label=component.label,
            unit_structure_hash=component.structure_hash,
            materialization_kind=DETERMINISTIC_GENERATOR,
            source_artifact_key=artifact_key,
            source_path=entry.retained_path,
            generator_id=GENERATION_METHOD,
            weight_numerator=component.weight_numerator,
            weight_denominator=component.weight_denominator,
            condition_scope={
                "weighting_assumption": execution.weighting_assumption,
            },
        )
        for component in execution.components
    )


def build_b5_dev_structure_unit_plan(
    dev_plan: B5DevDiagnosticPlan,
    *,
    repo_root: Path,
    structure_ledger: StructureResolutionLedger,
    artifact_registry: ArtifactRegistry,
    retention_index: ArtifactRetentionIndex,
) -> B5DevStructureUnitPlan:
    """Expand each DEV material into representation-correct structure units."""
    case_by_material = {case.material_key: case for case in structure_ledger.cases}
    registry_by_key = {
        entry.artifact_key: entry
        for entry in artifact_registry.entries
    }
    receipt_by_key = {
        receipt.artifact_key: receipt
        for receipt in retention_index.receipts
    }

    units: list[B5DevStructureUnit] = []
    for member in dev_plan.members:
        try:
            case = case_by_material[member.material_key]
        except KeyError as exc:
            raise ValueError("B5 DEV member lacks structure-resolution case") from exc
        if visible_structure_hash(case) != member.structure_hash:
            raise ValueError("B5 DEV plan structure hash differs from canonical resolution")

        mode = ResolutionMode(case.mode)
        if mode == ResolutionMode.DIRECT:
            if len(case.retained_artifact_keys) != 1 or len(case.artifact_hashes) != 1:
                raise ValueError("DIRECT B5 DEV case requires one retained artifact")
            units.append(
                _retained_unit(
                    material_key=member.material_key,
                    material_structure_hash=member.structure_hash,
                    mode=mode.value,
                    label="direct",
                    artifact_key=case.retained_artifact_keys[0],
                    artifact_hash=case.artifact_hashes[0],
                    condition_scope=case.reference_conditions,
                    registry_by_key=registry_by_key,
                    receipt_by_key=receipt_by_key,
                )
            )
        elif mode == ResolutionMode.PHASE_SET:
            mapping = case.reference_conditions.get("phase_condition_mapping")
            if not isinstance(mapping, Mapping):
                raise ValueError("PHASE_SET B5 DEV case requires phase-condition mapping")
            hash_by_key = dict(zip(case.retained_artifact_keys, case.artifact_hashes))
            for label in sorted(mapping):
                phase = mapping[label]
                if not isinstance(phase, Mapping):
                    raise ValueError("PHASE_SET phase mapping must be a mapping")
                artifact_key = str(phase["artifact_key"])
                try:
                    artifact_hash = hash_by_key[artifact_key]
                except KeyError as exc:
                    raise ValueError("PHASE_SET B5 DEV phase is not retained") from exc
                units.append(
                    _retained_unit(
                        material_key=member.material_key,
                        material_structure_hash=member.structure_hash,
                        mode=mode.value,
                        label=str(label),
                        artifact_key=artifact_key,
                        artifact_hash=artifact_hash,
                        condition_scope={
                            key: value
                            for key, value in phase.items()
                            if key != "artifact_key"
                        },
                        registry_by_key=registry_by_key,
                        receipt_by_key=receipt_by_key,
                    )
                )
        elif mode == ResolutionMode.ENSEMBLE:
            units.extend(
                _expand_ensemble(
                    repo_root=repo_root,
                    material_key=member.material_key,
                    material_structure_hash=member.structure_hash,
                    case=case,
                    registry_by_key=registry_by_key,
                    receipt_by_key=receipt_by_key,
                )
            )
        else:
            raise ValueError("UNREPRESENTABLE case cannot enter B5 DEV")

    material_keys = {unit.material_key for unit in units}
    expected_keys = {member.material_key for member in dev_plan.members}
    if material_keys != expected_keys:
        raise ValueError("B5 DEV structure-unit expansion lost or added materials")

    ensemble_units = [
        unit
        for unit in units
        if unit.representation_mode == ResolutionMode.ENSEMBLE.value
    ]
    if ensemble_units:
        if sum(
            (
                Fraction(unit.weight_numerator, unit.weight_denominator)
                for unit in ensemble_units
            ),
            Fraction(0, 1),
        ) != 1:
            raise ValueError("B5 DEV ENSEMBLE execution-unit weights must sum to one")

    result = B5DevStructureUnitPlan(
        plan_version=B5_DEV_STRUCTURE_UNIT_PLAN_VERSION,
        dev_diagnostic_plan_hash=dev_plan.content_hash,
        units=tuple(sorted(units, key=lambda item: (item.material_key, item.component_label))),
        diagnostic_only=True,
        qualification_evidence_authorized=False,
        held_out_execution_authorized=False,
        production_search_authorized=False,
    )
    result.validate()
    return result
