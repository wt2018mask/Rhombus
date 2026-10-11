"""0160-E: genuinely group-capped original-source candidate screening.

0159 evaluated each numeric OBELiX TRAIN row as a candidate, despite some
rows belonging to the same large DOI/composition connected identity group.
This experiment spends each 10%/20% fixed review unit on *one group*, with
group median out-of-family source labels only used after ranks are frozen.
The original 0150 entire-anion-family embargo and frozen 0157 RF weighting
are unchanged. No independent specimens, no public original TEST access.
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

from rhombus.qualification.obelix_benchmark_intake import _json_bytes
from scripts.science.obelix_real_grouped_oof_0146 import run_official_original_oof
from scripts.science.obelix_original_author_features_0149 import (
    _fold_impute_geometry, load_original_train_features,
)
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_rf_source_shift_0150 import (
    _leave_chemical_class_out, MIN_CLASS_GROUPS, MIN_CLASS_ROWS,
)
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy, ANION_PROXY_BINS
from scripts.science.obelix_balanced_rf_0157 import (
    _round, _scores, train_only_group_weights,
)
from scripts.science.obelix_family_ood_weighted_rf_0158 import (
    separate_family_with_group_embargo,
)
from scripts.science.obelix_budget_selective_0159 import (
    SCREEN_BUDGETS, screening_at_budgets, take_budget_ranked,
    chance_oracle_hit_tail,
)

SCHEMA="rhombus-0160-OBELIX-real-source-connected-identity-group-budget-screening-v1"


def _blind_group_score(group, family):
    """Stable pseudo-random review priority depends only on source group ID."""
    h=hashlib.sha256(("rhombus-0160-group-blind:"+family+":"+str(group)).encode()).digest()
    return int.from_bytes(h[:8],"big") / (2**64)


def group_capped_screening(held_groups, y, predictions, family):
    """At most one review unit per connected DOI/formula group.

    Predictions and group membership define ranking. Measured heldout source
    labels are used ONLY after the group rankings are complete, to score
    retrospective median-label group outcomes.
    """
    y=np.asarray(y,dtype=float)
    if (y.ndim!=1 or len(y)<MIN_CLASS_ROWS or not np.isfinite(y).all()
        or len(held_groups)!=len(y) or family not in ANION_PROXY_BINS):
        raise ValueError("invalid original family group-screening population")
    predicted={}
    for name,vals in predictions.items():
        a=np.asarray(vals,dtype=float)
        if a.shape!=y.shape or not np.isfinite(a).all() or name=="blind_group":
            raise ValueError("group model prediction misaligned")
        predicted[name]=a
    if not {"original_RF","balanced_RF_0157"}<=set(predicted):
        raise ValueError("two fixed source RF comparators missing")

    membership=defaultdict(list)
    for i,g in enumerate(held_groups):
        membership[str(g)].append(i)
    names=sorted(membership)
    n=len(names)
    if n<MIN_CLASS_GROUPS:
        raise ValueError("insufficient independent connected identity group units")
    counts=np.asarray([len(membership[g]) for g in names],dtype=int)
    if not np.all(counts>0) or counts.sum()!=len(y):
        raise ValueError("group units overlap or omit heldout source rows")
    # Define one retrospective outcome per group as its median numeric source
    # label, not its max/highest cherry-picked sample. Source groups are NOT
    # independent physical material samples.
    true_group=np.asarray([np.median(y[membership[g]]) for g in names])
    pred_groups={key:np.asarray([
        np.median(predicted[key][membership[g]]) for g in names
    ]) for key in predicted}
    pred_groups["blind_group"] = np.asarray([
        _blind_group_score(g,family) for g in names
    ])
    out={}
    for budget in SCREEN_BUDGETS:
        k=max(1,int(np.ceil(n*budget)))
        oracle=set(take_budget_ranked(true_group,k).tolist())
        record={
            "group_pool_units":n,"one_connected_group_one_review_unit":True,
            "review_budget_group_units":k,
            "analytical_uniform_group_draw_expected_oracle_hits":_round(k*k/n),
            "analytical_uniform_group_draw_expected_top_recall":_round(k/n),
        }
        for method,score in pred_groups.items():
            indices=take_budget_ranked(score,k)
            hits=len(set(indices.tolist())&oracle)
            record[method]={
                "selected_connected_group_units":k,
                "source_group_median_label_oracle_top_hits":hits,
                "source_group_median_label_oracle_recall":_round(hits/k),
                "actual_selected_group_median_log10_conductivity":_round(
                    np.mean(true_group[indices])),
                "exact_uniform_group_random_right_tail_at_least_hits":
                    chance_oracle_hit_tail(n,k,hits),
            }
        out[f"{int(round(budget*100))}pct"]=record
    return {
        "original_source_rows_in_family":len(y),
        "connected_identity_group_count":n,
        "max_rows_in_one_connected_group":int(max(counts)),
        "largest_group_fraction_of_source_rows":_round(max(counts)/len(y)),
        "source_rows_beyond_one_per_group":len(y)-n,
        "median_group_numeric_source_label_not_independent_specimen":True,
        "outcome_is_retrospective_group_median_not_actual_one_sample_measured":True,
        "group_budget_selection":out,
    }


def evaluate_original_0160(prior, ephemeral, raw, geometry, *, strict_official=True):
    from sklearn.ensemble import RandomForestRegressor
    y=np.asarray(ephemeral["y"],dtype=float)
    x=np.asarray(ephemeral["x"],dtype=float)
    groups=tuple(ephemeral["groups"])
    n=len(y)
    if (n<MIN_CLASS_ROWS or x.shape!=(n,118) or raw.shape!=(n,118) or
        geometry.shape!=(n,7) or len(groups)!=n or
        not np.isfinite(y).all() or not np.isfinite(raw).all() or
        not np.isfinite(x).all()):
        raise ValueError("invalid original numeric TRAIN population")
    if (prior["original_official_test_reserved_unread"]<1
        or prior["scientific_qualification_authorized"] is not False
        or prior["all_folds_have_zero_group_identity_leakage"] is not True
        or prior["out_of_fold_numeric_source_records_scored"]!=n):
        raise ValueError("TEST quarantine or grouped source constraint")
    if strict_official and (n!=449 or len(set(groups))!=102
        or prior["original_source_train_count"]!=478
        or prior["original_official_test_reserved_unread"]!=121
        or prior["original_raw_censored_upper_bounds_excluded"]!=29):
        raise ValueError("immutable original OBELiX public TRAIN population drift")
    labels=tuple(_family_proxy(a) for a in x)
    prior0150=_leave_chemical_class_out(y,groups,labels,raw,geometry)
    result={}
    total=0
    for family in ANION_PROXY_BINS:
        held,train,embargo=separate_family_with_group_embargo(groups,labels,family)
        total+=len(held)
        admissible=(len(held)>=MIN_CLASS_ROWS and
                    len(set(groups[int(i)] for i in held))>=MIN_CLASS_GROUPS
                    and len(train)>=20)
        prior_state=prior0150[family]["status"]
        if (prior_state!=("REAL_RETROSPECTIVE_CLASS_SHIFT_SCORED" if admissible
                         else "NOT_ADMITTED_TOO_FEW_ROWS_OR_GROUPS")
            or prior0150[family]["training_source_rows_after_group_embargo"]!=len(train)
            or prior0150[family]["other_proxy_rows_embargoed_due_to_shared_identity_group"]!=embargo):
            raise ValueError("original 0150 source group embargo/split changed")
        record={
            "family":family,"source_rows_heldout":len(held),
            "source_train_rows_after_embargo":len(train),
            "original_0150_family_holdout_verbatim":True,
            "group_selection":"ACTUAL" if admissible else "NOT_ADMITTED",
        }
        if admissible:
            tg,vg,_=_fold_impute_geometry(geometry[train],geometry[held])
            a=np.concatenate((raw[train],tg),axis=1)
            b=np.concatenate((raw[held],vg),axis=1)
            rf=RandomForestRegressor(**RF_PARAMS)
            rf.fit(a,y[train])
            original=rf.predict(b)
            if _scores(y[held],original)!=prior0150[family]["RF"]:
                raise ValueError("original 0150 unweighted RF benchmark drift")
            weights=train_only_group_weights(groups,train)
            weighted=RandomForestRegressor(**RF_PARAMS)
            if np.all(weights==weights[0]):
                weighted.fit(a,y[train])
            else:
                weighted.fit(a,y[train],sample_weight=weights)
            altered=weighted.predict(b)
            hgroups=[groups[int(i)] for i in held]
            capped=group_capped_screening(
                hgroups,y[held],{"original_RF":original,"balanced_RF_0157":altered},family)
            rows=screening_at_budgets(
                y[held],{"original_RF":original,"balanced_RF_0157":altered},family)
            record.update({
                "group_capped":capped,
                "original_0159_row_budget_comparator":{
                    k:{
                        "review_budget_rows":v["analytic_uniform_blind_random_expectation"]["review_budget_rows"],
                        "original_RF_hits":v["original_RF"]["actual_source_oracle_top_budget_recovered"],
                        "balanced_RF_hits":v["balanced_RF_0157"]["actual_source_oracle_top_budget_recovered"],
                    }
                    for k,v in rows.items()
                },
                "original_0150_RF_log10_MAE":_scores(y[held],original)["log10_MAE"],
                "balanced_RF_log10_MAE":_scores(y[held],altered)["log10_MAE"],
                "no_heldout_label_in_prediction_or_group_rank":True,
            })
        result[family]=record
    if total!=n or set(result)!=set(ANION_PROXY_BINS):
        raise ValueError("heldout original source accounting incomplete")
    return {
        "schema_version":SCHEMA,
        "original_source_commit":prior.get("original_upstream_commit"),
        "official_TRAIN_total":prior["original_source_train_count"],
        "official_TEST_reserved_unread":prior["original_official_test_reserved_unread"],
        "official_TEST_scored_or_trained":False,
        "eligible_numeric_public_TRAIN":n,
        "connected_train_identity_groups":len(set(groups)),
        "whole_chemistry_family_embargo_reused":True,
        "fixed_review_group_budgets_percent":[10,20],
        "group_outcome":"MEDIAN_WITHIN_SOURCE_DOI_FORMULA_GROUP",
        "group_aggregation_not_an_independent_material_sample":True,
        "family_source_group_screening":result,
        "new_external_source_or_independent_blind":False,
        "physical_materials_newly_qualified":0,
        "scientific_GO":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
    }


def run_original(checkout:Path, dest:Path):
    original=Path(checkout).resolve(strict=True)
    output=Path(dest).resolve()
    if output.exists() or output==original or original in output.parents:
        raise ValueError("output must be new and outside immutable original source")
    with tempfile.TemporaryDirectory(prefix="rhombus-0160-private-") as tmp:
        prior,e=run_official_original_oof(
            original,Path(tmp)/"0146-source",return_internal=True)
        raw,geo=load_original_train_features(
            original,source_ids=e["source_ids"],
            expected_processed_sha256=prior["source_processed_csv_sha256"],
            reference_fractions=e["x"])
        report=evaluate_original_0160(prior,e,raw,geo)
        output.parent.mkdir(parents=True,exist_ok=True)
        staged=Path(tempfile.mkdtemp(prefix=".rhombus-0160-",dir=output.parent))
        try:
            (staged/"original_group_capped_screening_0160.json").write_bytes(
                _json_bytes(report)+b"\n")
            if output.exists():
                raise ValueError("output already created")
            staged.rename(output)
        finally:
            if staged.exists():
                shutil.rmtree(staged)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    data=run_original(args.original_obelix_checkout,args.output_dir)
    print("0160_ORIGINAL_CONNECTED_GROUP_CAPPED_SELECTION_RUN_COMPLETE")
    print(json.dumps({
        "source_numeric_TRAIN_rows":data["eligible_numeric_public_TRAIN"],
        "source_unique_identity_groups":data["connected_train_identity_groups"],
        "family_results":{
            k:{"state":v["group_selection"],
               "group_budget":v.get("group_capped",{}).get("group_budget_selection"),
               "group_count":v.get("group_capped",{}).get("connected_identity_group_count"),
               "original_0159_row_hits":v.get("original_0159_row_budget_comparator")}
            for k,v in data["family_source_group_screening"].items()
        },
        "scientific_GO":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
