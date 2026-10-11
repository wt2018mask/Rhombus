"""0158-A: ACTUAL chemical-family-out stress of the 0157 balanced RF.

Original pinned 478 TRAIN / 121 TEST quarantined; genuine 449 public TRAIN
source numeric labels, 102 connected DOI/formula groups. Reproduce 0150
leave-anion-proxy-family-out splits and group embargo before fitting, and
compare unchanged RF vs previously fixed 0157 TRAIN-only inverse-sqrt group
weights. It is NOT external blind or independently qualified experiments.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
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
    train_only_group_weights, _round, _scores, _macro,
    FROZEN_WEIGHT_EXPONENT,
)

SCHEMA="rhombus-original-0158-real-family-out-weighted-RF-transfer-v1"
EXPECTED_ORIGINAL_S_ONLY_UNWEIGHTED_RF_MINUS_MEAN=1.0588909
GROUP_BOOTSTRAP_SEED=158
GROUP_BOOTSTRAP_SAMPLES=512


def separate_family_with_group_embargo(groups, labels, family):
    """No group shared between training and heldout composition proxy."""
    if len(groups)!=len(labels) or family not in ANION_PROXY_BINS:
        raise ValueError("unaligned proxy labels or unapproved chemical class")
    held=np.asarray([i for i,label in enumerate(labels) if label==family],dtype=int)
    held_groups={groups[int(i)] for i in held}
    allowed=np.asarray([i for i,label in enumerate(labels)
                        if label!=family and groups[i] not in held_groups],dtype=int)
    embargo=sum(label!=family and groups[i] in held_groups for i,label in enumerate(labels))
    if set(groups[int(i)] for i in allowed)&held_groups:
        raise ValueError("DOI/formula connected group leakage into training")
    return held, allowed, int(embargo)


def paired_group_uncertainty(y,original,weighted,groups,held):
    members=defaultdict(list)
    for i in held:
        members[groups[int(i)]].append(int(i))
    if len(members)<MIN_CLASS_GROUPS:
        raise ValueError("insufficient heldout original connected groups")
    diffs=np.asarray([
        np.mean(np.abs(weighted[ix]-y[ix])-np.abs(original[ix]-y[ix]))
        for _,ix in sorted(members.items())
    ],dtype=float)
    if not np.isfinite(diffs).all():
        raise ValueError("nonfinite paired group differences")
    rng=np.random.default_rng(GROUP_BOOTSTRAP_SEED)
    bs=np.mean(rng.choice(diffs,size=(GROUP_BOOTSTRAP_SAMPLES,len(diffs)),replace=True),axis=1)
    return {
        "balanced_minus_original_equal_group_macro_MAE":_round(diffs.mean()),
        "group_bootstrap_512_heuristic_95pct_interval":[
            _round(q) for q in np.quantile(bs,[0.025,0.975])],
        "source_groups_are_independent_physical_experimental_samples":False,
    }


def evaluate_original_family_out_0158(prior, ephemeral, raw, geometry, *,
                                      strict_official=True):
    from sklearn.ensemble import RandomForestRegressor
    x=np.asarray(ephemeral["x"],dtype=float)
    y=np.asarray(ephemeral["y"],dtype=float)
    groups=tuple(ephemeral["groups"])
    n=len(y)
    if (n<25 or x.shape!=(n,118) or raw.shape!=(n,118)
        or geometry.shape!=(n,7) or len(groups)!=n
        or not np.isfinite(x).all() or not np.isfinite(raw).all()
        or not np.isfinite(y).all() or len(set(groups))<5
        or len(ephemeral["fold_indices"])!=5):
        raise ValueError("source descriptor and family OOD evaluation cohort invalid")
    if (prior["original_official_test_reserved_unread"]<1
        or not prior["all_folds_have_zero_group_identity_leakage"]
        or prior["scientific_qualification_authorized"] is not False
        or prior["out_of_fold_numeric_source_records_scored"]!=n):
        raise ValueError("source TEST embargo or scientific quality gate invalid")
    if strict_official and (
        n!=449 or len(set(groups))!=102
        or prior["original_source_train_count"]!=478
        or prior["original_official_test_reserved_unread"]!=121
        or prior["original_raw_censored_upper_bounds_excluded"]!=29):
        raise ValueError("original official 449 TRAIN/121 TEST source population drift")

    labels=tuple(_family_proxy(row) for row in x)
    old=_leave_chemical_class_out(y,groups,labels,raw,geometry)
    summary={}
    total=0
    for family in ANION_PROXY_BINS:
        held,train,embargo=separate_family_with_group_embargo(groups,labels,family)
        total+=len(held)
        baseline=old[family]
        expected_status=(
            "NOT_ADMITTED_TOO_FEW_ROWS_OR_GROUPS"
            if len(held)<MIN_CLASS_ROWS or len({groups[int(i)] for i in held})<MIN_CLASS_GROUPS
            or len(train)<20 else "REAL_RETROSPECTIVE_CLASS_SHIFT_SCORED"
        )
        if (baseline["status"]!=expected_status
            or baseline["heldout_original_numeric_source_records"]!=len(held)
            or baseline["training_source_rows_after_group_embargo"]!=len(train)
            or baseline["other_proxy_rows_embargoed_due_to_shared_identity_group"]!=embargo):
            raise ValueError("original 0150 chemistry family split or embargo changed")
        rec={
            "family":family,
            "status":baseline["status"],
            "source_rows_heldout":len(held),
            "heldout_source_groups":len({groups[int(i)] for i in held}),
            "source_train_rows_after_DOI_formula_group_embargo":len(train),
            "other_family_rows_embargoed":embargo,
            "original_0150_fixed_RF_parameters_unchanged":True,
            "original_0150_family_split_reproduced":True,
            "external_independent_chemistry_blind":False,
        }
        if expected_status!="REAL_RETROSPECTIVE_CLASS_SHIFT_SCORED":
            rec["original_0150_RF_log10_MAE"]=None
            rec["balanced_0158_RF_log10_MAE"]=None
            summary[family]=rec
            continue

        gt,gv,_=_fold_impute_geometry(geometry[train],geometry[held])
        train_x=np.concatenate([raw[train],gt],axis=1)
        held_x=np.concatenate([raw[held],gv],axis=1)
        if not np.isfinite(train_x).all() or not np.isfinite(held_x).all():
            raise ValueError("nonfinite training-only imputation for true family shift")
        orig=RandomForestRegressor(**RF_PARAMS)
        orig.fit(train_x,y[train])
        orig_p=orig.predict(held_x)
        if _scores(y[held],orig_p)!=baseline["RF"]:
            raise ValueError("recomputed unweighted 0150 RF changed; invalid comparison")
        w=train_only_group_weights(groups,train)
        weighted=RandomForestRegressor(**RF_PARAMS)
        if np.all(w==w[0]):
            weighted.fit(train_x,y[train])
        else:
            weighted.fit(train_x,y[train],sample_weight=w)
        wp=weighted.predict(held_x)
        mean=np.full(len(held),float(np.mean(y[train])))
        if _scores(y[held],mean)!=baseline["other_class_training_mean"]:
            raise ValueError("0150 cheap training-only source mean changed")
        if not np.isfinite(wp).all() or wp.shape!=orig_p.shape:
            raise ValueError("weighted RF produced invalid unseen chemistry predictions")
        macro=paired_group_uncertainty(
            y,orig_p_full(n,held,orig_p),orig_p_full(n,held,wp),groups,held)
        orig_mae=_scores(y[held],orig_p)["log10_MAE"]
        weighted_mae=_scores(y[held],wp)["log10_MAE"]
        mean_mae=_scores(y[held],mean)["log10_MAE"]
        rec.update({
            "original_0150_RF_log10_MAE":orig_mae,
            "balanced_0158_RF_log10_MAE":weighted_mae,
            "unseen_family_training_mean_log10_MAE":mean_mae,
            "balanced_minus_original_RF_log10_MAE":_round(weighted_mae-orig_mae),
            "balanced_minus_cheap_train_mean_log10_MAE":_round(weighted_mae-mean_mae),
            "original_RF_minus_cheap_train_mean_log10_MAE":baseline["RF_minus_other_class_training_mean_log10_MAE"],
            "balanced_RF_log10_RMSE":_scores(y[held],wp)["log10_RMSE"],
            "weighted_train_fold_min":_round(np.min(w)),
            "weighted_train_fold_max":_round(np.max(w)),
            "unchanged_0157_weight_exponent":FROZEN_WEIGHT_EXPONENT,
            "train_only_source_group_weight_fitting":True,
            **macro,
        })
        summary[family]=rec
    if total!=n or set(summary)!=set(ANION_PROXY_BINS):
        raise ValueError("family proxy source population not exhaustive")
    if n==449 and (old["S_ONLY"]["RF_minus_other_class_training_mean_log10_MAE"]!=
                   EXPECTED_ORIGINAL_S_ONLY_UNWEIGHTED_RF_MINUS_MEAN):
        raise ValueError("original real 0150 S-only source transfer failure drift")
    active={name:info for name,info in summary.items()
            if info["status"]=="REAL_RETROSPECTIVE_CLASS_SHIFT_SCORED"}
    clearly_worse_than_cheap=[
        name for name,info in active.items()
        if info["balanced_minus_cheap_train_mean_log10_MAE"]>0
    ]
    weighed_worse_than_original=[
        name for name,info in active.items()
        if info["balanced_minus_original_RF_log10_MAE"]>0
    ]
    return {
        "schema_version":SCHEMA,
        "experiment":"UNSEEN_ANION_PROXY_FAMILY_OUT_DOI_FORMULA_EMBARGO_ORIGINAL_0157_WEIGHTING_STRESS",
        "real_original_commit":prior.get("original_upstream_commit"),
        "original_public_TRAIN_population":prior["original_source_train_count"],
        "original_public_TEST_reserved_unread":prior["original_official_test_reserved_unread"],
        "original_public_TEST_features_or_labels_used":False,
        "original_uncensored_numeric_source_rows":n,
        "original_source_DOI_formula_groups":len(set(groups)),
        "original_0150_exact_family_heldout_group_embargo_reused":True,
        "0157_reused_fixed_RF_features_hyperparameters_weight_exponent":True,
        "frozen_weight_exponent":FROZEN_WEIGHT_EXPONENT,
        "retrospective_five_0146_folds_not_used_as_chemical_transfer_evidence":True,
        "source_chemistry_transfer_by_family":summary,
        "source_family_count_scored":len(active),
        "number_family_transfer_arms_worse_than_cheap_mean":len(clearly_worse_than_cheap),
        "which_family_transfer_arms_worse_than_cheap_mean":clearly_worse_than_cheap,
        "which_family_transfer_arms_worse_than_unweighted_RF":weighed_worse_than_original,
        "unqualified_default_model_adoption":"BLOCKED_FAMILY_TRANSFER_UNSAFE"
           if clearly_worse_than_cheap or weighed_worse_than_original
           else "STILL_BLOCKED_PENDING_NEW_INDEPENDENT_BLIND",
        "source_chemistry_proxy_is_physical_structure_attestation":False,
        "public_TRAIN_retrospective_design_not_external_blind":True,
        "MLIP_MD_transport_predictions":0,
        "scientific_GO":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
    }


def orig_p_full(n, indices, values):
    """Sparse temporary heldout prediction array, never written to disk."""
    p=np.full(n,np.nan)
    p[indices]=values
    return p


def run_original_0158(checkout:Path,output_dir:Path):
    source=Path(checkout).resolve(strict=True)
    out=Path(output_dir).resolve()
    if out.exists() or out==source or source in out.parents:
        raise ValueError("original source/output must be separate new paths")
    with tempfile.TemporaryDirectory(prefix="rhombus-0158-source-private-") as td:
        t=Path(td)
        prior,ephemeral=run_official_original_oof(source,t/"source0146",return_internal=True)
        raw,geo=load_original_train_features(
            source,source_ids=ephemeral["source_ids"],
            expected_processed_sha256=prior["source_processed_csv_sha256"],
            reference_fractions=ephemeral["x"])
        result=evaluate_original_family_out_0158(prior,ephemeral,raw,geo)
        out.parent.mkdir(parents=True,exist_ok=True)
        staging=Path(tempfile.mkdtemp(prefix=".rhombus-0158-",dir=out.parent))
        try:
            (staging/"original_family_out_balanced_RF_0158.json").write_bytes(
                _json_bytes(result)+b"\n")
            if out.exists():
                raise ValueError("output path changed during performance experiment")
            staging.rename(out)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    result=run_original_0158(a.original_obelix_checkout,a.output_dir)
    print("0158_REAL_PINNED_ORIGINAL_CHEMICAL_FAMILY_OUT_WEIGHTED_RF_COMPLETE")
    print(json.dumps({
        "original_source_rows":result["original_uncensored_numeric_source_rows"],
        "source_groups":result["original_source_DOI_formula_groups"],
        "family_scores":{k:{
          "status":v["status"],
          "RF_0150":v["original_0150_RF_log10_MAE"],
          "weighted_RF_0158":v["balanced_0158_RF_log10_MAE"],
          "delta_to_unweighted":v.get("balanced_minus_original_RF_log10_MAE"),
          "delta_to_cheap_mean":v.get("balanced_minus_cheap_train_mean_log10_MAE"),
          } for k,v in result["source_chemistry_transfer_by_family"].items()},
        "model_default_gate":result["unqualified_default_model_adoption"],
        "scientific_GO":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
