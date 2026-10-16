"""0189: quantify composition-only irreducible error on original O_ONLY 25C TOTAL source states.

Reconstruct all 22 author-observed source conditions from the SAME genuine five
original JATS papers as checkpoint 0188. The optimal per-nominal-composition
constant is a *retrospective in-sample oracle*, NOT a learned process model,
nor an independent prospective out-of-source validation. No new DOI claims.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import tempfile

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import SOURCE_COMMIT,build_obelix_benchmark_intake,_json_bytes
from scripts.science.obelix_real_grouped_oof_0146 import _composition,run_official_original_oof
from scripts.science.obelix_solo_oxide_jats_three_doi_0187 import (
    PMCS as ORIGINAL_THREE_PMCS,
    get_original, get_jats, inspect_2022, inspect_2020,
)
from scripts.science.obelix_solo_oxide_five_doi_0188 import (
    ALL_DOIS, FIRST_FORMULAS, FIRST_VALUES, DOI18, DOI21,
    original_2018, original_2021, evaluate,
)

SCHEMA="rhombus-0189-solo-oxide-manufacturing-composition-identifiability-v1"
SIZES=(2,6,5,5,4)
EXPECTED_ROWS=22
EXPECTED_DOIS=5
MODEL_NAMES=("POOLED_RF","O_ONLY_RF","O_ONLY_RIDGE","O_ONLY_TRAIN_MEAN")

def source_conditions(first,second,third,fourth,fifth):
    if (first.get("original_doi")!=ALL_DOIS[0]
        or first.get("measurement_temperature_C")!=25):
        raise ValueError("first original DOI or measurement target mismatch")
    blocks=[
        [(ALL_DOIS[0],"TA0.5_PRISTINE",FIRST_FORMULAS[0],FIRST_VALUES[0]),
         (ALL_DOIS[0],"GA0.2_PRISTINE",FIRST_FORMULAS[1],FIRST_VALUES[1])],
        second[0],third[0],fourth[0],fifth[0],
    ]
    if tuple(len(x) for x in blocks)!=SIZES:
        raise ValueError("original author states population drift")
    out=sum(blocks,[])
    if len(out)!=EXPECTED_ROWS:
        raise ValueError("expected 22 author experimental reference conditions")
    for d,block in zip(ALL_DOIS,blocks):
        if any(row[0]!=d for row in block):
            raise ValueError("source paper DOI-to-quantity mixing")
    return out

def weighted_median_objective(pairs):
    """Exact minimum weighted absolute loss among constant predictors."""
    if not pairs or any(not math.isfinite(float(x)) or not math.isfinite(float(w)) or w<=0 for x,w in pairs):
        raise ValueError("nonfinite or nonpositive weighted source target")
    ordered=sorted((float(x),float(w)) for x,w in pairs)
    total=sum(w for _,w in ordered)
    running=0.0
    median=None
    for v,w in ordered:
        running+=w
        if running>=total/2:
            median=v
            break
    if median is None:raise ValueError("weighted median computation failed")
    return sum(w*abs(v-median) for v,w in ordered), median

def audit_process_identifiability(source_rows,existing_scores):
    """Source-verified log10 lower bounds; no external outcome used to fit any model."""
    if len(source_rows)!=EXPECTED_ROWS or len({r[0] for r in source_rows})!=EXPECTED_DOIS:
        raise ValueError("five author-DOI 22-row cohort required")
    if set(r[0] for r in source_rows)!=set(ALL_DOIS):
        raise ValueError("unknown science DOI in source cohort")
    if set(existing_scores)!=set(MODEL_NAMES):
        raise ValueError("frozen comparator identities changed")
    grouped=defaultdict(list)
    counts=defaultdict(int)
    groups_seen=defaultdict(set)
    for index, row in enumerate(source_rows):
        if len(row)!=4:raise ValueError("invalid original paper row")
        d,label,raw,sigma=row
        if not (isinstance(d,str) and isinstance(label,str) and label
                and isinstance(raw,str)):
            raise ValueError("missing original source label/nominal formula")
        parsed=_composition(raw)
        if parsed is None:raise ValueError("invalid author nominal formula")
        reduced,feat=parsed
        from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
        if _family_proxy(feat)!="O_ONLY":
            raise ValueError("non-O_ONLY original science record")
        try:sigma=float(sigma)
        except (TypeError,ValueError) as exc:raise ValueError("invalid author conductivity") from exc
        if not math.isfinite(sigma) or not 0<sigma<1:
            raise ValueError("not a physically admissible total-conductivity record")
        counts[d]+=1
        grouped[reduced].append((d,index,math.log10(sigma)))
        groups_seen[reduced].add(d)
    if tuple(counts[d] for d in ALL_DOIS)!=SIZES:
        raise ValueError("source 0188 DOI order or count drift")
    if any(any(not math.isfinite(z) for z in [float(scores["row_MAE_log10"]),
                 float(scores["equal_DOI_macro_MAE_log10"])]) for scores in existing_scores.values()):
        raise ValueError("frozen original model scores malformed")
    losses_row=0.0
    losses_macro=0.0
    spread=[]
    repeated=[]
    for formula,values in grouped.items():
        pair=[(logv,1.0) for _,_,logv in values]
        x,_=weighted_median_objective(pair)
        losses_row+=x
        macro_pairs=[(logv,1.0/counts[d]) for d,_,logv in values]
        x,_=weighted_median_objective(macro_pairs)
        losses_macro+=x
        if len(values)>1:
            logs=[z for _,_,z in values]
            span=max(logs)-min(logs)
            if span>1e-10:
                spread.append((len(values),len(groups_seen[formula]),span))
                repeated.append(len(values))
    lower_row=losses_row/len(source_rows)
    lower_macro=losses_macro/len(ALL_DOIS)
    best_row=min(float(s["row_MAE_log10"]) for s in existing_scores.values())
    best_macro=min(float(s["equal_DOI_macro_MAE_log10"]) for s in existing_scores.values())
    if lower_row>best_row+1e-7 or lower_macro>best_macro+1e-7:
        raise ValueError("mathematical constant-composition lower bound exceeded actual frozen model")
    # This is not a performance forecast: these optimal constants are selected
    # with already-revealed evaluation truth and cannot be used as a prediction.
    return {
        "distinct_nominal_reduced_formulas":len(grouped),
        "original_DOI_groups":len(ALL_DOIS),
        "source_reference_conditions":len(source_rows),
        "DOI_source_counts":dict(counts),
        "nominal_formulas_with_nonidentical_target_values":len(spread),
        "observation_rows_in_variable_nominal_groups":sum(repeated),
        "nominal_formula_groups_crossing_DOIs":sum(len(groups_seen[x])>1 for x in grouped),
        "maximum_same_nominal_formula_log10_target_range":round(max((z[2] for z in spread),default=0.0),8),
        "row_MAE_best_truth_selected_composition_constant_lower_bound_log10":round(lower_row,8),
        "equal_DOI_macro_MAE_best_truth_selected_composition_constant_lower_bound_log10":round(lower_macro,8),
        "frozen_O_ONLY_RF_row_MAE_log10":float(existing_scores["O_ONLY_RF"]["row_MAE_log10"]),
        "frozen_O_ONLY_RF_equal_DOI_macro_MAE_log10":float(existing_scores["O_ONLY_RF"]["equal_DOI_macro_MAE_log10"]),
        "O_ONLY_RF_row_gap_to_truth_selected_oracle_NOT_process_model":round(
            float(existing_scores["O_ONLY_RF"]["row_MAE_log10"])-lower_row,8),
        "O_ONLY_RF_DOI_macro_gap_to_truth_selected_oracle_NOT_process_model":round(
            float(existing_scores["O_ONLY_RF"]["equal_DOI_macro_MAE_log10"])-lower_macro,8),
        "equal_formula_input_implies_identical_composition_only_prediction":True,
        "oracle_uses_all_external_truth_NO_valid_out_of_sample_prediction":True,
        "formula_proxy_not_verified_post_sintering_composition":True,
        "process_metadata_required_for_state_specific_output_but_gain_unproven":True,
        "all_parent_physical_P0_still_BLOCKED":True,
    }

def run(original_source_checkout:Path,output:Path):
    checkout=original_source_checkout.resolve(strict=True)
    if output.exists() or checkout in output.resolve().parents:
        raise ValueError("outputs cannot replace original evidence or exist beforehand")
    with tempfile.TemporaryDirectory(prefix="rhombus-0189-") as tmp:
        prior,arrays=run_official_original_oof(checkout,Path(tmp)/"obelix",return_internal=True)
        records,_=build_obelix_benchmark_intake(checkout,expected_commit=SOURCE_COMMIT)
        p1=get_original()
        p2=inspect_2022(get_jats(ORIGINAL_THREE_PMCS[1]))
        p3=inspect_2020(get_jats(ORIGINAL_THREE_PMCS[2]))
        p4=original_2018(get_jats("PMC9079727"))
        p5=original_2021(get_jats("PMC8620275"))
        frozen=evaluate(prior,arrays,records,p1,p2,p3,p4,p5)
        if (frozen["source_DOIs"]!=list(ALL_DOIS)
            or frozen["distinct_DOI_groups"]!=5
            or frozen["actual_reference_conditions"]!=EXPECTED_ROWS
            or frozen["original_official_TEST_reserved_UNREAD"]!=121
            or frozen["original_TEST_fields_parsed"] is not False):
            raise ValueError("original five-paper/O_ONLY privacy and source evidence drift")
        source_rows=source_conditions(p1,p2,p3,p4,p5)
        audit=audit_process_identifiability(source_rows,frozen["model_scores"])
        result={
            "schema_version":SCHEMA,
            "original_five_DOI_recomputed_source_sha256":hashlib.sha256(_json_bytes(frozen)).hexdigest(),
            "primary_source_DOIs":list(ALL_DOIS),
            "original_publisher_TEST_reserved_UNREAD":121,
            "original_publisher_TEST_fields_ever_parsed":False,
            "original_author_25C_TOTAL_verified":True,
            "source_material_count_strictly_not_22_unique_pellets":True,
            "frozen_models_retrained_only_on_original_OBELIX_TRAIN":True,
            "original_compared_model_scores":frozen["model_scores"],
            "composition_only_oracle":audit,
            "new_independent_DOI_added":0,
            "original_SOURCE_P0_01":"BLOCKED","original_SOURCE_P0_02":"BLOCKED","original_SOURCE_P0_03":"BLOCKED",
            "physical_scientific_GO":False,
            "production_O_ONLY_model_enabled":False,
            "next_action":"0190-SOLO-O_ONLY-NEW_AUTHOR_DOIS_PLUS_FROZEN_PROCESS_DESCRIPTOR_PROTOCOL",
        }
    output.mkdir(parents=True,exist_ok=False)
    (output/"0189_original_oxide_process_identifiability.json").write_bytes(_json_bytes(result)+b"\n")
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--original-obelix-checkout",required=True,type=Path)
    parser.add_argument("--output-dir",required=True,type=Path)
    args=parser.parse_args()
    report=run(args.original_obelix_checkout,args.output_dir)
    print("0189_ACTUAL_FIVE_ORIGINAL_DOI_PROCESS_IDENTIFIABILITY_AUDIT_COMPLETE")
    print(json.dumps({
        "source_DOIs":len(report["primary_source_DOIs"]),
        "source_reference_conditions":report["composition_only_oracle"]["source_reference_conditions"],
        "composition_oracle":report["composition_only_oracle"],
        "model_activation":False,"scientific_GO":False},sort_keys=True))
