"""0192: author-source heldout 2022 ACS O_ONLY six-hour temperature comparison.

A single NEW publicly exposed author DOI, not a prospective blind. Ten measured
25C TOTAL condition references (five formulas, 1050/1100C, six-hour sintering).
The paper also reports 12h mother-powder-covered conditions: NOT comparable
to unchanged six-hour conditions and deliberately excluded. Numeric heldout
test truths are never inputs to learned process models, nor to model selection.

The source's total-conductivity table unit is reviewed independently from the
10 original prose S/cm values; no silent table unit reinterpretation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

from rhombus.qualification.obelix_benchmark_intake import SOURCE_COMMIT, _json_bytes, build_obelix_benchmark_intake
from scripts.science.obelix_real_grouped_oof_0146 import _composition, run_official_original_oof
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_solo_oxide_five_doi_0188 import embargo
from scripts.science.obelix_solo_oxide_jats_three_doi_0187 import get_jats, norm, simple, tag, flatten
from scripts.science.obelix_solo_oxide_process_transfer_0191 import (
    original_process_2018, original_process_2020, features, ALPHA, DOI18, DOI20
)

SOURCE_DOI="10.1021/acsomega.2c06544"
SOURCE_PMC="PMC9773338"
SCHEMA="rhombus-0192-six-hour-original-acs-source-temperature-transfer-v1"
FORMULAS=(
    "Li7La3Zr2O12",
    "Li6.4La3Zr1.4Ta0.6O12",
    "Li6.4Ga0.067La3Zr1.6Ta0.4O12",
    "Li6.4Ga0.133La3Zr1.8Ta0.2O12",
    "Li6.4Ga0.2La3Zr2O12",
)
# Every value is in the same original author's 25C TOTAL ionic conductivity
# prose, in 10^-4 S/cm, ordered by LLZO, Ta0.6, Ta0.4Ga0.067, Ta0.2Ga0.133, Ga0.2.
# These expected values only authenticate the HELDOUT source, never train a model.
SIX_HOUR_VALUES_1050=(0.017,0.102,0.386,0.356,0.243)
SIX_HOUR_VALUES_1100=(0.020,0.169,1.100,1.191,0.713)


def original_six_hour_conditions(blob:bytes):
    if not isinstance(blob,bytes) or not 0<len(blob)<=8_000_000:
        raise ValueError("publisher original JATS byte size")
    upper=blob.upper()
    if b"<!ENTITY" in upper:
        raise ValueError("untrusted original JATS ENTITY")
    # Permit only a single bounded, simple first-party JATS doctype, as in
    # existing 0187/0188 readers; internal subsets and entities stay rejected.
    clean=blob
    if b"<!DOCTYPE" in upper:
        clean,n=re.subn(rb"<!DOCTYPE\\s+article\\b[^<>\\[\\]]{0,2000}>",b"",blob,flags=re.I)
        if n!=1 or b"<!DOCTYPE" in clean.upper():
            raise ValueError("untrusted original JATS DTD/internal subset")
    try: root=ET.fromstring(clean)
    except ET.ParseError as exc: raise ValueError("source JATS invalid") from exc
    if tag(root)!="article": raise ValueError("not an original author article")
    dois={flatten(e).lower() for e in root.iter() if tag(e)=="article-id" and e.attrib.get("pub-id-type")=="doi"}
    pmcs={flatten(e).upper().removeprefix("PMC") for e in root.iter() if tag(e)=="article-id" and e.attrib.get("pub-id-type") in ("pmc","pmcid")}
    if SOURCE_DOI not in dois or SOURCE_PMC.removeprefix("PMC") not in pmcs:
        raise ValueError("wrong first-party source DOI/PMCID")
    bodies=[x for x in root.iter() if tag(x)=="body"]
    if len(bodies)!=1:raise ValueError("source author body invalid")
    paragraphs=[norm("".join(e.itertext())) for e in bodies[0].iter() if tag(e)=="p"]
    source=[p for p in paragraphs if "radius of the semicircle" in p.lower()
            and "increased from" in p.lower() and "0.017" in p]
    if len(source)!=1:
        raise ValueError("original source 6h 25C total numeric prose absent or duplicated")
    phrase=source[0].split("increased from",1)[1]
    if "for LLZO" not in phrase:raise ValueError("author composition ordering absent")
    phrase=phrase.split("for LLZO",1)[0]
    actual=tuple(float(t) for t in re.findall(r"(?<![0-9])(?:[0-9]+)\.[0-9]{3}(?![0-9])",phrase))
    expected=SIX_HOUR_VALUES_1050+SIX_HOUR_VALUES_1100
    if len(actual)!=10 or any(not math.isclose(x,y,rel_tol=0,abs_tol=1e-12) for x,y in zip(actual,expected)):
        raise ValueError("original two six-hour temperature EIS numbers changed or reordered")
    normalized=norm(phrase).lower().replace(" ","")
    if normalized.count("10-4scm-1")!=2:
        raise ValueError("original prose total conductivity S/cm scaling not twice supported")
    methods=" ".join(paragraphs).lower()
    if ("1050" not in methods or "1100" not in methods or "6 h" not in methods
        or "12 h" not in methods or "mother powder" not in methods):
        raise ValueError("process and 12h mother powder confound unverified")
    # The first-party Table1 total column has a S m^-1 versus source prose
    # S cm^-1 discrepancy in some hosted renderings. Do NOT derive labels
    # by silently reinterpreting the table. Record it, and independently
    # authenticate all ten explicit prose values. This is a limited source.
    tables=[t for t in root.iter() if tag(t)=="table-wrap"]
    table_meta=[(flatten(t),len([c for c in t.iter() if tag(c)=="tr"])) for t in tables]
    if not any("ionicconductivities" in simple(s) for s,n in table_meta if n>=10):
        raise ValueError("original first-party ionic-conductivity table absent")
    conditions=[]
    for temp,values in ((1050,SIX_HOUR_VALUES_1050),(1100,SIX_HOUR_VALUES_1100)):
        for i,(formula,val) in enumerate(zip(FORMULAS,values)):
            conditions.append((SOURCE_DOI,f"ACS_{temp}_{i}",formula,temp,360,val*1e-4))
    meta={"DOI":SOURCE_DOI,"PMCID":SOURCE_PMC,"JATS_SHA256":hashlib.sha256(blob).hexdigest(),
          "source_endpoint":"AUTHORED_PROSE_25C_TOTAL_10^-4_S_CM",
          "not_using_potentially_conflicting_table_units":True,
          "six_hour_uncovered_reference_conditions":10,
          "twelve_hour_powder_covered_conditions_quarantined":10,
          "nominal_formula_not_certified_final_pellet":True}
    return conditions,meta


def score(prior,arrays,records,older_a,older_b,new,meta):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    if (prior["original_upstream_commit"]!=SOURCE_COMMIT
        or prior["original_source_train_count"]!=478
        or prior["original_official_test_reserved_unread"]!=121
        or prior["original_raw_censored_upper_bounds_excluded"]!=29
        or prior["scientific_qualification_authorized"] is not False):
        raise ValueError("original OBELiX split changed")
    if len(older_a)!=5 or len(older_b)!=5 or len(new)!=10:
        raise ValueError("number of independent author conditions changed")
    if meta["DOI"]!=SOURCE_DOI or {r[0] for r in new}!={SOURCE_DOI}:
        raise ValueError("unrecognized heldout original DOI")
    if {r[0] for r in older_a}!={DOI18} or {r[0] for r in older_b}!={DOI20}:
        raise ValueError("training author source mixed")
    candidate=older_a+older_b+new
    source_rows=[(r[0],r[1],r[2],r[5]) for r in candidate]
    mask,matched,excluded=embargo(records,arrays,source_rows)
    x,y=np.asarray(arrays["x"]),np.asarray(arrays["y"])
    if x.shape!=(449,118) or y.shape!=(449,):
        raise ValueError("original numeric source changed")
    indices=np.asarray([i for i in np.where(mask)[0] if _family_proxy(x[i])=="O_ONLY"],dtype=int)
    if len(indices)<80:raise ValueError("embargo leaves too few O_ONLY train rows")
    rf=RandomForestRegressor(**RF_PARAMS).fit(x[indices],y[indices])
    training=older_a+older_b
    old_x=np.asarray([_composition(r[2])[1] for r in training])
    heldout_x=np.asarray([_composition(r[2])[1] for r in new])
    if old_x.shape!=(10,118) or heldout_x.shape!=(10,118):
        raise ValueError("expected 118 physical descriptors")
    if any(_family_proxy(z)!="O_ONLY" for z in heldout_x):
        raise ValueError("heldout elements outside O_ONLY")
    base_tr=rf.predict(old_x)
    base_ho=rf.predict(heldout_x)
    ytr=np.log10([r[5] for r in training])
    yho=np.log10([r[5] for r in new])
    corrections=ytr-base_tr
    p_base=base_ho
    p_mean=base_ho+float(np.mean(corrections))
    p_proc=base_ho+Ridge(alpha=ALPHA,fit_intercept=True).fit(features(training),corrections).predict(features(new))
    metrics={}
    for label,pred in (("O_ONLY_RF",p_base),("TRAIN_DOI_MEAN_RESIDUAL",p_mean),("TRAIN_DOI_PROCESS_RIDGE",p_proc)):
        if not np.isfinite(pred).all():raise ValueError("nonfinite source predictions")
        pair_correct=pair_abstained=0
        pair_regret=[]
        # New cohort rows arranged 1050 conditions first (i), then 1100 (i+5).
        for i in range(5):
            a,b=pred[i],pred[i+5]
            measured=np.asarray([yho[i],yho[i+5]])
            if abs(float(a-b))<1e-9:
                pair_abstained+=1
            else:
                chosen=0 if a>b else 1
                pair_correct+=int(chosen==int(measured.argmax()))
                pair_regret.append(float(measured.max()-measured[chosen]))
        metrics[label]={
            "heldout_MAE_log10_S_cm":round(float(abs(pred-yho).mean()),8),
            "paired_process_top1_correct":pair_correct,
            "paired_process_abstentions":pair_abstained,
            "paired_process_regret_log10_S_cm":round(float(np.mean(pair_regret)),8) if pair_regret else None}
    if any(new[i][2]!=new[i+5][2] or new[i][4]!=new[i+5][4] for i in range(5)):
        raise ValueError("heldout 6h source pairing changed")
    higher_winners=sum(int(yho[i+5]>yho[i]) for i in range(5))
    # Trivial comparator is important: all five author targets favor hotter!
    return {"schema_version":"rhombus-0192-author-acs-six-hour-source-eval-v1",
            "new_DOI":SOURCE_DOI,"author_conditions":10,"source_nominal_formulas":5,
            "source_heldout_DOI_groups":1,"source_train_DOI_groups":2,
            "frozen_process_features":["temperature_C","holding_min"],
            "published_truth_eligible_for_new_blind":False,
            "original_training_TEST_121_unread":True,
            "source_numeric_TRAIN_before_quarantine":449,
            "eligible_source_O_ONLY_TRAIN":len(indices),
            "TRAIN_original_matched":matched,"TRAIN_components_excluded":excluded,
            "source_meta":meta,"models":metrics,
            "constant_time_pair_high_temp_oracle_heuristic_correct":higher_winners,
            "higher_temperature_source_winner_pairs":higher_winners,
            "below_source_training_temperature_min_rows":5,
            "twelve_hour_powder_covered_excluded":10,
            "improved_prediction_implies_selection_GO":False,
            "production_enabled":False,"scientific_GO":False,
            "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
            "next_action":"0193-O_ONLY-NEW_COMPATIBLE_DOIS_PLUS_PROCESS_OOD_ABSTENTION"}


def run(checkout:Path,out:Path):
    if out.exists() or checkout.resolve(strict=True) in out.resolve().parents:
        raise ValueError("unsafe original source and output path")
    with tempfile.TemporaryDirectory(prefix="rhombus-0192-") as d:
        prior,arr=run_official_original_oof(checkout.resolve(),Path(d)/"original",return_internal=True)
        records,_=build_obelix_benchmark_intake(checkout.resolve(),expected_commit=SOURCE_COMMIT)
        a,ma=original_process_2018(get_jats("PMC9079727"))
        b,mb=original_process_2020(get_jats("PMC7040616"))
        newer,meta=original_six_hour_conditions(get_jats(SOURCE_PMC))
        result=score(prior,arr,records,a,b,newer,meta)
        result["training_DOI_original_source_SHA256"]=[ma["original_JATS_SHA256"],mb["xml_SHA256"]]
    out.mkdir(parents=True,exist_ok=False)
    (out/"0192_new_author_six_hour_source_heldout.json").write_bytes(_json_bytes(result)+b"\n")
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    q=p.parse_args()
    result=run(q.original_obelix_checkout,q.output_dir)
    print("0192_ACTUAL_NEW_PUBLISHER_SIX_HOUR_SOURCE",json.dumps({
        "conditions":result["author_conditions"],"models":result["models"],
        "trivial_hotter_baseline_correct":result["constant_time_pair_high_temp_oracle_heuristic_correct"],
        "scientific_GO":False},sort_keys=True))
