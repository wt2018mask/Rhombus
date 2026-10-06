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
