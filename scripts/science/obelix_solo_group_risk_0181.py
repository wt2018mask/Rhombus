"""0181: solo/public TRAIN-only genuine group-size and RF-disagreement audit.

Exactly the frozen 0146 source-derived outer DOI/formula connected-group folds,
same 0147 RF settings, no outer outcome based tuning. Measure whether a
model-computed RF tree-dispersion proxy predicts heldout group risk and can
produce safer *group-level* selective coverage than deterministic blind ranks.

A public diagnostic is not externally sealed, physical transport validated, or
an actual individual specimen uncertainty calibration.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import _json_bytes, SOURCE_COMMIT
from scripts.science.obelix_real_grouped_oof_0146 import run_official_original_oof
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS, _metrics

SCHEMA="rhombus-0181-public-source-group-size-rf-dispersion-risk-v1"
COVERAGES=(0.60,0.80)
BLIND_SEEDS=128
RANDOM_SEED_LABEL="rhombus-0181-blind-source-group-rank:"
RF_EXPECTED_MAE=1.94487886
MEAN_EXPECTED_MAE=1.86702336
RF_EXPECTED_MACRO=1.90046024
MEAN_EXPECTED_MACRO=2.26818583


def _finite(values):
    arr=np.asarray(values,dtype=float)
    return bool(np.isfinite(arr).all())


def _rank_correlation(a,b):
    """Tied values get stable average ranks; diagnostic Spearman proxy."""
    a=np.asarray(a,dtype=float)
    b=np.asarray(b,dtype=float)
    if a.ndim!=1 or b.shape!=a.shape or len(a)<10 or not _finite(a) or not _finite(b):
        raise ValueError("invalid risk / uncertainty correlation population")
    def ranks(x):
        perm=np.argsort(x,kind="stable")
        res=np.empty(len(x),dtype=float)
        start=0
        while start<len(x):
            end=start+1
            while end<len(x) and x[perm[end]]==x[perm[start]]:
                end+=1
            res[perm[start:end]]=(start+1+end)/2.0
            start=end
        return res
    x,y=ranks(a),ranks(b)
    astd,bstd=np.std(x),np.std(y)
    if astd<=1e-12 or bstd<=1e-12:
        return None
    return round(float(np.mean((x-np.mean(x))*(y-np.mean(y)))/(astd*bstd)),8)


def risk_and_size_report(y,mean,rf,rf_dispersion,groups,folds):
    """Group identity used only to aggregate out-of-fold diagnostics, never fit."""
    y=np.asarray(y,dtype=float)
    mean=np.asarray(mean,dtype=float)
    rf=np.asarray(rf,dtype=float)
    rf_dispersion=np.asarray(rf_dispersion,dtype=float)
    n=len(y)
    if (n<20 or any(v.shape!=(n,) for v in (mean,rf,rf_dispersion))
        or len(groups)!=n or not all(_finite(a) for a in (y,mean,rf,rf_dispersion))
        or np.any(rf_dispersion<0)):
        raise ValueError("unbounded nonfinite original-source uncertainty metric")
    members=defaultdict(list)
    for ix,g in enumerate(groups):
        members[str(g)].append(ix)
    names=sorted(members)
    if len(names)<10:raise ValueError("too few connected source groups")

    group_size=np.array([len(members[g]) for g in names],dtype=int)
    rf_err=np.array([float(np.mean(np.abs(rf[ix]-y[ix])))
                     for g in names for ix in [members[g]]])
    mean_err=np.array([float(np.mean(np.abs(mean[ix]-y[ix])))
                       for g in names for ix in [members[g]]])
    dispersion=np.array([float(np.mean(rf_dispersion[members[g]]))
                          for g in names])
    if not _finite(rf_err) or not _finite(mean_err) or not _finite(dispersion):
        raise ValueError("bad group-scoped source audit")

    bands={}
    for tag,mask in (
        ("single_row_group",group_size==1),
        ("two_to_five_rows",(group_size>=2)&(group_size<=5)),
        ("six_or_more_rows",group_size>=6),
    ):
        size=int(np.sum(mask))
        bands[tag]={
            "source_connected_groups":size,
            "source_rows_in_groups":int(np.sum(group_size[mask])),
            "max_rows_in_single_group":int(np.max(group_size[mask])) if size else 0,
            "RF_macro_group_MAE":round(float(np.mean(rf_err[mask])),8) if size else None,
            "mean_macro_group_MAE":round(float(np.mean(mean_err[mask])),8) if size else None,
            "RF_minus_mean_group_MAE":round(float(np.mean(rf_err[mask]-mean_err[mask])),8) if size else None,
            "public_identity_groups_NOT_individual_pellets":True,
        }
    if sum(v["source_connected_groups"] for v in bands.values())!=len(names):
        raise ValueError("group strata inconsistent")

    # Frozen no-label sorting: ensemble disagreement is computed using only
    # the model fitted on each fold's source TRAIN records. Never uses y here.
    dispersion_order=sorted(range(len(names)),key=lambda i:(dispersion[i],names[i]))
    # False confidence risk is judged only AFTER the ranking is frozen.
    full=float(np.mean(rf_err))
    full_mean=float(np.mean(mean_err))
    risk_coverage={}
    for fraction in COVERAGES:
        k=int(math.ceil(fraction*len(names)))
        chosen=np.array(dispersion_order[:k],dtype=int)
        blind_risks=[]
        for seed in range(BLIND_SEEDS):
            ranked=sorted(range(len(names)),key=lambda i:hashlib.sha256(
                (RANDOM_SEED_LABEL+str(seed)+":"+names[i]).encode()).digest())
            blind_risks.append(float(np.mean(rf_err[ranked[:k]])))
        blind=np.array(blind_risks)
        value=float(np.mean(rf_err[chosen]))
        mean_selected=float(np.mean(mean_err[chosen]))
        key=f"{int(fraction*100)}pct"
        risk_coverage[key]={
            "source_identity_coverage_target":fraction,
            "selected_connected_groups":k,
            "selected_public_source_rows":int(np.sum(group_size[chosen])),
            "selected_rows_are_NOT_independent_pellets":True,
            "RF_selected_macro_group_MAE":round(value,8),
            "mean_on_same_selected_groups_macro_MAE":round(mean_selected,8),
            "RF_full_coverage_macro_group_MAE":round(full,8),
            "RF_selected_minus_full_macro_group_MAE":round(value-full,8),
            "RF_selected_minus_same_group_mean_MAE":round(value-mean_selected,8),
            "blind_uniform_group_selection_trials":BLIND_SEEDS,
            "blind_uniform_source_group_mean_risk":round(float(np.mean(blind)),8),
            "blind_uniform_group_risk_95pct_interval":[round(float(t),8) for t in np.quantile(blind,[.025,.975])],
            "blind_group_trial_fraction_with_equal_or_lower_risk_than_RF_proxy":round(float(np.mean(blind<=value)),8),
            "selected_using_RF_tree_disagreement_NO_public_holdout_labels":True,
        }
    rho=_rank_correlation(dispersion,rf_err)
    # This is diagnostic; it must NOT claim a new, sealed independent test.
    wins=sum(risk_coverage[key]["RF_selected_macro_group_MAE"]<round(full,8)
             and risk_coverage[key]["RF_selected_macro_group_MAE"]<
                 risk_coverage[key]["blind_uniform_source_group_mean_risk"]
             for key in risk_coverage)
    if wins==2 and rho is not None and rho>0:
        diagnosis="PASS_RETROSPECTIVE_GROUP_RISK_SIGNAL_ONLY"
    elif wins==0 or (rho is not None and rho<=0):
        diagnosis="FAIL_NO_RELIABLE_SOURCE_GROUP_RISK_SIGNAL"
    else:
        diagnosis="INCONCLUSIVE_PUBLIC_GROUP_RISK_DIAGNOSTIC"
    return {
        "source_rows":n,
        "source_connected_groups":len(names),
        "group_size_distribution":{
            "largest_connected_group_rows":int(np.max(group_size)),
            "five_largest_groups_total_rows":int(np.sum(np.sort(group_size)[-5:])),
            "top_five_group_share_of_public_source_rows":round(float(np.sum(np.sort(group_size)[-5:])/n),8),
            "groups_size_one_count":int(np.sum(group_size==1)),
        },
        "group_size_strata":bands,
        "original_outer_fold_connected_group_counts":list(folds),
        "model_error":{
            "RF_row_log10_MAE":_metrics(y,rf)["log10_MAE"],
            "cheap_mean_row_log10_MAE":_metrics(y,mean)["log10_MAE"],
            "RF_macro_group_log10_MAE":round(full,8),
            "cheap_mean_macro_group_log10_MAE":round(full_mean,8),
            "RF_minus_mean_row_log10_MAE":round(float(np.mean(np.abs(rf-y)-np.abs(mean-y))),8),
            "RF_minus_mean_macro_group_log10_MAE":round(float(np.mean(rf_err-mean_err)),8),
            "connected_source_groups_RF_better_than_mean":int(np.sum(rf_err<mean_err)),
            "connected_source_groups_RF_worse_than_mean":int(np.sum(rf_err>mean_err)),
        },
        "RF_tree_disagreement_vs_actual_group_abs_error_spearman":rho,
        "RF_ensemble_tree_std_NOT_validated_uncertainty_probability":True,
        "risk_coverage":risk_coverage,
        "solo_public_risk_diagnostic":diagnosis,
    }


def run_live_original_source(prior,ephemeral,*,strict=True):
    from sklearn.ensemble import RandomForestRegressor

    y=np.asarray(ephemeral["y"],dtype=float)
    x=np.asarray(ephemeral["x"],dtype=float)
    groups=tuple(ephemeral["groups"])
    folds=ephemeral["fold_indices"]
    mean=np.asarray(ephemeral["mean_oof"],dtype=float)
    if (x.shape!=(len(y),118) or len(groups)!=len(y) or len(folds)!=5
        or not all(_finite(v) for v in (y,x,mean))
        or prior["all_folds_have_zero_group_identity_leakage"] is not True
        or prior["scientific_qualification_authorized"] is not False):
        raise ValueError("invalid original public TRAIN numeric source or group boundaries")
    if strict and (len(y)!=449 or len(set(groups))!=102
                   or prior["original_source_train_count"]!=478
                   or prior["original_official_test_reserved_unread"]!=121
                   or prior["original_raw_censored_upper_bounds_excluded"]!=29
                   or prior["original_upstream_commit"]!=SOURCE_COMMIT):
        raise ValueError("original publisher TRAIN / TEST / censored population changed")

    n=len(y)
    pred=np.full(n,np.nan)
    dispersion=np.full(n,np.nan)
    seen=set()
    sizes=[]
    all_indices=np.arange(n)
    for fold,ix in enumerate(folds):
        held=np.asarray(ix,dtype=int)
        if held.ndim!=1 or not len(held) or len(set(held.tolist()))!=len(held):
            raise ValueError("missing or repeated frozen heldout indices")
        if min(held)<0 or max(held)>=n or seen & set(held.tolist()):
            raise ValueError("untrusted outer heldout index")
        seen.update(held.tolist())
        training=np.setdiff1d(all_indices,held,assume_unique=True)
        frozen=prior["grouped_folds"][fold]
        count=len(set(groups[i] for i in held))
        sizes.append(count)
        if (set(groups[i] for i in training) & set(groups[i] for i in held)
            or len(held)!=frozen["heldout_record_count"]
            or len(training)!=frozen["training_record_count"]
            or count!=frozen["heldout_connected_identity_groups"]):
            raise ValueError("not original zero-leak 0146 group folds")
        forest=RandomForestRegressor(**RF_PARAMS)
        forest.fit(x[training],y[training])
        pred[held]=forest.predict(x[held])
        # Per-sample estimator disagreement; do not use heldout labels.
        tree_preds=np.stack([tree.predict(x[held]) for tree in forest.estimators_],axis=0)
        dispersion[held]=np.std(tree_preds,axis=0,ddof=0)
        if not np.allclose(mean[held],np.mean(y[training]),atol=1e-10,rtol=0):
            raise ValueError("original cheap train-fold mean baseline drift")
    if seen!=set(range(n)) or not _finite(pred) or not _finite(dispersion):
        raise ValueError("missing original group-heldout genuine predictions")

    report=risk_and_size_report(y,mean,pred,dispersion,groups,sizes)
    metrics=report["model_error"]
    if strict and (
        metrics["RF_row_log10_MAE"]!=RF_EXPECTED_MAE
        or metrics["cheap_mean_row_log10_MAE"]!=MEAN_EXPECTED_MAE
        or metrics["RF_macro_group_log10_MAE"]!=RF_EXPECTED_MACRO
        or metrics["cheap_mean_macro_group_log10_MAE"]!=MEAN_EXPECTED_MACRO
    ):
        raise ValueError("original 0147/0180 benchmark original scores drifted")
    report.update({
        "schema_version":SCHEMA,
        "evaluation":"REAL_ORIGINAL_PUBLIC_TRAIN_ZERO_GROUP_LEAKAGE_UNCERTAINTY_DIAGNOSTIC",
        "original_upstream_commit":prior["original_upstream_commit"],
        "source_processed_CSV_SHA256":prior["source_processed_csv_sha256"],
        "raw_source_workbook_SHA256":prior["original_raw_workbook_sha256"],
        "source_label_policy_SHA256":prior["original_raw_train_label_policy_sha256"],
        "public_source_TRAIN_count":prior["original_source_train_count"],
        "public_source_TEST_count_reserved_unread":prior["original_official_test_reserved_unread"],
        "public_source_TEST_used_in_any_selection":False,
        "public_numeric_uncensored_source_rows":n,
        "original_source_upper_bound_labels_excluded":prior["original_raw_censored_upper_bounds_excluded"],
        "frozen_outer_group_folds_reused":True,
        "fixed_original_RF_hyperparameters":dict(RF_PARAMS),
        "source_identity_groups_not_physical_independent_materials":True,
        "public_retrospective_outcomes_exposed_before_0181_experiment":True,
        "no_new_unseen_sealed_blind_science_data":True,
        "no_independent_physical_materials_attested":True,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "physical_scientific_GO":False,
    })
    return report


def run_from_publisher_checkout(checkout:Path,output:Path):
    source=Path(checkout).resolve(strict=True)
    out=Path(output).resolve()
    if out.exists() or out==source or source in out.parents:
        raise ValueError("original source checkout or output invariant")
    with tempfile.TemporaryDirectory(prefix="rhombus-0181-live-") as temp:
        prior,ephemeral=run_official_original_oof(
            source,Path(temp)/"0146",return_internal=True)
        report=run_live_original_source(prior,ephemeral)
        out.parent.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix=".rhombus-0181-report-",dir=out.parent))
        try:
            (stage/"original_source_group_risk_0181.json").write_bytes(_json_bytes(report)+b"\n")
            if out.exists():raise ValueError("source report file race")
            stage.rename(out)
        finally:
            if stage.exists():shutil.rmtree(stage)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    result=run_from_publisher_checkout(a.original_obelix_checkout,a.output_dir)
    print("0181_ACTUAL_OBELIX_SOURCE_GROUP_SIZE_RISK_COVERAGE_DIAGNOSTIC_PASS")
    print(json.dumps({
        "rows":result["source_rows"],
        "source_connected_groups":result["source_connected_groups"],
        "RF_group_macro":result["model_error"]["RF_macro_group_log10_MAE"],
        "mean_group_macro":result["model_error"]["cheap_mean_macro_group_log10_MAE"],
        "risk_spearman":result["RF_tree_disagreement_vs_actual_group_abs_error_spearman"],
        "risk_diagnostic":result["solo_public_risk_diagnostic"],
        "risk_coverage":result["risk_coverage"],
        "external_physical_GO":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
