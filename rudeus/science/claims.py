"""Deterministic scoped claims; workers and schedulers cannot confer qualification."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from rudeus.science.contracts import (
    Record, ClaimSpec, Observation, Uncertainty, ClaimAssessment, Verdict,
    UNRESOLVED, digest, require_hash,
)


@dataclass(frozen=True, kw_only=True)
class QualificationRecord(Record):
    """Scientific registry entry, not a worker-provided `sufficient` flag.

    No production entry is shipped. Scientific qualification requires a scoped
    registered experiment and its evidence, independently reviewed/registered.
    """
    protocol_hash: str
    estimator: str
    uncertainty_method: str
    nominal_coverage: float
    scope: Mapping
    evidence_hashes: tuple[str, ...]
    requirements_hash: str
    estimator_version: str
    uncertainty_method_version: str
    status: str = UNRESOLVED

    def validate(self):
        super().validate()
        for value in (self.protocol_hash, self.requirements_hash) + self.evidence_hashes:
            require_hash(value)
        if not 0 < self.nominal_coverage < 1:
            raise ValueError("invalid qualification coverage")
        if not self.estimator_version or not self.uncertainty_method_version:
            raise ValueError("qualification must bind estimator and uncertainty versions")


def evaluate_claim(spec: ClaimSpec, observation: Observation | None,
                   uncertainty: Uncertainty | None = None, *, checks: Mapping | None = None,
                   qualification_registry: Mapping[str, QualificationRecord] | None = None,
                   conflicting_evidence: tuple[str, ...] = ()) -> ClaimAssessment:
    checks = dict(checks or {})
    unresolved = []
    verdict = Verdict.UNKNOWN
    reasons = []
    if spec.acceptance is None:
        reasons.append("acceptance_region_unresolved")
    elif observation is None:
        reasons.append("assessment_not_available")
    elif (observation.protocol_hash != spec.protocol_hash
          or observation.quantity != spec.estimand or observation.units != spec.units
          or any(observation.conditions.get(k) != v for k, v in spec.scope.items())
          or observation.observable_type not in spec.admissible_evidence):
        reasons.append("evidence_outside_claim_scope")
        verdict = Verdict.INDETERMINATE
    elif spec.acceptance.kind == "interval" and spec.uncertainty_requirements is None:
        reasons.append("uncertainty_requirements_unresolved")
    else:
        required = (spec.assumptions + spec.applicability_requirements
                    + spec.sufficiency_requirements + spec.independence_requirements)
        unresolved = [key for key in required if checks.get(key) is not True]
        if conflicting_evidence:
            reasons.append("conflicting_evidence_requires_resolution")
            verdict = Verdict.INDETERMINATE
        elif unresolved or not observation.artifact_hashes:
            reasons.append("prerequisites_not_established")
            verdict = Verdict.INDETERMINATE
        elif spec.acceptance.kind == "exact":
            if not isinstance(observation.value, bool):
                verdict = Verdict.INDETERMINATE
                reasons.append("exact_predicate_requires_boolean_evidence")
            else:
                verdict = Verdict.PASS if observation.value == spec.acceptance.expected else Verdict.FAIL
                reasons.append("exact_predicate")
        else:
            registry = qualification_registry or {}
            cert = registry.get(uncertainty.calibration_reference) if uncertainty else None
            qualified = bool(
                uncertainty and uncertainty.bounds is not None and cert
                and cert.content_hash == uncertainty.calibration_reference
                and cert.status == "QUALIFIED" and cert.evidence_hashes
                and cert.requirements_hash == digest(spec.uncertainty_requirements)
                and cert.protocol_hash == spec.protocol_hash
                and cert.estimator == observation.estimator
                and cert.estimator_version == observation.estimator_version
                and cert.uncertainty_method == uncertainty.method
                and cert.uncertainty_method_version == uncertainty.method_version
                and uncertainty.observation_hash == observation.content_hash
                and cert.nominal_coverage == uncertainty.nominal_coverage
                and dict(cert.scope) == dict(spec.scope)
                and not uncertainty.unavailable_reasons)
            if not qualified:
                verdict = Verdict.INDETERMINATE
                reasons.append("confidence_set_not_qualified")
            else:
                lo, hi = uncertainty.bounds
                lower, upper = spec.acceptance.lower, spec.acceptance.upper
                inside = (lower is None or lo >= lower) and (upper is None or hi <= upper)
                outside = (lower is not None and hi < lower) or (upper is not None and lo > upper)
                verdict = Verdict.PASS if inside else Verdict.FAIL if outside else Verdict.INDETERMINATE
                reasons.append("confidence_set_contained" if inside else "confidence_set_disjoint"
                               if outside else "confidence_set_overlaps")
    return ClaimAssessment(
        claim_id=spec.claim_id, claim_hash=spec.content_hash, protocol_hash=spec.protocol_hash,
        verdict=verdict, assumptions={k: checks.get(k) for k in spec.assumptions},
        applicability={k: checks.get(k) for k in spec.applicability_requirements},
        statistical_sufficiency={k: checks.get(k) for k in spec.sufficiency_requirements},
        reason_codes=tuple(reasons), unresolved_requirements=tuple(unresolved),
        supporting_evidence=observation.artifact_hashes if observation else (),
        conflicting_evidence=conflicting_evidence)


def final_claim_vector(mandatory: tuple[ClaimSpec, ...] | None,
                       assessments: tuple[ClaimAssessment, ...]) -> dict:
    if not mandatory:
        return {"verdict": "UNKNOWN", "reason": "mandatory_claim_set_undefined", "claims": []}
    if len({c.claim_id for c in mandatory}) != len(mandatory):
        raise ValueError("duplicate mandatory claim identity")
    rows = []
    for claim in sorted(mandatory, key=lambda c: c.claim_id):
        matches = {a.content_hash: a for a in assessments if a.claim_hash == claim.content_hash
                   and a.claim_id == claim.claim_id and a.protocol_hash == claim.protocol_hash}
        if len(matches) > 1:
            verdict, reason = Verdict.INDETERMINATE, "conflicting_assessments"
        elif matches:
            verdict, reason = next(iter(matches.values())).verdict, "assessed"
        else:
            verdict, reason = Verdict.UNKNOWN, "missing_assessment"
        rows.append({"claim_id": claim.claim_id, "claim_hash": claim.content_hash,
                     "verdict": Verdict(verdict).value, "reason": reason})
    verdicts = {r["verdict"] for r in rows}
    final = next(v for v in ("FAIL", "UNKNOWN", "INDETERMINATE", "PASS") if v in verdicts)
    return {"verdict": final, "claims": rows, "profile_hash": digest([c.content_hash for c in
            sorted(mandatory, key=lambda c: c.claim_id)])}
