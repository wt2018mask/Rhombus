"""0184 SOLO family-specialized ORIGINAL OBELiX TRAIN benchmark.

Compare O_ONLY and S_ONLY family-trained models against a pooled model on
strict connected DOI/formula identity-group OOF folds WITHIN each family.
No retrospective selection activates models, and all original official
TEST rows remain unread. Anion element-presence is a proxy, not phase.
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

from rhombus.qualification.obelix_benchmark_intake import SOURCE_COMMIT, _json_bytes
from scripts.science.obelix_real_grouped_oof_0146 import run_official_original_oof
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy, ANION_PROXY_BINS

SCHEMA="rhombus-0184-solo-public-original-train-family-specialization-v1"
TARGETS=("O_ONLY","S_ONLY")
FOLDS=5
BOOTSTRAPS=512
BOOTSTRAP_SEED=184
RIDGE_ALPHA=10.0
ABSOLUTE_GROUP_MAE_CANDIDATE_THRESHOLD=1.0
MODEL_NAMES=("POOLED_RF","FAMILY_RF","FAMILY_RIDGE","FAMILY_TRAIN_MEAN")


def connected_group_folds(indices,groups):
    """Balanced deterministic group folds, based ONLY on training source IDs."""
    source_groups=defaultdict(list)
    for idx in indices: source_groups[str(groups[int(idx)])].append(int(idx))
    if len(source_groups)<FOLDS:
        raise ValueError("too few target-family connected identities")
    batches=[[] for _ in range(FOLDS)]
    loads=[0]*FOLDS
    counts=[0]*FOLDS
    for group,rows in sorted(source_groups.items(),key=lambda item:(-len(item[1]),item[0])):
        fold=min(range(FOLDS),key=lambda z:(loads[z],counts[z],z))
        batches[fold].extend(rows)
        loads[fold]+=len(rows)
        counts[fold]+=1
    if not all(batches) or sorted(i for part in batches for i in part)!=sorted(indices):
        raise ValueError("incomplete group-only source family split")
    if len(set(groups[i] for rows in batches for i in rows))!=len(source_groups):
        raise ValueError("source group duplicated across folds")
    return tuple(np.asarray(sorted(v),dtype=int) for v in batches)


def source_scores(y,pred,groups):
    """All groups counted equally; never pretend they are IID physical samples."""
    y=np.asarray(y,dtype=float)
    p=np.asarray(pred,dtype=float)
    if y.shape!=p.shape or not len(y) or not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError("missing or nonfinite actual source OOF score")
    bygroup=defaultdict(list)
    for i,g in enumerate(groups):bygroup[str(g)].append(float(abs(y[i]-p[i])))
    group_errors=np.array([np.mean(v) for _,v in sorted(bygroup.items())],dtype=float)
    return {
        "source_rows":len(y),
        "source_connected_groups":len(bygroup),
        "row_MAE_log10":round(float(np.mean(abs(y-p))),8),
        "equal_group_macro_MAE_log10":round(float(np.mean(group_errors)),8),
        "equal_group_p90_abs_error_log10":round(float(np.percentile(group_errors,90)),8),
        "worst_connected_source_group_MAE_log10":round(float(np.max(group_errors)),8),
        "connected_source_groups_not_independent_physical_pellets":True,
    }


def paired_group_delta(y,special,reference,groups):
    """Diagnostic resampling of connected PUBLIC groups, not external intervals."""
    d=defaultdict(list)
    for i,g in enumerate(groups):
        d[str(g)].append(float(abs(special[i]-y[i])-abs(reference[i]-y[i])))
    v=np.asarray([float(np.mean(row)) for _,row in sorted(d.items())],dtype=float)
    if len(v)<5 or not np.isfinite(v).all():
        raise ValueError("too few physical-source groups for diagnostic paired delta")
    rng=np.random.default_rng(BOOTSTRAP_SEED)
    sample=np.mean(v[rng.integers(0,len(v),size=(BOOTSTRAPS,len(v)))],axis=1)
    return {
        "family_specialist_minus_reference_group_macro_MAE":round(float(np.mean(v)),8),
        "heuristic_group_bootstrap_95pct_interval":[
            round(float(z),8) for z in np.quantile(sample,[.025,.975])],
        "number_of_connected_source_groups":len(v),
        "source_groups_specialist_better":int(np.sum(v<0)),
        "source_groups_specialist_worse":int(np.sum(v>0)),
        "source_groups_tied":int(np.sum(v==0)),
        "diagnostic_NOT_independent_physical_experimental_CI":True,
    }


def compute_specialists(prior,ephemeral,*,strict=True):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    x=np.asarray(ephemeral["x"],dtype=float)
    y=np.asarray(ephemeral["y"],dtype=float)
    groups=tuple(ephemeral["groups"])
    if (x.ndim!=2 or x.shape!=(len(y),118) or len(y)!=len(groups) or
        not np.isfinite(x).all() or not np.isfinite(y).all() or len(ephemeral["fold_indices"])!=5
        or prior["scientific_qualification_authorized"] is not False
        or prior["all_folds_have_zero_group_identity_leakage"] is not True):
        raise ValueError("untrusted original source TRAIN numeric cohort")
    if strict and (len(y)!=449 or len(set(groups))!=102
        or prior["original_upstream_commit"]!=SOURCE_COMMIT
        or prior["original_source_train_count"]!=478
        or prior["original_official_test_reserved_unread"]!=121
        or prior["original_raw_censored_upper_bounds_excluded"]!=29):
        raise ValueError("original publisher source/official TEST quarantine drift")
    labels=tuple(_family_proxy(row) for row in x)
    family_reports={}
    for family in ANION_PROXY_BINS:
        ids=np.asarray([i for i,z in enumerate(labels) if z==family],dtype=int)
        n=len(ids)
        connected=len(set(groups[i] for i in ids))
        if family not in TARGETS:
            family_reports[family]={
                "status":"DEFERRED_NOT_ENOUGH_PREDECLARED_SCOPE",
                "original_source_rows":n,
                "connected_source_groups":connected,
                "eligible_for_specialization":False,
                "actual_fold_scores":None,
                "predictions_exposed_to_policy_selection":False,
            }
            continue
        if n<20 or connected<10:
            raise ValueError("predeclared target family count too small to evaluate")
        heldouts=connected_group_folds(ids,groups)
        oof={name:np.full(n,np.nan) for name in MODEL_NAMES}
        positions={int(row):j for j,row in enumerate(ids)}
        observed=set()
        folds=[]
        for fold,held in enumerate(heldouts,1):
            held_groups=set(groups[int(i)] for i in held)
            if observed & set(held): raise ValueError("outer group row reuse")
            observed.update(map(int,held))
            safe_global=np.asarray([i for i,g in enumerate(groups) if g not in held_groups],dtype=int)
            safe_family=np.asarray([i for i in safe_global if labels[int(i)]==family],dtype=int)
            if (len(safe_global)<20 or len(safe_family)<20
                or set(groups[int(i)] for i in safe_global)&held_groups
                or set(groups[int(i)] for i in safe_family)&held_groups):
                raise ValueError("source DOI/formula connected-group leakage or missing TRAIN")
            global_rf=RandomForestRegressor(**RF_PARAMS)
            global_rf.fit(x[safe_global],y[safe_global])
            specialist_rf=RandomForestRegressor(**RF_PARAMS)
            specialist_rf.fit(x[safe_family],y[safe_family])
            ridge=make_pipeline(StandardScaler(),Ridge(alpha=RIDGE_ALPHA))
            ridge.fit(x[safe_family],y[safe_family])
            models={
                "POOLED_RF":global_rf.predict(x[held]),
                "FAMILY_RF":specialist_rf.predict(x[held]),
                "FAMILY_RIDGE":ridge.predict(x[held]),
                "FAMILY_TRAIN_MEAN":np.full(len(held),float(np.mean(y[safe_family]))),
            }
            for model,values in models.items():
                if not np.isfinite(values).all():raise ValueError("nonfinite original family-heldout prediction")
                for i,value in zip(held,values):
                    pos=positions[int(i)]
                    if not np.isnan(oof[model][pos]):
                        raise ValueError("duplicate OOF family group")
                    oof[model][pos]=value
            folds.append({
                "fold":fold,
                "outer_heldout_source_rows":len(held),
                "heldout_DOI_formula_connected_groups":len(held_groups),
                "pooled_RF_original_TRAIN_source_rows":len(safe_global),
                "specialist_RF_Ridge_Mean_TRAIN_source_rows":len(safe_family),
                "heldout_groups_in_pooled_training":0,
                "heldout_groups_in_specialist_training":0,
                "same_frozen_RF_hyperparameters_for_pooled_and_specialist":True,
                "source_labels_used_to_choose_model_for_this_fold":False,
            })
        if observed!=set(map(int,ids)) or any(not np.isfinite(v).all() for v in oof.values()):
            raise ValueError("missing eligible family source rows")
        truth=y[ids]
        local_groups=[groups[int(i)] for i in ids]
        scores={m:source_scores(truth,v,local_groups) for m,v in oof.items()}
        reference=scores["POOLED_RF"]
        family_mean=scores["FAMILY_TRAIN_MEAN"]
        sp=scores["FAMILY_RF"]
        rdiff=paired_group_delta(truth,oof["FAMILY_RF"],oof["POOLED_RF"],local_groups)
        mdiff=paired_group_delta(truth,oof["FAMILY_RF"],oof["FAMILY_TRAIN_MEAN"],local_groups)
        # Stringent PREDECLARED research-priority flag; no activation from
        # the already-public exploratory cohort, even when metrics happen to PASS.
        best=(sp["row_MAE_log10"]<reference["row_MAE_log10"]
              and sp["row_MAE_log10"]<family_mean["row_MAE_log10"]
              and sp["equal_group_macro_MAE_log10"]<reference["equal_group_macro_MAE_log10"]
              and sp["equal_group_macro_MAE_log10"]<family_mean["equal_group_macro_MAE_log10"]
              and sp["equal_group_macro_MAE_log10"]<=ABSOLUTE_GROUP_MAE_CANDIDATE_THRESHOLD
              and rdiff["heuristic_group_bootstrap_95pct_interval"][1]<0
              and mdiff["heuristic_group_bootstrap_95pct_interval"][1]<0)
        family_reports[family]={
            "status":"EXPLORATORY_RESEARCH_PRIORITIZATION_ONLY",
            "original_source_rows":n,
            "connected_source_groups":connected,
            "eligible_for_specialization":True,
            "outer_folds":folds,
            "source_scoped_model_metrics":scores,
            "FAMILY_RF_minus_POOLED_RF":rdiff,
            "FAMILY_RF_minus_FAMILY_TRAIN_MEAN":mdiff,
            "stringent_group_and_row_RF_specialist_research_candidate":bool(best),
            "domain_router_production_permission":False,
            "failure_counts":{"unscored_source_rows":0,"heldout_source_group_overlap":0},
            "family_anion_presence_is_NOT_verified_crystal_phase":True,
        }
    if set(family_reports)!=set(ANION_PROXY_BINS) or sum(v["original_source_rows"] for v in family_reports.values())!=len(y):
        raise ValueError("five family source population not exhausted")
    return {
        "schema_version":SCHEMA,
        "experiment":"SOLO_ORIGINAL_PUBLIC_TRAIN_FIXED_FAMILY_SPECIALIZATION_OOF",
        "original_upstream_commit":prior["original_upstream_commit"],
        "source_processed_CSV_SHA256":prior["source_processed_csv_sha256"],
        "source_raw_workbook_SHA256":prior["original_raw_workbook_sha256"],
        "source_train_label_policy_SHA256":prior["original_raw_train_label_policy_sha256"],
        "original_official_TRAIN_records":prior["original_source_train_count"],
        "original_official_TEST_records_RESERVED_UNREAD":prior["original_official_test_reserved_unread"],
        "original_official_TEST_features_or_labels_used":False,
        "original_eligible_uncensored_numeric_TRAIN":len(y),
        "original_censored_upper_bound_records_excluded":prior["original_raw_censored_upper_bounds_excluded"],
        "connected_original_public_source_DOI_formula_groups":len(set(groups)),
        "predeclared_focus_families":list(TARGETS),
        "predeclared_specialist_models":list(MODEL_NAMES),
        "unchanged_frozen_RF_hyperparameters":dict(RF_PARAMS),
        "ridge_only_training_standardization_alpha":RIDGE_ALPHA,
        "fixed_within_family_group_outer_folds":FOLDS,
        "research_priority_macro_group_MAE_limit":ABSOLUTE_GROUP_MAE_CANDIDATE_THRESHOLD,
        "families":family_reports,
        "public_source_predictions_were_previously_explored":True,
        "original_TEST_still_untouched_but_not_claimed_new_blind":True,
        "no_model_or_domain_router_activated_from_this_derived_result":True,
        "new_prospective_independent_physical_materials":0,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_external_GO":False,
        "next_action":"0185 solo freeze one candidate+application domain before distinct original PUBLIC source/time-cohort evaluation",
    }


def run_original(checkout:Path, output:Path):
    source=Path(checkout).resolve(strict=True)
    out=Path(output).resolve()
    if out.exists() or out==source or source in out.parents:
        raise ValueError("new derived output required outside immutable publisher source")
    with tempfile.TemporaryDirectory(prefix="rhombus-0184-") as folder:
        prior,arrays=run_official_original_oof(source,Path(folder)/"0146",return_internal=True)
        result=compute_specialists(prior,arrays)
        out.parent.mkdir(parents=True,exist_ok=True)
        tmp=Path(tempfile.mkdtemp(prefix=".rhombus-0184-output-",dir=out.parent))
        try:
            (tmp/"family_specialist_public_benchmark_0184.json").write_bytes(_json_bytes(result)+b"\n")
            if out.exists():raise ValueError("cannot replace original benchmark receipt")
            tmp.rename(out)
        finally:
            if tmp.exists():shutil.rmtree(tmp)
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--original-obelix-checkout",required=True,type=Path)
    ap.add_argument("--output-dir",required=True,type=Path)
    opts=ap.parse_args()
    r=run_original(opts.original_obelix_checkout,opts.output_dir)
    print("0184_SOLO_GENUINE_ORIGINAL_TRAIN_FAMILY_SPECIALIST_BENCHMARK_PASS")
    print(json.dumps({
        "rows":r["original_eligible_uncensored_numeric_TRAIN"],
        "source_groups":r["connected_original_public_source_DOI_formula_groups"],
        "families":{family:{
            "status":d["status"],
            "source_rows":d["original_source_rows"],
            "connected_groups":d["connected_source_groups"],
            "model_metrics":d.get("source_scoped_model_metrics"),
            "research_priority":d.get("stringent_group_and_row_RF_specialist_research_candidate"),
        } for family,d in r["families"].items()},
        "official_TEST_unread":True,
        "physical_GO":False,
    },sort_keys=True))


if __name__=="__main__": main()
