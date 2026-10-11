"""0148 failure audit adversarial tests: synthetic rows only, never real source facts."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from tests.test_phase3_rf_mlp_frozen_group_oof_0147 import synthetic_evaluation
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import evaluate_frozen_baselines
from scripts.science.obelix_group_failure_audit_0148 import (
    ANION_PROXY_BINS, _family_proxy, _family_scores,
    _paired_group_delta, _publisher_protocol_inspection,
    inspect_actual_failure_causes, SCHEMA,
)


def source_fixture(tmp_path):
    publisher = tmp_path / "benchmark"
    publisher.mkdir()
    (publisher / "parse.py").write_text(
        "flatten_comp Space group number mendeleev usecols"
    )
    (publisher / "RF.py").write_text(
        "GridSearchCV RandomForestRegressor StandardScaler train_idx.csv"
    )
    (publisher / "MLP.py").write_text(
        "GridSearchCV MLPRegressor StandardScaler train_idx.csv"
    )
    return tmp_path


def data_fixture(tmp_path):
    prior, private = synthetic_evaluation()
    prior.update({
        "original_upstream_commit": "4eaac889809dd489e3bae468c45d5c0e02b9147a",
        "source_processed_csv_sha256": "a" * 64,
        "original_raw_workbook_sha256": "b" * 64,
    })
    baseline, preds = evaluate_frozen_baselines(prior, private, return_internal=True)
    assert baseline["original_paper_baseline_protocol_exactly_reproduced"] is False
    root = source_fixture(tmp_path)
    return root, prior, private, baseline, preds


def test_all_genuine_fixed_model_predictions_can_be_retrieved_ephemerally(tmp_path):
    root, prior, private, base, preds = data_fixture(tmp_path)
    assert set(preds) == {
        "training_fold_mean_0146", "random_forest", "mlp", "ridge_0146"
    }
    assert all(v.shape == (35,) for v in preds.values())
    assert all(np.isfinite(v).all() for v in preds.values())


def test_frozen_models_and_source_groups_accounted_once(tmp_path):
    root, prior, private, base, preds = data_fixture(tmp_path)
    result = inspect_actual_failure_causes(root, prior, private, base, preds)
    assert result["schema_version"] == SCHEMA
    assert result["original_public_TRAIN_numeric_source_rows_predicted_per_model"] == 35
    assert result["original_identity_connected_groups"] == 35
    assert result["official_public_TEST_reserved_unread"] == 1
    assert result["official_public_TEST_predictions"] == 0
    assert result["source_group_size_concentration"]["top_5_groups_source_rows"] == 5
    assert len(result["per_fold_error_and_raw_label_spread"]) == 5
    assert sum(x["source_records"] for x in result["per_fold_error_and_raw_label_spread"]) == 35
    assert len(result["paired_model_minus_mean_group_error_diagnostics"]) == 3
    assert result["author_protocol_difference"]["exact_publisher_paper_protocol_reproduced"] is False
    assert result["scientific_claim_GO"] is False
    assert result["P0_01_status"] == result["P0_02_status"] == result["P0_03_status"] == "BLOCKED"
    for model, m in result["model_global_log10_MAE"].items():
        assert m == base["out_of_fold_metrics"][model]["log10_MAE"]
    assert sum(p["source_record_count"] for p in result["predeclared_anion_element_presence_proxy_bins"].values()) == 35
    assert len(result["predeclared_anion_element_presence_proxy_bins"]) == 5


def test_author_script_code_is_readonly_and_drift_denied(tmp_path):
    root = source_fixture(tmp_path)
    result = _publisher_protocol_inspection(root)
    assert set(result["author_source_code_verified_readonly"]) == {
        "benchmark/parse.py", "benchmark/RF.py", "benchmark/MLP.py",
    }
    assert all(len(x["sha256"]) == 64 for x in result["author_source_code_verified_readonly"].values())
    assert not result["exact_publisher_paper_protocol_reproduced"]
    (root/"benchmark"/"RF.py").write_text("modified")
    with pytest.raises(ValueError, match="drift"):
        _publisher_protocol_inspection(root)


def test_five_composition_proxy_bins_are_mutually_exclusive():
    x = np.zeros((5, 118))
    x[0, 7] = x[0, 15] = 0.5
    x[1, 7] = 1
    x[2, 15] = 1
    x[3, 16] = 1
    x[4, 2] = 1
    assert tuple(map(_family_proxy,x)) == ANION_PROXY_BINS


def test_rare_family_scores_suppressed_in_small_sample():
    x = np.zeros((15, 118))
    x[:13, 7] = 1.0
    x[13:, 15] = 1.0
    y = np.arange(15., dtype=float)
    preds = {name: y.copy()+1. for name in (
        "training_fold_mean_0146", "random_forest", "mlp", "ridge_0146"
    )}
    out = _family_scores(x, y, tuple(str(i) for i in range(15)), preds)
    assert out["O_ONLY"]["source_record_count"] == 13
    assert "model_log10_MAE" in out["O_ONLY"]
    assert out["S_ONLY"]["source_record_count"] == 2
    assert "model_log10_MAE" not in out["S_ONLY"]
    assert out["S_ONLY"]["score_suppressed_by_minimum_coverage"]


def test_paired_group_bootstrap_is_reproducible_and_not_specimen_ci():
    y = np.arange(20.,dtype=float)
    groups = tuple("g"+str(i//2) for i in range(20))
    pred = {"training_fold_mean_0146": y+1, "random_forest": y+2,
            "mlp": y+3,"ridge_0146": y+4}
    a = _paired_group_delta(y,groups,pred)
    assert a == _paired_group_delta(y,groups,pred)
    assert a["random_forest"]["record_weighted_model_minus_mean_log10_MAE"] == 1
    assert a["mlp"]["equal_connected_group_macro_model_minus_mean_log10_MAE"] == 2
    assert not a["ridge_0146"]["is_independent_material_statistical_CI"]


def test_original_test_and_fake_qualification_gates_halt(tmp_path):
    root, prior, private, base, preds = data_fixture(tmp_path)
    modified = dict(prior)
    modified["original_official_test_reserved_unread"] = 0
    with pytest.raises(ValueError, match="embargo drift"):
        inspect_actual_failure_causes(root, modified, private, base, preds)
    modified = dict(prior)
    modified["scientific_qualification_authorized"] = True
    with pytest.raises(ValueError, match="embargo drift"):
        inspect_actual_failure_causes(root, modified, private, base, preds)


def test_wrong_baseline_or_malformed_private_array_fails(tmp_path):
    root, prior, private, base, preds = data_fixture(tmp_path)
    altered = {k: v.copy() for k, v in preds.items()}
    altered["random_forest"][0] += 12
    with pytest.raises(ValueError, match="scores drift"):
        inspect_actual_failure_causes(root, prior, private, base, altered)
    altered = dict(preds)
    altered["mlp"] = np.full(35, np.nan)
    with pytest.raises(ValueError, match="unmatched prior"):
        inspect_actual_failure_causes(root, prior, private, base, altered)


def test_no_source_ids_truths_or_chemical_row_arrays_in_report(tmp_path):
    root, prior, private, base, preds = data_fixture(tmp_path)
    report = inspect_actual_failure_causes(root, prior, private, base, preds)
    raw = json.dumps(report)
    for bad in ("s000", "s001", "nevertest", "UNREAD_PRIVATE_TRUTH",
                "10.5555/artificial", "material_predictions", "per_source_id"):
        assert bad not in raw
    assert "independent_physical_specimen_count" in raw
    assert report["actual_independent_physical_specimen_count"] is None
