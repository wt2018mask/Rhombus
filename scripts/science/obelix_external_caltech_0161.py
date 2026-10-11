"""0161-E original CaltechDATA external-source *zero-shot* transport diagnostic.

Fit on pinned original OBELiX public TRAIN only. Freeze two existing 0147
stoichiometry RF variants and a cheap source training mean BEFORE opening
Caltech's external experimental conductivity labels. Treat no matching DOI
or reduced formula as a *candidate* non-overlap, never proven independence.
Preserve source rights: raw Caltech records, formulas, DOI, ICSD IDs and
per-record predictions never leave the transient GitHub runner.

This is retrospective cross-corpus stress, NOT a blind public leaderboard or
a scientifically qualified physical sample/temperature/phase score.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import (
    SOURCE_COMMIT, _json_bytes, build_obelix_benchmark_intake,
)
from scripts.science.obelix_real_grouped_oof_0146 import (
    _composition, _positive_log10, run_official_original_oof,
)
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_balanced_rf_0157 import train_only_group_weights, _round
from scripts.science.public_transport_benchmark import (
    CALTECH_MD5, CALTECH_EXPECTED_ROWS, inspect_caltech_original_csv,
)
from scripts.science.public_transport_overlap import _doi

SCHEMA="rhombus-0161-original-pinned-CALTECH-external-zero-shot-public-diagnostic-v1"
CALTECH_SOURCE_SHA256="868c4bd793d7c31b929787dc69478691b27ced0440d19269075143c98ecd1545"
ORIGINAL_TRAIN_NUMERIC=449
ORIGINAL_TRAIN_TOTAL=478
RESERVED_OFFICIAL_TEST=121
CALTECH_COLS=("compound","icsd_collectioncode","conductivity_doi",
              "conductivity_siemens_per_cm","lowest_extrapolation_temperature_K")


def original_train_identity(records, *, strict_official=True):
    """Never read a TEST entry's compound, DOI, structure or label."""
    if not isinstance(records,list) or (strict_official and len(records)!=599):
        raise ValueError("incorrect canonical original TRAIN/TEST source census")
    formulas=set()
    dois=set()
    train=0
    test=0
    for item in records:
        if not isinstance(item,dict):
            raise ValueError("untrusted source record")
        split=item.get("official_split")
        if split=="TEST":
            test+=1
            continue  # PROTECTED: no fields of a TEST record are consulted
        if split!="TRAIN":
            raise ValueError("invalid original source partition")
        train+=1
        parsed=_composition(item.get("reported_composition"))
        if parsed is not None:
            formulas.add(parsed[0])
        source_dois=item.get("reference_dois")
        if not isinstance(source_dois,list) or any(type(d)!=str for d in source_dois):
            raise ValueError("unverified official TRAIN DOI lineage")
        for d in source_dois:
            token=_doi(d)
            if token.startswith("10.") and len(token)<=256:
                dois.add(token)
    if strict_official and (train,test)!=(ORIGINAL_TRAIN_TOTAL,RESERVED_OFFICIAL_TEST):
        raise ValueError("original 478 TRAIN / 121 reserved TEST drift")
    if train<10 or test<1 or not formulas or not dois:
        raise ValueError("incomplete original TRAIN-only exclusion signatures")
    return {"train_rows":train,"reserved_test_rows_UNREAD":test,
            "train_doi_tokens":dois,"train_reduced_formulas":formulas}


def _parse_external(caltech_bytes:bytes, *, strict_official=True):
    """External CSV only; do not substitute extrapolation Tmin for measurement T."""
    if not isinstance(caltech_bytes,bytes) or len(caltech_bytes)>350000:
        raise ValueError("external Caltech source violates bounded bytes")
    if strict_official:
        checked=inspect_caltech_original_csv(
            caltech_bytes,expected_md5=CALTECH_MD5,expected_rows=CALTECH_EXPECTED_ROWS)
        if checked["official_file_sha256"]!=CALTECH_SOURCE_SHA256:
            raise ValueError("external original Caltech source byte identity drift")
    rows=list(csv.DictReader(io.StringIO(caltech_bytes.decode("utf-8-sig"),newline="")))
    if not rows or tuple(rows[0])!=CALTECH_COLS:
        raise ValueError("wrong first-party external dataset schema")
    if strict_official and len(rows)!=CALTECH_EXPECTED_ROWS:
        raise ValueError("Caltech 571 source rows drift")
    return rows


def prepare_crosssource_candidates(rows, identity):
    """Flags are source-provenance filters, not proof of physical independence."""
    if "train_doi_tokens" not in identity or "train_reduced_formulas" not in identity:
        raise ValueError("source identity missing")
    counters=Counter()
    candidates=[]
    for row in rows:
        counters["external_original_rows"]+=1
        source_doi=_doi(row["conductivity_doi"])
        if source_doi and not source_doi.startswith("10."):
            counters["unusable_external_source_DOI"]+=1
            source_doi=""
        is_matched_doi=bool(source_doi and source_doi in identity["train_doi_tokens"])
        if is_matched_doi:
            counters["exact_original_train_DOI_signal_rows"]+=1
        else:
            counters["without_original_train_DOI_signal_rows"]+=1
        parsed=_composition(row["compound"])
        if parsed is None or not parsed[1][2]>0: # atomic number 3: Li
            counters["unparseable_or_not_lithium_compound"]+=1
            continue
        formula,vector=parsed
        if formula in identity["train_reduced_formulas"]:
            counters["exact_original_train_reduced_formula_signal_rows"]+=1
        number=_positive_log10(row["conductivity_siemens_per_cm"])
        if number is None:
            counters["external_nonpositive_censored_or_unparseable_conductivity"]+=1
            continue
        counters["parseable_positive_experimental_source_labels"]+=1
        if not source_doi:
            counters["external_positive_but_missing_stable_DOI"]+=1
        tier=("WITHOUT_TRAIN_DOI" if not is_matched_doi else "ALL_VALID")
        noformula=formula not in identity["train_reduced_formulas"]
        if not is_matched_doi and noformula:
            counters["strict_no_TRAIN_DOI_or_reduced_formula_signal"]+=1
        candidates.append({
            "x":vector,"y":number,"doi":source_doi,
            "formula":formula,
            "no_train_doi":not is_matched_doi,
            "no_train_formula":noformula,
            "reported_temperature_metadata":row["lowest_extrapolation_temperature_K"],
            "source_original_row_reference":"TRANSIENT_PRIVATE_NOT_ARTIFACT",
        })
    return candidates,counters


def _scores(true,pred):
    if len(true)!=len(pred) or not np.isfinite(true).all() or not np.isfinite(pred).all():
        raise ValueError("invalid actual external-source predictive scores")
    return {"log10_MAE":_round(np.mean(abs(true-pred))),
            "log10_RMSE":_round(np.sqrt(np.mean((true-pred)**2)))}


def _equal_formula_macro(y,pred,formulas):
    groups=defaultdict(list)
    for i,f in enumerate(formulas):
        groups[f].append(abs(float(y[i])-float(pred[i])))
    return _round(np.mean([np.mean(a) for a in groups.values()]))


def _group_label_median_model_scores(rows, pred, names):
    """One reduced-composition unit, median labels; not one real physical sample."""
    merged=defaultdict(list)
    for i,rec in enumerate(rows):
        merged[rec["formula"]].append(i)
    if len(merged)<3:
        return None
    y=np.asarray([np.median([rows[i]["y"] for i in ix])
                  for _,ix in sorted(merged.items())])
    scored={}
    for model,vals in pred.items():
        q=np.asarray([np.median(vals[ix]) for _,ix in sorted(merged.items())])
        scored[model]=_scores(y,q)
    return {"original_external_distinct_reduced_formula_units":len(merged),
            "metric_by_reduced_formula_median":scored,
            "not_independently_verified_physical_specimens":True}


def evaluate_crosssource(original_train_x, original_train_y, original_groups,
                         original_records, caltech_bytes, *, strict_official=True):
    """Public source TRAIN model frozen and trained before external labels opened."""
    from sklearn.ensemble import RandomForestRegressor
    x=np.asarray(original_train_x,dtype=float)
    y=np.asarray(original_train_y,dtype=float)
    groups=tuple(original_groups)
    if x.ndim!=2 or x.shape[1]!=118 or y.shape!=(len(x),) or len(groups)!=len(y):
        raise ValueError("misaligned original TRAIN features/group census")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or len(set(groups))<2:
        raise ValueError("invalid pinned original TRAIN numeric source")
    if strict_official and (len(y)!=ORIGINAL_TRAIN_NUMERIC or len(set(groups))!=102):
        raise ValueError("original source TRAIN 449/102 frozen cohort drift")
    identity=original_train_identity(original_records,strict_official=strict_official)

    # SCIENCE IMMUTABLE: models fitted before any external target/labels are parsed.
    original=RandomForestRegressor(**RF_PARAMS)
    original.fit(x,y)
    weights=train_only_group_weights(groups,np.arange(len(y)))
    balanced=RandomForestRegressor(**RF_PARAMS)
    if np.all(weights==weights[0]):
        balanced.fit(x,y)
    else:
        balanced.fit(x,y,sample_weight=weights)
    mean=float(np.mean(y))
    # External source file hash and schema verification only after model fixed.
    external=_parse_external(caltech_bytes,strict_official=strict_official)
    candidates,counters=prepare_crosssource_candidates(external,identity)
    if strict_official and counters["external_original_rows"]!=571:
        raise ValueError("original Caltech external 571 population drift")
    if not candidates:
        raise ValueError("external source cannot produce model-comparable labels")
    xs=np.stack([p["x"] for p in candidates])
    pred={"cheap_OBELiX_TRAIN_mean":np.full(len(xs),mean),
          "original_0147_stoichiometry_RF":original.predict(xs),
          "0157_source_group_balanced_stoichiometry_RF":balanced.predict(xs)}
    out={}
    for key,select in (
        ("ALL_ORIGINAL_VALID",lambda q:True),
        ("NO_EXACT_ORIGINAL_TRAIN_DOI",lambda q:q["no_train_doi"]),
        ("NO_EXACT_TRAIN_DOI_AND_REDUCED_FORMULA",
         lambda q:q["no_train_doi"] and q["no_train_formula"]),
    ):
        ix=np.asarray([i for i,row in enumerate(candidates) if select(row)],dtype=int)
        if len(ix)<5:
            out[key]={"source_records":len(ix),"score_status":"INSUFFICIENT_SOURCE_RECORDS"}
            continue
        true=np.asarray([candidates[i]["y"] for i in ix])
        formulas=[candidates[i]["formula"] for i in ix]
        scores={model:{**_scores(true,p[ix]),
                       "equal_reduced_formula_macro_log10_MAE":
                           _equal_formula_macro(true,p[ix],formulas)}
                for model,p in pred.items()}
        rows=[candidates[i] for i in ix]
        group_report=_group_label_median_model_scores(
            rows,{name:p[ix] for name,p in pred.items()},tuple(scores))
        out[key]={
            "source_records":len(ix),
            "distinct_reduced_formula_strings":len(set(formulas)),
            "score_status":"PUBLIC_CROSS_CORPUS_SOURCE_DIAGNOSTIC_NOT_BLIND",
            "row_weighted_models":scores,
            "reduced_formula_group_median_diagnostic":group_report,
            "source_label_target":"PUBLISHED_CALTECH_REPORTED_ROOM_TEMPERATURE_IONIC_CONDUCTIVITY",
            "independently_verified_same_measurement_temperature_and_bulk_total":False,
            "independently_verified_new_experimental_materials":0,
        }
    if strict_official and counters["exact_original_train_DOI_signal_rows"]!=225:
        raise ValueError("previous pinned Caltech/OBELiX exact original TRAIN DOI overlap census drift")
    return {
        "schema_version":SCHEMA,"original_upstream_obelix_commit":SOURCE_COMMIT,
        "external_caltech_original_SHA256":hashlib.sha256(caltech_bytes).hexdigest(),
        "original_obelix_public_TRAIN_numeric_fit":len(y),
        "original_obelix_public_TRAIN_total":identity["train_rows"],
        "original_obelix_public_TEST_reserved_unread":identity["reserved_test_rows_UNREAD"],
        "original_TEST_features_DOIs_or_labels_read":False,
        "external_reported_original_records":len(external),
        "external_source_input_counts_only":dict(sorted(counters.items())),
        "official_frozen_original_RF_params":dict(RF_PARAMS),
        "only_original_public_TRAIN_used_to_fit_models":True,
        "external_labels_opened_after_models_fit":True,
        "source_heldout_overlap_filters_are_signals_not_independence":True,
        "external_zero_shot_cohorts":out,
        "original_caltech_temperature_column":"LOWEST_EXTRAPOLATION_TEMPERATURE_K_NOT_EXACT_PER_RECORD_MEASURED_T",
        "source_row_truth_unqualified_without_primary_paper":True,
        "Caltech_source_reuse_rights_unverified_raw_values_NOT_republished":True,
        "no_external_row_formula_DOI_ICSD_or_label_published":True,
        "no_independent_physically_verified_materials_newly_qualified":0,
        "no_external_sealed_prediction_commitment":True,
        "scientific_GO":False,"P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
    }


def run_original(obelix_checkout:Path,external_csv:Path,output:Path):
    original=Path(obelix_checkout).resolve(strict=True)
    ext=Path(external_csv).resolve(strict=True)
    dest=Path(output).resolve()
    if dest.exists() or dest==original or original in dest.parents or dest==ext:
        raise ValueError("original/source/output must be separate immutable paths")
    with tempfile.TemporaryDirectory(prefix="rhombus-0161-private-") as td:
        prior,ephemeral=run_official_original_oof(original,Path(td)/"0146-original",return_internal=True)
        if (prior["original_official_test_reserved_unread"]!=121
            or prior["original_source_train_count"]!=478 or
            prior["out_of_fold_numeric_source_records_scored"]!=449 or
            not prior["all_folds_have_zero_group_identity_leakage"] or
            prior["scientific_qualification_authorized"] is not False):
            raise ValueError("original TRAIN-only model fitting source gate")
        records,_=build_obelix_benchmark_intake(original,expected_commit=SOURCE_COMMIT)
        if ext.is_symlink() or ext.stat().st_size>350000:
            raise ValueError("untrusted external Caltech source file")
        data=ext.read_bytes()
        report=evaluate_crosssource(ephemeral["x"],ephemeral["y"],
                                    ephemeral["groups"],records,data)
        dest.parent.mkdir(parents=True,exist_ok=True)
        staged=Path(tempfile.mkdtemp(prefix=".rhombus-0161-",dir=dest.parent))
        try:
            (staged/"crosssource_caltech_zero_shot_0161.json").write_bytes(
                _json_bytes(report)+b"\n")
            if dest.exists():
                raise ValueError("external result path race")
            staged.rename(dest)
        finally:
            if staged.exists():
                shutil.rmtree(staged)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--original-caltech-csv",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    o=run_original(a.original_obelix_checkout,a.original_caltech_csv,a.output_dir)
    print("0161_ACTUAL_PUBLIC_CROSS_CORPUS_OBELIX_TO_CALTECH_ZERO_SHOT_RUN")
    print(json.dumps({
        "source":o["external_caltech_original_SHA256"],
        "records":o["external_reported_original_records"],
        "counters":o["external_source_input_counts_only"],
        "metrics":o["external_zero_shot_cohorts"],
        "scientific_GO":False},sort_keys=True))
if __name__=="__main__":
    main()
