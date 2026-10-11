"""0150 real-source, post-hoc source-group and chemical-shift RF robustness.

Only original public TRAIN numerical source rows. Retrospective evidence, not
independent external blind or independent material truth.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
from pathlib import Path
import math
import shutil
import tempfile
import numpy as np

from rhombus.qualification.obelix_benchmark_intake import _json_bytes
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

SCHEMA = "rhombus-original-obelix-0150-rf-posthoc-group-chemistry-stress-v1"
MODELS = ("mean_0146", "fraction_rf_0147", "stoich_rf_0149", "geometry_rf_0149")
MIN_CLASS_ROWS = 10
MIN_CLASS_GROUPS = 3


def _round(x):
    v=float(x)
    if not math.isfinite(v):
        raise ValueError("nonfinite calculated result")
    return round(v,8)


def _metrics(y,pred):
    if len(y) != len(pred) or not np.isfinite(y).all() or not np.isfinite(pred).all():
        raise ValueError("invalid source numerical performance")
    return {
        "log10_MAE":_round(np.mean(np.abs(pred-y))),
        "log10_RMSE":_round(np.sqrt(np.mean((pred-y)**2))),
    }


def _source_weight_slices(y,groups,predictions):
    members=defaultdict(list)
    for i,g in enumerate(groups):
        members[g].append(i)
    ordered=sorted(members,key=lambda g:(-len(members[g]),g))
    if len(ordered)<5:
        raise ValueError("insufficient source connected groups")
    top=set(ordered[:5])
    slices={"all_groups":ordered,"largest_five":ordered[:5],"remaining_groups":ordered[5:]}
    rng=np.random.default_rng(150)
    result={}
    for name, group_ids in slices.items():
        index=[i for g in group_ids for i in members[g]]
        if not index:
            raise ValueError("empty prespecified connected source group slice")
        out={
            "source_record_count":len(index),
            "connected_group_count":len(group_ids),
            "models":{},
        }
        group_lists=[members[g] for g in group_ids]
        base_err=np.abs(predictions["mean_0146"]-y)
        for model in MODELS:
            err=np.abs(predictions[model]-y)
            values=np.array([np.mean(err[ix]) for ix in group_lists],dtype=float)
            delta=np.array([np.mean((err-base_err)[ix]) for ix in group_lists],dtype=float)
            item={
                "record_weighted_log10_MAE":_round(np.mean(err[index])),
                "equal_connected_group_macro_log10_MAE":_round(np.mean(values)),
                "record_weighted_minus_mean_log10_MAE":_round(np.mean((err-base_err)[index])),
                "equal_group_macro_minus_mean_log10_MAE":_round(np.mean(delta)),
                "group_bootstrap_heuristic_only":True,
                "independent_material_confidence_interval":False,
            }
            if len(group_ids)>=5:
                bs=np.mean(rng.choice(delta,size=(512,len(delta)),replace=True),axis=1)
                item["paired_group_delta_heuristic_interval_95pct"]=[
                    _round(z) for z in np.quantile(bs,[0.025,0.975])
                ]
            else:
                item["paired_group_delta_heuristic_interval_95pct"]=None
            out["models"][model]=item
        result[name]=out
    if result["largest_five"]["source_record_count"]+result["remaining_groups"]["source_record_count"]!=len(y):
        raise ValueError("connected groups not exhaustive")
    if result["largest_five"]["connected_group_count"]!=5:
        raise ValueError("largest five source-group selection drift")
    return result


def _chemistry_slices(x,y,groups,predictions):
    labels=tuple(_family_proxy(row) for row in x)
    out={}
    for family in ANION_PROXY_BINS:
        ix=np.array([i for i,f in enumerate(labels) if f==family],dtype=int)
        n=len(ix)
        ng=len({groups[i] for i in ix})
        report={
            "proxy":family,
            "source_record_count":n,
            "connected_group_count":ng,
            "scores_suppressed":n<MIN_CLASS_ROWS or ng<MIN_CLASS_GROUPS,
            "structural_family_independently_authenticated":False,
        }
        if not report["scores_suppressed"]:
            report["MAE"]={m:_round(np.mean(np.abs(p[ix]-y[ix]))) for m,p in predictions.items()}
            report["geometry_RF_minus_mean_log10_MAE"]=_round(
                report["MAE"]["geometry_rf_0149"]-report["MAE"]["mean_0146"])
        out[family]=report
    if sum(row["source_record_count"] for row in out.values())!=len(y):
        raise ValueError("chemistry source proxies lost rows")
    return labels,out


def _leave_chemical_class_out(y,groups,labels,raw,geometry):
    """Train fixed full-feature RF on all other classes, with group embargo."""
    from sklearn.ensemble import RandomForestRegressor
    summary={}
    for family in ANION_PROXY_BINS:
        held=np.asarray([i for i,l in enumerate(labels) if l==family],dtype=int)
        held_groups={groups[i] for i in held}
        allowed=np.asarray([
            i for i,l in enumerate(labels)
            if l!=family and groups[i] not in held_groups
        ],dtype=int)
        shared_removed=sum(l!=family and groups[i] in held_groups for i,l in enumerate(labels))
        entry={
            "proxy":family,"heldout_original_numeric_source_records":int(len(held)),
            "heldout_connected_groups":len(held_groups),
            "other_proxy_rows_embargoed_due_to_shared_identity_group":int(shared_removed),
            "training_source_rows_after_group_embargo":int(len(allowed)),
            "status":"NOT_ADMITTED_TOO_FEW_ROWS_OR_GROUPS",
            "independent_chemistry_generalization_test":False,
            "genuine_new_test_labels":False,
        }
        if len(held)<MIN_CLASS_ROWS or len(held_groups)<MIN_CLASS_GROUPS or len(allowed)<20:
            summary[family]=entry
            continue
        if set(groups[i] for i in allowed)&held_groups:
            raise ValueError("chemistry source identity leakage")
        train_geo,test_geo,_=_fold_impute_geometry(geometry[allowed],geometry[held])
        train_x=np.concatenate((raw[allowed],train_geo),axis=1)
        held_x=np.concatenate((raw[held],test_geo),axis=1)
        if not np.isfinite(train_x).all() or not np.isfinite(held_x).all():
            raise ValueError("missingness imputation failed")
        rf=RandomForestRegressor(**RF_PARAMS)
        rf.fit(train_x,y[allowed])
        pred=rf.predict(held_x)
        mean=np.full(len(held),float(np.mean(y[allowed])),dtype=float)
        entry.update({
            "status":"REAL_RETROSPECTIVE_CLASS_SHIFT_SCORED",
            "RF":_metrics(y[held],pred),
            "other_class_training_mean":_metrics(y[held],mean),
            "RF_minus_other_class_training_mean_log10_MAE":_round(
                np.mean(np.abs(pred-y[held]))-np.mean(np.abs(mean-y[held]))
            ),
            "training_only_median_imputation":True,
            "fixed_RF_configuration_no_search":True,
        })
        summary[family]=entry
    return summary


def evaluate_real_source_0150(prior,ephemeral,old,base_predictions,feature,feature_predictions,raw,geometry):
    y=ephemeral["y"];groups=ephemeral["groups"];x=ephemeral["x"]
    if (
        y.ndim!=1 or x.shape!=(len(y),118) or raw.shape!=(len(y),118)
        or geometry.shape!=(len(y),7) or len(groups)!=len(y)
        or not np.isfinite(x).all() or not np.isfinite(y).all()
        or prior["out_of_fold_numeric_source_records_scored"]!=len(y)
        or old["real_out_of_fold_source_record_predictions_per_model"]!=len(y)
        or feature["real_source_numeric_rows_scored_per_model"]!=len(y)
        or prior["original_official_test_reserved_unread"]<1
        or not prior["all_folds_have_zero_group_identity_leakage"]
        or old["scientific_qualification_authorized"] is not False
        or feature["science_go"] is not False
    ):
        raise ValueError("original source/qualification/feature data invalid")
    if len(set(groups))!=feature["connected_source_DOI_formula_groups"]:
        raise ValueError("identity groups changed after original OOF experiment")
    pred={
        "mean_0146":base_predictions["training_fold_mean_0146"],
        "fraction_rf_0147":base_predictions["random_forest"],
        "stoich_rf_0149":feature_predictions["raw_stoichiometry"]["RF"],
        "geometry_rf_0149":feature_predictions["raw_stoichiometry_plus_seven_lattice_spacegroup"]["RF"],
    }
    if any(p.shape!=y.shape or not np.isfinite(p).all() for p in pred.values()):
        raise ValueError("original source predictions failed to cover evaluation")
    for name,expected in (
        ("mean_0146",old["out_of_fold_metrics"]["training_fold_mean_0146"]["log10_MAE"]),
        ("fraction_rf_0147",old["out_of_fold_metrics"]["random_forest"]["log10_MAE"]),
        ("stoich_rf_0149",feature["actual_oof_results"]["raw_stoichiometry"]["RF"]["log10_MAE"]),
        ("geometry_rf_0149",feature["actual_oof_results"]["raw_stoichiometry_plus_seven_lattice_spacegroup"]["RF"]["log10_MAE"]),
    ):
        if _metrics(y,pred[name])["log10_MAE"]!=expected:
            raise ValueError("published prior original-source numerical model result drift")
    labels,categories=_chemistry_slices(x,y,groups,pred)
    report={
        "schema_version":SCHEMA,
        "evaluation":"POSTHOC_PUBLIC_ORIGINAL_TRAIN_RF_SOURCE_AND_CHEMICAL_SHIFT",
        "source_original_commit":prior.get("original_upstream_commit"),
        "source_processed_csv_sha256":prior.get("source_processed_csv_sha256"),
        "source_raw_workbook_sha256":prior.get("original_raw_workbook_sha256"),
        "original_official_train_records":prior["original_source_train_count"],
        "original_official_test_reserved_unread":prior["original_official_test_reserved_unread"],
        "official_public_TEST_predictions":0,
        "source_original_upper_bounds_excluded":prior["original_raw_censored_upper_bounds_excluded"],
        "original_uncensored_numeric_source_rows":len(y),
        "DOI_formula_connected_groups":len(set(groups)),
        "all_prior_0146_0147_0149_group_folds_and_model_config_unchanged":True,
        "frozen_original_source_MAE":{m:_metrics(y,p)["log10_MAE"] for m,p in pred.items()},
        "source_group_size_robustness":_source_weight_slices(y,groups,pred),
        "predeclared_chemical_anion_proxy_slices":categories,
        "retrospective_leave_proxy_class_out":_leave_chemical_class_out(y,groups,labels,raw,geometry),
        "source_connected_group_bootstrap_is_independent_material_inference":False,
        "posthoc_feature_and_reused_source_data_not_prospective":True,
        "experiment_source_phase_temperature_qualified":False,
        "true_independent_material_count":None,
        "new_independently_blind_specimens":0,
        "scientific_GO":False,
        "P0_01_status":"BLOCKED","P0_02_status":"BLOCKED","P0_03_status":"BLOCKED",
    }
    return report


def run_original_source_0150(checkout:Path,output_dir:Path):
    root=Path(checkout).resolve(strict=True)
    dest=Path(output_dir).resolve()
    if dest.exists() or dest==root or root in dest.parents:
        raise ValueError("original source and new output must remain separate")
    with tempfile.TemporaryDirectory(prefix="rhombus-0150-source-private-") as temp:
        t=Path(temp)
        prior,ephemeral=run_official_original_oof(root,t/"source0146",return_internal=True)
        old,old_p=evaluate_frozen_baselines(prior,ephemeral,return_internal=True)
        raw,geometry=load_original_train_features(
            root,source_ids=ephemeral["source_ids"],
            expected_processed_sha256=prior["source_processed_csv_sha256"],
            reference_fractions=ephemeral["x"],
        )
        feature,new_p=evaluate_predeclared_author_features(
            prior,ephemeral,old,raw,geometry,return_internal=True
        )
        report=evaluate_real_source_0150(prior,ephemeral,old,old_p,feature,new_p,raw,geometry)
        if (
            report["original_uncensored_numeric_source_rows"]!=449
            or report["original_official_test_reserved_unread"]!=121
            or report["DOI_formula_connected_groups"]!=102
        ):
            raise ValueError("cannot label non-official source experiment real 0150")
        dest.parent.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix=".rhombus-0150-",dir=dest.parent))
        try:
            (stage/"source_rf_robustness_aggregate.json").write_bytes(_json_bytes(report)+b"\n")
            if dest.exists():
                raise ValueError("output path occupied")
            stage.rename(dest)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        r=run_original_source_0150(args.original_obelix_checkout,args.output_dir)
    except (ValueError,OSError,TypeError) as e:
        p.error(str(e))
    print(json.dumps({
        "source_rows":r["original_uncensored_numeric_source_rows"],
        "connected_groups":r["DOI_formula_connected_groups"],
        "actual_mae":r["frozen_original_source_MAE"],
        "large_groups_rf_minus_mean":r["source_group_size_robustness"]["largest_five"]["models"]["geometry_rf_0149"]["record_weighted_minus_mean_log10_MAE"],
        "small_groups_rf_minus_mean":r["source_group_size_robustness"]["remaining_groups"]["models"]["geometry_rf_0149"]["record_weighted_minus_mean_log10_MAE"],
        "class_shift":{k:{"status":v["status"],"rf_minus_mean":v.get("RF_minus_other_class_training_mean_log10_MAE")} for k,v in r["retrospective_leave_proxy_class_out"].items()},
        "science_GO":False,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
