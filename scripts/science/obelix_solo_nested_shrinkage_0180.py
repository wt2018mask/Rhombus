"""0180 solo-only prospective-SEPARATED research design on PUBLIC OBELiX TRAIN.

For every immutable 0146 outer fold, choose the RF vs mean shrinkage
weight exclusively by a DIFFERENT, training-only inner DOI/formula-group
heldout CV. Never select using outer-fold outcomes. This is a retrospective
public benchmark, not scientific independent experimental GO.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import _json_bytes, SOURCE_COMMIT
from scripts.science.obelix_real_grouped_oof_0146 import run_official_original_oof
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import (
    RF_PARAMS, _metrics, _group_metrics,
)

SCHEMA="rhombus-0180-solo-original-train-nested-frozen-group-rf-shrinkage-v1"
WEIGHTS=(0.0,0.25,0.50,0.75,1.0)
INNER_FOLDS=3
BOOTSTRAPS=512
SEED=180


def inner_assignments(groups):
    """Group identity never splits across inner calibration folds."""
    if len(groups)<9 or len(set(groups))<9:
        raise ValueError("too few independent DOI/composition groups")
    identities=sorted(set(str(g) for g in groups))
    # Repeatable, material identity-only ordering; no y or outer outcomes.
    identities.sort(key=lambda v: hashlib.sha256(
        ("rhombus-0180-inner-"+v).encode()).digest())
    allocation={g:i%INNER_FOLDS for i,g in enumerate(identities)}
    return tuple(np.array([i for i,g in enumerate(groups)
                            if allocation[str(g)]==fold],dtype=int)
                 for fold in range(INNER_FOLDS))


def choose_weight_from_inner_groups(x,y,groups):
    """Only the designated OUTER TRAIN partition may enter this function."""
    from sklearn.ensemble import RandomForestRegressor

    x=np.asarray(x,dtype=float)
    y=np.asarray(y,dtype=float)
    groups=tuple(groups)
    if (x.ndim!=2 or x.shape[1]!=118 or y.shape!=(len(x),)
        or len(groups)!=len(y) or not np.isfinite(x).all()
        or not np.isfinite(y).all()):
        raise ValueError("invalid training-only feature/label arrays")

    mean=np.full(len(y),np.nan,dtype=float)
    rf=np.full(len(y),np.nan,dtype=float)
    seen=set()
    assignments=inner_assignments(groups)
    for held in assignments:
        remaining=np.setdiff1d(np.arange(len(y)),held,assume_unique=True)
        if not len(held) or len(remaining)<20:
            raise ValueError("invalid group-only inner fold sizes")
        if set(groups[i] for i in held) & set(groups[i] for i in remaining):
            raise ValueError("nested group identity contamination")
        if seen & set(held.tolist()):
            raise ValueError("duplicate original inner calibration row")
        seen.update(held.tolist())
        mean[held]=float(np.mean(y[remaining]))
        forest=RandomForestRegressor(**RF_PARAMS)
        forest.fit(x[remaining],y[remaining])
        rf[held]=forest.predict(x[held])
    if (seen!=set(range(len(y))) or not np.isfinite(mean).all()
        or not np.isfinite(rf).all()):
        raise ValueError("incomplete or nonfinite inner predictions")

    members=defaultdict(list)
    for i,g in enumerate(groups):
        members[str(g)].append(i)
    group_names=sorted(members)
    losses={}
    for weight in WEIGHTS:
        errs=np.abs((mean+weight*(rf-mean))-y)
        # Each shared-DOI/formula connected group has equal decision weight.
        losses[weight]=float(np.mean([
            float(np.mean(errs[members[g]])) for g in group_names]))
    # Tie policy is cheaper MEAN, not random RF tuning on heldout data.
    selected=min(WEIGHTS,key=lambda w:(round(losses[w],12),w))
    return selected,{
        "chosen_RF_weight":selected,
        "inner_connected_groups":len(group_names),
        "inner_cv_group_macro_MAE_by_weight":{
            f"{w:.2f}":round(losses[w],8) for w in WEIGHTS},
        "label_access":"OUTER_TRAIN_ONLY_INNER_GROUP_CV",
        "inner_group_count_per_fold":[len(set(groups[i] for i in ix))
                                      for ix in assignments],
        "inner_group_identity_overlap":0,
    }


def paired_group_comparison(y,pred,mean,rf,groups):
    """A group bootstrap over PUBLIC source identities, not physical specimens."""
    n=len(y)
    if not (pred.shape==mean.shape==rf.shape==y.shape==(n,)
            and len(groups)==n and np.isfinite(pred).all()):
        raise ValueError("incorrect paired prediction population")
    errors=np.abs(pred-y)
    base_errors=np.abs(mean-y)
    units=defaultdict(list)
    for i,g in enumerate(groups):units[str(g)].append(i)
    names=sorted(units)
    deltas=np.array([float(np.mean(errors[units[g]]-base_errors[units[g]]))
                     for g in names])
    if len(names)<10:raise ValueError("insufficient source groups")
    rng=np.random.default_rng(SEED)
    idx=rng.integers(0,len(names),size=(BOOTSTRAPS,len(names)))
    boots=np.mean(deltas[idx],axis=1)
    return {
        "source_group_count":len(names),
        "macro_group_delta_MAE_shrink_minus_mean":round(float(np.mean(deltas)),8),
        "group_bootstrap_delta_95pct_interval":[round(float(x),8)
                for x in np.quantile(boots,[0.025,0.975])],
        "bootstraps":BOOTSTRAPS,
        "bootstrap_is_heuristic_shared_source_DOI_groups_NOT_individual_pellets":True,
        "row_paired_delta_log10_MAE_shrink_minus_mean":round(
            float(np.mean(errors-base_errors)),8),
        "row_paired_delta_log10_MAE_rf_minus_mean":round(
            float(np.mean(np.abs(rf-y)-base_errors)),8),
        "source_groups_where_shrink_beats_mean":int(np.sum(deltas<0)),
        "source_groups_tied_with_mean":int(np.sum(deltas==0)),
        "source_groups_where_shrink_worse_than_mean":int(np.sum(deltas>0)),
    }


def evaluate_nested_policy(prior,internal,*,strict=True):
    from sklearn.ensemble import RandomForestRegressor
    x=np.asarray(internal["x"],dtype=float)
    y=np.asarray(internal["y"],dtype=float)
    groups=tuple(internal["groups"])
    folds=internal["fold_indices"]
    if (x.shape!=(len(y),118) or len(y)!=len(groups) or len(folds)!=5
        or not np.isfinite(x).all() or not np.isfinite(y).all()
        or prior["all_folds_have_zero_group_identity_leakage"] is not True
        or prior["scientific_qualification_authorized"] is not False
        or prior["original_official_test_reserved_unread"]<1):
        raise ValueError("source feature/fold or blind original embargo violation")
    if strict and (len(y)!=449 or len(set(groups))!=102
        or prior["original_source_train_count"]!=478
        or prior["original_official_test_reserved_unread"]!=121
        or prior["original_raw_censored_upper_bounds_excluded"]!=29
        or prior["original_upstream_commit"]!=SOURCE_COMMIT):
        raise ValueError("0180 original frozen public TRAIN population drift")

    rf=np.full(len(y),np.nan)
    shrink=np.full(len(y),np.nan)
    mean=np.asarray(internal["mean_oof"],dtype=float)
    seen=set()
    fold_receipts=[]
    for i,indices in enumerate(folds):
        held=np.asarray(indices,dtype=int)
        if (held.ndim!=1 or len(held)==0 or np.any(held<0)
            or np.any(held>=len(y)) or len(set(held))!=len(held)
            or seen.intersection(held.tolist())):
            raise ValueError("outer fold contains invalid/duplicate original indices")
        seen.update(held.tolist())
        train=np.setdiff1d(np.arange(len(y)),held,assume_unique=True)
        if set(groups[j] for j in held) & set(groups[j] for j in train):
            raise ValueError("outer source group leakage")
        m=prior["grouped_folds"][i]
        if (len(held)!=m["heldout_record_count"]
            or len(train)!=m["training_record_count"]
            or len(set(groups[j] for j in held))!=m["heldout_connected_identity_groups"]):
            raise ValueError("changed exact original source 0146 outer fold")
        w,inner=choose_weight_from_inner_groups(
            x[train],y[train],tuple(groups[j] for j in train))
        mdl=RandomForestRegressor(**RF_PARAMS)
        mdl.fit(x[train],y[train])
        rf[held]=mdl.predict(x[held])
        # Uses training-fold mean. The 0146 frozen mean must agree exactly.
        outer_mean=float(np.mean(y[train]))
        if not np.allclose(mean[held],outer_mean,atol=1e-10,rtol=0):
            raise ValueError("prior cheap mean fold changed")
        shrink[held]=outer_mean+w*(rf[held]-outer_mean)
        fold_receipts.append({
            "outer_fold":i+1,
            "original_holdout_rows":len(held),
            "original_train_rows":len(train),
            "original_heldout_connected_groups":m["heldout_connected_identity_groups"],
            "fixed_RF_fitted_on_outer_train_only":True,
            **inner,
            "outer_fold_RF_MAE":_metrics(y[held],rf[held])["log10_MAE"],
            "outer_fold_shrink_MAE":_metrics(y[held],shrink[held])["log10_MAE"],
            "outer_fold_mean_MAE":_metrics(y[held],mean[held])["log10_MAE"],
        })
    if seen!=set(range(len(y))) or not np.isfinite(shrink).all():
        raise ValueError("incomplete group heldout original source record coverage")
    score={"train_fold_mean":_metrics(y,mean),
           "original_RF_0147":_metrics(y,rf),
           "nested_shrunk_RF":_metrics(y,shrink)}
    if strict and (score["train_fold_mean"]["log10_MAE"]!=1.86702336
        or score["original_RF_0147"]["log10_MAE"]!=1.94487886):
        raise ValueError("immutable prior 0146 / 0147 actual source baseline changed")
    paired=paired_group_comparison(y,shrink,mean,rf,groups)
    report={
        "schema_version":SCHEMA,
        "experiment":"ACTUAL_PUBLIC_TRAIN_ONLY_NESTED_GROUP_CV_RF_SHRINKAGE",
        "source_commit":prior["original_upstream_commit"],
        "source_processed_CSV_SHA256":prior["source_processed_csv_sha256"],
        "source_raw_workbook_SHA256":prior["original_raw_workbook_sha256"],
        "source_raw_train_policy_SHA256":prior["original_raw_train_label_policy_sha256"],
        "original_source_train_records":prior["original_source_train_count"],
        "original_official_TEST_reserved_unread":prior["original_official_test_reserved_unread"],
        "original_official_TEST_used_for_selection_or_scoring":False,
        "original_censored_upper_bounds_excluded":prior["original_raw_censored_upper_bounds_excluded"],
        "source_numeric_records_OOF":len(y),
        "source_DOI_formula_connected_groups":len(set(groups)),
        "outer_frozen_0146_folds_exact":True,
        "inner_selected_without_outer_labels":True,
        "fixed_unmodified_RF_parameters":dict(RF_PARAMS),
        "fixed_RF_shrinkage_candidates":list(WEIGHTS),
        "inner_CV_folds":INNER_FOLDS,
        "outer_folds":fold_receipts,
        "model_metrics":score,
        "model_group_metrics":{
            "nested_shrunk_RF":_group_metrics(y,shrink,groups),
            "train_fold_mean":_group_metrics(y,mean,groups),
        },
        "paired_public_group_improvement":paired,
        "nested_policy_beats_cheap_mean_row_MAE":(
            score["nested_shrunk_RF"]["log10_MAE"]<
            score["train_fold_mean"]["log10_MAE"]),
        "nested_policy_beats_cheap_mean_macro_group_MAE":(
            _group_metrics(y,shrink,groups)["macro_group_log10_MAE"]<
            _group_metrics(y,mean,groups)["macro_group_log10_MAE"]),
        "source_is_retrospective_PUBLIC_TRAIN_not_new_blind":True,
        "training_selected_MACE_MPA0_frames_known":False,
        "independent_individual_physical_specimens_admitted":0,
        "historical_P0_01":"BLOCKED","historical_P0_02":"BLOCKED",
        "historical_P0_03":"BLOCKED",
        "scientific_external_GO":False,
        "solo_public_benchmark_status":"MEASURED_REPRODUCIBLE_REQUIRES_EXECUTED_SOURCE_CI",
    }
    if sum(f["original_holdout_rows"] for f in fold_receipts)!=len(y):
        raise ValueError("outer source count/identity drift")
    return report


def run_original(checkout:Path,out:Path):
    root=Path(checkout).resolve(strict=True)
    dest=Path(out).resolve()
    if dest.exists() or root==dest or root in dest.parents:
        raise ValueError("invalid original source or overwrite")
    with tempfile.TemporaryDirectory(prefix="rhombus-0180-private-") as t:
        old,arrays=run_official_original_oof(root,Path(t)/"old0146",return_internal=True)
        result=evaluate_nested_policy(old,arrays)
        dest.parent.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix=".rhombus-0180-report-",dir=dest.parent))
        try:
            (stage/"solo_nested_group_RF_0180.json").write_bytes(_json_bytes(result)+b"\n")
            if dest.exists():raise ValueError("append-only original report collision")
            stage.rename(dest)
        finally:
            if stage.exists():shutil.rmtree(stage)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--original-obelix-checkout",required=True,type=Path)
    parser.add_argument("--output-dir",required=True,type=Path)
    a=parser.parse_args()
    r=run_original(a.original_obelix_checkout,a.output_dir)
    print("0180_ACTUAL_ORIGINAL_SOLO_NESTED_GROUPED_RF_SOURCE_SCIENCE_PASS")
    print(json.dumps({
        "source_rows":r["source_numeric_records_OOF"],
        "groups":r["source_DOI_formula_connected_groups"],
        "weights":[f["chosen_RF_weight"] for f in r["outer_folds"]],
        "mean_MAE":r["model_metrics"]["train_fold_mean"]["log10_MAE"],
        "RF_MAE":r["model_metrics"]["original_RF_0147"]["log10_MAE"],
        "nested_MAE":r["model_metrics"]["nested_shrunk_RF"]["log10_MAE"],
        "source_benchmark_beats_mean":r["nested_policy_beats_cheap_mean_row_MAE"],
        "external_GO":False},sort_keys=True))

if __name__=="__main__": main()
