"""0168-A: Real one-paper, one-composition PROCESS holdout, not material discovery.

A fixed stoichiometry-only predictor cannot distinguish six original
Li6PS5Br heat treatments. Measure the *retrospective within-paper*
leave-one-PROCESS-CONDITION-out predictive gap using an unmodified
publisher-deposited original JATS table.

Two fixed rules only: 5-row training median of log10(S/cm) as chemistry-only
constant, and 5-row ordinary least-squares log sigma ~ HEAT TREATMENT C.
No heldout label can enter a fold fit. This is a small public-source
explanatory baseline, NOT prospective test, independent specimens, or
validated out-of-paper generalization. Thermal processing temperature
must never be confused with ionic-conductivity measurement T=25 C.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import shutil
import statistics
import tempfile
from scripts.science import original_sulfide_measurement_table_0166 as y

SCHEMA="rhombus-0168-original-JATS-same-chemistry-leave-processing-condition-out-v1"

def _admit_original(a:dict)->tuple[list[float],list[float]]:
    if (a.get("source_DOI")!=y.ORIGINAL_DOI or
        a.get("source_PMCID")!=y.SOURCE_PMCID or
        a.get("experiment_observation_unit")!="HEAT_TREATMENT_PROCESS_CONDITION_OF_Li6PS5Br_MATERIAL" or
        a.get("actual_quantitative_table_condition_rows")!=6 or
        a.get("conductivity_temperature_C")!=25 or
        a.get("actual_independent_qualified_materials")!=0 or
        a.get("scientific_GO") is not False):
        raise ValueError("source one-composition measured 25 C and qualified-unit identity drift")
    pts=a.get("six_original_public_process_condition_points")
    if not isinstance(pts,list) or len(pts)!=6):
        raise ValueError("six frozen experimental treatment conditions required")
    x=[];s=[]
    for i,row in enumerate(pts):
        if (row.get("source_condition_index")!=i+1 or
            row.get("original_measurement_temperature_C")!=25 or
            row.get("green_compact_pressing_MPa")!=720 or
            row.get("individual_sample_identifier_verified") is not False or
            row.get("admitted_as_material_level_transport_truth") is not False):
            raise ValueError("a source row was relabelled as a physical pellet or measurement T")
        x.append(row.get("heat_treatment_C_not_measurement_temperature"))
        s.append(row.get("source_ionic_conductivity_mS_per_cm"))
    if x!=y.EXPECTED_PROCESS_T_C or s!=y.EXPECTED_SIGMA_MSCM:
        raise ValueError("original published JATS table data values or treatment order drift")
    return list(map(float,x)),[math.log10(t/1000) for t in s]


def folded_predictions(temps:list[float],log_sigma:list[float])->dict:
    if (len(temps)!=6 or len(log_sigma)!=6 or
        any(type(t) not in (float,int) or not math.isfinite(t) for t in temps+log_sigma) or
        len(set(temps))!=6):
        raise ValueError("exact six finite unique heat-treatment conditions and labels needed")
    # Freeze rules BEFORE each fold. Training comprises the other 5 conditions.
    err_chem=[];err_process=[]
    signs=[]
    for heldout in range(6):
        train=[i for i in range(6) if i!=heldout]
        xx=[temps[i] for i in train]; yy=[log_sigma[i] for i in train]
        median=statistics.median(yy)
        mx=statistics.mean(xx);my=statistics.mean(yy)
        denom=sum((t-mx)**2 for t in xx)
        if denom<=0:
            raise ValueError("degenerate training treatment conditions")
        slope=sum((t-mx)*(v-my) for t,v in zip(xx,yy))/denom
        pred=my+slope*(temps[heldout]-mx)
        err_chem.append(abs(median-log_sigma[heldout]))
        err_process.append(abs(pred-log_sigma[heldout]))
        signs.append(slope>0)
    chem=statistics.mean(err_chem)
    process=statistics.mean(err_process)
    if chem<=0: raise ValueError("invalid chemistry constant comparator")
    return {
        "rows_evaluated_as_retrospective_LOO":6,
        "independent_material_compositions":1,
        "number_of_same_paper_source_condition_groups":6,
        "chemistry_only_five_fold_train_median_LOO_MAE_log10_S_per_cm":round(chem,8),
        "process_temp_five_fold_train_OLS_LOO_MAE_log10_S_per_cm":round(process,8),
        "process_OLS_minus_chemistry_median_MAE":round(process-chem,8),
        "process_temp_OLS_relative_MAE_reduction_over_training_median":round(1-process/chem,8),
        "five_row_treatment_slope_positive_each_fold":all(signs),
        "fold_training_row_count":5,
        "no_heldout_source_label_in_any_fit":True,
        "no_fold_hyperparameter_search":True,
        "boundary_treatment_LOO_uses_linear_extrapolation":True,
        "exploratory_source_selected_after_public_labels_seen":True,
        "within_one_paper_LOO_not_blind_material_generalization":True,
        "not_a_causal_effect_of_heat_treatment":True,
        "individual_pellet_and_phase_unattested":True,
    }


def run_actual_original()->dict:
    raw,url=y.fetch_original_public_jats()
    study=y.extract_table(raw)
    study["source_original_public_JATS_URL"]=url
    xs,ys=_admit_original(study)
    folds=folded_predictions(xs,ys)
    return {
        "schema_version":SCHEMA,
        "primary_source_DOI":y.ORIGINAL_DOI,
        "primary_JATS_sha256":study["original_public_jats_sha256"],
        "source_url_actual_official_archive":url,
        "original_one_nominal_formula":"Li6PS5Br",
        "process_treatments_C_versus_conductivity_measured_T_C_distinct":True,
        "real_original_25_C_source_measurement":True,
        "experimental_cross_condition_diagnostics":folds,
        "original_measurement_rows_used":6,
        "independent_exact_pellet_samples_physically_qualified":0,
        "material_level_out_of_family_evaluation":False,
        "external_prospectively_sealed_independent_blind":False,
        "physical_MLIP_MD_benchmark_improved":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_GO":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--live-original",action="store_true")
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    if not args.live_original:p.error("actual deposited primary original science opt-in required")
    target=args.output_dir.resolve()
    if target.exists():p.error("new empty output directory required")
    result=run_actual_original()
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".rhombus-0168-",dir=target.parent))
    try:
        (stage/"original_process_condition_LOO_0168.json").write_text(
            json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n",
            encoding="utf-8")
        if target.exists():raise ValueError("original science output collision")
        stage.rename(target)
    finally:
        if stage.exists():shutil.rmtree(stage)
    print("0168_FIRSTPARTY_ORIGINAL_25C_PROCESS_CONDITION_LOO_BENCHMARK_PASS")
    print(json.dumps({"mae_source_only_median":result["experimental_cross_condition_diagnostics"]["chemistry_only_five_fold_train_median_LOO_MAE_log10_S_per_cm"],
                      "mae_source_process_ols":result["experimental_cross_condition_diagnostics"]["process_temp_five_fold_train_OLS_LOO_MAE_log10_S_per_cm"],
                      "physically_verified_pellets":0,"scientific_GO":False},sort_keys=True))


if __name__=="__main__":main()
