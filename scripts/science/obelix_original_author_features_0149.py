"""0149 real source TRAIN-only, exact-fold publisher-feature ablation.

Fixed 0147 RF/MLP families/hyperparameters, two predeclared arms:
 raw stoichiometric counts; counts + 7 author source lattice/spacegroup values.
 Post-hoc comparison is NOT independent generalization or exact paper replication.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import tempfile
import warnings

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import _json_bytes
from scripts.science.obelix_real_grouped_oof_0146 import run_official_original_oof
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import (
    RF_PARAMS, MLP_PARAMS, evaluate_frozen_baselines,
)

SCHEMA = "rhombus-original-obelix-0149-author-feature-posthoc-ablation-v1"
GEOMETRY_FIELDS = ("Space group number", "a", "b", "c", "alpha", "beta", "gamma")
ARMS = ("raw_stoichiometry", "raw_stoichiometry_plus_seven_lattice_spacegroup")
MAX_SOURCE_BYTES = 5_000_000


def _round(value):
    v = float(value)
    if not math.isfinite(v):
        raise ValueError("invalid numeric report metric")
    return round(v, 8)


def _parse_source_field(value, index):
    if not isinstance(value, str) or len(value) > 100:
        return float("nan")
    try:
        v = float(value.strip())
    except ValueError:
        return float("nan")
    if not math.isfinite(v):
        return float("nan")
    if index == 0:
        return v if 1 <= v <= 230 and v.is_integer() else float("nan")
    if index < 4:
        return v if 0 < v <= 500 else float("nan")
    return v if 0 < v < 180 else float("nan")


def load_original_train_features(checkout: Path, *, source_ids, expected_processed_sha256, reference_fractions):
    """Full-blob SHA check; TEST original row columns never accessed after ID.

    Original source identifiers are transient and never part of public results.
    """
    if not isinstance(expected_processed_sha256, str) or len(expected_processed_sha256) != 64:
        raise ValueError("invalid original public source SHA")
    original = Path(checkout).resolve(strict=True)
    source = original / "data" / "processed.csv"
    if source.is_symlink() or not source.is_file() or original not in source.resolve(strict=True).parents:
        raise ValueError("unsafe original publisher source path")
    with source.open("rb") as f:
        blob = f.read(MAX_SOURCE_BYTES + 1)
    if not blob or len(blob) > MAX_SOURCE_BYTES or hashlib.sha256(blob).hexdigest() != expected_processed_sha256:
        raise ValueError("modified/oversized original publisher source")
    if not isinstance(source_ids, tuple) or not source_ids or len(set(source_ids)) != len(source_ids):
        raise ValueError("source row identities must be unique ordered tuple")
    from pymatgen.core import Composition
    from pymatgen.core.periodic_table import Element
    try:
        reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig"), newline=""))
    except UnicodeError as exc:
        raise ValueError("invalid publisher source encoding") from exc
    required = {"ID","Composition",*GEOMETRY_FIELDS}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError("missing publisher feature columns")
    wanted = set(source_ids)
    raw_by_id = {}
    geometry_by_id = {}
    for source_row in reader:
        sid = source_row.get("ID")
        if not isinstance(sid, str) or not sid or len(sid) > 256:
            raise ValueError("invalid upstream original source identifier")
        if sid not in wanted:
            # *** Never access or parse any original TEST values/features. ***
            continue
        if sid in raw_by_id:
            raise ValueError("duplicate admitted TRAIN original source ID")
        formula = source_row["Composition"]
        if not isinstance(formula, str) or not 1 <= len(formula) <= 256:
            raise ValueError("missing original TRAIN composition")
        try:
            composition = Composition(formula)
            counts = composition.get_el_amt_dict()
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("original TRAIN composition cannot be parsed") from exc
        v = np.zeros(118, dtype=np.float64)
        for symbol, count in counts.items():
            z = Element(symbol).Z
            if not 1 <= z <= 118 or not math.isfinite(float(count)) or count <= 0:
                raise ValueError("invalid stoichiometric element count")
            v[z-1] = float(count)
        if not np.isfinite(v).all() or v.sum() <= 0:
            raise ValueError("original stoichiometry not physical numeric")
        raw_by_id[sid] = v
        geometry_by_id[sid] = np.asarray([
            _parse_source_field(source_row.get(field), index)
            for index, field in enumerate(GEOMETRY_FIELDS)
        ], dtype=float)
    if set(raw_by_id) != wanted:
        raise ValueError("original source TRAIN numeric cohort missing entries")
    raw = np.stack([raw_by_id[sid] for sid in source_ids])
    geometry = np.stack([geometry_by_id[sid] for sid in source_ids])
    if (
        reference_fractions.shape != raw.shape or
        not np.allclose(raw / raw.sum(axis=1, keepdims=True), reference_fractions, rtol=1e-8, atol=1e-8)
    ):
        raise ValueError("0146 original TRAIN fractions differ from original publisher formula")
    return raw, geometry


def _fold_impute_geometry(train, test):
    """Fit per-column finite median on TRAIN only, retain missing indicators."""
    if train.ndim != 2 or test.ndim != 2 or train.shape[1] != 7 or test.shape[1] != 7:
        raise ValueError("wrong publisher geometry feature shape")
    if np.isinf(train).any() or np.isinf(test).any():
        raise ValueError("unsafe infinite publisher geometry")
    median = np.array([
        np.median(col[np.isfinite(col)]) if np.isfinite(col).any() else 0.0
        for col in train.T
    ], dtype=float)
    miss_train = ~np.isfinite(train)
    miss_test = ~np.isfinite(test)
    filled_train = np.where(miss_train, median, train)
    filled_test = np.where(miss_test, median, test)
    return (
        np.concatenate((filled_train, miss_train.astype(float)), axis=1),
        np.concatenate((filled_test, miss_test.astype(float)), axis=1),
        int(np.sum(~np.isfinite(train).any(axis=0))),
    )


def evaluate_predeclared_author_features(prior, ephemeral, frozen_0147, raw, geometry):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.exceptions import ConvergenceWarning

    y = np.asarray(ephemeral["y"], dtype=float)
    groups = ephemeral["groups"]
    folds = ephemeral["fold_indices"]
    if (
        raw.shape != (len(y), 118) or geometry.shape != (len(y), 7)
        or not np.isfinite(raw).all() or not np.isfinite(y).all()
        or len(groups) != len(y) or len(folds) != 5
        or frozen_0147["real_out_of_fold_source_record_predictions_per_model"] != len(y)
        or prior["original_official_test_reserved_unread"] < 1
        or frozen_0147["official_public_TEST_predictions"] != 0
    ):
        raise ValueError("0146/0147 source held-out cohort drift")
    if (
        raw.min() < 0 or np.any(raw.sum(axis=1) <= 0)
        or prior["out_of_fold_numeric_source_records_scored"] != len(y)
    ):
        raise ValueError("invalid original stoichiometry or label population")
    source_missing = np.sum(~np.isfinite(geometry), axis=0)
    baseline = frozen_0147["out_of_fold_metrics"]["training_fold_mean_0146"]["log10_MAE"]
    predictions = {arm:{model:np.full(len(y), np.nan) for model in ("RF","MLP")} for arm in ARMS}
    per_fold = []
    warning_count = 0
    all_idx = set(range(len(y)))
    heldout_seen = set()
    for fold_n, original_idx in enumerate(folds):
        valid = np.asarray(original_idx,dtype=int)
        if not len(valid) or any(int(i) not in all_idx for i in valid):
            raise ValueError("invalid original frozen fold index")
        held = set(map(int,valid))
        if held & heldout_seen:
            raise ValueError("duplicate original heldout source row")
        heldout_seen.update(held)
        train = np.asarray(sorted(all_idx-held),dtype=int)
        if set(groups[i] for i in train) & set(groups[i] for i in valid):
            raise ValueError("shared DOI/formula group crosses heldout boundary")
        ref_fold=prior["grouped_folds"][fold_n]
        if (len(valid) != ref_fold["heldout_record_count"]
            or len(train) != ref_fold["training_record_count"]
            or len(set(groups[i] for i in valid)) != ref_fold["heldout_connected_identity_groups"]):
            raise ValueError("original published 0146 fold identity changed")
        imputed_train,imputed_test,all_missing_cols = _fold_impute_geometry(
            geometry[train],geometry[valid]
        )
        arm_features = {
            "raw_stoichiometry":(raw[train],raw[valid]),
            "raw_stoichiometry_plus_seven_lattice_spacegroup":(
                np.concatenate((raw[train],imputed_train),axis=1),
                np.concatenate((raw[valid],imputed_test),axis=1),
            ),
        }
        fold_report = {"fold":fold_n+1,"heldout_source_records":len(valid),
            "heldout_connected_groups":len(set(groups[i] for i in valid)),
            "group_leak_count":0,
            "geometry_columns_entirely_missing_in_training":all_missing_cols,
            "models":{}}
        for arm,(xtrain,xtest) in arm_features.items():
            rf=RandomForestRegressor(**RF_PARAMS)
            rf.fit(xtrain,y[train])
            rf_p=rf.predict(xtest)
            scaler=StandardScaler()
            train_scaled=scaler.fit_transform(xtrain)
            test_scaled=scaler.transform(xtest)
            mlp=MLPRegressor(**MLP_PARAMS)
            with warnings.catch_warnings(record=True) as ws:
                warnings.simplefilter("always",ConvergenceWarning)
                mlp.fit(train_scaled,y[train])
            warning_count += sum(issubclass(w.category,ConvergenceWarning) for w in ws)
            mlp_p=mlp.predict(test_scaled)
            for model,vals in (("RF",rf_p),("MLP",mlp_p)):
                if vals.shape != (len(valid),) or not np.isfinite(vals).all():
                    raise ValueError("invalid genuine held-out model output")
                predictions[arm][model][valid] = vals
                fold_report["models"][arm+"_"+model+"_log10_MAE"] = _round(np.mean(abs(vals-y[valid])))
        per_fold.append(fold_report)
    if heldout_seen != all_idx:
        raise ValueError("actual original heldout source rows omitted")
    out={}
    for arm, models in predictions.items():
        out[arm]={}
        for model,pred in models.items():
            if not np.isfinite(pred).all():
                raise ValueError("incomplete source OOF predictions")
            grouped=defaultdict(list)
            for i,g in enumerate(groups):
                grouped[g].append(abs(pred[i]-y[i]))
            macro=_round(np.mean([np.mean(v) for v in grouped.values()]))
            logmae=_round(np.mean(abs(pred-y)))
            out[arm][model]={
                "log10_MAE":logmae,
                "log10_RMSE":_round(np.sqrt(np.mean((pred-y)**2))),
                "macro_group_log10_MAE":macro,
                "record_weighted_model_minus_original_fold_mean_log10_MAE":_round(logmae-baseline),
                "score_measured_after_previous_feature_model_results_visible":True,
                "independent_test_generalization_claim_authorized":False,
                "all_frozen_source_records_predicted_once":len(y),
                "connected_identity_groups_scored":len(grouped),
            }
    return {
        "schema_version":SCHEMA,
        "study":"ORIGINAL_OBELIX_AUTHOR_FEATURE_FROZEN_GROUP_OOF_POSTHOC_EXPLORATORY",
        "source_original_commit":prior.get("original_upstream_commit"),
        "source_original_processed_csv_sha256":prior.get("source_processed_csv_sha256"),
        "source_original_raw_workbook_sha256":prior.get("original_raw_workbook_sha256"),
        "source_original_train_rows":prior["original_source_train_count"],
        "official_public_TEST_reserved_unread":prior["original_official_test_reserved_unread"],
        "official_public_TEST_predictions":0,
        "original_source_censored_upper_bounds_excluded":prior["original_raw_censored_upper_bounds_excluded"],
        "real_source_numeric_rows_scored_per_model":len(y),
        "connected_source_DOI_formula_groups":len(set(groups)),
        "original_exact_0146_fold_assignments_reused":True,
        "original_existing_fraction_models_log10_MAE":{
            "mean":baseline,
            "RF":frozen_0147["out_of_fold_metrics"]["random_forest"]["log10_MAE"],
            "MLP":frozen_0147["out_of_fold_metrics"]["mlp"]["log10_MAE"],
            "Ridge":frozen_0147["out_of_fold_metrics"]["ridge_0146"]["log10_MAE"],
        },
        "two_predeclared_feature_arms":list(ARMS),
        "raw_118_element_stoichiometric_counts":True,
        "publisher_spacegroup_and_lattice_columns":list(GEOMETRY_FIELDS),
        "missing_lattice_fields_by_column":{field:int(value) for field,value in zip(GEOMETRY_FIELDS,source_missing)},
        "missingness_flags_for_lattice_columns":True,
        "train_only_median_geometry_imputation_and_MLP_feature_scaling":True,
        "identical_frozen_0147_RF_MLP_hyperparameters_and_seeds":True,
        "MLP_convergence_warning_count":warning_count,
        "per_fold_scores":per_fold,
        "actual_oof_results":out,
        "original_author_paper_exact_feature_tuning_cv_reproduction":False,
        "source_paper_phase_temperature_measurement_attested":False,
        "unseen_fresh_holdout_evaluated":False,
        "science_go":False,
        "independent_physical_materials_authenticated":None,
        "P0_01_status":"BLOCKED",
        "P0_02_status":"BLOCKED",
        "P0_03_status":"BLOCKED",
    }


def run_publisher_feature_ablation(checkout: Path, output_dir: Path):
    source=Path(checkout).resolve(strict=True)
    out=Path(output_dir).resolve()
    if out.exists() or out == source or source in out.parents:
        raise ValueError("output must be new and independent of original source")
    with tempfile.TemporaryDirectory(prefix="rhombus-0149-source-private-") as tmp:
        t=Path(tmp)
        prior,ephemeral=run_official_original_oof(source,t/"0146-private",return_internal=True)
        existing=evaluate_frozen_baselines(prior,ephemeral)
        raw,geo=load_original_train_features(
            source,source_ids=ephemeral["source_ids"],
            expected_processed_sha256=prior["source_processed_csv_sha256"],
            reference_fractions=ephemeral["x"],
        )
        report=evaluate_predeclared_author_features(prior,ephemeral,existing,raw,geo)
        if (report["real_source_numeric_rows_scored_per_model"]!=449
            or report["official_public_TEST_reserved_unread"]!=121):
            raise ValueError("not the original exact public TRAIN experimental cohort")
        out.parent.mkdir(parents=True,exist_ok=True)
        staged=Path(tempfile.mkdtemp(prefix=".rhombus-0149-publisher-",dir=out.parent))
        try:
            (staged/"author_feature_ablation_aggregate.json").write_bytes(_json_bytes(report)+b"\n")
            if out.exists():
                raise ValueError("report output claimed unexpectedly")
            staged.rename(out)
        finally:
            if staged.exists():
                shutil.rmtree(staged)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        report=run_publisher_feature_ablation(args.original_obelix_checkout,args.output_dir)
    except (ValueError,OSError,TypeError) as exc:
        p.error(str(exc))
    print(json.dumps({"actual_source_rows":report["real_source_numeric_rows_scored_per_model"],
                      "connected_groups":report["connected_source_DOI_formula_groups"],
                      "predeclared_arm_MAE":{arm:{model:v["log10_MAE"] for model,v in results.items()}
                          for arm,results in report["actual_oof_results"].items()},
                      "original_mean_MAE":report["original_existing_fraction_models_log10_MAE"]["mean"],
                      "science_GO":False},sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
