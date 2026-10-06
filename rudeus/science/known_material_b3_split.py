"""B3 authorization contract for freezing an immutable DEV/HELD_OUT split.

B2 remains evidence-only and never authorizes B3 itself.  This module is the
explicit transition gate: it can authorize split construction only from a
fresh zero-blocker B2 audit plus the canonical satisfied pre-split role-count
assessment.  It does not assign split membership.
"""
from __future__ import annotations

from dataclasses import dataclass

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_b2_coverage import B2CoverageAudit
from rudeus.science.known_material_sample_size import (
    SampleSizeAssessment,
    SampleSizeAssessmentState,
)


B3_SPLIT_AUTHORIZATION_VERSION = "known-material-b3-split-authorization-v1"


@dataclass(frozen=True, kw_only=True)
class B3SplitAuthorization(Record):
    authorization_version: str
    b2_audit_hash: str
    sample_size_assessment_hash: str
    authorized: bool
    reason_codes: tuple[str, ...]
    split_membership_assigned: bool = False

    def validate(self):
        super().validate()
        if self.authorization_version != B3_SPLIT_AUTHORIZATION_VERSION:
            raise ValueError("unsupported B3 split-authorization version")
        require_hash(self.b2_audit_hash)
        require_hash(self.sample_size_assessment_hash)
        if self.authorized is not True:
            raise ValueError("B3 authorization record may only freeze an authorized transition")
        if self.reason_codes != ("B2_ZERO_BLOCKERS", "MINIMUM_ROLE_COUNTS_SATISFIED"):
            raise ValueError("B3 authorization requires the canonical transition reasons")
        if self.split_membership_assigned is not False:
            raise ValueError("authorization must precede immutable split assignment")


def authorize_b3_split(
    audit: B2CoverageAudit,
    sample_size: SampleSizeAssessment,
) -> B3SplitAuthorization:
    if audit.global_blockers:
        raise ValueError("B3 split cannot be authorized while B2 blockers remain")
    if sample_size.state != SampleSizeAssessmentState.SATISFIED.value:
        raise ValueError("B3 split requires satisfied pre-split role counts")
    if any(sample_size.required_additional_scoreable_per_role.values()):
        raise ValueError("B3 split requires zero pre-split role deficits")
    return B3SplitAuthorization(
        authorization_version=B3_SPLIT_AUTHORIZATION_VERSION,
        b2_audit_hash=audit.content_hash,
        sample_size_assessment_hash=sample_size.content_hash,
        authorized=True,
        reason_codes=("B2_ZERO_BLOCKERS", "MINIMUM_ROLE_COUNTS_SATISFIED"),
    )


B3_SPLIT_FREEZE_VERSION = "known-material-b3-split-freeze-v1"


@dataclass(frozen=True, kw_only=True)
class B3SplitMember(Record):
    benchmark_id: str
    split: str
    truth_bundle_hash: str

    def validate(self):
        super().validate()
        if not self.benchmark_id:
            raise ValueError("split member requires benchmark id")
        if self.split not in {"DEV", "HELD_OUT"}:
            raise ValueError("split must be DEV or HELD_OUT")
        require_hash(self.truth_bundle_hash)


@dataclass(frozen=True, kw_only=True)
class B3SplitFreeze(Record):
    freeze_version: str
    authorization_hash: str
    assignment_method: str
    members: tuple[B3SplitMember, ...]

    def validate(self):
        super().validate()
        if self.freeze_version != B3_SPLIT_FREEZE_VERSION:
            raise ValueError("unsupported B3 split-freeze version")
        require_hash(self.authorization_hash)
        if self.assignment_method != "ROLE_STRATIFIED_TRUTH_BUNDLE_HASH_ASCENDING":
            raise ValueError("unsupported split assignment method")
        ids = [member.benchmark_id for member in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError("split freeze requires unique benchmark ids")


def freeze_b3_split(
    authorization: B3SplitAuthorization,
    role_to_bundle_hashes: dict[str, tuple[tuple[str, str], ...]],
) -> B3SplitFreeze:
    """Freeze one DEV and one HELD_OUT member per benchmark role.

    Within each role, members are sorted by frozen truth-bundle content hash,
    then benchmark id as a deterministic tie-breaker.  The first becomes DEV
    and the second HELD_OUT.  Exactly two scoreable members per role are
    required by this v1 freeze so later evidence cannot silently reshuffle the
    original held-out cohort.
    """
    if not authorization.authorized:
        raise ValueError("split freeze requires B3 authorization")
    expected_roles = {"POSITIVE", "NEGATIVE", "BORDERLINE"}
    if set(role_to_bundle_hashes) != expected_roles:
        raise ValueError("split freeze requires positive/negative/borderline roles")

    members: list[B3SplitMember] = []
    for role in sorted(expected_roles):
        candidates = role_to_bundle_hashes[role]
        if len(candidates) != 2:
            raise ValueError("B3 v1 freeze requires exactly two scoreable members per role")
        ordered = sorted(candidates, key=lambda item: (item[1], item[0]))
        for split, (benchmark_id, bundle_hash) in zip(("DEV", "HELD_OUT"), ordered):
            require_hash(bundle_hash)
            members.append(
                B3SplitMember(
                    benchmark_id=benchmark_id,
                    split=split,
                    truth_bundle_hash=bundle_hash,
                )
            )

    return B3SplitFreeze(
        freeze_version=B3_SPLIT_FREEZE_VERSION,
        authorization_hash=authorization.content_hash,
        assignment_method="ROLE_STRATIFIED_TRUTH_BUNDLE_HASH_ASCENDING",
        members=tuple(members),
    )
