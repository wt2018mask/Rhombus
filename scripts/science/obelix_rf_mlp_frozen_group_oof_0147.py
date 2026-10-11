"""0147: actual original-source RF/MLP baselines on exact frozen 0146 OOF folds.

RF and MLP use published model *families* and a fixed configuration; 0146
chemical descriptors and connected DOI/formula grouping are intentionally
different from the publisher's RF/MLP tuning / benchmark preprocessing.
Neither exact paper replication nor independently blinded validation.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import shutil
import tempfile
import warnings

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import _json_bytes
from scripts.science.obelix_real_grouped_oof_0146 import (
    run_official_original_oof,
)

SCHEMA = "rhombus-0147-public-train-frozen-group-rf-mlp-v1"
RF_PARAMS = {
    "n_estimators": 50, "max_depth": 12, "max_features": "sqrt",
    "min_samples_leaf": 2, "random_state": 147, "n_jobs": 2,
}
MLP_PARAMS = {
    "hidden_layer_sizes": (32, 32), "activation": "relu",
    "solver": "adam", "learning_rate_init": 0.001,
    "alpha": 0.001, "batch_size": 32, "max_iter": 400,
    "early_stopping": False, "random_state": 147,
}


def _metrics(y, predicted):
    if predicted.shape != y.shape or not np.isfinite(predicted).all():
        raise ValueError("nonfinite, missing or incorrect out-of-fold prediction")
    e = predicted - y
    return {
        "log10_MAE": round(float(np.mean(abs(e))), 8),
        "log10_RMSE": round(float(np.sqrt(np.mean(e * e))), 8),
    }


def _group_metrics(y, predicted, groups):
    """Group-weighted error and diagnostic bootstrap; groups != IID specimens."""
    errors = abs(predicted - y)
    members = defaultdict(list)
    for i, g in enumerate(groups):
        members[g].append(float(errors[i]))
    by_group = np.array([float(np.mean(v)) for k, v in sorted(members.items())])
    if len(by_group) < 5:
        raise ValueError("too few identity groups for uncertainty diagnostic")
    rng = np.random.default_rng(147)
    boots = np.mean(rng.choice(by_group, size=(512, len(by_group)), replace=True), axis=1)
    return {
        "macro_group_log10_MAE": round(float(np.mean(by_group)), 8),
        "group_log10_MAE_p90": round(float(np.percentile(by_group, 90)), 8),
        "worst_group_log10_MAE": round(float(np.max(by_group)), 8),
        "group_bootstrap_macro_log10_MAE_95pct_interval": [
            round(float(q), 8) for q in np.quantile(boots, [0.025, 0.975])
        ],
        "bootstrap_resamples": 512,
        "bootstrap_scope": "HEURISTIC_SHARED_DOI_FORMULA_GROUPS_NOT_IID_PHYSICAL_SAMPLES",
        "group_count": len(by_group),
    }


def evaluate_frozen_baselines(prior, ephemeral, *, return_internal=False):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.exceptions import ConvergenceWarning

    x = ephemeral["x"]
    y = ephemeral["y"]
    groups = ephemeral["groups"]
    fold_indices = ephemeral["fold_indices"]
    if (
        x.ndim != 2 or x.shape[1] != 118 or
        not np.isfinite(x).all() or not np.isfinite(y).all() or
        len(y) != x.shape[0] or len(groups) != len(y)
        or len(fold_indices) != 5
    ):
        raise ValueError("invalid frozen real source descriptors or labels")
    if len(y) != prior["out_of_fold_numeric_source_records_scored"]:
        raise ValueError("0146 scored population drift")
    if len(set(groups)) != prior["shared_doi_formula_connected_components_scored"]:
        raise ValueError("0146 connected source groups drift")
    if prior["original_official_test_reserved_unread"] < 1 or not prior[
        "all_folds_have_zero_group_identity_leakage"
    ] or prior["scientific_qualification_authorized"] is not False:
        raise ValueError("original TEST / group embargo / scientific gate failed")

    predictions = {
        "random_forest": np.full(len(y), np.nan),
        "mlp": np.full(len(y), np.nan),
        "ridge_0146": ephemeral["ridge_oof"].copy(),
        "training_fold_mean_0146": ephemeral["mean_oof"].copy(),
    }
    all_indices = set(range(len(y)))
    per_fold = []
    warnings_count = 0
    test_seen = set()
    for fold, indices in enumerate(fold_indices):
        valid = np.asarray(indices, dtype=int)
        if not len(valid) or any(i < 0 or i >= len(y) for i in valid):
            raise ValueError("invalid original frozen test fold")
        if set(map(int, valid)) & test_seen:
            raise ValueError("source sample already evaluated in another fold")
        test_seen.update(map(int, valid))
        training = np.asarray(sorted(all_indices - set(map(int, valid))), dtype=int)
        if set(groups[i] for i in training) & set(groups[i] for i in valid):
            raise ValueError("original group identity leaked to training")
        frozen_fold = prior["grouped_folds"][fold]
        if (len(valid) != frozen_fold["heldout_record_count"]
            or len(training) != frozen_fold["training_record_count"]
            or len(set(groups[i] for i in valid)) != frozen_fold["heldout_connected_identity_groups"]):
            raise ValueError("0146 original frozen fold identity/size drift")

        rf = RandomForestRegressor(**RF_PARAMS)
        rf.fit(x[training], y[training])
        predictions["random_forest"][valid] = rf.predict(x[valid])

        # All transformations are fitted only on the training portion of this
        # original GROUP-HOLDOFF fold: never scale using target/held-out rows.
        scaler = StandardScaler()
        train_scaled = scaler.fit_transform(x[training])
        held_scaled = scaler.transform(x[valid])
        mlp = MLPRegressor(**MLP_PARAMS)
        with warnings.catch_warnings(record=True) as warns:
            warnings.simplefilter("always", ConvergenceWarning)
            mlp.fit(train_scaled, y[training])
        warnings_count += sum(issubclass(w.category, ConvergenceWarning) for w in warns)
        predictions["mlp"][valid] = mlp.predict(held_scaled)
        per_fold.append({
            "fold": fold + 1,
            "heldout_source_record_count": len(valid),
            "heldout_connected_identity_group_count": len(set(groups[i] for i in valid)),
            "train_source_record_count": len(training),
            "group_leakage_count": 0,
            "rf_log10_MAE": _metrics(y[valid], predictions["random_forest"][valid])["log10_MAE"],
            "mlp_log10_MAE": _metrics(y[valid], predictions["mlp"][valid])["log10_MAE"],
            "fold_mean_log10_MAE": _metrics(y[valid], predictions["training_fold_mean_0146"][valid])["log10_MAE"],
            "ridge_log10_MAE": _metrics(y[valid], predictions["ridge_0146"][valid])["log10_MAE"],
        })
    if test_seen != all_indices:
        raise ValueError("some frozen eligible source records omitted from evaluation")
    model_results = {}
    for name, pred in predictions.items():
        model_results[name] = {
            **_metrics(y, pred),
            **_group_metrics(y, pred, groups),
            "strict_original_0146_group_folds_reused": True,
            "source_record_out_of_fold_count": len(y),
        }
    if model_results["ridge_0146"]["log10_MAE"] != prior["trained_ridge_oof_metrics"]["log10_MAE"]:
        raise ValueError("prior actual ridge aggregate score changed")
    if model_results["training_fold_mean_0146"]["log10_MAE"] != prior["training_fold_mean_oof_metrics"]["log10_MAE"]:
        raise ValueError("prior actual source-fold mean aggregate score changed")

    result = {
        "schema_version": SCHEMA,
        "experiment": "ACTUAL_ORIGINAL_OBELIX_TRAIN_GROUPED_RF_MLP_VS_RIDGE_MEAN",
        "original_source_commit": prior.get("original_upstream_commit"),
        "original_source_processed_sha256": prior.get("source_processed_csv_sha256"),
        "original_raw_workbook_sha256": prior.get("original_raw_workbook_sha256"),
        "original_raw_train_label_policy_sha256": prior.get("original_raw_train_label_policy_sha256"),
        "original_official_train_records": prior["original_source_train_count"],
        "original_official_test_reserved_unread": prior["original_official_test_reserved_unread"],
        "original_source_numeric_point_metadata": prior["original_raw_point_source_records"],
        "censored_source_upper_bounds_excluded": prior["original_raw_censored_upper_bounds_excluded"],
        "real_out_of_fold_source_record_predictions_per_model": len(y),
        "source_DOI_formula_connected_groups_scored": len(set(groups)),
        "exact_0146_split_and_feature_identity": "REUSED_UNALTERED_GROUP_ASSIGNMENT_118_ELEMENT_FRACTIONS",
        "random_forest_frozen_hyperparameters": dict(RF_PARAMS),
        "mlp_frozen_hyperparameters": dict(MLP_PARAMS),
        "mlp_convergence_warning_fold_count": warnings_count,
        "out_of_fold_metrics": model_results,
        "fold_metrics": per_fold,
        "original_paper_baseline_protocol_exactly_reproduced": False,
        "upstream_RF_baseline_source": "NRC-Mila/OBELiX/benchmark/RF.py@4eaac889809dd489e3bae468c45d5c0e02b9147a",
        "upstream_MLP_baseline_source": "NRC-Mila/OBELiX/benchmark/MLP.py@4eaac889809dd489e3bae468c45d5c0e02b9147a",
        "upstream_publication_has_different_features_and_hyperparameter_search": True,
        "group_bootstrap_scientific_material_confidence_intervals_authorized": False,
        "independent_physical_material_count": None,
        "external_scientific_blind_completed": False,
        "model_training_exposure_authenticated": False,
        "official_public_TEST_predictions": 0,
        "experimental_conductivity_values_independently_paper_attested": False,
        "scientific_qualification_authorized": False,
        "P0_01_status": "BLOCKED",
        "P0_02_status": "BLOCKED",
        "P0_03_status": "BLOCKED",
    }
    if result["original_source_numeric_point_metadata"] - result["real_out_of_fold_source_record_predictions_per_model"] != (
        prior["original_numeric_but_formula_unparseable"] + prior["original_numeric_but_invalid_excluded"]
    ):
        raise ValueError("original source label/censor inclusion changed")
    if return_internal:
        # Follows the identical 0146 source-order and frozen heldout group IDs.
        # No source-row labels or predictions are ever persisted to artifacts.
        return result, {name: values.copy() for name, values in predictions.items()}
    return result


def run_original_source_strong_baselines(checkout: Path, output_dir: Path):
    out = Path(output_dir).resolve()
    if out.exists() or out == Path(checkout).resolve() or Path(checkout).resolve() in out.parents:
        raise ValueError("immutable source / output separation")
    with tempfile.TemporaryDirectory(prefix="rhombus-0147-private-numerics-") as tmp:
        t = Path(tmp)
        prior, ephemeral = run_official_original_oof(
            checkout, t / "0146-aggregate-ephemeral",
            return_internal=True,
        )
        report = evaluate_frozen_baselines(prior, ephemeral)
        out.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".rhombus-0147-", dir=out.parent))
        try:
            (staging / "source_group_rf_mlp_aggregate.json").write_bytes(_json_bytes(report) + b"\n")
            if out.exists():
                raise ValueError("0147 result path already claimed")
            staging.rename(out)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-obelix-checkout", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        r = run_original_source_strong_baselines(a.original_obelix_checkout, a.output_dir)
    except (ValueError, OSError, TypeError) as e:
        p.error(str(e))
    print(json.dumps({
        "source_train": r["original_official_train_records"],
        "source_test_reserved": r["original_official_test_reserved_unread"],
        "actual_OOF_source_records_per_model": r["real_out_of_fold_source_record_predictions_per_model"],
        "connected_groups": r["source_DOI_formula_connected_groups_scored"],
        "RF_MAE": r["out_of_fold_metrics"]["random_forest"]["log10_MAE"],
        "MLP_MAE": r["out_of_fold_metrics"]["mlp"]["log10_MAE"],
        "Ridge_MAE": r["out_of_fold_metrics"]["ridge_0146"]["log10_MAE"],
        "Mean_MAE": r["out_of_fold_metrics"]["training_fold_mean_0146"]["log10_MAE"],
        "science_go": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
