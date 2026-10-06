"""Raw P0 execution for the canonical B5 DEV structure units.

This module deliberately stops at unit-level observations.  It does not aggregate
DIRECT / PHASE_SET / ENSEMBLE components into a material verdict and therefore
cannot turn representation-specific behavior into a scientific material failure.
Execution exceptions remain ERROR records rather than FAIL/UNKNOWN observations.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path
from typing import Any, Mapping

from pymatgen.core import Structure
from pymatgen.io.cif import CifParser

from rudeus.filters.p0 import evaluate_p0
from rudeus.schema import ExistenceState
from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_b5_dev_units import (
    B5DevStructureUnit,
    B5DevStructureUnitPlan,
    DETERMINISTIC_GENERATOR,
    RETAINED_ARTIFACT,
)
from rudeus.science.known_material_cubic_llzo_policy_evidence import (
    GENERATION_METHOD,
)
from rudeus.science.known_material_cubic_llzo_weighted_ordered import (
    build_weighted_cubic_llzo_ordered_structures,
)


B5_P0_RAW_EXECUTION_VERSION = "known-material-b5-p0-raw-execution-v1"


class B5P0UnitExecutionStatus(str, Enum):
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


@dataclass(frozen=True, kw_only=True)
class B5P0UnitObservation(Record):
    execution_version: str
    structure_unit_hash: str
    material_key: str
    component_label: str
    representation_mode: str
    input_structure_hash: str
    execution_status: str
    input_formula: str | None
    existence_state: str | None
    passed: bool | None
    neutrality_ok: bool | None
    pauling_ok: bool | None
    geometry_ok: bool | None
    details: Mapping[str, Any]
    error_type: str | None = None
    error_message: str | None = None

    def validate(self):
        super().validate()
        if self.execution_version != B5_P0_RAW_EXECUTION_VERSION:
            raise ValueError("unsupported B5 P0 raw-execution version")
        require_hash(self.structure_unit_hash)
        require_hash(self.input_structure_hash)
        if not self.material_key or not self.component_label:
            raise ValueError("B5 P0 observation identity is incomplete")
        status = B5P0UnitExecutionStatus(self.execution_status)

        if status == B5P0UnitExecutionStatus.COMPLETED:
            if not self.input_formula:
                raise ValueError("completed B5 P0 observation requires input formula")
            if self.existence_state is None or self.passed is None:
                raise ValueError("completed B5 P0 observation requires scientific result")
            state = ExistenceState(self.existence_state)
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("completed B5 P0 observation cannot carry execution error")
            expected_passed = state == ExistenceState.PLAUSIBLE
            if self.passed is not expected_passed:
                raise ValueError("B5 P0 passed flag disagrees with existence state")
            if state == ExistenceState.UNKNOWN:
                if all(
                    value is not None
                    for value in (self.neutrality_ok, self.pauling_ok, self.geometry_ok)
                ):
                    raise ValueError("P0 UNKNOWN requires at least one unresolved check")
            elif state == ExistenceState.FAIL:
                if not any(
                    value is False
                    for value in (self.neutrality_ok, self.pauling_ok, self.geometry_ok)
                ):
                    raise ValueError("P0 FAIL requires at least one failed check")
            elif state == ExistenceState.PLAUSIBLE:
                if (self.neutrality_ok, self.pauling_ok, self.geometry_ok) != (
                    True,
                    True,
                    True,
                ):
                    raise ValueError("P0 PLAUSIBLE requires all checks true")
            else:
                raise ValueError("B5 P0 cannot promote raw P0 result to SUPPORTED")
        else:
            if not self.error_type or not self.error_message:
                raise ValueError("B5 P0 execution ERROR requires explicit error")
            if any(
                value is not None
                for value in (
                    self.input_formula,
                    self.existence_state,
                    self.passed,
                    self.neutrality_ok,
                    self.pauling_ok,
                    self.geometry_ok,
                )
            ):
                raise ValueError(
                    "B5 P0 execution ERROR cannot carry scientific result fields"
                )


@dataclass(frozen=True, kw_only=True)
class B5P0RawExecutionReport(Record):
    execution_version: str
    structure_unit_plan_hash: str
    observations: tuple[B5P0UnitObservation, ...]
    completed_count: int
    error_count: int
    material_verdicts_aggregated: bool
    diagnostic_only: bool
    qualification_evidence_authorized: bool = False
    held_out_execution_authorized: bool = False
    production_search_authorized: bool = False

    def validate(self):
        super().validate()
        if self.execution_version != B5_P0_RAW_EXECUTION_VERSION:
            raise ValueError("unsupported B5 P0 report version")
        require_hash(self.structure_unit_plan_hash)
        if not self.observations:
            raise ValueError("B5 P0 report requires observations")
        identities = tuple(
            (item.material_key, item.component_label)
            for item in self.observations
        )
        if identities != tuple(sorted(identities)):
            raise ValueError("B5 P0 observations must be canonically sorted")
        if len(identities) != len(set(identities)):
            raise ValueError("B5 P0 observations require unique structure units")
        expected_completed = sum(
            item.execution_status == B5P0UnitExecutionStatus.COMPLETED.value
            for item in self.observations
        )
        expected_errors = len(self.observations) - expected_completed
        if self.completed_count != expected_completed or self.error_count != expected_errors:
            raise ValueError("B5 P0 report counts disagree with observations")
        if self.material_verdicts_aggregated is not False:
            raise ValueError("raw B5 P0 execution must not aggregate material verdicts")
        if self.diagnostic_only is not True:
            raise ValueError("v1 B5 P0 execution is diagnostic only")
        if any(
            (
                self.qualification_evidence_authorized,
                self.held_out_execution_authorized,
                self.production_search_authorized,
            )
        ):
            raise ValueError("raw B5 P0 execution authorizes no qualification or production")


def _load_retained_structure(
    unit: B5DevStructureUnit,
    *,
    repo_root: Path,
) -> Structure:
    path = repo_root / unit.source_path
    payload = path.read_bytes()
    actual_hash = hashlib.sha256(payload).hexdigest()
    if actual_hash != unit.unit_structure_hash:
        raise ValueError("retained B5 P0 unit bytes differ from bound structure hash")
    structures = CifParser(str(path)).parse_structures(primitive=False)
    if len(structures) != 1:
        raise ValueError("retained B5 P0 CIF must contain exactly one structure")
    return structures[0]


def _load_generated_structure(
    unit: B5DevStructureUnit,
    *,
    repo_root: Path,
) -> Structure:
    if unit.generator_id != GENERATION_METHOD:
        raise ValueError("B5 P0 unit declares unsupported deterministic generator")
    source_path = repo_root / unit.source_path
    members = build_weighted_cubic_llzo_ordered_structures(source_path)
    matches = [
        member
        for member in members
        if member.structure_hash == unit.unit_structure_hash
    ]
    if len(matches) != 1:
        raise ValueError("B5 P0 generated unit does not resolve uniquely")
    match = matches[0]
    if (
        match.weight_numerator != unit.weight_numerator
        or match.weight_denominator != unit.weight_denominator
    ):
        raise ValueError("B5 P0 generated unit weight differs from bound unit")
    return match.structure


def materialize_b5_p0_structure(
    unit: B5DevStructureUnit,
    *,
    repo_root: Path,
) -> Structure:
    """Reconstruct exactly the structure represented by one B5 execution unit."""
    if unit.materialization_kind == RETAINED_ARTIFACT:
        return _load_retained_structure(unit, repo_root=repo_root)
    if unit.materialization_kind == DETERMINISTIC_GENERATOR:
        return _load_generated_structure(unit, repo_root=repo_root)
    raise ValueError("unsupported B5 P0 unit materialization kind")


def _formula_for_p0(structure: Structure) -> str:
    formula = str(structure.composition.reduced_formula)
    if not formula:
        raise ValueError("B5 P0 structure has empty composition")
    return formula


def execute_b5_p0_unit(
    unit: B5DevStructureUnit,
    *,
    repo_root: Path,
) -> B5P0UnitObservation:
    """Execute P0 for one unit; exceptions stay operational ERRORs."""
    try:
        structure = materialize_b5_p0_structure(unit, repo_root=repo_root)
        formula = _formula_for_p0(structure)
        result = evaluate_p0(formula, structure=structure)
        observation = B5P0UnitObservation(
            execution_version=B5_P0_RAW_EXECUTION_VERSION,
            structure_unit_hash=unit.content_hash,
            material_key=unit.material_key,
            component_label=unit.component_label,
            representation_mode=unit.representation_mode,
            input_structure_hash=unit.unit_structure_hash,
            execution_status=B5P0UnitExecutionStatus.COMPLETED.value,
            input_formula=formula,
            existence_state=result.existence_state.value,
            passed=result.passed,
            neutrality_ok=result.neutrality_ok,
            pauling_ok=result.pauling_ok,
            geometry_ok=result.geometry_ok,
            details=result.details,
        )
    except Exception as exc:
        observation = B5P0UnitObservation(
            execution_version=B5_P0_RAW_EXECUTION_VERSION,
            structure_unit_hash=unit.content_hash,
            material_key=unit.material_key,
            component_label=unit.component_label,
            representation_mode=unit.representation_mode,
            input_structure_hash=unit.unit_structure_hash,
            execution_status=B5P0UnitExecutionStatus.ERROR.value,
            input_formula=None,
            existence_state=None,
            passed=None,
            neutrality_ok=None,
            pauling_ok=None,
            geometry_ok=None,
            details={},
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
    observation.validate()
    return observation


def run_b5_p0_raw_execution(
    unit_plan: B5DevStructureUnitPlan,
    *,
    repo_root: Path,
) -> B5P0RawExecutionReport:
    """Execute all canonical DEV units without making any material-level verdict."""
    observations = tuple(
        sorted(
            (
                execute_b5_p0_unit(unit, repo_root=repo_root)
                for unit in unit_plan.units
            ),
            key=lambda item: (item.material_key, item.component_label),
        )
    )
    completed = sum(
        item.execution_status == B5P0UnitExecutionStatus.COMPLETED.value
        for item in observations
    )
    report = B5P0RawExecutionReport(
        execution_version=B5_P0_RAW_EXECUTION_VERSION,
        structure_unit_plan_hash=unit_plan.content_hash,
        observations=observations,
        completed_count=completed,
        error_count=len(observations) - completed,
        material_verdicts_aggregated=False,
        diagnostic_only=True,
        qualification_evidence_authorized=False,
        held_out_execution_authorized=False,
        production_search_authorized=False,
    )
    report.validate()
    return report


def require_clean_b5_p0_execution(report: B5P0RawExecutionReport) -> None:
    """Fail CI only on execution errors, never on a scientific P0 FAIL/UNKNOWN."""
    if report.error_count:
        raise RuntimeError(
            f"B5 P0 raw execution contains {report.error_count} execution errors"
        )
