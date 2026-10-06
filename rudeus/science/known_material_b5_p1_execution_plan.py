"""Deterministic DEV P1 execution plan for known-material B5.

This freezes eligible structure units and the existing pinned MACE P1 protocol.
It plans scientific inputs only; it does not create remote jobs or execute MLIP.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_b5_dev_units import (
    B5DevStructureUnit,
    B5DevStructureUnitPlan,
)
from rudeus.science.known_material_b5_p1_entry import (
    B5P1EntryDecision,
    P1EntryDisposition,
)


B5_P1_EXECUTION_PLAN_VERSION = "known-material-b5-p1-execution-plan-v1"


@dataclass(frozen=True, kw_only=True)
class B5P1ExecutionUnit(Record):
    unit_version: str
    material_key: str
    component_label: str
    representation_mode: str
    source_b5_structure_unit_hash: str
    input_structure_hash: str
    source_path: str
    checkpoint_id: str
    checkpoint_sha256: str
    checkpoint_url: str
    force_tol_ev_A: float
    max_relax_steps: int
    precision: str

    def validate(self):
        super().validate()
        if self.unit_version != B5_P1_EXECUTION_PLAN_VERSION:
            raise ValueError("unsupported B5 P1 execution-unit version")
        require_hash(self.source_b5_structure_unit_hash)
        require_hash(self.input_structure_hash)
        require_hash(self.checkpoint_sha256)
        if not self.material_key or not self.component_label or not self.source_path:
            raise ValueError("P1 execution unit identity is incomplete")
        if not self.checkpoint_id or not self.checkpoint_url:
            raise ValueError("P1 execution unit requires pinned checkpoint metadata")
        if self.force_tol_ev_A <= 0 or self.max_relax_steps <= 0:
            raise ValueError("P1 relaxation protocol values must be positive")
        if self.precision not in ("float32", "float64"):
            raise ValueError("unsupported P1 precision")


@dataclass(frozen=True, kw_only=True)
class B5P1ExecutionPlan(Record):
    plan_version: str
    source_structure_unit_plan_hash: str
    source_entry_decision_hashes: tuple[str, ...]
    units: tuple[B5P1ExecutionUnit, ...]
    planning_only: bool
    p1_tasks_created: bool
    qualification_evidence_authorized: bool = False
    held_out_execution_authorized: bool = False
    production_search_authorized: bool = False

    def validate(self):
        super().validate()
        if self.plan_version != B5_P1_EXECUTION_PLAN_VERSION:
            raise ValueError("unsupported B5 P1 execution-plan version")
        require_hash(self.source_structure_unit_plan_hash)
        for value in self.source_entry_decision_hashes:
            require_hash(value)
        identities = tuple((u.material_key, u.component_label) for u in self.units)
        if not self.units or identities != tuple(sorted(identities)):
            raise ValueError("P1 execution units must be nonempty and canonically sorted")
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate P1 execution unit")
        if self.planning_only is not True or self.p1_tasks_created is not False:
            raise ValueError("v1 P1 execution plan is planning-only")
        if any((
            self.qualification_evidence_authorized,
            self.held_out_execution_authorized,
            self.production_search_authorized,
        )):
            raise ValueError("DEV P1 plan authorizes no qualification or production")


def build_b5_p1_execution_plan(
    structure_plan: B5DevStructureUnitPlan,
    entry_decisions: Sequence[B5P1EntryDecision],
    *,
    mlip_config: Mapping,
) -> B5P1ExecutionPlan:
    decisions = {item.material_key: item for item in entry_decisions}
    if len(decisions) != len(tuple(entry_decisions)):
        raise ValueError("duplicate P1 entry decisions")

    required = (
        "primary_checkpoint",
        "checkpoint_url",
        "checkpoint_sha256",
        "force_tol_ev_A",
        "max_relax_steps",
        "precision",
    )
    missing = [key for key in required if key not in mlip_config]
    if missing:
        raise ValueError(f"P1 MLIP config missing required keys: {missing}")

    eligible_materials = {
        key
        for key, decision in decisions.items()
        if decision.p1_entry_disposition == P1EntryDisposition.ELIGIBLE.value
        and decision.p1_execution_authorized is True
    }
    units = []
    for source in structure_plan.units:
        if source.material_key not in eligible_materials:
            continue
        units.append(
            B5P1ExecutionUnit(
                unit_version=B5_P1_EXECUTION_PLAN_VERSION,
                material_key=source.material_key,
                component_label=source.component_label,
                representation_mode=source.representation_mode,
                source_b5_structure_unit_hash=source.content_hash,
                input_structure_hash=source.unit_structure_hash,
                source_path=source.source_path,
                checkpoint_id=str(mlip_config["primary_checkpoint"]),
                checkpoint_sha256=str(mlip_config["checkpoint_sha256"]),
                checkpoint_url=str(mlip_config["checkpoint_url"]),
                force_tol_ev_A=float(mlip_config["force_tol_ev_A"]),
                max_relax_steps=int(mlip_config["max_relax_steps"]),
                precision=str(mlip_config["precision"]),
            )
        )

    result = B5P1ExecutionPlan(
        plan_version=B5_P1_EXECUTION_PLAN_VERSION,
        source_structure_unit_plan_hash=structure_plan.content_hash,
        source_entry_decision_hashes=tuple(
            item.content_hash for item in sorted(entry_decisions, key=lambda x: x.material_key)
        ),
        units=tuple(sorted(units, key=lambda x: (x.material_key, x.component_label))),
        planning_only=True,
        p1_tasks_created=False,
        qualification_evidence_authorized=False,
        held_out_execution_authorized=False,
        production_search_authorized=False,
    )
    result.validate()
    return result
