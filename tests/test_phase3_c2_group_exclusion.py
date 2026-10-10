"""Synthetic public C2 group-exclusion diagnostics and adversarial no-leakage tests."""
from __future__ import annotations

import copy
import json

import pytest

from rhombus.qualification.group_exclusion import (
    SCHEMA, evaluate_group_exclusion, main,
)


def cohort():
    names = ["alpha", "beta", "gamma"]
    rows = [
        [
            ("m-a1", "POSITIVE", "POSITIVE", "SUCCEEDED"),
            ("m-a2", "NEGATIVE", "FAILED", "ERROR"),
        ], [
            ("m-b1", "BORDERLINE", "BORDERLINE", "SUCCEEDED"),
            ("m-b2", "POSITIVE", "UNKNOWN", "SUCCEEDED"),
        ], [
            ("m-c1", "NEGATIVE", "NEGATIVE", "SUCCEEDED"),
            ("m-c2", "BORDERLINE", "NONDIFFUSIVE", "SUCCEEDED"),
        ],
    ]
    groups = {}
    for name, entries in zip(names, rows):
        groups[name] = [
            {"material_id": mid, "observed_truth": truth,
             "predicted_outcome": pred, "operational_status": status}
            for mid, truth, pred, status in entries
        ]
    folds = []
    for i, name in enumerate(names):
        train = [g for g in names if g != name]
        folds.append({
            "held_out_group_id": name,
            "declared_training_group_ids": train,
            "declared_training_material_ids": sorted(
                mat["material_id"] for g in train for mat in groups[g]
            ),
            "fold_model_sha256": str(i + 1) * 64,
            "materials": groups[name],
        })
    return {
        "schema_version": SCHEMA,
        "scope": "PUBLIC_DIAGNOSTIC_ONLY",
        "method": "LOCO",
        "cohort_id": "synthetic-public-6",
        "model_family_id": "synthetic-model-not-mace",
        "folds": folds,
    }


def test_group_exclusion_all_materials_in_denominator():
    result = evaluate_group_exclusion(cohort())
    assert result["group_count"] == 3
    assert result["material_count"] == 6
    assert result["correct_count"] == 3
    assert result["diagnostic_correct_fraction"] == 0.5
    assert result["prediction_outcome_counts"]["FAILED"] == 1
    assert result["prediction_outcome_counts"]["UNKNOWN"] == 1
    assert result["prediction_outcome_counts"]["NONDIFFUSIVE"] == 1
    assert result["operational_status_counts"]["ERROR"] == 1
    assert [r["held_out_group_id"] for r in result["fold_results"]] == [
        "alpha", "beta", "gamma",
    ]
    assert all(r["excluded_training_group"] for r in result["fold_results"])
    assert all(r["declared_training_material_count"] == 4 for r in result["fold_results"])


@pytest.mark.parametrize("method", ["LOCO", "LOFO"])
def test_both_c2_methods_remain_scientifically_unqualified(method):
    c = cohort()
    c["method"] = method
    result = evaluate_group_exclusion(c)
    assert result["scientific_verdict"] == "INDETERMINATE"
    assert result["claim_authorized"] is False
    assert result["unseen_generalization_authorized"] is False
    assert result["actual_model_training_exclusion_independently_attested"] is False
    assert result["observed_materials_independently_sampled"] is False
    assert result["calibrated_error_estimate_available"] is False
    assert result["declared_material_exclusion_consistent"] is True
    assert result["per_fold_model_identity_distinct"] is True


def test_fold_order_does_not_change_material_metrics():
    c = cohort()
    original = evaluate_group_exclusion(c)
    c["folds"].reverse()
    c["folds"][0]["materials"].reverse()
    later = evaluate_group_exclusion(c)
    for key in ("fold_results", "material_count", "correct_count",
                "prediction_outcome_counts", "operational_status_counts"):
        assert later[key] == original[key]
    assert later["evaluation_input_sha256"] != original["evaluation_input_sha256"]


def test_outcome_failures_do_not_count_as_success():
    c = cohort()
    c["folds"][0]["materials"][0]["operational_status"] = "ERROR"
    with pytest.raises(ValueError, match="cannot report conclusive"):
        evaluate_group_exclusion(c)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["folds"][0].update(held_out_group_id="beta"),
        lambda c: c["folds"][1]["materials"][0].update(material_id="m-a1"),
        lambda c: c["folds"][0]["declared_training_group_ids"].append("alpha"),
        lambda c: c["folds"][0]["declared_training_group_ids"].remove("beta"),
        lambda c: c["folds"][0]["declared_training_material_ids"].append("m-a1"),
        lambda c: c["folds"][0]["declared_training_material_ids"].remove("m-b1"),
        lambda c: c["folds"][0]["declared_training_material_ids"].append("m-b1"),
        lambda c: c["folds"][0].update(fold_model_sha256="bad"),
        lambda c: c["folds"][1].update(fold_model_sha256=c["folds"][0]["fold_model_sha256"]),
        lambda c: c["folds"][0]["materials"][0].update(observed_truth="UNKNOWN"),
        lambda c: c["folds"][0]["materials"][0].update(predicted_outcome="PASS"),
        lambda c: c["folds"][0]["materials"][0].update(operational_status="RUNNING"),
        lambda c: c["folds"][0]["materials"][0].update(observed_truth=[]),
        lambda c: c.update(scope="EXTERNAL"),
        lambda c: c.update(method="K_FOLD"),
        lambda c: c["folds"][0]["materials"].clear(),
        lambda c: c["folds"][0].update(extra="unexpected"),
    ],
)
def test_adversarial_group_leakage_and_invalid_science_rejected(mutate):
    c = cohort()
    mutate(c)
    with pytest.raises(ValueError):
        evaluate_group_exclusion(c)


def test_public_diagnostic_must_have_two_folds():
    c = cohort()
    c["folds"] = c["folds"][:1]
    with pytest.raises(ValueError, match="at least two"):
        evaluate_group_exclusion(c)


def test_cli_json_report_is_deterministic(tmp_path, capsys):
    source = tmp_path / "cohort.json"
    source.write_text(json.dumps(cohort()), encoding="utf-8")
    assert main(["--evaluation-json", str(source)]) == 0
    a = json.loads(capsys.readouterr().out)
    assert main(["--evaluation-json", str(source)]) == 0
    b = json.loads(capsys.readouterr().out)
    assert a == b
    assert a["material_count"] == 6
    assert a["scientific_verdict"] == "INDETERMINATE"


@pytest.mark.parametrize("content", [
    '{"schema_version":"x","schema_version":"y"}',
    '{"scope":NaN}',
    '[]',
])
def test_cli_malformed_json_rejected(tmp_path, content):
    source = tmp_path / "bad.json"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["--evaluation-json", str(source)])


def test_cli_excessive_bytes_rejected(tmp_path):
    source = tmp_path / "large.json"
    source.write_bytes(b" " * (1024 * 1024 + 10))
    with pytest.raises(SystemExit):
        main(["--evaluation-json", str(source)])


def test_input_is_never_mutated():
    c = cohort()
    original = copy.deepcopy(c)
    evaluate_group_exclusion(c)
    assert c == original


def test_evaluation_id_binds_exact_input_without_matched_secret():
    c = cohort()
    original = evaluate_group_exclusion(c)
    c["folds"][0]["materials"][1]["predicted_outcome"] = "INDETERMINATE"
    updated = evaluate_group_exclusion(c)
    assert updated["evaluation_input_sha256"] != original["evaluation_input_sha256"]
