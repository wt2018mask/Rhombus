"""Sealed material evaluation: authenticated ordering and conservative statistics.

Only synthetic cohorts belong in the public repository. Real opaque identifiers,
truth and stewardship keys stay with independently governed external systems.
All results are diagnostic; this module never grants scientific qualification.
"""

from __future__ import annotations

import math
from statistics import NormalDist

from rhombus.evidence.receipts import (
    ZERO_SHA256,
    bounded_text,
    digest,
    evidence_sha256,
    exact_fields,
    integer,
    verify_evidence_receipt,
)

OUTCOMES = (
    "POSITIVE",
    "NEGATIVE",
    "BORDERLINE",
    "UNKNOWN",
    "FAILED",
    "INDETERMINATE",
    "NONDIFFUSIVE",
)
SCHEMA = "rhombus-sealed-material-evaluation-v1"
MAX_MATERIALS = 100_000


def aggregate_material_outcome(trajectories):
    """Repeated/correlated trajectories never become extra statistical units."""
    if (
        not isinstance(trajectories, list)
        or len(trajectories) > 10_000
        or any(v not in OUTCOMES for v in trajectories)
    ):
        raise ValueError("invalid trajectory outcomes")
    for adverse in ("FAILED", "INDETERMINATE", "UNKNOWN"):
        if adverse in trajectories:
            return adverse
    if not trajectories:
        return "UNKNOWN"
    return trajectories[0] if len(set(trajectories)) == 1 else "INDETERMINATE"


def wilson_material_interval(successes, total, confidence_level=0.95):
    integer(total, high=MAX_MATERIALS)
    integer(successes, low=0, high=total)
    if (
        type(confidence_level) not in (int, float)
        or not 0.8 <= confidence_level <= 0.99
    ):
        raise ValueError("unsupported confidence level")
    z = NormalDist().inv_cdf((1 + confidence_level) / 2)
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = (
        z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    )
    return [max(0.0, center - radius), min(1.0, center + radius)]


def _validate_protocol(protocol):
    exact_fields(
        protocol,
        (
            "schema_version",
            "evaluation_id",
            "evaluation_version",
            "model_sha256",
            "cohort_commitment_sha256",
            "scope",
            "development_group",
            "statistical_plan",
        ),
        "sealed protocol",
    )
    if protocol["schema_version"] != SCHEMA or protocol["scope"] not in (
        "SYNTHETIC",
        "EXTERNAL",
    ):
        raise ValueError("unsupported sealed protocol")
    for key in ("evaluation_id", "evaluation_version", "development_group"):
        bounded_text(protocol[key])
    for key in ("model_sha256", "cohort_commitment_sha256"):
        digest(protocol[key])
    plan = protocol["statistical_plan"]
    exact_fields(
        plan,
        (
            "unit",
            "minimum_materials",
            "confidence_level",
            "maximum_half_width",
            "precision_justification",
            "aggregation",
            "metric",
            "outcomes",
            "sampling_design",
        ),
        "statistical plan",
    )
    if (
        plan["unit"] != "MATERIAL"
        or plan["aggregation"] != "CONSERVATIVE_UNANIMITY"
        or plan["metric"] != "CORRECT_FRACTION_ALL_MATERIALS"
        or plan["outcomes"] != list(OUTCOMES)
    ):
        raise ValueError("unsupported material accounting")
    if plan["sampling_design"] not in (
        "IID_MATERIALS",
        "DEPENDENT_OR_UNVERIFIED_MATERIALS",
    ):
        raise ValueError("unsupported material sampling design")
    integer(plan["minimum_materials"], high=MAX_MATERIALS)
    bounded_text(plan["precision_justification"])
    confidence, width = plan["confidence_level"], plan["maximum_half_width"]
    if type(confidence) not in (int, float) or not 0.8 <= confidence <= 0.99:
        raise ValueError("unsupported confidence level")
    if type(width) not in (int, float) or not 0 < width < 0.5:
        raise ValueError("invalid precision target")
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    required = max(1, math.ceil(z * z / (4 * width * width) - z * z))
    if plan["minimum_materials"] < required:
        raise ValueError("fabricated sample-size precision justification")


def evaluate_sealed_materials(
    *,
    protocol,
    predictions,
    truth,
    receipts,
    trusted_issuers,
    authoritative_overlap=None,
):
    _validate_protocol(protocol)
    context = evidence_sha256(protocol)
    exact_fields(
        predictions,
        ("protocol_sha256", "evaluation_version", "model_sha256", "materials"),
        "predictions",
    )
    exact_fields(
        truth,
        ("protocol_sha256", "evaluation_version", "materials", "cohort_nonce"),
        "truth",
    )
    digest(truth["cohort_nonce"])
    for payload in (predictions, truth):
        if (
            payload["protocol_sha256"] != context
            or payload["evaluation_version"] != protocol["evaluation_version"]
        ):
            raise ValueError("evaluation protocol/version mismatch")
    if predictions["model_sha256"] != protocol["model_sha256"]:
        raise ValueError("prediction model mismatch")
    if not isinstance(receipts, list) or len(receipts) != 3:
        raise ValueError("independent ordered receipts required")
    stages = [
        ("steward", "preregistered", context),
        ("witness", "predictions_committed", evidence_sha256(predictions)),
        ("steward", "truth_released", evidence_sha256(truth)),
    ]
    prior = ZERO_SHA256
    sequence = 0
    authorities = []
    for receipt, (role, event, subject) in zip(receipts, stages):
        issuer = verify_evidence_receipt(
            receipt,
            trusted_issuers=trusted_issuers,
            role=role,
            event=event,
            subject_sha256=subject,
            context_sha256=context,
            scope=protocol["scope"],
        )
        if (
            receipt["previous_receipt_sha256"] != prior
            or receipt["sequence"] <= sequence
        ):
            raise ValueError("ground truth/commitment ordering invalid")
        if issuer.independence_group == protocol["development_group"]:
            raise ValueError("development party is not an independent steward/witness")
        prior, sequence = evidence_sha256(receipt), receipt["sequence"]
        authorities.append(issuer)
    if (
        authorities[0] != authorities[2]
        or authorities[0].independence_group == authorities[1].independence_group
        or len({r["log_id"] for r in receipts}) != 1
    ):
        raise ValueError("independent stewardship and witnessed event log required")
    cohort = {}
    if (
        not isinstance(truth["materials"], list)
        or not 1 <= len(truth["materials"]) <= MAX_MATERIALS
    ):
        raise ValueError("invalid truth cohort")
    for row in truth["materials"]:
        exact_fields(row, ("material_token", "truth_outcome"), "truth row")
        token = bounded_text(row["material_token"])
        if token in cohort or row["truth_outcome"] not in OUTCOMES:
            raise ValueError("duplicate material or invalid truth outcome")
        cohort[token] = row["truth_outcome"]
    if (
        evidence_sha256(
            {"material_tokens": sorted(cohort), "nonce": truth["cohort_nonce"]}
        )
        != protocol["cohort_commitment_sha256"]
    ):
        raise ValueError("cohort commitment mismatch")
    predicted = {}
    if not isinstance(predictions["materials"], list) or len(
        predictions["materials"]
    ) != len(cohort):
        raise ValueError("missing results/unreported failures")
    for row in predictions["materials"]:
        exact_fields(
            row,
            ("material_token", "trajectories", "material_outcome"),
            "prediction row",
        )
        token = bounded_text(row["material_token"])
        if token in predicted or token not in cohort:
            raise ValueError("duplicate or unexpected material")
        actual = aggregate_material_outcome(row["trajectories"])
        if row["material_outcome"] != actual:
            raise ValueError("optimistic material outcome relabeling")
        predicted[token] = actual
    blockers = [
        "INDEPENDENT_SCIENTIFIC_QUALIFICATION_NOT_GRANTED",
        "MODEL_BIAS_AND_TEMPERATURE_TRANSFER_UNATTESTED",
    ]
    if authoritative_overlap is None:
        blockers.append("TRAINING_EVALUATION_OVERLAP_UNATTESTED")
    else:
        exact_fields(
            authoritative_overlap, ("evidence", "receipt"), "authoritative overlap"
        )
        overlap = authoritative_overlap["evidence"]
        exact_fields(
            overlap,
            (
                "protocol_sha256",
                "model_sha256",
                "identity_scheme",
                "training_material_tokens",
            ),
            "overlap evidence",
        )
        if (
            overlap["protocol_sha256"] != context
            or overlap["model_sha256"] != protocol["model_sha256"]
            or overlap["identity_scheme"] != "STEWARD_CANONICAL_MATERIAL_TOKEN_V1"
        ):
            raise ValueError("overlap identity binding mismatch")
        tokens = overlap["training_material_tokens"]
        if (
            not isinstance(tokens, list)
            or len(tokens) > MAX_MATERIALS
            or len(set(tokens)) != len(tokens)
        ):
            raise ValueError("invalid authoritative training tokens")
        for token in tokens:
            bounded_text(token)
        authority = verify_evidence_receipt(
            authoritative_overlap["receipt"],
            trusted_issuers=trusted_issuers,
            role="lineage_auditor",
            event="overlap_audited",
            subject_sha256=evidence_sha256(overlap),
            context_sha256=context,
            scope=protocol["scope"],
        )
        if (
            authority.independence_group == protocol["development_group"]
            or set(tokens) & cohort.keys()
        ):
            raise ValueError("training/evaluation overlap or nonindependent auditor")
    counts = {
        outcome: sum(value == outcome for value in predicted.values())
        for outcome in OUTCOMES
    }
    correct = sum(
        predicted[token] == label and label in OUTCOMES[:3]
        for token, label in cohort.items()
    )
    iid = protocol["statistical_plan"]["sampling_design"] == "IID_MATERIALS"
    interval = (
        wilson_material_interval(
            correct, len(cohort), protocol["statistical_plan"]["confidence_level"]
        )
        if iid
        else None
    )
    precise = (
        iid
        and len(cohort) >= protocol["statistical_plan"]["minimum_materials"]
        and (interval[1] - interval[0]) / 2
        <= protocol["statistical_plan"]["maximum_half_width"]
    )
    if not precise:
        blockers.append("MATERIAL_SAMPLE_SIZE_OR_PRECISION_UNSATISFIED")
    if not iid:
        blockers.append("INDEPENDENCE_OR_SAMPLING_MODEL_UNATTESTED")
    if protocol["scope"] == "SYNTHETIC":
        blockers.append("SYNTHETIC_FIXTURE_NOT_INDEPENDENT_SCIENCE")
    return {
        "schema_version": "rhombus-sealed-material-report-v1",
        "protocol_sha256": context,
        "scope": protocol["scope"],
        "material_count": len(cohort),
        "trajectory_count": sum(
            len(r["trajectories"]) for r in predictions["materials"]
        ),
        "outcome_counts": counts,
        "truth_counts": {o: sum(v == o for v in cohort.values()) for o in OUTCOMES},
        "correct_materials": correct,
        "conservative_fraction": correct / len(cohort),
        "wilson_interval": interval,
        "interval_state": "APPROXIMATE_BINOMIAL_CONDITIONAL_ON_IID"
        if iid
        else "NOT_DEFENSIBLE",
        "confidence_level": protocol["statistical_plan"]["confidence_level"],
        "precision_state": "SATISFIED" if precise else "UNDERPOWERED",
        "interval_assumption": "INDEPENDENT_MATERIAL_BERNOULLI_OUTCOMES_NOT_TRAJECTORIES",
        "external_assertions_authenticated": protocol["scope"] == "EXTERNAL",
        "scientific_verdict": "INDETERMINATE",
        "scientific_qualification_authorized": False,
        "performance_claim_authorized": False,
        "blockers": blockers,
    }
