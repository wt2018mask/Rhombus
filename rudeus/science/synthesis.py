"""Evidence synthesis contracts (stage S).

Stage S combines an already-existing primary scientific assessment with
independent-model cross-check (X) and negative-control (N) evidence. It is a
pure reducer: it does not recompute upstream science, does not resolve conflicts
by averaging, and cannot upgrade the primary claim beyond its existing verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from rudeus.science.contracts import (
    ClaimAssessment,
    Record,
    Verdict,
    digest,
    require_hash,
)
from rudeus.science.negative_controls import NAssessment, NStatus
from rudeus.science.xcheck import XAssessment, XStatus


class SStatus(str, Enum):
    CONSISTENT = "CONSISTENT"
    CONFLICT = "CONFLICT"
    INDETERMINATE = "INDETERMINATE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, kw_only=True)
class SynthesisAssessment(Record):
    status: SStatus
    primary_claim_hash: str
    primary_assessment_hash: str
    primary_verdict: Verdict
    x_assessment_hashes: tuple[str, ...]
    n_assessment_hashes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    supporting_evidence: tuple[str, ...] = ()
    conflicting_evidence: tuple[str, ...] = ()
    unresolved_requirements: tuple[str, ...] = ()
    final_claim_verdict: Verdict = Verdict.UNKNOWN
    primary_verdict_changed: bool = False

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["status"] = SStatus(value["status"])
        value["primary_verdict"] = Verdict(value["primary_verdict"])
        value["final_claim_verdict"] = Verdict(value["final_claim_verdict"])
        return cls(**value)

    def validate(self):
        super().validate()
        SStatus(self.status)
        Verdict(self.primary_verdict)
        Verdict(self.final_claim_verdict)
        require_hash(self.primary_claim_hash)
        require_hash(self.primary_assessment_hash)
        for value in self.x_assessment_hashes + self.n_assessment_hashes:
            require_hash(value)
        for value in self.supporting_evidence + self.conflicting_evidence:
            require_hash(value)
        if self.primary_verdict_changed:
            raise ValueError("stage S must never rewrite the primary assessment")
        # Conservative monotonicity: S cannot improve the upstream claim.
        rank = {
            Verdict.FAIL: 0,
            Verdict.INDETERMINATE: 1,
            Verdict.UNKNOWN: 2,
            Verdict.PASS: 3,
        }
        if rank[self.final_claim_verdict] > rank[self.primary_verdict]:
            raise ValueError("stage S cannot upgrade the primary verdict")


def synthesize(
    primary: ClaimAssessment,
    *,
    x_assessments: Sequence[XAssessment] = (),
    n_assessments: Sequence[NAssessment] = (),
) -> SynthesisAssessment:
    """Reduce primary/X/N evidence without masking disagreement or falsification."""
    for x in x_assessments:
        if x.primary_verdict_changed:
            raise ValueError("invalid X input attempts to change primary verdict")
    for n in n_assessments:
        if n.target_verdict_changed:
            raise ValueError("invalid N input attempts to change target verdict")
        if n.target_claim_hash != primary.claim_hash:
            raise ValueError("N assessment targets a different claim")

    x_hashes = tuple(x.content_hash for x in x_assessments)
    n_hashes = tuple(n.content_hash for n in n_assessments)

    conflicting = list(primary.conflicting_evidence)
    supporting = list(primary.supporting_evidence)
    unresolved = list(primary.unresolved_requirements)
    reasons = []

    x_conflict = False
    x_blocked = False
    x_indeterminate = False
    for x in x_assessments:
        if x.status == XStatus.DISAGREEMENT:
            x_conflict = True
            conflicting.extend(x.conflicting_evidence)
            reasons.append("x_disagreement")
        elif x.status == XStatus.AGREEMENT:
            supporting.extend(x.supporting_evidence)
            reasons.append("x_agreement_support_only")
        elif x.status in (XStatus.BLOCKED_NOT_INDEPENDENT, XStatus.BLOCKED_SCOPE_MISMATCH):
            x_blocked = True
            reasons.append(f"x_{x.status.value.lower()}")
        else:
            x_indeterminate = True
            reasons.append("x_indeterminate")

    n_falsified = False
    n_blocked = False
    n_indeterminate = False
    for n in n_assessments:
        if n.status == NStatus.FALSIFIED:
            n_falsified = True
            conflicting.extend(n.conflicting_evidence)
            reasons.append("n_falsified")
        elif n.status == NStatus.CONTROL_PASSED:
            supporting.extend(n.control_evidence)
            reasons.append("n_control_passed_support_only")
        elif n.status == NStatus.BLOCKED_SCOPE_MISMATCH:
            n_blocked = True
            reasons.append("n_blocked_scope_mismatch")
        else:
            n_indeterminate = True
            reasons.append("n_indeterminate")

    if x_conflict or n_falsified or conflicting:
        status = SStatus.CONFLICT
        final = Verdict.FAIL if primary.verdict == Verdict.FAIL else Verdict.INDETERMINATE
        reasons.append("conflicting_evidence_requires_resolution")
    elif x_blocked or n_blocked:
        status = SStatus.BLOCKED
        final = primary.verdict if primary.verdict == Verdict.FAIL else Verdict.INDETERMINATE
        reasons.append("downstream_evidence_blocked")
    elif x_indeterminate or n_indeterminate:
        status = SStatus.INDETERMINATE
        final = primary.verdict if primary.verdict == Verdict.FAIL else Verdict.INDETERMINATE
        reasons.append("downstream_evidence_incomplete")
    else:
        status = SStatus.CONSISTENT
        final = primary.verdict
        reasons.append("no_downstream_conflict_detected")

    return SynthesisAssessment(
        status=status,
        primary_claim_hash=primary.claim_hash,
        primary_assessment_hash=primary.content_hash,
        primary_verdict=primary.verdict,
        x_assessment_hashes=x_hashes,
        n_assessment_hashes=n_hashes,
        reason_codes=tuple(dict.fromkeys(reasons)),
        supporting_evidence=tuple(dict.fromkeys(supporting)),
        conflicting_evidence=tuple(dict.fromkeys(conflicting)),
        unresolved_requirements=tuple(dict.fromkeys(unresolved)),
        final_claim_verdict=final,
        primary_verdict_changed=False,
    )


def s_record(
    primary: ClaimAssessment,
    *,
    x_assessments: Sequence[XAssessment] = (),
    n_assessments: Sequence[NAssessment] = (),
) -> dict[str, Any]:
    assessment = synthesize(
        primary,
        x_assessments=x_assessments,
        n_assessments=n_assessments,
    )
    return {
        "stage": "S",
        "primary": primary.to_dict(),
        "x_assessments": [x.to_dict() for x in x_assessments],
        "n_assessments": [n.to_dict() for n in n_assessments],
        "assessment": assessment.to_dict(),
    }


def verify_s_record(record: Mapping[str, Any]) -> dict[str, Any]:
    required = {"stage", "primary", "x_assessments", "n_assessments", "assessment"}
    if set(record) != required or record.get("stage") != "S":
        raise ValueError("invalid S record schema")

    primary = ClaimAssessment.from_dict(record["primary"])
    xs = tuple(XAssessment.from_dict(v) for v in record["x_assessments"])
    ns = tuple(NAssessment.from_dict(v) for v in record["n_assessments"])
    stored = SynthesisAssessment.from_dict(record["assessment"])
    replayed = synthesize(primary, x_assessments=xs, n_assessments=ns)
    if stored != replayed:
        raise ValueError("S assessment replay mismatch")

    return {
        "record": dict(record),
        "record_hash": digest(record),
        "status": replayed.status.value,
        "final_claim_verdict": replayed.final_claim_verdict.value,
        "primary_verdict_changed": False,
        "conflicting_evidence": list(replayed.conflicting_evidence),
    }
