"""Scientific C2: synthetic LOCO/LOFO contracts, fail-closed material accounting."""
from __future__ import annotations

import copy
import json

import pytest

from rhombus.qualification.group_exclusion import evaluate_group_exclusion, main


def cohort():
    return {
        "schema_version": "rhombus-group-exclusion-evaluation-v1",
        "scope": "PUBLIC_DIAGNOSTIC_ONLY",
        "method": "LOCO",
        "cohort_id": "test-only-public",
        "model_checkpoint_sha256": "a" * 64,
        "folds": [
            {
                "held_out_group_id": "family-a",
                "declared_training_group_ids": ["family-b"],
                "materials": [
                    {
                        "material_id": "test-only-material-1",
                        "observed_truth": "POSITIVE",
                        "predicted_outcome": "POSITIVE",
                        "operational_status": "SUCCEEDED",
                    },
                    {
                        "material_id": "test-only-material-2",
                        "observed_truth": "NEGATIVE",
                        "predicted_outcome": "FAILED",
                        "operational_status": "ERROR",
                    },
                ],
            },
            {
                "held_out_group_id": "family-b",
                "declared_training_group_ids": ["family-a"],
                "materials": [
                    {
                        "material_id": "test-only-material-3",
                        "observed_truth": "BORDERLINE",
                        "predicted_outcome": "INDETERMINATE",
                        "operational_status": "SUCCEEDED",
                    },
                    {
                        "material_id": "test-only-material-4",
                        "observed_truth": "NEGATIVE",
                        "predicted_outcome": "NONDIFFUSIVE",
                        "operational_status": "SUCCEEDED",
                    },
                ],
            },
        ],
    }


def test_material_denominator_includes_failed_indeterminate_nondiffusive():
    result = evaluate_group_exclusion(cohort())
    assert result["group_count"] == 2
    assert result["material_count"] == 4
    assert result["correct_count"] == 1
    assert result["diagnostic_correct_fraction"] == 0.25
    assert result["prediction_outcome_counts"]["FAILED"] == 1
    assert result["prediction_outcome_counts"]["INDETERMINATE"] == 1
    assert result["prediction_outcome_counts"]["NONDIFFUSIVE"] == 1
    assert result["operational_status_counts"]["ERROR"] == 1
    assert sum(result["prediction_outcome_counts"].values()) == 4
    assert result["fold_results"][0]["material_count"] == 2


def test_perfect_synthetic_split_is_still_not_scientific_pass():
    item = cohort()
    for fold in item["folds"]:
        for material in fold["materials"]:
            material["predicted_outcome"] = material["observed_truth"]
            material["operational_status"] = "SUCCEEDED"
    report = evaluate_group_exclusion(item)
    assert report["correct_count"] == 4
    assert report["scientific_verdict"] == "INDETERMINATE"
    assert report["unseen_generalization_authorized"] is False
    assert report["actual_model_training_exclusion_independently_attested"] is False
    assert report["calibrated_error_estimate_available"] is False


def test_loco_and_lofo_share_strict_group_exclusion_contract():
    sample = cohort()
    sample["method"] = "LOFO"
    report = evaluate_group_exclusion(sample)
    assert report["method"] == "LOFO"
    assert report["declared_group_exclusion_consistent"] is True
    assert report["material_count"] == 4


@pytest.mark.parametrize("tamper", [
    "training_contains_held_out",
    "training_missing_other_group",
    "duplicate_material",
    "duplicate_group",
    "duplicate_training",
    "empty_fold",
    "missing_fold",
    "unknown_group",
])
def test_group_leakage_and_incomplete_folds_rejected(tamper):
    sample = cohort()
    a, b = sample["folds"]
    if tamper == "training_contains_held_out":
        a["declared_training_group_ids"] = ["family-a", "family-b"]
    elif tamper == "training_missing_other_group":
        a["declared_training_group_ids"] = []
    elif tamper == "duplicate_material":
        b["materials"][0]["material_id"] = a["materials"][0]["material_id"]
    elif tamper == "duplicate_group":
        b["held_out_group_id"] = "family-a"
    elif tamper == "duplicate_training":
        a["declared_training_group_ids"] = ["family-b", "family-b"]
    elif tamper == "empty_fold":
        b["materials"] = []
    elif tamper == "missing_fold":
        sample["folds"].pop()
    elif tamper == "unknown_group":
        a["declared_training_group_ids"] = ["ghost"]
    with pytest.raises(ValueError):
        evaluate_group_exclusion(sample)


def test_failed_operation_cannot_report_positive_success():
    sample = cohort()
    sample["folds"][0]["materials"][0]["operational_status"] = "ERROR"
    with pytest.raises(ValueError, match="cannot report conclusive"):
        evaluate_group_exclusion(sample)


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(scope="EXTERNAL"),
    lambda x: x.update(scope="SEALED"),
    lambda x: x.update(method="RANDOM_CV"),
    lambda x: x.update(model_checkpoint_sha256="publisher-only"),
    lambda x: x["folds"][0]["materials"][0].update(predicted_outcome="SUCCESS"),
    lambda x: x["folds"][0]["materials"][0].update(observed_truth="UNKNOWN"),
    lambda x: x["folds"][0]["materials"][0].update(operator_command="do-something"),
])
def test_unsupported_scopes_models_truths_and_fields_rejected(mutation):
    data = cohort()
    mutation(data)
    with pytest.raises(ValueError):
        evaluate_group_exclusion(data)


def test_fold_order_changes_only_input_digest_not_material_counts():
    original = cohort()
    reordered = copy.deepcopy(original)
    reordered["folds"].reverse()
    first, second = evaluate_group_exclusion(original), evaluate_group_exclusion(reordered)
    assert first["fold_results"] == second["fold_results"]
    assert first["prediction_outcome_counts"] == second["prediction_outcome_counts"]
    assert first["evaluation_input_sha256"] != second["evaluation_input_sha256"]


def test_avoids_exposing_material_ids_in_aggregate_report():
    report = evaluate_group_exclusion(cohort())
    assert "test-only-material-" not in json.dumps(report)


def test_cli_can_report_offline_public_diagnostic(tmp_path, capsys):
    path = tmp_path / "public-cohort.json"
    path.write_text(json.dumps(cohort()), encoding="utf-8")
    assert main(["--evaluation-json", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["material_count"] == 4
    assert result["claim_authorized"] is False


def test_cli_rejects_duplicate_keys_and_nonfinite(tmp_path):
    for text in ('{"scope":"PUBLIC_DIAGNOSTIC_ONLY","scope":"EXTERNAL"}', '{"x":NaN}'):
        path = tmp_path / "bad.json"
        path.write_text(text)
        with pytest.raises(SystemExit):
            main(["--evaluation-json", str(path)])


def test_rejects_more_than_one_material_with_same_identity_across_groups():
    sample = cohort()
    sample["folds"][1]["materials"][1]["material_id"] = "test-only-material-2"
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_group_exclusion(sample)
