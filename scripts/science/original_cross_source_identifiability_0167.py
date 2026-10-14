"""0167: two genuinely original papers, different observables, falsify chemistry-only σ.

Yubuchi 2019 Li6PS5Br six heat-treatment conditions, all measured σ at 25 °C
are original numeric publisher-deposited JATS table observations.
Kraft 2018 original author SI Table S17 is BULK RESISTANCE R(T) in Ω,
not σ(S/cm), and is not directly poolable with the first paper.

A deterministic stoichiometry-only predictor MUST return one identical
value for all six Yubuchi records (same nominal chemical formula). The best
possible retrospective constant log10-conductivity MAE is the median absolute
deviation about a single constant. This is only a *source-series diagnostic*,
never six independent material test labels or prospective generalization.

No original OBELiX TEST material data read here and no model fitted/tuned.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import tempfile

from scripts.science import original_sulfide_measurement_table_0166 as sulfide
from scripts.science import obelix_kraft_original_tabular_impedance_0166 as kraft

SCHEMA="rhombus-0167-original-two-paper-physical-identity-and-composition-only-bound-v1"
LOG_RATIO_PRECISION=8


def analyze_actual_sources(a:dict,b:dict)->dict:
    if not isinstance(a,dict) or not isinstance(b,dict):
        raise ValueError("two primary-source authenticated science dictionaries required")
    pts=a.get("six_original_public_process_condition_points")
    if (a.get("source_DOI")!=sulfide.ORIGINAL_DOI or
        a.get("source_PMCID")!=sulfide.SOURCE_PMCID or
        a.get("experiment_observation_unit")!="HEAT_TREATMENT_PROCESS_CONDITION_OF_Li6PS5Br_MATERIAL" or
        a.get("actual_quantitative_table_condition_rows")!=6 or
        a.get("conductivity_temperature_C")!=25 or
        a.get("actual_independent_qualified_materials")!=0 or
        a.get("scientific_GO") is not False or
        not isinstance(pts,list) or len(pts)!=6):
        raise ValueError("unadmitted or different original source conductivity experiment")
    if (b.get("DOI")!=kraft.DOI or
        b.get("original_S17_canonical_numeric_table_SHA256")!=kraft.EXPECTED_S17_CANONICAL_DATA_SHA256 or
        b.get("scientific_GO") is not False):
        raise ValueError("original bulk resistance source identity or scientific policy mismatch")
    k=b.get("quantitative_physical_bulk_R_temperature_evidence",{})
    if (k.get("raw_source_fit_resistance_values_read_NOT_REPUBLISHED")!=120 or
        k.get("original_distinct_nominal_compositions")!=10 or
        k.get("unique_temperatures_K")!=11 or
        k.get("duplicate_298K_Rbulk_records")!=10 or
        k.get("R_bulk_ohm_NOT_S_per_cm") is not True or
        k.get("individual_true_sample_labels_qualified")!=0):
        raise ValueError("original second paper experimental unit or source census drift")
    ht=[];sig=[];ea=[]
    for p in pts:
        if (p.get("original_measurement_temperature_C")!=25 or
            p.get("green_compact_pressing_MPa")!=720 or
            p.get("admitted_as_material_level_transport_truth") is not False or
            p.get("individual_sample_identifier_verified") is not False):
            raise ValueError("source processing/measurement T or sample-unit drift")
        ht.append(p.get("heat_treatment_C_not_measurement_temperature"))
        sig.append(p.get("source_ionic_conductivity_mS_per_cm"))
        ea.append(p.get("source_activation_energy_kJ_per_mol"))
    if ht!=sulfide.EXPECTED_PROCESS_T_C or sig!=sulfide.EXPECTED_SIGMA_MSCM or ea!=sulfide.EXPECTED_EA_KJMOL:
        raise ValueError("primary JATS original numeric table row values changed")
    if any(type(y) not in (int,float) or not 0<y<100 for y in sig):
        raise ValueError("source mS/cm invalid")
    log_sigma=[math.log10(v/1000.0) for v in sig]
    best_stoichiometry_only_constant=statistics.median(log_sigma)
    mae=statistics.mean(abs(y-best_stoichiometry_only_constant) for y in log_sigma)
    log_range=max(log_sigma)-min(log_sigma)
    if not math.isclose(log_range, math.log10(max(sig)/min(sig)),abs_tol=1e-12):
        raise ValueError("log physical label unit ratio mismatch")
    if not any(sig[i+1]<sig[i] for i in range(len(sig)-1)):
        raise ValueError("frozen source nonmonotonicity observation unexpectedly absent")
    min_ea_i=min(range(len(ea)),key=lambda i:ea[i])
    max_sigma_i=max(range(len(sig)),key=lambda i:sig[i])
    return {
        "schema_version":SCHEMA,
        "source_papers":2,
        "published_primary_source_DOIs":[sulfide.ORIGINAL_DOI,kraft.DOI],
        "source1_deposited_JATS_xml_sha256":a.get("original_public_jats_sha256"),
        "source2_stable_original_S17_table_numeric_sha256":b["original_S17_canonical_numeric_table_SHA256"],
        "source1_observable":"IONIC_CONDUCTIVITY_S_PER_CM_AT_MEASURED_25C",
        "source1_measurement_unit":"CONDUCTIVITY_S_PER_CM",
        "source1_processing_independent_variable":"HEAT_TREATMENT_C_NOT_MEASUREMENT_T",
        "source1_one_nominal_chemistry_process_conditions":6,
        "source1_distinct_material_compositions":1,
        "source1_experimental_independently_attested_pellets":0,
        "source1_actual_original_same_formula_max_to_min_sigma_ratio":round(max(sig)/min(sig),LOG_RATIO_PRECISION),
        "source1_log10_S_per_cm_label_range":round(log_range,LOG_RATIO_PRECISION),
        "source1_STOICHIOMETRY_ONLY_or_any_single_constant_MIN_EMPIRICAL_log10_MAE":round(mae,LOG_RATIO_PRECISION),
        "source1_empirical_constant_best_log10_prediction":round(best_stoichiometry_only_constant,LOG_RATIO_PRECISION),
        "source1_number_nonmonotonic_heat_steps":sum(sig[i+1]<sig[i] for i in range(len(sig)-1)),
        "source1_thermal_processing_condition_for_min_Ea_C":ht[min_ea_i],
        "source1_thermal_processing_condition_for_max_sigma_C":ht[max_sigma_i],
        "source1_exploratory_same_paper_retroactive_error_NOT_validated_test_performance":True,
        "source2_observable":"FITTED_BULK_RESISTANCE_OHMS_BY_TEMPERATURE",
        "source2_measurement_unit":"BULK_RESISTANCE_OHM_NOT_SIGMA",
        "source2_nominal_compositions":k["original_distinct_nominal_compositions"],
        "source2_published_original_bulk_R_number_of_numeric_values":k["raw_source_fit_resistance_values_read_NOT_REPUBLISHED"],
        "source2_unique_measured_temperatures":k["unique_temperatures_K"],
        "source2_duplicate_298K_not_proven_independent_pellets":True,
        "source2_pellet_electrode_area_not_attested":True,
        "sources_can_pool_into_single_conductivity_accuracy_target":False,
        "sources_are_two_papers_not_126_independent_new_materials":True,
        "physical_specimens_jointly_qualified":0,
        "source_external_prospective_blind":False,
        "MLIP_finite_T_ion_transport_executed":False,
        "scientific_GO":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
    }


def build_live_actual_original_report()->dict:
    xml,url=sulfide.fetch_original_public_jats()
    one=sulfide.extract_table(xml)
    one["source_original_public_JATS_URL"]=url
    two=kraft.run_original()
    return analyze_actual_sources(one,two)


def write_original_report(out:Path)->dict:
    target=Path(out).resolve()
    if target.exists():
        raise ValueError("source aggregate directory must be new")
    report=build_live_actual_original_report()
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".rhombus-0167-",dir=target.parent))
    try:
        (stage/"two_primary_papers_observable_identity_0167.json").write_text(
            json.dumps(report,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n",encoding="utf-8")
        if target.exists():raise ValueError("source result collision")
        stage.rename(target)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--live-original",action="store_true")
    p.add_argument("--output-dir",type=Path,required=True)
    opts=p.parse_args()
    if not opts.live_original:
        p.error("real primary publication source opt-in required")
    report=write_original_report(opts.output_dir)
    print("0167_REAL_TWO_ORIGINAL_PAPERS_PROCESS_DEPENDENCE_AND_NONPOOLABLE_OBSERVABLES_PASS")
    print(json.dumps({
        "log10_min_MAE":report["source1_STOICHIOMETRY_ONLY_or_any_single_constant_MIN_EMPIRICAL_log10_MAE"],
        "same_chemistry_sigma_ratio":report["source1_actual_original_same_formula_max_to_min_sigma_ratio"],
        "other_paper_R_ohms_entries":report["source2_published_original_bulk_R_number_of_numeric_values"],
        "qualified_pellets":report["physical_specimens_jointly_qualified"],
        "scientific_GO":False,
    },sort_keys=True))


if __name__=="__main__":main()
