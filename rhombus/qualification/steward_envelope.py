"""Verify an identifier-free signed sealed-cohort preregistration handoff.

Only a host-provisioned trust store can authenticate issuer signatures.
A signature authenticates an assertion, not true physical material sampling.
Even EXTERNAL packets never grant scientific or statistical authorization.
"""
from __future__ import annotations

from rhombus.evidence.receipts import (
    ZERO_SHA256, bounded_text, digest, evidence_sha256, exact_fields, integer,
    verify_evidence_receipt,
)
from scripts.science.independent_material_study_feasibility import (
    plan_independent_material_study,
    IID_DESIGN,
)

SCHEMA = "rhombus-independent-steward-sealed-cohort-envelope-0143-v1"
MODEL_SHA256 = "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"
IDENTITY_SCHEME = "STEWARD_CANONICAL_MATERIAL_TOKEN_V1"
PRIVACY = "ONLY_HASHES_AND_COUNT_ASSERTIONS_NO_ROSTER_OR_TRUTH"
RESULT_SCHEMA = "rhombus-independent-steward-intake-review-0143-v1"


def verify_steward_preregistration(*, envelope, study_plan, receipts, trusted_issuers):
    """Authenticated chain review, strictly not cohort or scientific verification.

    The trusted_issuers mapping MUST be provisioned independently by the host;
    neither the public packet nor this verifier's output can create real trust.
    """
    exact_fields(
        envelope,
        (
            "schema_version", "scope", "evaluation_id", "evaluation_version",
            "model_sha256", "study_plan_sha256", "cohort_commitment_sha256",
            "identity_scheme", "privacy_policy", "development_group",
            "declared_independent_material_count",
            "declared_prospective_recruited_count", "outcome_policy",
        ),
        "sealed study envelope",
    )
    if envelope["schema_version"] != SCHEMA or envelope["scope"] not in (
        "SYNTHETIC", "EXTERNAL",
    ):
        raise ValueError("unsupported sealed envelope")
    for k in ("evaluation_id", "evaluation_version", "development_group"):
        bounded_text(envelope[k])
    if (envelope["model_sha256"] != MODEL_SHA256 or
        envelope["identity_scheme"] != IDENTITY_SCHEME or
        envelope["privacy_policy"] != PRIVACY or
        envelope["outcome_policy"] !=
            "ALL_ENROLLED_MATERIALS_INCLUDING_FAILED_UNKNOWN_ABSTAINED"):
        raise ValueError("model, cohort identity or full-outcome policy mismatch")
    digest(envelope["cohort_commitment_sha256"])
    digest(envelope["study_plan_sha256"])
    if not isinstance(study_plan, dict):
        raise ValueError("study plan must be object")
    plan = plan_independent_material_study(study_plan)
    if (
        plan["plan_status"] != "PLAN_ONLY_NOT_EVIDENCE"
        or study_plan["sampling_design"] != IID_DESIGN
        or envelope["study_plan_sha256"] != plan["validated_prospective_plan_sha256"]
    ):
        raise ValueError("unsupported or unbound prospective independent-material plan")
    asserted = integer(envelope["declared_independent_material_count"])
    recruited = integer(envelope["declared_prospective_recruited_count"])
    if (
        asserted < plan["independent_materials_needed_if_IID"]
        or recruited < asserted
        or recruited < plan["prospective_minimum_recruitment_if_IID"]
    ):
        raise ValueError("declared material count below prospective requirement")
    if not isinstance(trusted_issuers, dict) or not trusted_issuers:
        raise ValueError("host-provisioned independent public-key anchors required")
    if not isinstance(receipts, list) or len(receipts) != 2:
        raise ValueError("two independently bound signed receipts required")
    context = evidence_sha256(envelope)
    previous = ZERO_SHA256
    authorities = []
    for index, (role, event) in enumerate((
        ("steward", "cohort_preregistered"),
        ("witness", "cohort_commitment_witnessed"),
    ), start=1):
        receipt = receipts[index - 1]
        authority = verify_evidence_receipt(
            receipt,
            trusted_issuers=trusted_issuers,
            role=role,
            event=event,
            subject_sha256=context,
            context_sha256=context,
            scope=envelope["scope"],
        )
        if (
            receipt["previous_receipt_sha256"] != previous
            or receipt["sequence"] != index
            or authority.independence_group == envelope["development_group"]
        ):
            raise ValueError("unordered or developer-controlled preregistration chain")
        previous = evidence_sha256(receipt)
        authorities.append(authority)
    if (
        authorities[0].independence_group == authorities[1].independence_group
        or authorities[0].log_id != authorities[1].log_id
        or receipts[0]["log_id"] != receipts[1]["log_id"]
        or receipts[0]["issuer"] == receipts[1]["issuer"]
    ):
        raise ValueError("separate independent steward and witness required")
    return {
        "schema_version": RESULT_SCHEMA,
        "scope": envelope["scope"],
        "sealed_envelope_sha256": context,
        "bound_study_plan_sha256": plan["validated_prospective_plan_sha256"],
        "bound_model_sha256": MODEL_SHA256,
        "two_role_bound_signatures_cryptographically_verified": True,
        "claimed_material_count_not_independently_verified": asserted,
        "claimed_recruited_count_not_independently_verified": recruited,
        "new_private_cohort_source_independently_verified": False,
        "physical_material_independence_and_sampling_frame_verified": False,
        "external_parties_real_world_independence_verified": False,
        "experimental_phase_temperature_measurement_verified": False,
        "all_actual_material_outcomes_or_blind_truth_received": False,
        "actual_model_predictions_committed_before_truth": False,
        "mace_selected_training_frames_overlap_audited": False,
        "externally_qualified_independent_material_count": 0,
        "scientific_verdict": "INDETERMINATE",
        "P0_01_status": "BLOCKED",
        "P0_02_status": "BLOCKED",
        "P0_03_status": "BLOCKED",
        "scientific_release_authorized": False,
        "status": "SIGNED_PREREGISTRATION_ASSERTION_ONLY",
    }
