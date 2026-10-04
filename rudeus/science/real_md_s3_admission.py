"""Admission guards for real-MD S3 calibration.

This module is intentionally pure and side-effect free.  It does not run MD,
change P2/P2.5 verdicts, or confer statistical qualification.  Its only job is
to decide whether persisted upstream evidence is admissible to the real-MD S3
calibration population.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


REAL_MD_DOMAIN = "real-md"
BROWNIAN_SYNTHETIC_DOMAIN = "brownian-synthetic"

ADMISSION_ELIGIBLE = "ELIGIBLE"
ADMISSION_INELIGIBLE = "INELIGIBLE"
ADMISSION_BLOCKED = "BLOCKED"

POPULATION_READY = "READY"
POPULATION_BLOCKED = "BLOCKED_NEEDS_DIFFUSIVE_CANDIDATE"


@dataclass(frozen=True)
class RealMDS3Admission:
    """Immutable admission decision for one persisted candidate."""

    eligible: bool
    status: str
    evidence_role: str
    reasons: tuple[str, ...]
    candidate_material_id: str | None
    batch_id: str | None
    p2_verdict: str | None
    p25_verdict: str | None
    transport_state: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "status": self.status,
            "evidence_role": self.evidence_role,
            "reasons": list(self.reasons),
            "candidate_material_id": self.candidate_material_id,
            "batch_id": self.batch_id,
            "p2_verdict": self.p2_verdict,
            "p25_verdict": self.p25_verdict,
            "transport_state": self.transport_state,
        }


def _result(document: Mapping[str, Any]) -> Mapping[str, Any]:
    value = document.get("result", document)
    return value if isinstance(value, Mapping) else {}


def assess_real_md_s3_admission(
    p2: Mapping[str, Any],
    p25: Mapping[str, Any],
    *,
    integrity_ok: bool = True,
    execution_ok: bool = True,
) -> RealMDS3Admission:
    """Classify one candidate for real-MD S3 calibration admission.

    Admission requires all of:
    - execution and integrity checks succeeded;
    - P2 and P2.5 documents identify the same candidate/batch when both fields
      are available;
    - P2 verdict is PASS;
    - P2.5 verdict and transport_state are both DIFFUSIVE.

    NONDIFFUSIVE evidence is retained as a negative-control role, but it is not
    a calibration member.  INDETERMINATE/NOT_RUN and upstream P2 non-PASS
    states are simply ineligible.  Integrity/execution problems are BLOCKED and
    are never converted into a material verdict.
    """

    p2r = _result(p2)
    p25r = _result(p25)

    candidate_p2 = p2r.get("candidate_material_id")
    candidate_p25 = p25r.get("candidate_material_id")
    batch_p2 = p2r.get("batch_id", p2.get("batch_id"))
    batch_p25 = p25r.get("batch_id", p25.get("batch_id"))

    candidate = candidate_p25 or candidate_p2
    batch_id = batch_p25 or batch_p2
    p2_verdict = p2r.get("p2_verdict")
    p25_verdict = p25r.get("p25_verdict")
    transport_state = p25r.get("transport_state")

    blocked: list[str] = []
    if not integrity_ok:
        blocked.append("integrity_failure")
    if not execution_ok:
        blocked.append("execution_failure")
    if candidate_p2 and candidate_p25 and candidate_p2 != candidate_p25:
        blocked.append("candidate_identity_mismatch")
    if batch_p2 and batch_p25 and batch_p2 != batch_p25:
        blocked.append("batch_identity_mismatch")
    if p25_verdict is not None and transport_state is not None and p25_verdict != transport_state:
        blocked.append("p25_transport_state_mismatch")

    if blocked:
        return RealMDS3Admission(
            eligible=False,
            status=ADMISSION_BLOCKED,
            evidence_role="excluded",
            reasons=tuple(blocked),
            candidate_material_id=candidate,
            batch_id=batch_id,
            p2_verdict=p2_verdict,
            p25_verdict=p25_verdict,
            transport_state=transport_state,
        )

    reasons: list[str] = []
    if p2_verdict != "PASS":
        reasons.append("p2_not_pass")

    if p25_verdict != "DIFFUSIVE" or transport_state != "DIFFUSIVE":
        reasons.append("p25_not_diffusive")

    if not reasons:
        return RealMDS3Admission(
            eligible=True,
            status=ADMISSION_ELIGIBLE,
            evidence_role="calibration_candidate",
            reasons=(),
            candidate_material_id=candidate,
            batch_id=batch_id,
            p2_verdict=p2_verdict,
            p25_verdict=p25_verdict,
            transport_state=transport_state,
        )

    role = (
        "negative_control"
        if p2_verdict == "PASS"
        and p25_verdict == "NONDIFFUSIVE"
        and transport_state == "NONDIFFUSIVE"
        else "excluded"
    )
    return RealMDS3Admission(
        eligible=False,
        status=ADMISSION_INELIGIBLE,
        evidence_role=role,
        reasons=tuple(reasons),
        candidate_material_id=candidate,
        batch_id=batch_id,
        p2_verdict=p2_verdict,
        p25_verdict=p25_verdict,
        transport_state=transport_state,
    )


def qualification_domain_compatible(source_domain: str, target_domain: str) -> bool:
    """Return True only for exact registered-domain matches.

    In particular, a Brownian/synthetic qualification can never authorize a
    real-MD uncertainty bound.
    """

    return bool(source_domain) and source_domain == target_domain


def interim_artifact_allows_final_s3(artifact: Mapping[str, Any]) -> bool:
    """Return whether an artifact explicitly carries all final claim scopes.

    This is deliberately fail-closed.  A feasibility/interim artifact cannot
    become final merely because it contains a numerical diffusion estimate.
    """

    scope = artifact.get("claim_scope")
    if not isinstance(scope, Mapping):
        return False
    required = (
        "stage1_final_qualification",
        "diffusion_coefficient_qualified",
        "uncertainty_transfer_qualified",
    )
    return all(scope.get(key) is True for key in required)


def summarize_real_md_s3_population(
    candidates: Iterable[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> dict[str, Any]:
    """Summarize whether a candidate collection can start real-MD S3 work."""

    decisions = [assess_real_md_s3_admission(p2, p25) for p2, p25 in candidates]
    eligible = [d for d in decisions if d.eligible]
    return {
        "status": POPULATION_READY if eligible else POPULATION_BLOCKED,
        "n_candidates": len(decisions),
        "n_eligible": len(eligible),
        "n_negative_controls": sum(d.evidence_role == "negative_control" for d in decisions),
        "eligible_candidate_material_ids": [
            d.candidate_material_id for d in eligible if d.candidate_material_id is not None
        ],
        "decisions": [d.to_dict() for d in decisions],
    }
