"""0171-B: exact paired superiority power for truly independent blinded materials.

This is a PRE-ENROLLMENT CONDITIONAL planning calculation, not a material
benchmark. It does not accept any real/private material IDs or truth.
Existing 0142 Wilson precision design is separate; do NOT conflate
precision with statistical power or independence with source-row count.

A binary material-level success/failure is compared between Rhombus and
a frozen baseline under the same budget. A paired win is R correct/B
incorrect; loss is reversed; tie includes both correct OR both
unsuccessful, failed, abstained or unknown after conservative accounting.
No truth or model outcomes may be used to tune these assumptions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

SCHEMA="rhombus-0171-exact-paired-independent-material-power-plan-v1"
BASE_ALPHA_DENOM=20
COMPARE_ARMS=(1,3) # single prespecified primary vs confirmatory three-arm
SCENARIOS=((0.65,0.30),(0.65,0.50),(0.70,0.30),(0.70,0.50))
TARGET_POWER=0.80
MAX_MATERIALS=600
PRE_ENROLLMENT_NONACQUISITION=0.20
WILSON_PREVIOUS_0142_N=93


def _fraction(x: float, *, low: float, high: float) -> float:
    if type(x) not in (float,int) or not math.isfinite(x) or not low < x < high:
        raise ValueError("finite strictly bounded prospective parameter required")
    return float(x)


def _exact_critical(discordants: int, arm_count: int) -> int:
    """Smallest win count with ONE-SIDED exact null tail <= 0.05/arms.

    0.05/arms is tested by integers: 20*arms * sum(C(n,k)) <= 2^n.
    Avoid floating rounding of a discrete critical region.
    """
    if type(discordants) is not int or not 0 <= discordants <= MAX_MATERIALS:
        raise ValueError("discordants invalid")
    if type(arm_count) is not int or arm_count not in COMPARE_ARMS:
        raise ValueError("invalid multiplicity")
    tail=0
    critical=discordants+1  # may have no attainable rejection for small n
    for wins in range(discordants,-1,-1):
        more=tail+math.comb(discordants,wins)
        if BASE_ALPHA_DENOM*arm_count*more > (1<<discordants):
            break
        tail=more
        critical=wins
    return critical


def _binomial_survival(n: int, threshold: int, p: float) -> float:
    if threshold > n:
        return 0.0
    if threshold <= 0:
        return 1.0
    logp=math.log(p)
    logq=math.log1p(-p)
    ln=math.lgamma(n+1)
    result=math.fsum(math.exp(ln-math.lgamma(k+1)-math.lgamma(n-k+1)
                              +k*logp+(n-k)*logq)
                     for k in range(threshold,n+1))
    return min(1.0,max(0.0,result))


def _binomial_probability(n: int, k: int, p: float) -> float:
    if p==0:
        return float(k==0)
    if p==1:
        return float(k==n)
    return math.exp(math.lgamma(n+1)-math.lgamma(k+1)
                    -math.lgamma(n-k+1)+k*math.log(p)
                    +(n-k)*math.log1p(-p))


def unconditional_power(
    enrolled: int, win_given_discordant: float, discordant_fraction: float,
    arm_count: int,
    conditional_cache: list[float] | None = None,
) -> float:
    """Exact unconditional power integrated over random discordant count.

    D~Bin(N,q); win|D=m~Bin(m,p); conditional null X~Bin(m,.5).
    Independence of material-level trials is an ASSUMPTION not evidence.
    """
    if type(enrolled) is not int or not 1<=enrolled<=MAX_MATERIALS:
        raise ValueError("invalid independent material count")
    p=_fraction(win_given_discordant,low=.50,high=.95)
    q=_fraction(discordant_fraction,low=0.0,high=1.0)
    if arm_count not in COMPARE_ARMS or type(arm_count) is not int:
        raise ValueError("invalid comparator count")
    if conditional_cache is None:
        conditional_cache=[
            _binomial_survival(m,_exact_critical(m,arm_count),p)
            for m in range(enrolled+1)]
    if len(conditional_cache) < enrolled+1:
        raise ValueError("incomplete critical power table")
    return min(1.0,max(0.0,math.fsum(
        _binomial_probability(enrolled,m,q)*conditional_cache[m]
        for m in range(enrolled+1)
    )))


def minimum_independent_materials(
    win_given_discordant: float, discordant_fraction: float,
    arm_count: int, *, maximum: int = MAX_MATERIALS,
) -> tuple[int,float,float]:
    p=_fraction(win_given_discordant,low=.50,high=.95)
    q=_fraction(discordant_fraction,low=0.0,high=1.0)
    if type(maximum) is not int or not 1<=maximum<=MAX_MATERIALS:
        raise ValueError("invalid prospectively bounded maximum")
    cache=[_binomial_survival(m,_exact_critical(m,arm_count),p)
           for m in range(maximum+1)]
    for n in range(1,maximum+1):
        power=unconditional_power(n,p,q,arm_count,cache)
        if power + 1e-12>=TARGET_POWER:
            return n,power,(unconditional_power(n-1,p,q,arm_count,cache)
                            if n>1 else 0.0)
    raise ValueError("proposed superiority effect too weak within budget")


def plan() -> dict:
    records=[]
    for arms in COMPARE_ARMS:
        for p,q in SCENARIOS:
            n,power,prior=minimum_independent_materials(p,q,arms)
            recl=math.ceil(n/(1-PRE_ENROLLMENT_NONACQUISITION))
            records.append({
                "confirmatory_comparator_count":arms,
                "Bonferroni_familywise_one_sided_alpha":round(
                    1/(BASE_ALPHA_DENOM*arms),12),
                "assumed_Rhombus_win_fraction_among_discordants":p,
                "assumed_discordance_fraction_per_independent_material":q,
                "minimum_independent_enrolled_materials_assuming_IID":n,
                "exact_unconditional_power":round(power,9),
                "power_at_preceding_count":round(prior,9),
                "prospective_recruitment_if_20pct_pre_enrollment_nonacquisition":recl,
                "prior_0142_precision_only_material_count":WILSON_PREVIOUS_0142_N,
                "primary_superiority_and_precision_joint_IID_minimum":max(
                    n,WILSON_PREVIOUS_0142_N),
            })
    return {
        "schema_version":SCHEMA,
        "date":"2026-10-14",
        "statistical_design":"TWO_SIDED_METHOD_COMPARISON_WITH_ONE_SIDED_EXACT_PAIRED_SIGN_TEST",
        "endpoint":"FROZEN_PER_MATERIAL_BINARY_SAME_BUDGET_CORRECT_DECISION",
        "primary_unit":"INDEPENDENT_NEW_PHYSICAL_MATERIAL_NOT_PELLET_REPEAT_NOT_MD_FRAME",
        "outcome_censoring":"UNKNOWN_FAILED_ABSTAINED_NOT_DROPPED_FROM_ENROLLED_DENOMINATOR",
        "sampling_model":"IID_MATERIALS_ASSUMED_UNPROVEN",
        "three_arm_fwer":"BONFERRONI_0_05_OVER_THREE_PRESPECIFIED_COMPARISONS",
        "assumed_effects_NOT_observed_from_Rhombus":True,
        "material_eligibility_phase_temperature_observable_attestation":"UNVERIFIED",
        "existing_0142_precision_reused_not_claimed_as_power":True,
        "data_reuse_public_OBELIX_TEST_old_B3_prohibited":True,
        "sealed_roster_truth_or_individual_sample_IDs_accessed":False,
        "sample_independence_actually_attested":False,
        "study_pre_registered_by_independent_steward":False,
        "same_budget_prospective_predictions_executed":False,
        "model_training_selected_frame_exposure_resolved":False,
        "power_scenarios":records,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_GO":False,
        "status":"PLANNING_SENSITIVITY_NOT_INDEPENDENT_EXPERIMENT",
    }


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-dir",type=Path,required=True)
    a=parser.parse_args()
    dst=a.output_dir.resolve()
    if dst.exists() or dst.is_symlink():
        parser.error("new output directory required; overwrite forbidden")
    result=plan()
    payload=json.dumps(result,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n"
    dst.mkdir(parents=True,exist_ok=False)
    (dst/"power_plan_0171.json").write_text(payload,encoding="utf-8")
    print("0171_EXACT_PAIRED_MATERIAL_POWER_CONDITIONAL_PLANNING_PASS")
    print(json.dumps({
        "one_arm_worst_case_materials":result["power_scenarios"][0]["minimum_independent_enrolled_materials_assuming_IID"],
        "three_arm_worst_case_materials":result["power_scenarios"][4]["minimum_independent_enrolled_materials_assuming_IID"],
        "scientific_GO":False},sort_keys=True))


if __name__=="__main__":
    main()
