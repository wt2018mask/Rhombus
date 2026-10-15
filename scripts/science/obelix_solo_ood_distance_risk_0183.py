"""0183: solo ORIGINAL public TRAIN-only family shift error/risk diagnostic.

Tests prediction-only group ranking with RF-tree disagreement, training-only
nearest-neighbour standardized compositional distance and a fixed equal-rank
fusion. These are exploratory retrospective diagnostics following observed
0182 O_ONLY failure, NOT a tuned adopted predictor or untouched confirmatory
assessment. No official original TEST, outside lab, or physical pellet.
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
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy, ANION_PROXY_BINS
from scripts.science.obelix_family_ood_weighted_rf_0158 import (
    separate_family_with_group_embargo, MIN_CLASS_ROWS, MIN_CLASS_GROUPS,
)
from scripts.science.obelix_solo_family_out_risk_0182 import (
    evaluate_original_family_out, select_family_groups, COVERAGES, BLIND_TRIALS,
)
from scripts.science.obelix_solo_group_risk_0181 import _rank_correlation

SCHEMA="rhombus-0183-original-family-shift-distance-vs-tree-risk-v1"
SCALE_FLOOR=0.02
BATCH_ROWS=64
METHODS=("RF_TREE_STD","TRAIN_ONLY_NEAREST_DISTANCE","EQUAL_RANK_FUSION")
MIN_SOURCE_TRAIN=20


def nearest_training_composition_distance(train_x, held_x):
    """TRAIN-only scale; heldout compositions used for distance, never labels."""
    train=np.asarray(train_x,dtype=float)
    held=np.asarray(held_x,dtype=float)
    if (train.ndim!=2 or held.ndim!=2 or train.shape[1]!=118
        or held.shape[1]!=118 or len(train)<MIN_SOURCE_TRAIN
        or not len(held) or not np.isfinite(train).all() or not np.isfinite(held).all()
        or not (np.all(train>=0) and np.all(held>=0))):
        raise ValueError("invalid fraction-only source features")
    # Minimum dispersion is fixed a priori in unit-fraction space. Otherwise
    # absent training elements spuriously get zero penalty as std=0.
    sd=np.maximum(np.std(train,axis=0,ddof=0),SCALE_FLOOR)
    out=np.empty(len(held),dtype=float)
    for lo in range(0,len(held),BATCH_ROWS):
        hi=min(lo+BATCH_ROWS,len(held))
        diffs=(held[lo:hi,None,:]-train[None,:,:])/sd[None,None,:]
        dist=np.sqrt(np.sum(diffs*diffs,axis=2)/train.shape[1])
        out[lo:hi]=np.min(dist,axis=1)
    if not np.isfinite(out).all() or np.any(out<0):
        raise ValueError("training-only source distance failed")
    return out


def group_rank(values,names):
    """Prediction-only score ordinal in the SAME chemical holdout population."""
    arr=np.asarray(values,dtype=float)
    if len(arr)!=len(names) or not len(arr) or not np.isfinite(arr).all():
        raise ValueError("invalid proxy group ranking")
    order=sorted(range(len(names)),key=lambda i:(arr[i],names[i]))
    rank=np.empty(len(names),dtype=float)
    for position,i in enumerate(order):rank[i]=position
    return rank


def score_source_family(groups,y,rf,cheap,tree_std,distance,*,name):
    y=np.asarray(y,dtype=float)
    rf=np.asarray(rf,dtype=float)
    cheap=np.asarray(cheap,dtype=float)
    tree_std=np.asarray(tree_std,dtype=float)
    distance=np.asarray(distance,dtype=float)
    source_groups=tuple(str(x) for x in groups)
    n=len(y)
    if (len(source_groups)!=n or n<MIN_CLASS_ROWS
        or any(a.shape!=(n,) or not np.isfinite(a).all()
               for a in (rf,cheap,tree_std,distance,y))
        or np.any(tree_std<0) or np.any(distance<0)
        or name not in ANION_PROXY_BINS):
        raise ValueError("nonfinite or forged original heldout source risk")
    ids=defaultdict(list)
    for i,g in enumerate(source_groups):ids[g].append(i)
    names=sorted(ids)
    if len(names)<MIN_CLASS_GROUPS:
        raise ValueError("too few source connected groups")
    err=np.array([float(np.mean(np.abs(rf[ids[g]]-y[ids[g]]))) for g in names])
    cheaper=np.array([float(np.mean(np.abs(cheap[ids[g]]-y[ids[g]]))) for g in names])
    diversity=np.array([float(np.mean(tree_std[ids[g]])) for g in names])
    novelty=np.array([float(np.mean(distance[ids[g]])) for g in names])
    size=np.array([len(ids[g]) for g in names])
    # Equal ordinal ranks; no coefficients chosen after 0182 O_ONLY failure.
    fused=0.5*(group_rank(diversity,names)+group_rank(novelty,names))
    methods={
        "RF_TREE_STD":diversity,
        "TRAIN_ONLY_NEAREST_DISTANCE":novelty,
        "EQUAL_RANK_FUSION":fused,
    }
    full=float(np.mean(err))
    blind_by_fraction={}
    for fraction in COVERAGES:
        key=f"{int(fraction*100)}pct"
        k=math.ceil(fraction*len(names))
        draws=[]
        for seed in range(BLIND_TRIALS):
            order=sorted(range(len(names)),key=lambda i:hashlib.sha256(
                ("rhombus-0183-family-audit:"+name+":"+str(seed)+":"+names[i]).encode()).digest())
            draws.append(float(np.mean(err[order[:k]])))
        blind_by_fraction[key]=(_fixed(float(np.mean(draws))),draws)
    out={}
    for method,scores in methods.items():
        sorted_groups=sorted(range(len(names)),key=lambda i:(scores[i],names[i]))
        rows={}
        for fraction in COVERAGES:
            key=f"{int(fraction*100)}pct"
            k=math.ceil(fraction*len(names))
            subset=sorted_groups[:k]
            selected=float(np.mean(err[subset]))
            blind_mean,blind_trials=blind_by_fraction[key]
            rows[key]={
                "selected_source_connected_groups":k,
                "total_source_connected_groups":len(names),
                "selected_source_rows":int(np.sum(size[subset])),
                "source_heldout_rows":n,
                "selected_RF_macro_group_MAE":_fixed(selected),
                "selected_cheap_mean_on_exact_groups_MAE":_fixed(np.mean(cheaper[subset])),
                "full_RF_macro_group_MAE":_fixed(full),
                "same_family_equal_budget_blind_mean_MAE":blind_mean,
                "blind_trials":BLIND_TRIALS,
                "blind_draws_with_equal_or_lower_error":int(np.sum(np.array(blind_trials)<=selected)),
                "selection_uses_original_heldout_labels":False,
                "coverage_units":"DOI_FORMULA_CONNECTED_GROUP_NOT_PHYSICAL_PELLET",
            }
        out[method]={
            "heldout_error_risk_spearman":(
                _rank_correlation(scores,err) if len(names)>=10 else None),
            "ranking_a_priori_label_free":True,
            "risk_coverage":rows,
        }
    # Compare exact previous 0182 RF std selected budget; intentionally
    # conservatively verify that source/OOD definition did not drift.
    prior=select_family_groups(source_groups,y,rf,cheap,tree_std)
    for frac in COVERAGES:
        k=f"{int(frac*100)}pct"
        if out["RF_TREE_STD"]["risk_coverage"][k]["selected_RF_macro_group_MAE"]!=(
              prior["risk_coverage"][k]["selected_RF_group_MAE"]):
            raise ValueError("original 0182 tree disagreement reference drift")
    return {
        "source_family":name,
        "source_rows":n,
        "source_connected_groups":len(names),
        "largest_group_row_count":int(np.max(size)),
        "source_groups_one_row":int(np.sum(size==1)),
        "RF_full_group_MAE":_fixed(full),
        "train_only_mean_full_group_MAE":_fixed(np.mean(cheaper)),
        "nearest_training_distance_group_range":[_fixed(np.min(novelty)),_fixed(np.max(novelty))],
        "rf_tree_std_group_range":[_fixed(np.min(diversity)),_fixed(np.max(diversity))],
        "methods":out,
        "no_heldout_labels_in_distance_or_uncertainty_or_fusion_rank":True,
        "no_same_physical_specimen_asserted":True,
    }


def _fixed(v):
    value=float(v)
    if not math.isfinite(value):raise ValueError("nonfinite original source metric")
    return round(value,8)


def evaluate_real(prior,ephemeral,*,strict=True):
    from sklearn.ensemble import RandomForestRegressor
    x=np.asarray(ephemeral["x"],dtype=float)
    y=np.asarray(ephemeral["y"],dtype=float)
    groups=tuple(ephemeral["groups"])
    if (x.shape!=(len(y),118) or len(groups)!=len(y) or
        not np.isfinite(x).all() or not np.isfinite(y).all()
        or len(ephemeral["fold_indices"])!=5
        or prior["all_folds_have_zero_group_identity_leakage"] is not True
        or prior["scientific_qualification_authorized"] is not False):
        raise ValueError("public original population or frozen OOF not verified")
    if strict and (
        prior["original_upstream_commit"]!=SOURCE_COMMIT
        or prior["original_source_train_count"]!=478
        or prior["original_official_test_reserved_unread"]!=121
        or prior["original_raw_censored_upper_bounds_excluded"]!=29
        or len(y)!=449 or len(set(groups))!=102):
        raise ValueError("publisher frozen original source TEST embargo drift")
    # Exactly replay the known 0182 scores first. This uses only prior source
    # DATA, not alternative hidden publisher TEST. The probe itself remains
    # explicitly exploratory because the earlier public outcomes were seen.
    baseline=evaluate_original_family_out(prior,ephemeral,strict_original=strict)
    labels=tuple(_family_proxy(z) for z in x)
    result={}
    for family in ANION_PROXY_BINS:
        hold,train,embargo=separate_family_with_group_embargo(groups,labels,family)
        prior_class=baseline["family_source_coverage"][family]
        state={
            "family":family,
            "heldout_source_rows":len(hold),
            "heldout_connected_groups":len(set(groups[i] for i in hold)),
            "source_train_rows_after_family_plus_group_embargo":len(train),
            "source_rows_group_embargoed":embargo,
            "source_score":None,
            "status":prior_class["status"],
        }
        if state["status"]=="ELIGIBLE_SOURCE_PUBLIC_FAMILY_OUT":
            model=RandomForestRegressor(**RF_PARAMS)
            model.fit(x[train],y[train])
            rf=model.predict(x[hold])
            std=np.std(np.stack([tree.predict(x[hold]) for tree in model.estimators_]),axis=0)
            cheap=np.full(len(hold),float(np.mean(y[train])))
            distances=nearest_training_composition_distance(x[train],x[hold])
            source=score_source_family(tuple(groups[i] for i in hold),y[hold],rf,cheap,std,distances,name=family)
            old=prior_class["source_group_risk"]
            if source["RF_full_group_MAE"]!=old["RF_full_group_MAE"]:
                raise ValueError("0182 original whole-family RF changed")
            state["source_score"]=source
        else:
            if prior_class["source_group_risk"] is not None:
                raise ValueError("cannot silently drop an original eligible family")
        result[family]=state
    if set(result)!=set(ANION_PROXY_BINS) or sum(d["heldout_source_rows"] for d in result.values())!=len(y):
        raise ValueError("original chemistry family source partition changed")
    return {
        "schema_version":SCHEMA,
        "original_upstream_commit":prior["original_upstream_commit"],
        "original_processed_csv_SHA256":prior["source_processed_csv_sha256"],
        "original_raw_xlsx_SHA256":prior["original_raw_workbook_sha256"],
        "original_raw_train_policy_SHA256":prior["original_raw_train_label_policy_sha256"],
        "original_public_TRAIN_count":prior["original_source_train_count"],
        "original_public_TEST_reserved_UNREAD":prior["original_official_test_reserved_unread"],
        "original_TEST_features_or_labels_used_for_selection":False,
        "original_censored_source_labels_excluded":prior["original_raw_censored_upper_bounds_excluded"],
        "original_numeric_source_rows":len(y),
        "source_DOI_formula_connected_groups":len(set(groups)),
        "chemical_families":result,
        "predeclared_risk_methods":list(METHODS),
        "predeclared_equal_group_coverage_budgets":list(COVERAGES),
        "predeclared_group_random_draws":BLIND_TRIALS,
        "distance_metric":"TRAIN_ONLY_ZSCORE_EUCLIDEAN_NEAREST_118_FRACTIONS_SCALE_FLOOR_0p02",
        "unseen_anion_family_is_proxy_not_verified_crystal_phase":True,
        "post_0182_failure_followup_exploratory_NOT_unseen_confirmatory":True,
        "adopt_any_new_risk_policy_as_validated":False,
        "individual_physical_pellets":0,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_external_GO":False,
        "next_action":"0184 solo external PUBLIC source-family validation with new source cohorts or prospective public chronology",
    }


def from_original_checkout(checkout:Path,output:Path):
    source=Path(checkout).resolve(strict=True)
    target=Path(output).resolve()
    if target.exists() or target==source or source in target.parents:
        raise ValueError("new append-only scientific output outside original source required")
    with tempfile.TemporaryDirectory(prefix="rhombus-0183-authentic-") as t:
        prior,arrays=run_official_original_oof(source,Path(t)/"frozen0146",return_internal=True)
        report=evaluate_real(prior,arrays)
        target.parent.mkdir(parents=True,exist_ok=True)
        staging=Path(tempfile.mkdtemp(prefix=".rhombus-0183-",dir=target.parent))
        try:
            (staging/"solo_public_family_distance_risk_0183.json").write_bytes(_json_bytes(report)+b"\n")
            if target.exists():raise ValueError("race writing public-source evidence")
            staging.rename(target)
        finally:
            if staging.exists():shutil.rmtree(staging)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    r=from_original_checkout(a.original_obelix_checkout,a.output_dir)
    print("0183_ACTUAL_SOLO_PUBLIC_CHEMISTRY_OOD_DISTANCE_RISK_DIAGNOSTIC_PASS")
    brief={fam:{
        "rows":rec["heldout_source_rows"],"groups":rec["heldout_connected_groups"],
        "status":rec["status"],
        "scores":({key:val["risk_coverage"] for key,val in rec["source_score"]["methods"].items()}
                  if rec["source_score"] is not None else None)
    } for fam,rec in r["chemical_families"].items()}
    print(json.dumps({"families":brief,"official_original_TEST_unread":True,"scientific_external_GO":False},sort_keys=True))


if __name__=="__main__":main()
