"""0182 solo actual PUBLIC TRAIN leave-anion-proxy-family-out selective-risk stress.

Reuses exactly 0150/0158 proxy classes and transitive DOI/formula group
embargo, not the easier 0181 within-distribution five folds. Holds out
all rows of a chemistry proxy family, refits immutable fraction-only 0147
RF on remaining family & unshared identities, ranks original heldout
source groups by RF-tree dispersion WITHOUT heldout targets. Evaluate
frozen equal-GROUP 60/80% budgets; no public official TEST ever admitted.
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

from rhombus.qualification.obelix_benchmark_intake import SOURCE_COMMIT, _json_bytes
from scripts.science.obelix_real_grouped_oof_0146 import run_official_original_oof
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy, ANION_PROXY_BINS
from scripts.science.obelix_family_ood_weighted_rf_0158 import (
    separate_family_with_group_embargo, MIN_CLASS_ROWS, MIN_CLASS_GROUPS,
)

SCHEMA="rhombus-0182-solo-genuine-family-out-RF-selective-risk-v1"
COVERAGES=(.60,.80)
BLIND_TRIALS=128
MIN_TRAIN_ROWS=20


def _round(v):
    n=float(v)
    if not math.isfinite(n):
        raise ValueError("nonfinite empirical source group risk")
    return round(n,8)


def select_family_groups(group_ids, y, rf_prediction, cheap_prediction, tree_std):
    """Source-group observations, no group label in uncertainty ranking."""
    y=np.asarray(y,dtype=float)
    rf=np.asarray(rf_prediction,dtype=float)
    cheap=np.asarray(cheap_prediction,dtype=float)
    unc=np.asarray(tree_std,dtype=float)
    groups=tuple(str(v) for v in group_ids)
    n=len(y)
    if (n<MIN_CLASS_ROWS or len(groups)!=n or
        any(a.shape!=(n,) or not np.isfinite(a).all() for a in (rf,cheap,unc)) or
        not np.isfinite(y).all() or np.any(unc<0)):
        raise ValueError("invalid family-heldout prediction or diversity")
    members=defaultdict(list)
    for i,g in enumerate(groups):members[g].append(i)
    names=sorted(members)
    if len(names)<MIN_CLASS_GROUPS:
        raise ValueError("source group family eligibility threshold failed")
    size=np.array([len(members[g]) for g in names],dtype=int)
    errors=np.array([float(np.mean(np.abs(rf[members[g]]-y[members[g]])))
                     for g in names])
    base_errors=np.array([float(np.mean(np.abs(cheap[members[g]]-y[members[g]])))
                          for g in names])
    dispersion=np.array([float(np.mean(unc[members[g]])) for g in names])
    order=sorted(range(len(names)),key=lambda i:(dispersion[i],names[i]))
    result={}
    full=float(np.mean(errors))
    for frac in COVERAGES:
        k=int(math.ceil(frac*len(names)))
        selected=order[:k]
        score=float(np.mean(errors[selected]))
        blind=[]
        for trial in range(BLIND_TRIALS):
            rnd=sorted(range(len(names)),key=lambda i:hashlib.sha256(
                ("rhombus-0182-family-only-blind-"+str(trial)+":"+names[i]).encode()).digest())
            blind.append(float(np.mean(errors[rnd[:k]])))
        average=float(np.mean(blind))
        result[f"{int(frac*100)}pct"]={
            "selected_connected_groups":k,
            "heldout_connected_groups":len(names),
            "selected_source_rows":int(sum(size[i] for i in selected)),
            "family_heldout_source_rows":n,
            "selected_RF_group_MAE":_round(score),
            "full_RF_group_MAE":_round(full),
            "selected_cheap_train_mean_group_MAE":_round(np.mean(base_errors[selected])),
            "blind_equal_group_budget_random_mean_MAE":_round(average),
            "blind_draws_with_lower_or_equal_error_than_proxy":int(np.sum(np.asarray(blind)<=score)),
            "blind_uniform_draws":BLIND_TRIALS,
            "reduced_risk_versus_full":bool(score<full),
            "reduced_risk_versus_blind_mean":bool(score<average),
            "selection_predetermined_by_RF_dispersion_NOT_heldout_labels":True,
            "source_group_coverage_not_physical_material_fraction":True,
        }
    return {
        "heldout_source_rows":n,
        "heldout_connected_groups":len(names),
        "largest_connected_source_group_rows":int(max(size)),
        "RF_full_group_MAE":_round(full),
        "cheap_train_only_mean_full_group_MAE":_round(np.mean(base_errors)),
        "risk_coverage":result,
    }


def evaluate_original_family_out(prior, ephemeral, *, strict_original=True):
    from sklearn.ensemble import RandomForestRegressor
    x=np.asarray(ephemeral["x"],dtype=float)
    y=np.asarray(ephemeral["y"],dtype=float)
    groups=tuple(ephemeral["groups"])
    if (x.shape!=(len(y),118) or len(y)!=len(groups) or len(y)<25
        or not np.isfinite(x).all() or not np.isfinite(y).all()
        or prior["all_folds_have_zero_group_identity_leakage"] is not True
        or prior["scientific_qualification_authorized"] is not False
        or len(ephemeral["fold_indices"])!=5):
        raise ValueError("original public source feature/cv guards failed")
    if strict_original and (
        len(y)!=449 or len(set(groups))!=102
        or prior["original_source_train_count"]!=478
        or prior["original_official_test_reserved_unread"]!=121
        or prior["original_raw_censored_upper_bounds_excluded"]!=29
        or prior["original_upstream_commit"]!=SOURCE_COMMIT):
        raise ValueError("original OBELiX official reserved TEST boundary changed")
    labels=tuple(_family_proxy(row) for row in x)
    summary={}
    total_rows=0
    eligible=0
    for family in ANION_PROXY_BINS:
        held,train,removed=separate_family_with_group_embargo(groups,labels,family)
        total_rows+=len(held)
        held_groups={groups[int(i)] for i in held}
        allow=(len(held)>=MIN_CLASS_ROWS and
               len(held_groups)>=MIN_CLASS_GROUPS and len(train)>=MIN_TRAIN_ROWS)
        state={
            "public_anion_presence_proxy":family,
            "original_public_heldout_rows":int(len(held)),
            "heldout_connected_groups":len(held_groups),
            "training_rows_after_DOI_formula_embargo":int(len(train)),
            "other_family_training_rows_embargoed_for_same_source_group":removed,
            "chemistry_family_is_ANION_PRESENCE_PROXY_not_XRD_phase":True,
            "zero_train_heldout_source_identity_overlap":not bool(
                held_groups & set(groups[int(i)] for i in train)),
            "status":"ELIGIBLE_SOURCE_PUBLIC_FAMILY_OUT" if allow else
                     "NOT_SCORED_INSUFFICIENT_ROWS_GROUPS_OR_TRAIN",
            "source_group_risk":None,
        }
        if not state["zero_train_heldout_source_identity_overlap"]:
            raise ValueError("DOI/formula connected group leaked across family embargo")
        if allow:
            rf=RandomForestRegressor(**RF_PARAMS)
            rf.fit(x[train],y[train])
            pred=rf.predict(x[held])
            tree_prediction=np.asarray([tree.predict(x[held])
                       for tree in rf.estimators_],dtype=float)
            if tree_prediction.shape!=(len(rf.estimators_),len(held)):
                raise ValueError("incorrect trained-only RF ensemble prediction shape")
            proxy_std=np.std(tree_prediction,axis=0,ddof=0)
            mean=np.full(len(held),float(np.mean(y[train])))
            state["source_group_risk"]=select_family_groups(
                [groups[int(i)] for i in held],y[held],pred,mean,proxy_std)
            state["source_group_risk"]["same_source_family_baseline_training_only"]=True
            state["source_group_risk"]["fixed_fraction_only_RF_not_0150_geometry_RF"]=True
            eligible+=1
        summary[family]=state
    if total_rows!=len(y) or set(summary)!=set(ANION_PROXY_BINS):
        raise ValueError("family-out source row partition incomplete")
    active=[s for s in summary.values() if s["source_group_risk"] is not None]
    outcomes={f"{int(q*100)}pct":{
        "eligible_family_count":len(active),
        "families_better_than_full_and_blind_mean":sum(
            s["source_group_risk"]["risk_coverage"][f"{int(q*100)}pct"]["reduced_risk_versus_full"]
            and s["source_group_risk"]["risk_coverage"][f"{int(q*100)}pct"]["reduced_risk_versus_blind_mean"]
            for s in active),
        "family_equal_weight_RF_macro_MAE_full":_round(np.mean([
            s["source_group_risk"]["RF_full_group_MAE"] for s in active])) if active else None,
        "family_equal_weight_RF_macro_MAE_selected":_round(np.mean([
            s["source_group_risk"]["risk_coverage"][f"{int(q*100)}pct"]["selected_RF_group_MAE"]
            for s in active])) if active else None,
        "all_families_improved_both_comparators":bool(active) and all(
            s["source_group_risk"]["risk_coverage"][f"{int(q*100)}pct"]["reduced_risk_versus_full"]
            and s["source_group_risk"]["risk_coverage"][f"{int(q*100)}pct"]["reduced_risk_versus_blind_mean"]
            for s in active)
    } for q in COVERAGES}
    if eligible<2:
        decision="INCONCLUSIVE_TOO_FEW_SOURCE_FAMILIES"
    elif all(v["all_families_improved_both_comparators"] for v in outcomes.values()):
        decision="PASS_RETROSPECTIVE_FAMILY_OUT_ALL_ELIGIBLE_FAMILIES_ONLY"
    elif all(v["families_better_than_full_and_blind_mean"]==0 for v in outcomes.values()):
        decision="FAIL_SOURCE_FAMILY_TRANSFER_SELECTIVITY"
    else:
        decision="INCONCLUSIVE_MIXED_OR_NONTRANSFERABLE_SOURCE_FAMILIES"
    return {
        "schema_version":SCHEMA,
        "original_public_upstream_commit":prior["original_upstream_commit"],
        "original_train_source_records":prior["original_source_train_count"],
        "original_reserved_public_TEST_unread":prior["original_official_test_reserved_unread"],
        "original_public_TEST_scored_or_used_in_selection":False,
        "uncensored_numeric_original_TRAIN_records":len(y),
        "original_censored_excluded":prior["original_raw_censored_upper_bounds_excluded"],
        "original_connected_DOI_formula_groups":len(set(groups)),
        "source_processed_CSV_SHA256":prior["source_processed_csv_sha256"],
        "source_raw_workbook_SHA256":prior["original_raw_workbook_sha256"],
        "source_train_label_policy_SHA256":prior["original_raw_train_label_policy_sha256"],
        "fixed_original_fraction_RF_hyperparameters":dict(RF_PARAMS),
        "family_out_group_embargo_is_exact_0158_policy":True,
        "all_labels_are_original_TRAIN_only":True,
        "n_eligible_families":eligible,
        "family_source_coverage":summary,
        "across_family_equal_weight_score":outcomes,
        "solo_family_out_risk_transfer_status":decision,
        "this_is_retrospective_exploratory_public_SOURCE_not_prospective_independent":True,
        "RF_tree_disagreement_not_calibrated_physical_uncertainty_probability":True,
        "physically_authenticated_independent_materials":0,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_external_GO":False,
    }


def run_real_source(checkout:Path,destination:Path):
    original=Path(checkout).resolve(strict=True)
    target=Path(destination).resolve()
    if target.exists() or target==original or original in target.parents:
        raise ValueError("must not overwrite original source, truth or prior receipt")
    with tempfile.TemporaryDirectory(prefix="rhombus-0182-src-") as folder:
        prior,ephemeral=run_official_original_oof(
            original,Path(folder)/"source0146",return_internal=True)
        result=evaluate_original_family_out(prior,ephemeral)
        target.parent.mkdir(parents=True,exist_ok=True)
        staged=Path(tempfile.mkdtemp(prefix=".rhombus-0182-",dir=target.parent))
        try:
            (staged/"real_source_family_out_risk_0182.json").write_bytes(
                _json_bytes(result)+b"\n")
            if target.exists():raise ValueError("append-only public benchmark output race")
            staged.rename(target)
        finally:
            if staged.exists():shutil.rmtree(staged)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    a=p.parse_args()
    result=run_real_source(a.original_obelix_checkout,a.output_dir)
    print("0182_REAL_OBELIX_SOLO_FAMILY_OUT_UNCERTAINTY_SELECTIVITY_PASS")
    print(json.dumps({
        "numeric_original_TRAIN":result["uncensored_numeric_original_TRAIN_records"],
        "eligible_families":result["n_eligible_families"],
        "family_transfer_status":result["solo_family_out_risk_transfer_status"],
        "family_summary":{name:{"status":item["status"],
            "heldout_rows":item["original_public_heldout_rows"],
            "groups":item["heldout_connected_groups"],
            "risk":item["source_group_risk"]}
            for name,item in result["family_source_coverage"].items()},
        "physical_GO":False},sort_keys=True))


if __name__=="__main__":main()
