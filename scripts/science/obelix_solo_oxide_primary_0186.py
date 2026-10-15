"""0186 SOLO O_ONLY genuine 2025 primary-paper 25C total-conductivity falsification.

Exactly TWO nominal compositions and FOUR processing-state observations from
ONE original paper; no independent material generalization claim. Source is
original Europe PMC JATS, never hand-entered benchmark labels or official TEST.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import SOURCE_COMMIT, _json_bytes, build_obelix_benchmark_intake
from scripts.science.obelix_real_grouped_oof_0146 import _composition, run_official_original_oof
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
from scripts.science.obelix_solo_family_specialists_0184 import RIDGE_ALPHA
from scripts.science.obelix_solo_oxide_external_0185 import doi

SOURCE_DOI="10.1039/d5ra03917g"
PMCID="PMC12315797"
ORIGINAL_JATS="https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12315797/fullTextXML"
MAX_XML_BYTES=7_000_000
SCHEMA="rhombus-0186-solo-oxide-primary-jats-temperature-target-gate-v1"
# Original-paper measurement claims, NOT a pretense of an unused test.
FORMULAS=("Li6.5La3Zr1.5Ta0.5O12","Li6.4Ga0.2La3Zr2O12")
NOMINAL=("Ta0.5_LLZO","Ga0.2_LLZO")
PRISTINE=(2.32e-4,7.14e-4)
POST_LI_SI_CONTACT=(2.86e-4,3.29e-4)
MODELS=("POOLED_RF","O_ONLY_RF","O_ONLY_RIDGE","O_ONLY_TRAIN_MEAN")


def tag(element):
    return element.tag.split("}")[-1] if isinstance(element.tag,str) else ""

def normalized(text):
    s=unicodedata.normalize("NFKC",text)
    for p,q in (("\u2212","-"),("\u2011","-"),("\u2010","-"),("\u2013","-"),("\u00d7","x"),("\u00ad",""),("\u2060","")):
        s=s.replace(p,q)
    return re.sub(r"\s+"," ",s).strip()

def numerical_exponents(text,items):
    s=normalized(text).lower()
    for coef,power in items:
        needle=r"(?<!\d)"+re.escape(coef)+r"\s*(?:x|\*)\s*10\s*-\s*"+str(power)+r"(?!\d)"
        if not re.search(needle,s):
            raise ValueError("published experimental coefficient/exponent absent or altered: "+coef)
    return True

def unique_paragraph(paragraphs,terms):
    hits=[p for p in paragraphs if all(k.lower() in p.lower() for k in terms)]
    if len(hits)!=1:
        raise ValueError("missing or ambiguous ORIGINAL primary-paper context "+str(terms))
    return hits[0]

def parse_original_jats(payload):
    if not isinstance(payload,bytes) or not payload or len(payload)>MAX_XML_BYTES:
        raise ValueError("original publisher XML resource budget exceeded")
    # JATS may carry a harmless external DTD declaration; never resolve it.
    # Strip ONLY one bounded bare ARTICLE declaration, reject all internal
    # subsets/entities rather than allowing XML entity expansion.
    if b"<!ENTITY" in payload.upper():
        raise ValueError("XML entity declarations prohibited")
    clean=payload
    if b"<!DOCTYPE" in payload.upper():
        clean,count=re.subn(rb"<!DOCTYPE\\s+article\\b[^<>\\[\\]]{0,2000}>",b"",payload,flags=re.I)
        if count!=1 or b"<!DOCTYPE" in clean.upper():
            raise ValueError("untrusted JATS doctype or internal subset")
    try:root=ET.fromstring(clean)
    except ET.ParseError as exc:raise ValueError("malformed original JATS") from exc
    if tag(root)!="article":raise ValueError("not first-party journal article")
    ids={normalized("".join(n.itertext())).lower()
         for n in root.iter() if tag(n)=="article-id" and n.attrib.get("pub-id-type","")=="doi"}
    pmcs={normalized("".join(n.itertext())).upper().removeprefix("PMC")
          for n in root.iter() if tag(n)=="article-id" and n.attrib.get("pub-id-type","") in ("pmc","pmcid")}
    if SOURCE_DOI not in ids or "12315797" not in pmcs:
        raise ValueError("article DOI and independent PMC identity mismatch")
    bodies=[n for n in root.iter() if tag(n)=="body"]
    if len(bodies)!=1:raise ValueError("primary article body unavailable")
    paras=[normalized("".join(n.itertext())) for n in bodies[0].iter() if tag(n)=="p"]
    paras=[s for s in paras if s]
    if len(paras)<15:raise ValueError("truncated article science")
    full=" ".join(paras)
    if not ("Li6.5La3Zr1.5Ta0.5O12".lower() in re.sub(r"\s+","",full).lower()
            and "Li6.4Ga0.2La3Zr2O12".lower() in re.sub(r"\s+","",full).lower()):
        raise ValueError("original nominal O_ONLY compositions not identified")
    methods=unique_paragraph(paras,("total conductivity","bulk","grain"))
    if not ("25" in full and "EIS" in full and "XRD" in full):
        raise ValueError("original 25C EIS and powder diffraction context missing")
    if not ("bulk" in methods.lower() and "grain" in methods.lower()):
        raise ValueError("original bulk and grain contribution scope missing")
    # Two genuinely authored science paragraphs, not the introduction's older
    # literature values or Figure captions, and not extracted pixels.
    before=unique_paragraph(paras,("room-temperature ionic conductivities calculated","Ta-","Ga-"))
    numerical_exponents(before,(("2.32",4),("7.14",4)))
    if not ("respectively" in before.lower() and "total" in " ".join(paras).lower()):
        raise ValueError("primary measurement pairing/total observable absent")
    after_ta=unique_paragraph(paras,("moderate increase","Ta-LLZO"))
    after_ga=unique_paragraph(paras,("substantial decrease","Ga-LLZO"))
    numerical_exponents(after_ta,(("2.32",4),("2.86",4)))
    numerical_exponents(after_ga,(("7.14",4),("3.29",4)))
    if not ("room temperature" in after_ta.lower() and "room temperature" in after_ga.lower()):
        raise ValueError("processing-state values not at measured room temperature")
    source_text=full.lower()
    if not ("25" in source_text and "room temperature" in source_text
            and "interface" in source_text and "pellet" in source_text):
        raise ValueError("measurement condition and pellet methods not established")
    return {
        "original_publisher_source_JATS_SHA256":hashlib.sha256(payload).hexdigest(),
        "source_body_paragraphs":len(paras),
        "original_doi":SOURCE_DOI,
        "original_pmcid":PMCID,
        "measurement_temperature_C":25,
        "transport_endpoint":"AUTHOR_TOTAL_IONIC_CONDUCTIVITY_S_PER_CM",
        "nominal_compositions":list(FORMULAS),
        "verified_author_pristine_S_per_cm":list(PRISTINE),
        "verified_author_after_li_si_contact_S_per_cm":list(POST_LI_SI_CONTACT),
        "nominal_chemistries":2,
        "reported_conditions":4,
        "distinct_original_papers":1,
        "same_individual_diffraction_EIS_pellet_verified":False,
        "unique_per_pellet_geometry_uncertainties_verified":False,
    }

def get_original():
    req=urllib.request.Request(ORIGINAL_JATS,headers={"Accept":"application/xml, text/xml",
        "User-Agent":"Rhombus-0186-primary-physical-science"})
    with urllib.request.urlopen(req,timeout=45) as response:
        a=urllib.parse.urlsplit(response.geturl())
        e=urllib.parse.urlsplit(ORIGINAL_JATS)
        if (a.scheme,a.hostname,a.path)!=(e.scheme,e.hostname,e.path):
            raise ValueError("original publisher redirect drift")
        raw=response.read(MAX_XML_BYTES+1)
    return parse_original_jats(raw)

def components_to_embargo(records,source_ids,grouped):
    """Use ALL TRAIN including censored as identity links; official TEST opaque."""
    train={};reserved=0
    for v in records:
        if v.get("official_split")=="TEST":
            reserved+=1
            continue
        if v.get("official_split")!="TRAIN":raise ValueError("source split drift")
        sid=v.get("source_entry_id")
        if sid in train:raise ValueError("duplicate TRAIN entry")
        train[sid]=v
    if (len(train),reserved)!=(478,121):raise ValueError("official TEST quarantine drift")
    parent={sid:sid for sid in train}
    def find(sid):
        while parent[sid]!=sid:
            parent[sid]=parent[parent[sid]]
            sid=parent[sid]
        return sid
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    seen={};goal={_composition(s)[0] for s in FORMULAS}
    matched=set()
    for sid,v in sorted(train.items()):
        p=_composition(v.get("reported_composition"))
        keys=["RAW:"+str(v.get("reported_composition","")).strip().casefold()]
        if p:keys.append("REDUCED:"+p[0])
        for item in v.get("reference_dois",[]):
            x=doi(item)
            if not x:raise ValueError("untrusted source DOI")
            keys.append("DOI:"+x)
        if (p and p[0] in goal) or SOURCE_DOI in [doi(t) for t in v.get("reference_dois",[])]:
            matched.add(sid)
        for key in set(keys):
            if key in seen:union(sid,seen[key])
            else:seen[key]=sid
    excluded={find(sid) for sid in matched}
    if len(source_ids)!=len(grouped):raise ValueError("source identity shape drift")
    # numeric source group IDs from existing 0146 SHOULD be exactly the same
    # connected-component representative; this checks it independently.
    if any(find(sid)!=group for sid,group in zip(source_ids,grouped)):
        raise ValueError("source group graph mismatch")
    mask=np.array([find(sid) not in excluded for sid in source_ids],dtype=bool)
    return mask,len(excluded),len(matched)

def evaluate_original(primary,prior,arrays,records):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if (prior["original_upstream_commit"]!=SOURCE_COMMIT or
        prior["original_source_train_count"]!=478 or prior["original_official_test_reserved_unread"]!=121 or
        prior["original_raw_censored_upper_bounds_excluded"]!=29 or
        prior["scientific_qualification_authorized"] is not False):
        raise ValueError("original source preparation drift")
    x=np.asarray(arrays["x"]);y=np.asarray(arrays["y"])
    if x.shape!=(449,118) or y.shape!=(449,) or len(set(arrays["groups"]))!=102:
        raise ValueError("original source population mismatch")
    train_mask,n_removed_groups,n_matched=components_to_embargo(records,arrays["source_ids"],arrays["groups"])
    base_ids=np.where(train_mask)[0]
    focused=np.array([i for i in base_ids if _family_proxy(x[i])=="O_ONLY"],dtype=int)
    if len(focused)<100 or len(base_ids)<300:raise ValueError("too few leakage-free TRAIN inputs")
    features=np.array([_composition(f)[1] for f in FORMULAS])
    if any(_family_proxy(f)!="O_ONLY" for f in features):
        raise ValueError("non O_ONLY original paper candidate")
    pooled=RandomForestRegressor(**RF_PARAMS).fit(x[base_ids],y[base_ids])
    focused_rf=RandomForestRegressor(**RF_PARAMS).fit(x[focused],y[focused])
    ridge=make_pipeline(StandardScaler(),Ridge(alpha=RIDGE_ALPHA)).fit(x[focused],y[focused])
    mean=float(np.mean(y[focused]))
    preds={"POOLED_RF":pooled.predict(features),"O_ONLY_RF":focused_rf.predict(features),
           "O_ONLY_RIDGE":ridge.predict(features),"O_ONLY_TRAIN_MEAN":np.array([mean,mean])}
    before=np.log10(np.array(PRISTINE))
    after=np.log10(np.array(POST_LI_SI_CONTACT))
    delta=np.abs(after-before)
    result={
        "schema_version":SCHEMA,
        "article":primary,
        "original_obelix_commit":SOURCE_COMMIT,
        "official_obelix_TRAIN":478,"original_numeric_TRAIN":449,
        "official_obelix_TEST_reserved_UNREAD":121,
        "original_official_TEST_features_or_labels_used":False,
        "focus":"O_ONLY_ONLY",
        "historical_training_source_matching_groups_embargoed":n_removed_groups,
        "historical_TRAIN_rows_exact_paper_DOI_or_formula_match":n_matched,
        "training_rows_after_all_source_group_embargo":len(base_ids),
        "O_ONLY_training_rows_after_embargo":len(focused),
        "frozen_models":list(MODELS),
        "all_models_trained_before_original_2025_paper_truth_scoring":True,
        "study_source_groups":1,
        "different_nominal_compositions":2,
        "processing_states_per_nominal_composition":2,
        "paper_known_public_labels_retroactive":True,
        "source_label_qualified_exact_25C_and_TOTAL":True,
        "individual_pellet_replicate_and_phase_join_certified":False,
        "identical_nominal_input_has_two_processing_specific_experimental_outcomes":True,
        "pristine_Ga_over_Ta_author_ratio":round(float(PRISTINE[1]/PRISTINE[0]),8),
        "post_contact_Ga_over_Ta_author_ratio":round(float(POST_LI_SI_CONTACT[1]/POST_LI_SI_CONTACT[0]),8),
        "paper_paired_processing_log10_spread_by_material":[round(float(v),8) for v in delta],
        "irreducible_four_state_mean_absolute_log10_error_lower_bound_for_composition_only_prediction":
            round(float(sum(delta)/4),8),
        "model_pristine_pair_MAE_log10":{
            name:round(float(np.mean(np.abs(p-before))),8) for name,p in preds.items()},
        "model_post_contact_pair_MAE_log10":{
            name:round(float(np.mean(np.abs(p-after))),8) for name,p in preds.items()},
        "model_all_four_processing_states_MAE_log10":{
            name:round(float(np.mean(np.concatenate((np.abs(p-before),np.abs(p-after))))),8)
            for name,p in preds.items()},
        "no_group_bootstrap_with_one_source_paper":True,
        "cannot_admit_any_model_on_two_compositions_from_one_source":True,
        "new_prospective_blind_materials":0,
        "source_paper_observation_status":"ACTUAL_PRIMARY_JOURNAL_25C_TOTAL_2_CHEMISTRY_4_STATES",
        "production_O_ONLY_router_enabled":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_EXTERNAL_GO":False,
        "next_action":"0187-SOLO-O_ONLY-INDEPENDENT-DOI-COHORT-ACQUISITION",
    }
    return result

def run(checkout,output):
    if output.exists():raise ValueError("original evidence output immutable")
    original=checkout.resolve(strict=True)
    if original in output.resolve().parents:raise ValueError("cannot write into original checkout")
    with tempfile.TemporaryDirectory(prefix="rhombus-0186-") as tmp:
        prior,arrays=run_official_original_oof(original,Path(tmp)/"obelix",return_internal=True)
        records,_=build_obelix_benchmark_intake(original,expected_commit=SOURCE_COMMIT)
        original_article=get_original()
        report=evaluate_original(original_article,prior,arrays,records)
    output.mkdir(parents=True,exist_ok=False)
    (output/"0186_original_25C_total_primary_paper.json").write_bytes(_json_bytes(report)+b"\n")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    report=run(a.original_obelix_checkout,a.output_dir)
    print("0186_REAL_ORIGINAL_25C_TOTAL_O_ONLY_SOURCE_DIAGNOSTIC_PASS")
    print(json.dumps({k:report[k] for k in (
        "training_rows_after_all_source_group_embargo",
        "O_ONLY_training_rows_after_embargo",
        "model_pristine_pair_MAE_log10",
        "model_post_contact_pair_MAE_log10",
        "irreducible_four_state_mean_absolute_log10_error_lower_bound_for_composition_only_prediction",
        "production_O_ONLY_router_enabled","scientific_EXTERNAL_GO")},sort_keys=True))

if __name__=="__main__":main()
