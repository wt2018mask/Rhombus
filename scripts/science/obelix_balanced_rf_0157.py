"""0157-A: one fixed source-group-balanced RF performance ablation.

Research hypothesis: training group imbalance drives the 0149 RF's source
shift failures. Use unchanged original 0146 five transitive DOI/composition
heldout folds, 0149 feature/imputation schema and RF parameters; change ONLY
the training-set sample weights to inverse square root of source-group size.

This is retrospective model development on PUBLIC OBELiX TRAIN, *not* blind
generalization. No heldout labels or TEST data enter fitting or weighting.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import shutil
import tempfile

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import SOURCE_COMMIT, _json_bytes
from scripts.science.obelix_real_grouped_oof_0146 import run_official_original_oof
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import (
    evaluate_frozen_baselines, RF_PARAMS,
)
from scripts.science.obelix_original_author_features_0149 import (
    evaluate_predeclared_author_features, load_original_train_features,
    _fold_impute_geometry,
)
from scripts.science.obelix_group_failure_audit_0148 import (
    _family_proxy, ANION_PROXY_BINS,
)
from scripts.science.obelix_rf_source_shift_0150 import MIN_CLASS_ROWS, MIN_CLASS_GROUPS

SCHEMA = "rhombus-original-obelix-0157-group-balanced-RF-exploratory-v1"
FROZEN_WEIGHT_EXPONENT = 0.5
EXPECTED_NUMERIC = 449
EXPECTED_GROUPS = 102
PRIOR_GEOMETRY_RF_MAE = 1.62526468
PRIOR_MEAN_MAE = 1.86702336


def _round(x):
    v = float(x)
    if not math.isfinite(v):
        raise ValueError("nonfinite real regression statistic")
    return round(v, 8)


def train_only_group_weights(groups, train):
    """Strict TRAIN-only group counts. Larger groups receive less weight per row."""
    idx = np.asarray(train, dtype=int)
    if idx.ndim != 1 or not len(idx) or len(set(map(int,idx)))!=len(idx):
        raise ValueError("invalid unique source training index")
    if any(i<0 or i>=len(groups) for i in idx):
        raise ValueError("training index outside original source")
    counts = Counter(groups[int(i)] for i in idx)
    if len(counts)<2:
        raise ValueError("too few connected source TRAIN groups")
    raw = np.asarray([counts[groups[int(i)]] ** (-FROZEN_WEIGHT_EXPONENT) for i in idx],dtype=float)
    weights = raw / np.mean(raw)
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("nonfinite training source weighting")
    if not np.isclose(weights.mean(),1.0,atol=1e-12):
        raise ValueError("group training weight normalization drift")
    return weights


def _macro(y, prediction, groups):
    bag = defaultdict(list)
    for i,g in enumerate(groups):
        bag[g].append(abs(float(y[i])-float(prediction[i])))
    return _round(np.mean([np.mean(v) for v in bag.values()]))


def _scores(y,pred):
    return {"log10_MAE":_round(np.mean(abs(y-pred))),
            "log10_RMSE":_round(np.sqrt(np.mean((y-pred)**2)))}


def evaluate_balanced_rf(prior, ephemeral, frozen_0149, original_rf_predictions, raw, geometry, *, strict_official=True):
    from sklearn.ensemble import RandomForestRegressor
    y = np.asarray(ephemeral["y"],dtype=float)
    groups = tuple(ephemeral["groups"])
    folds = ephemeral["fold_indices"]
    if (len(y)<10 or raw.shape!=(len(y),118) or geometry.shape!=(len(y),7)
        or not np.isfinite(y).all() or not np.isfinite(raw).all()
        or len(groups)!=len(y) or len(folds)!=5):
        raise ValueError("original numerical source input shape invalid")
    if ((strict_official and (prior["original_official_test_reserved_unread"]!=121 or
        prior["original_source_train_count"]!=478)) or
        prior["original_official_test_reserved_unread"]<1 or
        not prior["all_folds_have_zero_group_identity_leakage"] or
        prior["scientific_qualification_authorized"] is not False or
        frozen_0149["official_public_TEST_predictions"]!=0):
        raise ValueError("TEST leakage / scientific evidence gate")
    if prior["out_of_fold_numeric_source_records_scored"]!=len(y):
        raise ValueError("original frozen source cohort changed")
    old = np.asarray(original_rf_predictions,dtype=float)
    if old.shape!=y.shape or not np.isfinite(old).all():
        raise ValueError("unaligned prior original RF OOF predictions")
    prev = frozen_0149["actual_oof_results"]["raw_stoichiometry_plus_seven_lattice_spacegroup"]["RF"]["log10_MAE"]
    if _scores(y,old)["log10_MAE"]!=prev:
        raise ValueError("prior original 0149 RF source results drift")
    if len(y)==EXPECTED_NUMERIC and prev!=PRIOR_GEOMETRY_RF_MAE:
        raise ValueError("exact previous measured 0149 source RF drift")
    allidx=set(range(len(y)))
    predicted=np.full(len(y),np.nan)
    heldseen=set()
    per_fold=[]
    for i, indices in enumerate(folds):
        test=np.asarray(indices,dtype=int)
        if not len(test) or any(int(z)<0 or int(z)>=len(y) for z in test):
            raise ValueError("invalid original 0146 frozen heldout indices")
        held=set(map(int,test))
        if held & heldseen:
            raise ValueError("same original sample predicted twice")
        heldseen |= held
        train=np.asarray(sorted(allidx-held),dtype=int)
        if {groups[z] for z in train} & {groups[z] for z in held}:
            raise ValueError("source identity group leakage")
        expected=prior["grouped_folds"][i]
        if (len(held)!=expected["heldout_record_count"]
            or len(train)!=expected["training_record_count"]
            or len({groups[z] for z in held})!=expected["heldout_connected_identity_groups"]):
            raise ValueError("original 0146 five-fold geometry/identity boundary drift")
        gt,gv,_=_fold_impute_geometry(geometry[train],geometry[test])
        xtrain=np.concatenate([raw[train],gt],axis=1)
        xval=np.concatenate([raw[test],gv],axis=1)
        if not np.isfinite(xtrain).all() or not np.isfinite(xval).all():
            raise ValueError("geometry transformed using incomplete training values")
        weights=train_only_group_weights(groups,train)
        rf=RandomForestRegressor(**RF_PARAMS)
        if np.all(weights == weights[0]):
            # Exact identity control: passing even uniform sample_weight can
            # change floating-point tree tie-breaking. For equal group sizes
            # recover the unchanged 0149 RandomForestRegressor execution.
            rf.fit(xtrain,y[train])
        else:
            rf.fit(xtrain,y[train],sample_weight=weights)
        result=rf.predict(xval)
        if result.shape!=(len(test),) or not np.isfinite(result).all():
            raise ValueError("bad genuinely heldout predictions")
        predicted[test]=result
        per_fold.append({
            "fold":i+1,"heldout_source_records":len(test),
            "heldout_connected_groups":len({groups[z] for z in held}),
            "group_leak_count":0,
            "train_weights_min":_round(min(weights)),
            "train_weights_max":_round(max(weights)),
            "balanced_RF_log10_MAE":_scores(y[test],result)["log10_MAE"],
            "prior_0149_geometry_RF_log10_MAE":_scores(y[test],old[test])["log10_MAE"],
        })
    if heldseen!=allidx or not np.isfinite(predicted).all():
        raise ValueError("original frozen 0146 heldout predictions incomplete")
    new_score=_scores(y,predicted)
    former_score=_scores(y,old)
    mean_source=np.asarray(ephemeral["mean_oof"],dtype=float)
    if mean_source.shape!=y.shape or not np.isfinite(mean_source).all():
        raise ValueError("prior training-fold mean OOF unavailable")
    if len(y)==EXPECTED_NUMERIC and _scores(y,mean_source)["log10_MAE"]!=PRIOR_MEAN_MAE:
        raise ValueError("original 0146 cheap baseline drift")

    grouping={}
    for name,v in (("fold_mean_0146",mean_source),("geometry_RF_0149",old),
                   ("balanced_geometry_RF_0157",predicted)):
        grouping[name]={"record_weighted":_scores(y,v),
                        "equal_connected_group_macro_log10_MAE":_macro(y,v,groups)}
    labels=tuple(_family_proxy(x) for x in ephemeral["x"])
    fam_report={}
    for family in ANION_PROXY_BINS:
        ix=np.asarray([i for i,label in enumerate(labels) if label==family],dtype=int)
        ng=len({groups[i] for i in ix})
        stat={"source_records":len(ix),"connected_groups":ng,
              "scores_suppressed":len(ix)<MIN_CLASS_ROWS or ng<MIN_CLASS_GROUPS}
        if not stat["scores_suppressed"]:
            stat["log10_MAE"]={key:_round(np.mean(abs(v[ix]-y[ix]))) for key,v in
                              (("fold_mean_0146",mean_source),("geometry_RF_0149",old),
                               ("balanced_RF_0157",predicted))}
        fam_report[family]=stat
    if sum(v["source_records"] for v in fam_report.values())!=len(y):
        raise ValueError("prespecified chemistry source proxy categories not exhaustive")
    groupindex=defaultdict(list)
    for i,g in enumerate(groups):
        groupindex[g].append(i)
    delta=np.asarray([
        np.mean(np.abs(predicted[ix]-y[ix])-np.abs(old[ix]-y[ix]))
        for _,ix in sorted(groupindex.items())
    ])
    rng=np.random.default_rng(157)
    boots=np.mean(rng.choice(delta,size=(512,len(delta)),replace=True),axis=1)

    return {
        "schema_version":SCHEMA,
        "experiment":"ONE_PREDECLARED_GROUP_BALANCED_0149_RF_NOT_HYPERPARAMETER_SEARCH",
        "actual_original_upstream_commit":prior.get("original_upstream_commit"),
        "original_processed_csv_sha256":prior.get("source_processed_csv_sha256"),
        "original_train_total":prior["original_source_train_count"],
        "original_public_TEST_reserved_unread":prior["original_official_test_reserved_unread"],
        "original_public_TEST_predictions":0,
        "real_numeric_source_rows":len(y),
        "original_uncensored_numeric_source_records":len(y),
        "source_DOI_formula_connected_groups":len(groupindex),
        "original_exact_five_0146_DOI_formula_folds_reused":True,
        "original_0149_RF_hyperparameters_reused_unmodified":dict(RF_PARAMS),
        "raw_stoichiometry_and_7_author_metadata_inputs_same_as_0149":True,
        "train_fold_only_geometry_median_and_missing_flag_columns":True,
        "only_new_model_change":"TRAIN_ONLY_INVERSE_SQRT_SOURCE_CONNECTED_GROUP_SIZE_SAMPLE_WEIGHTS",
        "weight_exponent_frozen":FROZEN_WEIGHT_EXPONENT,
        "all_real_original_TRAIN_out_of_fold_predictions_one_each":len(y),
        "model_scores":grouping,
        "new_weighted_minus_existing_geometry_RF_record_MAE":
            _round(new_score["log10_MAE"]-former_score["log10_MAE"]),
        "equal_connected_group_macro_paired_delta_mean":_round(np.mean(delta)),
        "heuristic_connected_source_group_bootstrap_interval_95pct":[
            _round(z) for z in np.quantile(boots,[0.025,0.975])
        ],
        "source_anion_proxy_chemistry_slices":fam_report,
        "per_original_frozen_fold":per_fold,
        "explicit_no_grid_search_or_test_tuning":True,
        "posthoc_hypothesis_after_prior_0149_0150_visible":True,
        "new_independent_external_blind":False,
        "no_physical_specimen_statistical_certainty":True,
        "actual_source_measurements_independently_authenticated":False,
        "scientific_GO":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
    }


def run_original_0157(checkout:Path,dest:Path):
    source=Path(checkout).resolve(strict=True)
    output=Path(dest).resolve()
    if output.exists() or output==source or source in output.parents:
        raise ValueError("output must be new and outside immutable source")
    with tempfile.TemporaryDirectory(prefix="rhombus-0157-source-private-") as tmp:
        temp=Path(tmp)
        prior,ephemeral=run_official_original_oof(source,temp/"0146-private",return_internal=True)
        previous,prevpred=evaluate_frozen_baselines(prior,ephemeral,return_internal=True)
        raw,geometry=load_original_train_features(
            source,source_ids=ephemeral["source_ids"],
            expected_processed_sha256=prior["source_processed_csv_sha256"],
            reference_fractions=ephemeral["x"],
        )
        old,pred=evaluate_predeclared_author_features(
            prior,ephemeral,previous,raw,geometry,return_internal=True)
        report=evaluate_balanced_rf(
            prior,ephemeral,old,
            pred["raw_stoichiometry_plus_seven_lattice_spacegroup"]["RF"],
            raw,geometry)
        if (report["real_numeric_source_rows"]!=EXPECTED_NUMERIC
            or report["source_DOI_formula_connected_groups"]!=EXPECTED_GROUPS
            or report["original_public_TEST_reserved_unread"]!=121
            or report["original_public_TEST_predictions"]!=0
            or report["scientific_GO"] is not False):
            raise ValueError("unrecognized original 0157 source evaluation cohort")
        output.parent.mkdir(parents=True,exist_ok=True)
        staged=Path(tempfile.mkdtemp(prefix=".rhombus-0157-balanced-",dir=output.parent))
        try:
            (staged/"original_balanced_RF_performance_0157.json").write_bytes(
                _json_bytes(report)+b"\n")
            if output.exists():
                raise ValueError("original result directory already exists")
            staged.rename(output)
        finally:
            if staged.exists():
                shutil.rmtree(staged)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--original-obelix-checkout",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    arg=parser.parse_args(argv)
    r=run_original_0157(arg.original_obelix_checkout,arg.output_dir)
    print("0157_REAL_ORIGINAL_PUBLIC_TRAIN_GROUP_BALANCED_RF_EVALUATED")
    print(json.dumps({
        "original_SOURCE_TRAIN_rows":r["real_numeric_source_rows"],
        "group_count":r["source_DOI_formula_connected_groups"],
        "benchmark_model_MAE":{k:v["record_weighted"]["log10_MAE"]
                               for k,v in r["model_scores"].items()},
        "balanced_minus_original_RF_MAE":
            r["new_weighted_minus_existing_geometry_RF_record_MAE"],
        "group_macro_paired_delta":r["equal_connected_group_macro_paired_delta_mean"],
        "science_GO":False,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
