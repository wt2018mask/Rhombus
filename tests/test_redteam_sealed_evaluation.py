from rhombus.qualification.sealed_evaluation import evaluate_sealed_materials


def test_self_reported_steward_cannot_authorize_evaluation():
    import pytest

    with pytest.raises(ValueError):
        evaluate_sealed_materials(
            protocol={}, predictions={}, truth={}, receipts=[], trusted_issuers={}
        )


import copy
from dataclasses import replace
import pytest

from rhombus.evidence.receipts import (
    evidence_sha256,
    read_evidence_json,
)
from rhombus.qualification.sealed_evaluation import (
    aggregate_material_outcome,
    wilson_material_interval,
    OUTCOMES,
)
from tests.redteam_batch_b_fixtures import sealed_fixture, reseal, receipt


def test_all_outcomes_are_retained_in_material_denominator():
    report = evaluate_sealed_materials(**sealed_fixture())
    assert report["material_count"] == 7
    assert report["outcome_counts"] == {o: 1 for o in OUTCOMES}
    assert report["correct_materials"] == 1
    assert report["conservative_fraction"] == 1 / 7
    assert report["precision_state"] == "UNDERPOWERED"
    assert not report["scientific_qualification_authorized"]
    assert not report["performance_claim_authorized"]


def test_repeated_trajectories_do_not_inflate_sample_size_or_precision():
    one = evaluate_sealed_materials(**sealed_fixture(repeated=1))
    repeated = evaluate_sealed_materials(**sealed_fixture(repeated=1000))
    assert one["wilson_interval"] == repeated["wilson_interval"]
    assert repeated["material_count"] == 7
    assert repeated["trajectory_count"] == 7000


@pytest.mark.parametrize(
    "outcomes,expected",
    [
        ([], "UNKNOWN"),
        (["POSITIVE", "FAILED"], "FAILED"),
        (["POSITIVE", "NEGATIVE"], "INDETERMINATE"),
        (["POSITIVE", "UNKNOWN"], "UNKNOWN"),
        (["NONDIFFUSIVE"], "NONDIFFUSIVE"),
    ],
)
def test_conservative_correlated_trajectory_aggregation(outcomes, expected):
    assert aggregate_material_outcome(outcomes) == expected


@pytest.mark.parametrize(
    "mutation",
    [
        "early_truth",
        "changed_prediction",
        "changed_protocol",
        "changed_truth",
        "duplicate_prediction",
        "duplicate_truth",
        "missing_result",
        "hidden_failure",
        "optimistic_label",
        "fabricated_claim",
        "bad_key",
        "same_steward",
        "developer_steward",
        "scope_promotion",
        "unsupported_interval",
        "insufficient_design",
        "wrong_model",
        "wrong_version",
    ],
)
def test_adversarial_evaluation_rejected(mutation):
    value = sealed_fixture()
    if mutation == "early_truth":
        value["receipts"][1], value["receipts"][2] = (
            value["receipts"][2],
            value["receipts"][1],
        )
    elif mutation == "changed_prediction":
        value["predictions"]["materials"][0]["trajectories"] = ["NEGATIVE"]
    elif mutation == "changed_protocol":
        value["protocol"]["statistical_plan"]["minimum_materials"] = 200
    elif mutation == "changed_truth":
        value["truth"]["materials"][0]["truth_outcome"] = "NEGATIVE"
    elif mutation == "bad_key":
        value["receipts"][0]["signature"] = "a" * 128
    elif mutation == "scope_promotion":
        value["protocol"]["scope"] = "EXTERNAL"
        reseal(value)
    else:
        if mutation == "duplicate_prediction":
            value["predictions"]["materials"][1] = copy.deepcopy(
                value["predictions"]["materials"][0]
            )
        elif mutation == "duplicate_truth":
            value["truth"]["materials"][1] = copy.deepcopy(
                value["truth"]["materials"][0]
            )
        elif mutation == "missing_result":
            value["predictions"]["materials"].pop()
        elif mutation == "hidden_failure":
            value["predictions"]["materials"][0]["trajectories"] = [
                "POSITIVE",
                "FAILED",
            ]
        elif mutation == "optimistic_label":
            value["predictions"]["materials"][3]["material_outcome"] = "NEGATIVE"
        elif mutation == "fabricated_claim":
            value["predictions"]["claimed_accuracy"] = 1.0
        elif mutation == "same_steward":
            value["trusted_issuers"]["witness"] = replace(
                value["trusted_issuers"]["witness"],
                independence_group=value["trusted_issuers"][
                    "steward"
                ].independence_group,
            )
        elif mutation == "developer_steward":
            value["trusted_issuers"]["steward"] = replace(
                value["trusted_issuers"]["steward"], independence_group="development"
            )
        elif mutation == "unsupported_interval":
            value["protocol"]["statistical_plan"]["confidence_level"] = 1.0
        elif mutation == "insufficient_design":
            value["protocol"]["statistical_plan"]["minimum_materials"] = 6
        elif mutation == "wrong_model":
            value["predictions"]["model_sha256"] = "b" * 64
        elif mutation == "wrong_version":
            value["truth"]["evaluation_version"] = "different-v2"
        reseal(value)  # Even authentic malformed assertions do not become valid.
    with pytest.raises(ValueError):
        evaluate_sealed_materials(**value)


def test_authoritative_training_overlap_fails_and_unsigned_claim_does_not_clear():
    value = sealed_fixture()
    context = evidence_sha256(value["protocol"])
    evidence = {
        "protocol_sha256": context,
        "model_sha256": value["protocol"]["model_sha256"],
        "identity_scheme": "STEWARD_CANONICAL_MATERIAL_TOKEN_V1",
        "training_material_tokens": ["synthetic-material-000"],
    }
    value["authoritative_overlap"] = {
        "evidence": evidence,
        "receipt": receipt(
            "auditor", "overlap_audited", evidence_sha256(evidence), context
        ),
    }
    with pytest.raises(ValueError, match="overlap"):
        evaluate_sealed_materials(**value)
    evidence["training_material_tokens"] = []
    with pytest.raises(ValueError, match="subject"):
        evaluate_sealed_materials(**value)


def test_mathematically_precise_synthetic_result_is_not_scientific_qualification():
    report = evaluate_sealed_materials(**sealed_fixture(["POSITIVE"] * 100))
    assert report["precision_state"] == "SATISFIED"
    assert not report["scientific_qualification_authorized"]
    assert not report["performance_claim_authorized"]
    lo, hi = wilson_material_interval(0, 100)
    assert lo == 0 and 0.03 < hi < 0.04


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b"{bad", b"\xff"])
def test_ambiguous_json_evidence_is_rejected(raw):
    with pytest.raises(ValueError):
        read_evidence_json(raw)


def test_dependent_or_unverified_materials_do_not_get_binomial_confidence():
    value = sealed_fixture(["POSITIVE"] * 100)
    value["protocol"]["statistical_plan"]["sampling_design"] = (
        "DEPENDENT_OR_UNVERIFIED_MATERIALS"
    )
    reseal(value)
    report = evaluate_sealed_materials(**value)
    assert report["wilson_interval"] is None
    assert report["interval_state"] == "NOT_DEFENSIBLE"
    assert report["precision_state"] == "UNDERPOWERED"
    assert not report["performance_claim_authorized"]


def test_cohort_salt_cannot_be_changed_after_preregistration():
    value = sealed_fixture()
    value["truth"]["cohort_nonce"] = "8" * 64
    reseal(value)
    with pytest.raises(ValueError, match="cohort commitment"):
        evaluate_sealed_materials(**value)
