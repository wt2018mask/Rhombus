"""B2 coverage audit for known-material benchmark closure.

This module does not authorize B3. It reports evidence/representation/control gaps
without inventing scientific truth or numeric qualification thresholds.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Mapping

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_benchmark import STAGES, TruthClass
from rudeus.science.known_material_failure_control import (
    FailureControlCaseState,
    FailureControlKind,
    FailureControlPlan,
    executable_failure_control_kinds,
    missing_executable_failure_control_kinds,
)
from rudeus.science.known_material_structure_resolution import (
    ResolutionStatus,
    StructureResolutionLedger,
)
from rudeus.science.known_material_truth import (
    EvidenceQuantityKind,
    KnownMaterialTruthBundle,
    TruthDisposition,
)
from rudeus.science.known_material_universe import MaterialUniverseIntake


TRUTH_BUNDLE_CATALOG_VERSION = "known-material-truth-bundle-catalog-v1"
B2_EXTERNAL_ASSESSMENT_VERSION = "known-material-b2-external-assessment-v1"
B2_COVERAGE_AUDIT_VERSION = "known-material-b2-coverage-audit-v1"

REQUIRED_EXTERNAL_ASSESSMENTS = (
    "mlip_exposure_accounting",
    "sample_size_power_rule",
)

TRUTH_BUNDLE_ROOT = Path("data/benchmarks/known_material/truth_bundles")


class CoverageState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    UNASSESSED = "UNASSESSED"


class TruthBundleAvailability(str, Enum):
    MISSING = "MISSING"
    DRAFT = "DRAFT"
    CURATED_FOR_B2 = "CURATED_FOR_B2"


@dataclass(frozen=True, kw_only=True)
class TruthBundleCatalogEntry(Record):
    material_key: str
    bundle_path: str
    file_sha256: str
    bundle_content_hash: str

    def validate(self):
        super().validate()
        if not self.material_key:
            raise ValueError("truth-bundle catalog entry requires material key")
        require_hash(self.file_sha256)
        require_hash(self.bundle_content_hash)
        path = Path(self.bundle_path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.is_relative_to(TRUTH_BUNDLE_ROOT)
        ):
            raise ValueError("truth-bundle path escapes benchmark truth-bundle root")


@dataclass(frozen=True, kw_only=True)
class TruthBundleCatalog(Record):
    catalog_version: str
    entries: tuple[TruthBundleCatalogEntry, ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["entries"] = tuple(
            TruthBundleCatalogEntry.from_dict(item) for item in value["entries"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.catalog_version != TRUTH_BUNDLE_CATALOG_VERSION:
            raise ValueError("unsupported truth-bundle catalog version")
        material_keys = [entry.material_key for entry in self.entries]
        paths = [entry.bundle_path for entry in self.entries]
        if len(material_keys) != len(set(material_keys)):
            raise ValueError("truth-bundle catalog requires unique material keys")
        if len(paths) != len(set(paths)):
            raise ValueError("truth-bundle catalog requires unique bundle paths")


@dataclass(frozen=True, kw_only=True)
class ExternalAssessmentEntry(Record):
    assessment_id: str
    state: str
    evidence_refs: tuple[str, ...] = ()
    rationale: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        state = CoverageState(self.state)
        if not self.assessment_id:
            raise ValueError("external assessment requires an id")
        if state == CoverageState.SATISFIED:
            if not self.evidence_refs:
                raise ValueError(
                    "satisfied external assessment requires evidence refs"
                )
        elif not self.rationale:
            raise ValueError(
                "unsatisfied or unassessed external assessment requires rationale"
            )


@dataclass(frozen=True, kw_only=True)
class ExternalAssessmentLedger(Record):
    ledger_version: str
    entries: tuple[ExternalAssessmentEntry, ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["entries"] = tuple(
            ExternalAssessmentEntry.from_dict(item) for item in value["entries"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.ledger_version != B2_EXTERNAL_ASSESSMENT_VERSION:
            raise ValueError("unsupported B2 external-assessment ledger version")
        ids = [entry.assessment_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("external-assessment ledger requires unique ids")
        missing = set(REQUIRED_EXTERNAL_ASSESSMENTS) - set(ids)
        if missing:
            raise ValueError(
                "external-assessment ledger is missing required assessments: "
                + ", ".join(sorted(missing))
            )


@dataclass(frozen=True, kw_only=True)
class MaterialCoverageRecord(Record):
    material_key: str
    proposed_role: str
    chemistry_family: str
    structure_case_statuses: tuple[str, ...]
    truth_bundle_availability: str
    scorable_stages: tuple[str, ...]
    p2_5_self_diffusion_supported: bool
    blocker_codes: tuple[str, ...]

    def validate(self):
        super().validate()
        TruthClass(self.proposed_role)
        TruthBundleAvailability(self.truth_bundle_availability)
        if not self.material_key or not self.chemistry_family:
            raise ValueError("material coverage identity is incomplete")
        for status in self.structure_case_statuses:
            ResolutionStatus(status)
        if any(stage not in STAGES for stage in self.scorable_stages):
            raise ValueError("coverage record contains unknown scorable stage")
        if len(self.scorable_stages) != len(set(self.scorable_stages)):
            raise ValueError("coverage record contains duplicate scorable stages")
        if len(self.blocker_codes) != len(set(self.blocker_codes)):
            raise ValueError("coverage record contains duplicate blockers")


@dataclass(frozen=True, kw_only=True)
class B2CoverageAudit(Record):
    audit_version: str
    material_records: tuple[MaterialCoverageRecord, ...]
    role_counts: Mapping[str, int]
    chemistry_family_count: int
    structure_status_counts: Mapping[str, int]
    truth_bundle_availability_counts: Mapping[str, int]
    scorable_stage_counts: Mapping[str, int]
    p2_5_self_diffusion_truth_count: int
    failure_control_requirement_count: int
    executable_failure_control_count: int
    failure_control_kind_counts: Mapping[str, int]
    missing_failure_control_kinds: tuple[str, ...]
    checks: Mapping[str, str]
    global_blockers: tuple[str, ...]
    b3_split_authorized: bool = False

    def validate(self):
        super().validate()
        if self.audit_version != B2_COVERAGE_AUDIT_VERSION:
            raise ValueError("unsupported B2 coverage audit version")
        if (
            self.chemistry_family_count < 0
            or self.p2_5_self_diffusion_truth_count < 0
            or self.failure_control_requirement_count < 0
            or self.executable_failure_control_count < 0
        ):
            raise ValueError("coverage counts cannot be negative")
        for kind in self.failure_control_kind_counts:
            FailureControlKind(kind)
        for kind in self.missing_failure_control_kinds:
            FailureControlKind(kind)
        for role in self.role_counts:
            TruthClass(role)
        for state in self.checks.values():
            CoverageState(state)
        if self.b3_split_authorized is not False:
            raise ValueError("B2 coverage audit never authorizes B3 split")
        keys = [record.material_key for record in self.material_records]
        if len(keys) != len(set(keys)):
            raise ValueError("B2 coverage audit requires unique material records")


def load_truth_bundle_catalog(path: Path) -> TruthBundleCatalog:
    return TruthBundleCatalog.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )


def load_external_assessment_ledger(path: Path) -> ExternalAssessmentLedger:
    return ExternalAssessmentLedger.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )


def load_cataloged_truth_bundles(
    catalog: TruthBundleCatalog,
    *,
    repo_root: Path,
) -> Mapping[str, KnownMaterialTruthBundle]:
    loaded: dict[str, KnownMaterialTruthBundle] = {}
    for entry in catalog.entries:
        path = repo_root / entry.bundle_path
        if not path.is_file():
            raise ValueError(
                f"cataloged truth bundle is missing: {entry.material_key}"
            )
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry.file_sha256:
            raise ValueError(
                f"truth-bundle file SHA256 mismatch: {entry.material_key}"
            )
        bundle = KnownMaterialTruthBundle.from_dict(
            json.loads(payload.decode("utf-8"))
        )
        if bundle.content_hash != entry.bundle_content_hash:
            raise ValueError(
                f"truth-bundle content hash mismatch: {entry.material_key}"
            )
        loaded[entry.material_key] = bundle
    return loaded


def _scorable_stages(bundle: KnownMaterialTruthBundle | None) -> tuple[str, ...]:
    if bundle is None:
        return ()
    return tuple(item.stage for item in bundle.stage_truths if item.scorable)


def _p2_5_self_diffusion_supported(
    bundle: KnownMaterialTruthBundle | None,
) -> bool:
    if bundle is None:
        return False
    stage = next(item for item in bundle.stage_truths if item.stage == "P2.5")
    return (
        stage.disposition == TruthDisposition.SUPPORTED.value
        and stage.scorable
        and EvidenceQuantityKind.SELF_DIFFUSION.value
        in stage.required_quantity_kinds
    )


def build_b2_coverage_audit(
    universe: MaterialUniverseIntake,
    structure_ledger: StructureResolutionLedger,
    *,
    truth_bundles: Mapping[str, KnownMaterialTruthBundle],
    external_assessments: ExternalAssessmentLedger,
    failure_control_plan: FailureControlPlan,
) -> B2CoverageAudit:
    universe_keys = {entry.material_key for entry in universe.entries}
    foreign_truth = tuple(sorted(set(truth_bundles) - universe_keys))
    if foreign_truth:
        raise ValueError(
            "truth bundles reference materials outside B2 universe: "
            + ", ".join(foreign_truth)
        )

    structure_by_material: dict[str, list[str]] = {}
    for case in structure_ledger.cases:
        if case.material_key not in universe_keys:
            raise ValueError(
                "structure ledger references material outside B2 universe: "
                + case.material_key
            )
        structure_by_material.setdefault(case.material_key, []).append(case.status)

    records: list[MaterialCoverageRecord] = []
    for entry in universe.entries:
        statuses = tuple(structure_by_material.get(entry.material_key, ()))
        bundle = truth_bundles.get(entry.material_key)
        if bundle is None:
            availability = TruthBundleAvailability.MISSING.value
        elif bundle.curation_state == "CURATED_FOR_B2":
            availability = TruthBundleAvailability.CURATED_FOR_B2.value
        else:
            availability = TruthBundleAvailability.DRAFT.value

        scorable = _scorable_stages(bundle)
        p25 = _p2_5_self_diffusion_supported(bundle)

        blockers: list[str] = []
        if not statuses:
            blockers.append("NO_STRUCTURE_RESOLUTION_SPEC")
        else:
            if ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value in statuses:
                blockers.append("STRUCTURE_BLOCKED_MISSING_ARTIFACT")
            if ResolutionStatus.BLOCKED_POLICY.value in statuses:
                blockers.append("STRUCTURE_BLOCKED_POLICY")
            if ResolutionStatus.UNREPRESENTABLE.value in statuses:
                blockers.append("STRUCTURE_UNREPRESENTABLE_FOR_EXECUTION")
        if availability == TruthBundleAvailability.MISSING.value:
            blockers.append("TRUTH_BUNDLE_MISSING")
        elif availability == TruthBundleAvailability.DRAFT.value:
            blockers.append("TRUTH_BUNDLE_NOT_CURATED_FOR_B2")
        if not p25:
            blockers.append("P2_5_SELF_DIFFUSION_TRUTH_NOT_SUPPORTED")

        records.append(
            MaterialCoverageRecord(
                material_key=entry.material_key,
                proposed_role=entry.proposed_role,
                chemistry_family=entry.chemistry_family,
                structure_case_statuses=statuses,
                truth_bundle_availability=availability,
                scorable_stages=scorable,
                p2_5_self_diffusion_supported=p25,
                blocker_codes=tuple(blockers),
            )
        )

    requirement_kinds = tuple(
        item.control_kind for item in failure_control_plan.requirements
    )
    executable_cases = tuple(
        case
        for case in failure_control_plan.cases
        if case.state == FailureControlCaseState.EXECUTABLE.value
    )
    executable_kinds = executable_failure_control_kinds(failure_control_plan)
    missing_control_kinds = missing_executable_failure_control_kinds(
        failure_control_plan
    )
    failure_control_kind_counts = Counter(
        case.control_kind for case in executable_cases
    )

    role_counts = Counter(entry.proposed_role for entry in universe.entries)
    structure_counts = Counter(
        status for record in records for status in record.structure_case_statuses
    )
    truth_counts = Counter(record.truth_bundle_availability for record in records)
    stage_counts = Counter(
        stage for record in records for stage in record.scorable_stages
    )
    p25_count = sum(record.p2_5_self_diffusion_supported for record in records)
    curated_count = truth_counts[TruthBundleAvailability.CURATED_FOR_B2.value]
    ready_structure_count = structure_counts[ResolutionStatus.READY.value]

    external_by_id = {
        entry.assessment_id: entry.state for entry in external_assessments.entries
    }
    checks = {
        "positive_control_present": (
            CoverageState.SATISFIED.value
            if role_counts[TruthClass.POSITIVE.value]
            else CoverageState.UNSATISFIED.value
        ),
        "negative_control_present": (
            CoverageState.SATISFIED.value
            if role_counts[TruthClass.NEGATIVE.value]
            else CoverageState.UNSATISFIED.value
        ),
        "borderline_control_present": (
            CoverageState.SATISFIED.value
            if role_counts[TruthClass.BORDERLINE.value]
            else CoverageState.UNSATISFIED.value
        ),
        "failure_control_role_present_in_universe": (
            CoverageState.SATISFIED.value
            if role_counts[TruthClass.FAILURE_CONTROL.value]
            else CoverageState.UNSATISFIED.value
        ),
        "failure_control_contract_defined": (
            CoverageState.SATISFIED.value
            if requirement_kinds
            else CoverageState.UNSATISFIED.value
        ),
        "failure_control_executable_coverage": (
            CoverageState.SATISFIED.value
            if requirement_kinds and not missing_control_kinds
            else CoverageState.UNSATISFIED.value
        ),
        "chemistry_family_diversity_present": (
            CoverageState.SATISFIED.value
            if len({entry.chemistry_family for entry in universe.entries}) >= 4
            else CoverageState.UNSATISFIED.value
        ),
        "executable_structure_case_present": (
            CoverageState.SATISFIED.value
            if ready_structure_count
            else CoverageState.UNSATISFIED.value
        ),
        "curated_truth_bundle_present": (
            CoverageState.SATISFIED.value
            if curated_count
            else CoverageState.UNSATISFIED.value
        ),
        "p2_5_self_diffusion_truth_present": (
            CoverageState.SATISFIED.value
            if p25_count
            else CoverageState.UNSATISFIED.value
        ),
        "mlip_exposure_accounting": external_by_id["mlip_exposure_accounting"],
        "sample_size_power_rule": external_by_id["sample_size_power_rule"],
    }

    blockers: list[str] = []
    if (
        checks["failure_control_contract_defined"]
        != CoverageState.SATISFIED.value
    ):
        blockers.append("FAILURE_CONTROL_CONTRACT_MISSING")
    if (
        checks["failure_control_executable_coverage"]
        != CoverageState.SATISFIED.value
    ):
        blockers.append("FAILURE_CONTROL_EXECUTABLE_COVERAGE_INCOMPLETE")
    if checks["executable_structure_case_present"] != CoverageState.SATISFIED.value:
        blockers.append("NO_EXECUTABLE_STRUCTURE_CASE")
    if checks["curated_truth_bundle_present"] != CoverageState.SATISFIED.value:
        blockers.append("NO_CURATED_TRUTH_BUNDLE")
    if checks["p2_5_self_diffusion_truth_present"] != CoverageState.SATISFIED.value:
        blockers.append("NO_P2_5_SELF_DIFFUSION_TRUTH")
    if checks["mlip_exposure_accounting"] == CoverageState.UNASSESSED.value:
        blockers.append("MLIP_EXPOSURE_UNASSESSED")
    if checks["sample_size_power_rule"] == CoverageState.UNASSESSED.value:
        blockers.append("SAMPLE_SIZE_POWER_RULE_UNASSESSED")

    return B2CoverageAudit(
        audit_version=B2_COVERAGE_AUDIT_VERSION,
        material_records=tuple(records),
        role_counts=dict(sorted(role_counts.items())),
        chemistry_family_count=len(
            {entry.chemistry_family for entry in universe.entries}
        ),
        structure_status_counts=dict(sorted(structure_counts.items())),
        truth_bundle_availability_counts=dict(sorted(truth_counts.items())),
        scorable_stage_counts={
            stage: stage_counts.get(stage, 0) for stage in STAGES
        },
        p2_5_self_diffusion_truth_count=p25_count,
        failure_control_requirement_count=len(requirement_kinds),
        executable_failure_control_count=len(executable_cases),
        failure_control_kind_counts={
            kind: failure_control_kind_counts.get(kind, 0)
            for kind in sorted(requirement_kinds)
        },
        missing_failure_control_kinds=missing_control_kinds,
        checks=checks,
        global_blockers=tuple(blockers),
    )
