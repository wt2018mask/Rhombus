"""0147 fixed RF/MLP scientific baseline tests; all source data is synthetic here."""
import copy
import json
import math

import numpy as np
import pytest

from scripts.science.obelix_real_grouped_oof_0146 import (
    evaluate_original_obelix_train,
)
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import (
    SCHEMA, RF_PARAMS, MLP_PARAMS, _group_metrics, evaluate_frozen_baselines,
)
from tests.test_phase3_obelix_real_grouped_oof_0146 import fixture


def synthetic_evaluation():
    records, labels = fixture()
    return evaluate_original_obelix_train(
        records, labels, strict_official=False, return_internal=True,
    )


def test_existing_0146_report_is_unchanged_when_not_requesting_ephemeral_arrays():
    records, labels = fixture()
    old = evaluate_original_obelix_train(records, labels, strict_official=False)
    shared, internal = evaluate_original_obelix_train(
        records, labels, strict_official=False, return_internal=True,
    )
    assert old == shared
    assert internal["x"].shape == (35,118)
    assert internal["y"].shape == (35,)
    assert len(internal["fold_indices"]) == 5
    assert np.isfinite(internal["ridge_oof"]).all()
    assert np.isfinite(internal["mean_oof"]).all()


def test_real_ridge_and_mean_from_prior_frozen_folds_remain_exact():
    prior, internal = synthetic_evaluation()
    report = evaluate_frozen_baselines(prior, internal)
    assert report["schema_version"] == SCHEMA
    assert report["real_out_of_fold_source_record_predictions_per_model"] == 35
    assert report["source_DOI_formula_connected_groups_scored"] == 35
    assert report["original_official_test_reserved_unread"] == 1
    assert report["original_paper_baseline_protocol_exactly_reproduced"] is False
    assert report["upstream_publication_has_different_features_and_hyperparameter_search"] is True
    assert report["out_of_fold_metrics"]["ridge_0146"]["log10_MAE"] == prior["trained_ridge_oof_metrics"]["log10_MAE"]
    assert report["out_of_fold_metrics"]["training_fold_mean_0146"]["log10_MAE"] == prior["training_fold_mean_oof_metrics"]["log10_MAE"]
    for key in ("random_forest","mlp","ridge_0146","training_fold_mean_0146"):
        v = report["out_of_fold_metrics"][key]
        assert math.isfinite(v["log10_MAE"])
        assert math.isfinite(v["log10_RMSE"])
        assert math.isfinite(v["macro_group_log10_MAE"])
        assert v["group_count"] == 35
        assert v["source_record_out_of_fold_count"] == 35
        assert v["bootstrap_scope"] == "HEURISTIC_SHARED_DOI_FORMULA_GROUPS_NOT_IID_PHYSICAL_SAMPLES"
    assert report["official_public_TEST_predictions"] == 0
    assert report["P0_01_status"] == report["P0_02_status"] == report["P0_03_status"] == "BLOCKED"
    assert report["scientific_qualification_authorized"] is False
    assert report["independent_physical_material_count"] is None
    assert all(f["group_leakage_count"] == 0 for f in report["fold_metrics"])


def test_same_model_seed_folds_gives_bitwise_reproducible_report():
    prior, internal = synthetic_evaluation()
    a = evaluate_frozen_baselines(prior, internal)
    b = evaluate_frozen_baselines(prior, internal)
    assert a == b


def test_all_original_group_assignments_kept_and_identity_leak_fails():
    prior, internal = synthetic_evaluation()
    bad = dict(internal)
    folds = list(internal["fold_indices"])
    folds[0] = np.asarray(list(folds[0]) + [int(folds[1][0])], dtype=int)
    bad["fold_indices"] = tuple(folds)
    with pytest.raises(ValueError, match="already evaluated|fold identity"):
        evaluate_frozen_baselines(prior, bad)


def test_group_spanning_two_folds_is_rejected_even_if_heldout_lengths_same():
    prior, internal = synthetic_evaluation()
    bad = dict(internal)
    groups = list(internal["groups"])
    a = int(internal["fold_indices"][0][0])
    b = int(internal["fold_indices"][1][0])
    groups[b] = groups[a]
    bad["groups"] = tuple(groups)
    with pytest.raises(ValueError, match="groups drift|leaked"):
        evaluate_frozen_baselines(prior, bad)


def test_heldout_source_label_not_used_for_training_predictions():
    prior, internal = synthetic_evaluation()
    i = int(internal["fold_indices"][0][0])
    altered = dict(internal)
    altered["y"] = internal["y"].copy()
    altered["y"][i] = float(altered["y"][i]) + 4
    # The original 0146 ridge/mean reference becomes incompatible, so the
    # only valid consequence is fail-closed, not silently retune heldout data.
    with pytest.raises(ValueError, match="prior actual|prior actual source"):
        evaluate_frozen_baselines(prior, altered)


def test_missing_source_rows_and_invalid_features_denied():
    prior, internal = synthetic_evaluation()
    bad = dict(internal)
    bad["x"] = internal["x"].copy()
    bad["x"][0,0] = float("nan")
    with pytest.raises(ValueError, match="invalid frozen"):
        evaluate_frozen_baselines(prior, bad)
    bad = dict(internal)
    bad["y"] = internal["y"][:-1]
    with pytest.raises(ValueError, match="invalid frozen"):
        evaluate_frozen_baselines(prior, bad)


def test_no_row_truth_or_identifiers_in_aggregate_output():
    prior, internal = synthetic_evaluation()
    out = json.dumps(evaluate_frozen_baselines(prior, internal))
    for secret in ("s000", "s001", "nevertest", "UNREAD_PRIVATE_TRUTH",
                   "10.5555/artificial", "Li2O"):
        assert secret not in out
    assert "source_record" in out  # aggregate count only
    assert "true_target_list" not in out
    assert "prediction_rows" not in out


def test_bootstrap_group_scope_not_material_iid_precision():
    y = np.asarray([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    predicted = y + np.asarray([0.0, 1.0, 1.0, 2.0, 4.0, 3.0])
    g = ["one", "one", "two", "two", "three", "four"]
    with pytest.raises(ValueError, match="too few"):
        _group_metrics(y, predicted, g)
    g = ["one","two","three","four","five","six"]
    metrics = _group_metrics(y, predicted, g)
    assert metrics["group_count"] == 6
    assert metrics["bootstrap_resamples"] == 512
    assert metrics["worst_group_log10_MAE"] == 4


def test_publisher_inspired_config_fixed_and_explicit():
    assert RF_PARAMS["n_estimators"] == 50
    assert RF_PARAMS["max_depth"] == 12
    assert RF_PARAMS["max_features"] == "sqrt"
    assert RF_PARAMS["min_samples_leaf"] == 2
    assert MLP_PARAMS["hidden_layer_sizes"] == (32,32)
    assert MLP_PARAMS["early_stopping"] is False
