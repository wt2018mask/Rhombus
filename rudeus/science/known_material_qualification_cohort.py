"""Versioned repair contract for a replacement strong-blind qualification cohort.

The public repository may freeze the selection protocol, role quotas, execution
schema, and sealing rules.  It must not contain replacement HELD_OUT member
identity, truth bindings, or identity↔structure bindings before blinded B7
results are frozen.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_b4_ingress import VISIBLE_FIELDS


QUALIFICATION_COHORT_REPAIR_VERSION = (
    "known-material-qualification-cohort-repair-v1"
)
QUALIFICATION_COHORT_VERSION = "known-material-qualification-cohort-v2"
SEALED_UNTIL = "AFTER_B7_BLINDED_RESULTS_FREEZE"
REQUIRED_ROLES = ("POSITIVE", "NEGATIVE", "BORDERLINE")
REQUIRED_SEALED_FIELDS = (
    "material_identity",
    "truth_class",
    "truth_bundle_hash",
    "literature_evidence",
    "expected_stage_outcomes",
    "opaque_identity_mapping",
    "structure_identity_binding",
    "source_artifact_binding",
)


@dataclass(frozen=True, kw_only=True)
class QualificationCohortRepairPlan(Record):
    repair_version: str
    qualification_cohort_version: str
    contaminated_v1_split_freeze_hash: str
    benchmark_protocol_hash: str
    minimum_held_out_per_role: Mapping[str, int]
    execution_visible_fields: tuple[str, ...]
    sealed_fields: tuple[str, ...]
    sealed_until: str
    repository_member_identity_authorized: bool = False
    repository_truth_binding_authorized: bool = False
    repository_structure_identity_binding_authorized: bool = False
    v1_held_out_qualification_reuse_authorized: bool = False
    v1_dev_diagnostic_reuse_authorized: bool = True
    held_out_execution_authorized: bool = False
    production_search_authorized: bool = False

    def validate(self):
        super().validate()
        if self.repair_version != QUALIFICATION_COHORT_REPAIR_VERSION:
            raise ValueError("unsupported qualification-cohort repair version")
        if self.qualification_cohort_version != QUALIFICATION_COHORT_VERSION:
            raise ValueError("unsupported qualification cohort version")
        require_hash(self.contaminated_v1_split_freeze_hash)
        require_hash(self.benchmark_protocol_hash)

        if tuple(self.minimum_held_out_per_role) != REQUIRED_ROLES:
            raise ValueError(
                "replacement cohort must pre-register positive/negative/borderline quotas"
            )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 1
            for value in self.minimum_held_out_per_role.values()
        ):
            raise ValueError("each held-out role requires at least one independent material")

        if self.execution_visible_fields != VISIBLE_FIELDS:
            raise ValueError("replacement cohort must preserve the B0 visible schema")
        if self.sealed_fields != REQUIRED_SEALED_FIELDS:
            raise ValueError("replacement cohort sealed fields differ from repair contract")
        if self.sealed_until != SEALED_UNTIL:
            raise ValueError("replacement cohort must stay sealed through B7 result freeze")

        if any(
            (
                self.repository_member_identity_authorized,
                self.repository_truth_binding_authorized,
                self.repository_structure_identity_binding_authorized,
                self.v1_held_out_qualification_reuse_authorized,
                self.held_out_execution_authorized,
                self.production_search_authorized,
            )
        ):
            raise ValueError(
                "repair plan cannot expose replacement HELD_OUT state or authorize execution"
            )
        if self.v1_dev_diagnostic_reuse_authorized is not True:
            raise ValueError("v1 contaminated cohort remains available only for DEV diagnostics")


def load_qualification_cohort_repair_plan(
    path: Path,
) -> QualificationCohortRepairPlan:
    return QualificationCohortRepairPlan.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )
