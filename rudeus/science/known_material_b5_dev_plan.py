"""B5 DEV-only diagnostic planning for the contaminated v1 benchmark cohort.

The v1 cohort is no longer eligible for strong HELD_OUT qualification because
its identity/truth bindings are public.  Its DEV members remain useful for
diagnostic falsification and recalibration.  This module builds a deterministic
plan that includes DEV only and explicitly carries no qualification authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_b3_split import B3SplitFreeze
from rudeus.science.known_material_b4_blind_package import visible_structure_hash
from rudeus.science.known_material_structure_resolution import (
    ResolutionMode,
    StructureResolutionLedger,
)
from rudeus.science.known_material_truth import KnownMaterialTruthBundle


B5_DEV_DIAGNOSTIC_PLAN_VERSION = "known-material-b5-dev-diagnostic-plan-v1"


@dataclass(frozen=True, kw_only=True)
class B5DevDiagnosticMember(Record):
    material_key: str
    split: str
    benchmark_role: str
    truth_bundle_hash: str
    structure_hash: str
    structure_mode: str
    scorable_stages: tuple[str, ...]

    def validate(self):
        super().validate()
        if not self.material_key:
            raise ValueError("B5 DEV diagnostic member requires material key")
        if self.split != "DEV":
            raise ValueError("B5 DEV diagnostic plan may contain DEV only")
        if self.benchmark_role not in {"POSITIVE", "NEGATIVE", "BORDERLINE"}:
            raise ValueError("B5 DEV diagnostic member has unsupported benchmark role")
        require_hash(self.truth_bundle_hash)
        require_hash(self.structure_hash)
        ResolutionMode(self.structure_mode)
        if not self.scorable_stages:
            raise ValueError("B5 DEV diagnostic member requires scoreable truth")


@dataclass(frozen=True, kw_only=True)
class B5DevDiagnosticPlan(Record):
    plan_version: str
    split_freeze_hash: str
    benchmark_protocol_hash: str
    members: tuple[B5DevDiagnosticMember, ...]
    identity_exposure_acknowledged: bool
    truth_exposure_acknowledged: bool
    diagnostic_only: bool
    qualification_evidence_authorized: bool = False
    held_out_execution_authorized: bool = False
    production_search_authorized: bool = False

    def validate(self):
        super().validate()
        if self.plan_version != B5_DEV_DIAGNOSTIC_PLAN_VERSION:
            raise ValueError("unsupported B5 DEV diagnostic plan version")
        require_hash(self.split_freeze_hash)
        require_hash(self.benchmark_protocol_hash)
        if not self.members:
            raise ValueError("B5 DEV diagnostic plan requires members")
        if any(member.split != "DEV" for member in self.members):
            raise ValueError("B5 DEV diagnostic plan may contain DEV only")
        material_keys = tuple(member.material_key for member in self.members)
        if len(material_keys) != len(set(material_keys)):
            raise ValueError("B5 DEV diagnostic plan requires unique materials")
        if material_keys != tuple(sorted(material_keys)):
            raise ValueError("B5 DEV diagnostic plan must be sorted by material key")
        if self.identity_exposure_acknowledged is not True:
            raise ValueError("v1 DEV plan must acknowledge public identity exposure")
        if self.truth_exposure_acknowledged is not True:
            raise ValueError("v1 DEV plan must acknowledge public truth exposure")
        if self.diagnostic_only is not True:
            raise ValueError("v1 DEV plan is diagnostic only")
        if any(
            (
                self.qualification_evidence_authorized,
                self.held_out_execution_authorized,
                self.production_search_authorized,
            )
        ):
            raise ValueError("B5 DEV diagnostic plan authorizes no qualification or production")


def build_b5_dev_diagnostic_plan(
    split_freeze: B3SplitFreeze,
    *,
    truth_bundles: Mapping[str, KnownMaterialTruthBundle],
    structure_ledger: StructureResolutionLedger,
) -> B5DevDiagnosticPlan:
    """Bind the frozen v1 DEV subset to canonical truth and executable structures."""
    dev_members = tuple(
        member for member in split_freeze.members if member.split == "DEV"
    )
    if not dev_members:
        raise ValueError("frozen split contains no DEV members")

    case_by_material = {
        case.material_key: case
        for case in structure_ledger.cases
    }
    members = []
    protocol_hashes = set()

    for frozen in dev_members:
        try:
            bundle = truth_bundles[frozen.benchmark_id]
        except KeyError as exc:
            raise ValueError("DEV member lacks canonical truth bundle") from exc
        if bundle.content_hash != frozen.truth_bundle_hash:
            raise ValueError("DEV truth bundle differs from frozen B3 binding")
        try:
            case = case_by_material[frozen.benchmark_id]
        except KeyError as exc:
            raise ValueError("DEV member lacks canonical structure-resolution case") from exc

        protocol_hashes.add(bundle.benchmark_protocol_hash)
        members.append(
            B5DevDiagnosticMember(
                material_key=frozen.benchmark_id,
                split="DEV",
                benchmark_role=bundle.benchmark_role,
                truth_bundle_hash=frozen.truth_bundle_hash,
                structure_hash=visible_structure_hash(case),
                structure_mode=case.mode,
                scorable_stages=tuple(
                    truth.stage
                    for truth in bundle.stage_truths
                    if truth.scorable
                ),
            )
        )

    if len(protocol_hashes) != 1:
        raise ValueError("B5 DEV members must share one benchmark protocol")

    plan = B5DevDiagnosticPlan(
        plan_version=B5_DEV_DIAGNOSTIC_PLAN_VERSION,
        split_freeze_hash=split_freeze.content_hash,
        benchmark_protocol_hash=next(iter(protocol_hashes)),
        members=tuple(sorted(members, key=lambda item: item.material_key)),
        identity_exposure_acknowledged=True,
        truth_exposure_acknowledged=True,
        diagnostic_only=True,
        qualification_evidence_authorized=False,
        held_out_execution_authorized=False,
        production_search_authorized=False,
    )
    plan.validate()
    return plan
