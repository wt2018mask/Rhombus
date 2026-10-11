"""0159-D/E: frozen-budget useful-candidate selection and abstention stress.

For each original 0150 genuinely whole-family-excluded source TRAIN cohort:
- refit the exact 0150 RF and 0157 fixed group-balanced RF on ONLY the
  nonfamily, connected-source-group-embargoed training rows;
- spend equal top 10%/20% review budget comparing true heldout log10 ionic
  conductivity of selected candidates, and oracle top-budget overlap;
- on the unweighted RF compare fully label-free chemical similarity vs
  tree disagreement vs seeded random abstention at fixed 25%/50%/75% coverage.
This tests the material-selection *utility* objective directly and not just
mean regression MAE. All findings are original source public TRAIN diagnostic
only; no independently authenticated specimens, no official public TEST.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import _json_bytes
from scripts.science.obelix_real_grouped_oof_0146 import run_official_original_oof
from scripts.science.obelix_original_author_features_0149 import (
    _fold_impute_geometry, load_original_train_features,
)
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_rf_source_shift_0150 import (
    _leave_chemical_class_out, MIN_CLASS_ROWS, MIN_CLASS_GROUPS,
)
from scripts.science.obelix_group_failure_audit_0148 import (
    _family_proxy, ANION_PROXY_BINS,
)
from scripts.science.obelix_balanced_rf_0157 import (
    _round, _scores, train_only_group_weights,
)
from scripts.science.obelix_family_ood_weighted_rf_0158 import (
    separate_family_with_group_embargo,
)

SCHEMA="rhombus-0159-source-TRAIN-whole-chemistry-family-budget-screening-abstention-v1"
SCREEN_BUDGETS=(0.10,0.20)
SELECTIVE_COVERAGES=(0.25,0.50,0.75)
FIRST_PARTY_TEST_RESERVED=121
SOURCE_EXPECTED=449


def chemical_train_similarity(train_composition, unseen_composition):
    """Only original source TRAIN descriptors, no target labels or heldout fitting."""
    tr=np.asarray(train_composition,dtype=float)
    te=np.asarray(unseen_composition,dtype=float)
    if (tr.ndim!=2 or te.ndim!=2 or tr.shape[1]!=118 or te.shape[1]!=118
        or len(tr)<1 or len(te)<1 or not np.isfinite(tr).all()
        or not np.isfinite(te).all() or (tr<0).any() or (te<0).any()):
        raise ValueError("invalid elemental composition data for support")
    tn=np.linalg.norm(tr,axis=1)
    vn=np.linalg.norm(te,axis=1)
    if (tn<=0).any() or (vn<=0).any():
        raise ValueError("zero source fractional descriptor is invalid")
    return np.max((te/vn[:,None]) @ (tr/tn[:,None]).T,axis=1)


def stable_blind_rank(n,family):
    """Reproducible label-free random-order baseline, no array ordering tie."""
    if n<2:
        raise ValueError("source cohort too small for prospective review budget")
    return np.asarray([int.from_bytes(hashlib.sha256(
        ("rhombus-0159-fixed-blind:"+family+":"+str(i)).encode()).digest()[:8],"big")
        for i in range(n)],dtype=np.uint64)


def take_budget_ranked(score,k):
    score=np.asarray(score,dtype=float)
    if not 1<=k<=len(score) or not np.isfinite(score).all():
        raise ValueError("invalid predeclared fixed review budget or score")
    return np.lexsort((np.arange(len(score)), -score))[:k]


def screening_at_budgets(y, scores, family):
    """Top high-conductivity observed log10 labels for equal-size inspection."""
    y=np.asarray(y,dtype=float)
    if not np.isfinite(y).all() or len(y)<MIN_CLASS_ROWS:
        raise ValueError("insufficient actual original TRAIN labels")
    if any(len(np.asarray(x))!=len(y) for x in scores.values()):
        raise ValueError("unaligned prediction/selection scores")
    random=stable_blind_rank(len(y),family).astype(float)
    pool={"blind_random_order":random,**scores}
    results={}
    for budget in SCREEN_BUDGETS:
        k=max(1,int(np.ceil(budget*len(y))))
        oracle=set(take_budget_ranked(y,k))
        # Exact hypergeometric chance expectation, not one favorable
        # or unfavorable deterministic blind random draw.
        row={"analytic_uniform_blind_random_expectation":{
            "source_pool_rows":len(y),
            "review_budget_rows":k,
            "expected_oracle_top_budget_hits":_round(k*k/len(y)),
            "expected_oracle_top_budget_recall":_round(k/len(y)),
            "expected_mean_selected_log10_conductivity":_round(np.mean(y)),
            "statistical_significance_or_independent_material_claim":False,
        }}
        for name,ranking in pool.items():
            picks=take_budget_ranked(ranking,k)
            row[name]={
                "selected_original_source_rows":k,
                "mean_actual_selected_log10_conductivity":_round(np.mean(y[picks])),
                "actual_source_oracle_top_budget_recovered":len(oracle & set(picks.tolist())),
                "source_oracle_recall_at_budget":_round(len(oracle & set(picks.tolist()))/k),
            }
        results[str(int(budget*100))+"pct"]=row
    return results


def selective_risk(y,pred,train_fraction,held_fraction,per_tree,family):
    """Unlabeled candidate acceptance, then label-based retrospective scoring."""
    y=np.asarray(y,dtype=float)
    prediction=np.asarray(pred,dtype=float)
    trees=np.asarray(per_tree,dtype=float)
    if (y.ndim!=1 or prediction.shape!=y.shape or
        trees.ndim!=2 or trees.shape[1]!=len(y) or len(trees)<2 or
        not np.isfinite(y).all() or not np.isfinite(prediction).all() or
        not np.isfinite(trees).all()):
        raise ValueError("incomplete original source error or model disagreement")
    similarity=chemical_train_similarity(train_fraction,held_fraction)
    spread=np.std(trees,axis=0)
    ranking={
        "chemical_similarity_high":similarity,
        "RF_tree_disagreement_low":-spread,
        "blind_random_acceptance":stable_blind_rank(len(y),family).astype(float),
    }
    out={"unselective_100pct_original_RF_log10_MAE":_scores(y,pred)["log10_MAE"],
         "support_and_uncertainty_score_depend_on_heldout_labels":False,
         "trained_RF_num_trees":len(trees),
         "coverage_curves":{}}
    for coverage in SELECTIVE_COVERAGES:
        k=max(1,int(np.ceil(coverage*len(y))))
        at={}
        for name,score in ranking.items():
            ix=take_budget_ranked(score,k)
            dropped=np.ones(len(y),dtype=bool);dropped[ix]=False
            selected_error=np.abs(y[ix]-prediction[ix])
            # Selection is label-blind; labels used only after masks freeze.
            at[name]={
                "source_rows_accepted":k,
                "source_rows_abstained":int(np.count_nonzero(dropped)),
                "accepted_RF_log10_MAE":_round(np.mean(selected_error)),
                "abstained_RF_log10_MAE":_round(np.mean(np.abs(
                    y[dropped]-prediction[dropped]))) if np.any(dropped) else None,
            }
        out["coverage_curves"][str(int(coverage*100))+"pct"]=at
    return out


def evaluate_original_0159(prior,ephemeral,raw,geometry,strict_official=True):
    from sklearn.ensemble import RandomForestRegressor
    y=np.asarray(ephemeral["y"],dtype=float)
    fraction=np.asarray(ephemeral["x"],dtype=float)
    groups=tuple(ephemeral["groups"])
    n=len(y)
    if (n<MIN_CLASS_ROWS or fraction.shape!=(n,118) or raw.shape!=(n,118) or
        geometry.shape!=(n,7) or len(groups)!=n or len(set(groups))<MIN_CLASS_GROUPS or
        not np.isfinite(y).all() or not np.isfinite(fraction).all() or
        not np.isfinite(raw).all()):
        raise ValueError("invalid original official numerical source data")
    if (prior["original_official_test_reserved_unread"]<1 or
        prior["scientific_qualification_authorized"] is not False or
        prior["all_folds_have_zero_group_identity_leakage"] is not True or
        prior["out_of_fold_numeric_source_records_scored"]!=n):
        raise ValueError("source test/quarantine/lineage gate violated")
    if strict_official and (n!=SOURCE_EXPECTED or len(set(groups))!=102 or
        prior["original_source_train_count"]!=478 or
        prior["original_official_test_reserved_unread"]!=FIRST_PARTY_TEST_RESERVED or
        prior["original_raw_censored_upper_bounds_excluded"]!=29):
        raise ValueError("original pinned real public TRAIN cohort drift")
    labels=tuple(_family_proxy(row) for row in fraction)
    legacy=_leave_chemical_class_out(y,groups,labels,raw,geometry)
    family_results={}
    counts=0
    for family in ANION_PROXY_BINS:
        held,train,embargo=separate_family_with_group_embargo(groups,labels,family)
        counts+=len(held)
        groups_held={groups[int(i)] for i in held}
        eligible=(len(held)>=MIN_CLASS_ROWS and
                  len(groups_held)>=MIN_CLASS_GROUPS and len(train)>=20)
        if legacy[family]["status"]!=(
            "REAL_RETROSPECTIVE_CLASS_SHIFT_SCORED" if eligible
            else "NOT_ADMITTED_TOO_FEW_ROWS_OR_GROUPS"):
            raise ValueError("0150 frozen chemistry family source split changed")
        record={
            "family":family,
            "heldout_rows":len(held),
            "heldout_connected_source_groups":len(groups_held),
            "training_rows_after_connected_source_group_embargo":len(train),
            "other_family_source_rows_embargoed":embargo,
            "state":"ACTUAL_BUDGET_SCORING" if eligible else "NOT_ADMITTED",
            "genuinely_external_or_independent_material_test":False,
        }
        if not eligible:
            family_results[family]=record;continue
        tr_geo,te_geo,_=_fold_impute_geometry(geometry[train],geometry[held])
        train_x=np.concatenate((raw[train],tr_geo),axis=1)
        val_x=np.concatenate((raw[held],te_geo),axis=1)
        rf=RandomForestRegressor(**RF_PARAMS)
        rf.fit(train_x,y[train])
        p=rf.predict(val_x)
        if _scores(y[held],p)!=legacy[family]["RF"]:
            raise ValueError("original 0150 RF exact performance/source protocol changed")
        w=train_only_group_weights(groups,train)
        weighted=RandomForestRegressor(**RF_PARAMS)
        if np.all(w==w[0]):
            weighted.fit(train_x,y[train])
        else:
            weighted.fit(train_x,y[train],sample_weight=w)
        weighted_p=weighted.predict(val_x)
        tr_mean=np.mean(y[train])
        tree_preds=np.asarray([tree.predict(val_x) for tree in rf.estimators_])
        observed=screening_at_budgets(y[held],{
            "original_RF":p, "balanced_RF_0157":weighted_p,
        },family)
        risk=selective_risk(y[held],p,fraction[train],fraction[held],tree_preds,family)
        record.update({
            "original_RF_log10_MAE":_scores(y[held],p)["log10_MAE"],
            "group_balanced_RF_log10_MAE":_scores(y[held],weighted_p)["log10_MAE"],
            "same_training_cheap_mean_log10_MAE":_scores(y[held],np.full(len(held),tr_mean))["log10_MAE"],
            "higher_log10_measurement_means_higher_conductivity":True,
            "screening_budget_top_conductivity":observed,
            "RF_abstention_risk_coverage":risk,
            "fixed_training_RF_hyperparams_reused":True,
            "heldout_label_used_in_ranking_or_abstention":False,
        })
        family_results[family]=record
    if counts!=n:
        raise ValueError("chemistry source cohort coverage drift")
    return {
      "schema_version":SCHEMA,
      "source_commit":prior.get("original_upstream_commit"),
      "original_official_TRAIN":prior["original_source_train_count"],
      "original_public_TEST_reserved_unread":prior["original_official_test_reserved_unread"],
      "original_public_TEST_training_or_scoring":False,
      "original_uncensored_numeric_source_rows":n,
      "original_DOI_formula_connected_groups":len(set(groups)),
      "family_results":family_results,
      "screening_budgets_percent":[10,20],
      "selective_acceptance_percent":[25,50,75],
      "predeclared_error_selection_not_optimized_on_family_labels":True,
      "source_rows_not_qualified_distinct_experimental_specimens":True,
      "material_selection_outcome_is_source_LABEL_not_verified_physical_discovery":True,
      "MLIP_MD_transport_computed":False,
      "scientific_GO":False,
      "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
    }


def run_original(checkout:Path, output:Path):
    source=Path(checkout).resolve(strict=True)
    out=Path(output).resolve()
    if out.exists() or out==source or source in out.parents:
        raise ValueError("output must not overwrite original immutable source")
    with tempfile.TemporaryDirectory(prefix="rhombus-0159-private-") as temp:
        prior,ephemeral=run_official_original_oof(
            source,Path(temp)/"source-0146",return_internal=True)
        raw,geometry=load_original_train_features(
            source,source_ids=ephemeral["source_ids"],
            expected_processed_sha256=prior["source_processed_csv_sha256"],
            reference_fractions=ephemeral["x"])
        result=evaluate_original_0159(prior,ephemeral,raw,geometry)
        out.parent.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix=".0159-aggregate-",dir=out.parent))
        try:
            (stage/"budgeted_screening_selective_risk_0159.json").write_bytes(
                _json_bytes(result)+b"\n")
            if out.exists():
                raise ValueError("result path collision")
            stage.rename(out)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    result=run_original(args.original_obelix_checkout,args.output_dir)
    print("0159_ACTUAL_ORIGINAL_PUBLIC_TRAIN_EQUALLY_BUDGETED_SELECTION_ABSTENTION_COMPLETE")
    print(json.dumps({
        "families":{k:{
          "status":v["state"],
          "RF_MAE":v.get("original_RF_log10_MAE"),
          "balanced_MAE":v.get("group_balanced_RF_log10_MAE"),
          "screen_10pct":v.get("screening_budget_top_conductivity",{}).get("10pct"),
          "accept_50pct":v.get("RF_abstention_risk_coverage",{}).get("coverage_curves",{}).get("50pct"),
        } for k,v in result["family_results"].items()},
        "science_GO":False,
    },sort_keys=True))
    return 0

if __name__=="__main__":
    main()
