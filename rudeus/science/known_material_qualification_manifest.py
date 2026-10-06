"""External sealed manifest contract for the replacement v2 qualification cohort.

Real replacement member identity, truth, and structure/source identity bindings
must remain outside the repository through the B7 blinded-results freeze.  This
module validates such external state and returns only a public-safe summary.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_b3_split import B3SplitFreeze
from rudeus.science.known_material_b4_blinding_amendment import OPAQUE_ID_RE
from rudeus.science.known_material_qualification_cohort import (
    QUALIFICATION_COHORT_VERSION,
    REQUIRED_ROLES,
    QualificationCohortRepairPlan,
)


SEALED_QUALIFICATION_MANIFEST_VERSION = (
    "known-material-sealed-qualification-cohort-v2"
)
SEALED_QUALIFICATION_VALIDATION_VERSION = (
    "known-material-sealed-qualification-validation-v1"
)


@dataclass(frozen=True, kw_only=True)
class SealedQualificationMember(Record):
    benchmark_id: str
    split: str
    material_identity: str
    truth_class: str
    truth_bundle_hash: str
    literature_evidence_hashes: tuple[str, ...]
    expected_stage_outcomes_hash: str
    structure_hash: str
    source_artifact_hashes: tuple[str, ...]

    def validate(self):
        super().validate()
        if not OPAQUE_ID_RE.fullmatch(self.benchmark_id):
            raise ValueError("sealed qualification benchmark id must be opaque")
        if self.split != "HELD_OUT":
            raise ValueError("replacement qualification manifest is HELD_OUT-only")
        if not self.material_identity:
            raise ValueError("sealed qualification member requires material identity")
        if self.truth_class not in REQUIRED_ROLES:
            raise ValueError("sealed qualification member has unsupported truth class")
        require_hash(self.truth_bundle_hash)
        require_hash(self.expected_stage_outcomes_hash)
        require_hash(self.structure_hash)
        if not self.literature_evidence_hashes:
            raise ValueError("sealed qualification member requires literature evidence")
        if not self.source_artifact_hashes:
            raise ValueError("sealed qualification member requires source artifact binding")
        for value in self.literature_evidence_hashes:
            require_hash(value)
        for value in self.source_artifact_hashes:
            require_hash(value)


@dataclass(frozen=True, kw_only=True)
class SealedQualificationCohortManifest(Record):
    manifest_version: str
    qualification_cohort_version: str
    repair_plan_hash: str
    benchmark_protocol_hash: str
    members: tuple[SealedQualificationMember, ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["members"] = tuple(
            SealedQualificationMember.from_dict(item)
            for item in value["members"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.manifest_version != SEALED_QUALIFICATION_MANIFEST_VERSION:
            raise ValueError("unsupported sealed qualification manifest version")
        if self.qualification_cohort_version != QUALIFICATION_COHORT_VERSION:
            raise ValueError("sealed manifest targets the wrong qualification cohort")
        require_hash(self.repair_plan_hash)
        require_hash(self.benchmark_protocol_hash)
        if not self.members:
            raise ValueError("sealed qualification manifest requires members")

        opaque_ids = tuple(member.benchmark_id for member in self.members)
        material_ids = tuple(member.material_identity for member in self.members)
        truth_hashes = tuple(member.truth_bundle_hash for member in self.members)
        structure_hashes = tuple(member.structure_hash for member in self.members)
        for values, label in (
            (opaque_ids, "opaque benchmark ids"),
            (material_ids, "material identities"),
            (truth_hashes, "truth-bundle hashes"),
            (structure_hashes, "structure hashes"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"sealed qualification manifest requires unique {label}")


@dataclass(frozen=True, kw_only=True)
class SealedQualificationValidation(Record):
    validation_version: str
    qualification_cohort_version: str
    benchmark_protocol_hash: str
    member_count: int
    role_counts: Mapping[str, int]
    external_sealed_state_validated: bool
    held_out_execution_authorized: bool = False
    production_search_authorized: bool = False

    def validate(self):
        super().validate()
        if self.validation_version != SEALED_QUALIFICATION_VALIDATION_VERSION:
            raise ValueError("unsupported sealed qualification validation version")
        if self.qualification_cohort_version != QUALIFICATION_COHORT_VERSION:
            raise ValueError("validation targets the wrong qualification cohort")
        require_hash(self.benchmark_protocol_hash)
        if self.member_count < 1:
            raise ValueError("sealed qualification validation requires members")
        if tuple(self.role_counts) != REQUIRED_ROLES:
            raise ValueError("sealed qualification validation role schema differs")
        if sum(self.role_counts.values()) != self.member_count:
            raise ValueError("sealed qualification validation role counts disagree")
        if self.external_sealed_state_validated is not True:
            raise ValueError("validation record requires external sealed state")
        if self.held_out_execution_authorized or self.production_search_authorized:
            raise ValueError("manifest validation alone authorizes no execution or production")


def load_external_sealed_qualification_manifest(
    path: Path,
    *,
    repo_root: Path,
) -> SealedQualificationCohortManifest:
    """Load secret cohort state only when it is physically outside the repository."""
    repo_root = repo_root.resolve()
    path = path.resolve()
    if path.is_relative_to(repo_root):
        raise ValueError("sealed qualification manifest must remain outside the repository")
    return SealedQualificationCohortManifest.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )


def validate_sealed_qualification_manifest(
    manifest: SealedQualificationCohortManifest,
    *,
    repair_plan: QualificationCohortRepairPlan,
    contaminated_v1_freeze: B3SplitFreeze,
) -> SealedQualificationValidation:
    """Validate the sealed cohort without returning any member-level secret state."""
    if repair_plan.contaminated_v1_split_freeze_hash != contaminated_v1_freeze.content_hash:
        raise ValueError("repair plan does not bind the supplied contaminated v1 freeze")
    if manifest.repair_plan_hash != repair_plan.content_hash:
        raise ValueError("sealed manifest does not bind the canonical repair plan")
    if manifest.benchmark_protocol_hash != repair_plan.benchmark_protocol_hash:
        raise ValueError("sealed manifest benchmark protocol differs from repair plan")

    public_v1_materials = {
        member.benchmark_id for member in contaminated_v1_freeze.members
    }
    reused = sorted(
        member.material_identity
        for member in manifest.members
        if member.material_identity in public_v1_materials
    )
    if reused:
        raise ValueError("replacement cohort reuses public v1 material identity")

    counts = Counter(member.truth_class for member in manifest.members)
    for role in REQUIRED_ROLES:
        if counts[role] < repair_plan.minimum_held_out_per_role[role]:
            raise ValueError("replacement cohort does not satisfy held-out role quotas")

    validation = SealedQualificationValidation(
        validation_version=SEALED_QUALIFICATION_VALIDATION_VERSION,
        qualification_cohort_version=manifest.qualification_cohort_version,
        benchmark_protocol_hash=manifest.benchmark_protocol_hash,
        member_count=len(manifest.members),
        role_counts={role: counts[role] for role in REQUIRED_ROLES},
        external_sealed_state_validated=True,
        held_out_execution_authorized=False,
        production_search_authorized=False,
    )
    validation.validate()
    return validation
