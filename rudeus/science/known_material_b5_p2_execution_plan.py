"""Planning-only B5 DEV P2 execution plan derived from retained real P1 evidence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from rudeus.mlip.p2 import batch_seed, protocol_config_hash
from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_b5_p1_real_evidence import (
    B5P1RealEvidenceBinding,
)


B5_P2_EXECUTION_PLAN_VERSION = "known-material-b5-p2-execution-plan-v1"


@dataclass(frozen=True, kw_only=True)
class B5P2ExecutionUnit(Record):
    unit_version: str
    batch_id: str
    material_key: str
    component_label: str
    p1_evidence_hash: str
    relaxed_structure_sha256: str
    p2_config_hash: str
    seed: int
    temperature_K: float
    mobile_species: str

    def validate(self):
        super().validate()
        if self.unit_version != B5_P2_EXECUTION_PLAN_VERSION:
            raise ValueError("unsupported B5 P2 execution unit version")
        if len(self.batch_id) != 16 or any(c not in "0123456789abcdef" for c in self.batch_id):
            raise ValueError("invalid P2 batch id")
        require_hash(self.p1_evidence_hash)
        require_hash(self.relaxed_structure_sha256)
        if len(self.p2_config_hash) != 16 or any(c not in "0123456789abcdef" for c in self.p2_config_hash):
            raise ValueError("invalid P2 protocol hash")
        if self.seed < 0:
            raise ValueError("P2 seed must be non-negative")
        if self.temperature_K <= 0 or not self.mobile_species:
            raise ValueError("P2 protocol identity incomplete")


@dataclass(frozen=True, kw_only=True)
class B5P2ExecutionPlan(Record):
    plan_version: str
    source_p1_evidence_hash: str
    p2_config_hash: str
    p2_protocol: Mapping
    units: tuple[B5P2ExecutionUnit, ...]
    planning_only: bool
    p2_tasks_created: bool
    qualification_evidence_authorized: bool = False
    held_out_execution_authorized: bool = False
    production_search_authorized: bool = False

    def validate(self):
        super().validate()
        if self.plan_version != B5_P2_EXECUTION_PLAN_VERSION:
            raise ValueError("unsupported B5 P2 execution plan version")
        require_hash(self.source_p1_evidence_hash)
        if len(self.p2_config_hash) != 16:
            raise ValueError("invalid P2 config hash")
        if protocol_config_hash(dict(self.p2_protocol)) != self.p2_config_hash:
            raise ValueError("P2 config hash disagrees with protocol")
        if len(self.units) != 3:
            raise ValueError("canonical B5 DEV P2 plan requires exactly three units")
        identities = tuple((u.material_key, u.component_label) for u in self.units)
        if identities != tuple(sorted(identities)) or len(set(identities)) != len(identities):
            raise ValueError("P2 units must be unique and canonically sorted")
        if any(u.p2_config_hash != self.p2_config_hash for u in self.units):
            raise ValueError("P2 units disagree on protocol hash")
        if self.planning_only is not True or self.p2_tasks_created is not False:
            raise ValueError("P2 execution plan must remain planning-only")
        if any((self.qualification_evidence_authorized,
                self.held_out_execution_authorized,
                self.production_search_authorized)):
            raise ValueError("P2 DEV plan authorizes no qualification or production")


def build_b5_p2_execution_plan(
    binding: B5P1RealEvidenceBinding,
    *,
    p2_protocol: Mapping,
) -> B5P2ExecutionPlan:
    protocol = dict(p2_protocol)
    cfg_hash = protocol_config_hash(protocol)
    base_seed = int(protocol.get("base_seed", 550))
    units = tuple(
        B5P2ExecutionUnit(
            unit_version=B5_P2_EXECUTION_PLAN_VERSION,
            batch_id=row.batch_id,
            material_key=row.material_key,
            component_label=row.component_label,
            p1_evidence_hash=binding.content_hash,
            relaxed_structure_sha256=row.relaxed_structure_sha256,
            p2_config_hash=cfg_hash,
            seed=batch_seed(base_seed, row.batch_id),
            temperature_K=float(protocol["temperature_K"]),
            mobile_species=str(protocol["mobile_species"]),
        )
        for row in binding.results
    )
    plan = B5P2ExecutionPlan(
        plan_version=B5_P2_EXECUTION_PLAN_VERSION,
        source_p1_evidence_hash=binding.content_hash,
        p2_config_hash=cfg_hash,
        p2_protocol=protocol,
        units=units,
        planning_only=True,
        p2_tasks_created=False,
    )
    plan.validate()
    return plan
