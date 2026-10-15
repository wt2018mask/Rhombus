"""0187 O_ONLY original 25C TOTAL: three genuinely different author JATS DOIs.

Measured source manuscripts are original Europe PMC full-text deposits. All values
checked in ORIGINAL article Table 2, not review tables or synthetic labels.
Precursors are NOMINAL descriptors, not certified measured pellet compositions.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re,tempfile,unicodedata
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import numpy as np
from rhombus.qualification.obelix_benchmark_intake import SOURCE_COMMIT,_json_bytes,build_obelix_benchmark_intake
from scripts.science.obelix_real_grouped_oof_0146 import _composition,run_official_original_oof
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_solo_family_specialists_0184 import RIDGE_ALPHA
from scripts.science.obelix_solo_oxide_primary_0186 import get_original,FORMULAS as FIRST_FORMULAS,PRISTINE as FIRST_VALUES,SOURCE_DOI as FIRST_DOI
from scripts.science.obelix_solo_oxide_external_0185 import doi

SCHEMA="rhombus-0187-solo-three-first-party-doi-25c-total-v1"
DOIS=(FIRST_DOI,"10.3390/nano12172946","10.3390/ma13030560")
PMCS=("PMC12315797","PMC9457903","PMC7040616")
SOURCE_ROOT="https://www.ebi.ac.uk/europepmc/webservices/rest/"
MAX_XML=8_000_000
MODELS=("POOLED_RF","O_ONLY_RF","O_ONLY_RIDGE","O_ONLY_TRAIN_MEAN")
# Source 2 original theoretical precursor formula Li_(x-0.75), not measured sintered chemistry.
LI_START=(6.9,7.7,8.4)
SERIES2022={
 "Al":((1.0,1.7,0.1),"Li{li}Al0.25La3Zr2O12"),
 "AGT":((1.8,3.6,0.2),"Li{li}Al0.172Ga0.072La3Zr1.982Ta0.018O12"),
}
SERIES2020="Li6.6La3Zr1.6Nb0.4O12"
COND2020=(1.58,5.09,3.49,0.51,0.35)
SINTER2020=("SL1","SL2","SL3","SL4","SL5")


def tag(t):return t.tag.split("}")[-1] if isinstance(t.tag,str) else ""
def flatten(e):return norm("".join(e.itertext()))
def norm(s):
    s=unicodedata.normalize("NFKC",s)
    for a,b in (("\u2212","-"),("\u2010","-"),("\u2011","-"),("\u2013","-"),("\u2014","-"),
                ("\u00ad",""),("\u2060",""),("\u00d7","x"),("\u200b",""),("\x02","")):s=s.replace(a,b)
    return re.sub(r"\s+"," ",s).strip()
def simple(s):return re.sub(r"[^a-z0-9.]","",norm(s).lower())

def parse_article(body,doi_value,pmcid):
    if not isinstance(body,bytes) or not 0<len(body)<=MAX_XML:raise ValueError("real original JATS body size invalid")
    if b"<!ENTITY" in body.upper():raise ValueError("external XML entities forbidden")
    clean=body
    if b"<!DOCTYPE" in body.upper():
        clean,n=re.subn(rb"<!DOCTYPE\s+article\b[^<>\[\]]{0,2000}>",b"",body,flags=re.I)
        if n!=1 or b"<!DOCTYPE" in clean.upper():raise ValueError("untrusted source DTD/internal entity")
    try:root=ET.fromstring(clean)
    except ET.ParseError as exc:raise ValueError("real JATS XML unparseable") from exc
    if tag(root)!="article":raise ValueError("not original author JATS")
    ids={flatten(t).lower() for t in root.iter() if tag(t)=="article-id" and t.attrib.get("pub-id-type")=="doi"}
    pmcids={flatten(t).upper().removeprefix("PMC") for t in root.iter()
            if tag(t)=="article-id" and t.attrib.get("pub-id-type") in ("pmc","pmcid")}
    if doi_value not in ids or pmcid.removeprefix("PMC") not in pmcids:
        raise ValueError("publisher article identity DOI+PMC mismatch")
    bodies=[t for t in root.iter() if tag(t)=="body"]
    if len(bodies)!=1:raise ValueError("original science body ambiguous")
    science=" ".join(flatten(t) for t in bodies[0].iter() if tag(t)=="p")
    if not all(x in science.lower() for x in ("conductivity","llzo")) and "Li" not in science:
        raise ValueError("unrelated experimental original science")
    tables=[]
    for tw in bodies[0].iter():
        if tag(tw)!="table-wrap":continue
        labels=[flatten(t) for t in tw if tag(t)=="label"]
        caption=[flatten(t) for t in tw if tag(t)=="caption"]
        if not labels or simple(labels[0])!="table2":continue
        rows=[]
        for tr in tw.iter():
            if tag(tr)=="tr":
                cells=[flatten(cell) for cell in tr if tag(cell) in ("td","th")]
                if cells:rows.append(cells)
        tables.append({"caption":" ".join(caption),"rows":rows})
    if len(tables)!=1:raise ValueError("original Table 2 unavailable or ambiguous")
    table=tables[0]
    cap=simple(table["caption"])
    if "total" not in cap or "conductivity" not in cap or ("25c" not in cap and "25" not in cap):
        raise ValueError("original Table 2 not exact 25C TOTAL transport")
    return {"table":table,"science":science,"source_metadata":{
        "DOI":doi_value,"PMCID":pmcid,"xml_SHA256":hashlib.sha256(body).hexdigest(),
        "original_Table2_25C_TOTAL":True,"author_pub_DOI_not_independent_pellet":True}}

def numeric_cell(cell):
    s=norm(cell)
    try:return float(s)
    except ValueError:return None

def inspect_2022(body):
    item=parse_article(body,DOIS[1],PMCS[1])
    t=item["table"]
    sc=simple(item["science"])
    if ("al0.25" not in sc or "al0.172" not in sc or
        "ga0.072" not in sc or "ta0.018" not in sc or
        not all(str(x) in sc for x in LI_START)):
        raise ValueError("original theoretical precursor formula/x source absent")
    # Original publisher Table 2: 6 explicit conditions columns and a single
    # ionic-conductivity numeric row, *10^-4 S/cm. Assert header and unit.
    cap=simple(t["caption"])
    joined=" ".join(" ".join(r) for r in t["rows"])
    sj=simple(joined)
    if not all(s in sj for s in ("al6.9","al7.7","al8.4","agt6.9","agt7.7","agt8.4")):
        raise ValueError("2022 original exact six table columns missing")
    if not ("10-4" in norm(joined) or "10−4" in joined or "10-4" in norm(t["caption"])):
        raise ValueError("2022 source conductivity 10^-4 unit scaling absent")
    vals=[]
    for row in t["rows"]:
        if "ionconductivity" in simple(row[0]):
            vals=[numeric_cell(c) for c in row[1:]]
            vals=[v for v in vals if v is not None]
            break
    expected=SERIES2022["Al"][0]+SERIES2022["AGT"][0]
    if len(vals)!=6 or any(abs(a-b)>1e-8 for a,b in zip(vals,expected)):
        raise ValueError("2022 Table2 conductivity values altered or unlinked to six columns")
    rows=[]
    for k,(group,(values,template)) in enumerate(SERIES2022.items()):
        for x,v in zip(LI_START,values):
            formula=template.format(li=f"{x-.75:.10g}")
            rows.append((DOIS[1],f"{group}_{x}",formula,v*1e-4))
    item["source_metadata"].update({
        "source_rows":6,"temp_C":25,"endpoint":"TOTAL_IONIC_CONDUCTIVITY",
        "nominal_precursor_composition_NOT_measured_final_pellet":True,
        "theoretical_formula_source_uses_initial_li_input":True})
    return rows,item["source_metadata"]

def inspect_2020(body):
    item=parse_article(body,DOIS[2],PMCS[2])
    t=item["table"];s=simple(item["science"])
    if simple(SERIES2020) not in s:
        raise ValueError("2020 original nominal Nb garnet formula missing")
    joined=" ".join(" ".join(r) for r in t["rows"])
    if "10-4" not in norm(joined) and "10-4" not in norm(t["caption"]):
        raise ValueError("2020 table conductivity 10^-4 S/cm scaling absent")
    seen=[]
    for label,expected in zip(SINTER2020,COND2020):
        found=[row for row in t["rows"] if row and simple(row[0])==label.lower()]
        if len(found)!=1:raise ValueError("2020 original sintering condition label missing: "+label)
        numerics=[v for c in found[0][1:] if (v:=numeric_cell(c)) is not None]
        if not any(abs(v-expected)<1e-8 for v in numerics):
            raise ValueError("2020 source 25C total value mispaired: "+label)
        seen.append((DOIS[2],label,SERIES2020,expected*1e-4))
    item["source_metadata"].update({"source_rows":5,"temp_C":25,
        "endpoint":"TOTAL_IONIC_CONDUCTIVITY",
        "same_nominal_formula_five_distinct_sintering_conditions":True,
        "original_pellet_level_physical_replicates_authenticated":False})
    return seen,item["source_metadata"]

def get_jats(pmc):
    uri=SOURCE_ROOT+pmc+"/fullTextXML"
    req=Request(uri,headers={"Accept":"application/xml, text/xml",
        "User-Agent":"Rhombus-0187-public-source-authentication"})
    with urlopen(req,timeout=45) as resp:
        a=urlsplit(resp.geturl());e=urlsplit(uri)
        if (a.scheme,a.hostname,a.path)!=(e.scheme,e.hostname,e.path):
            raise ValueError("original depositor redirect mismatch")
        data=resp.read(MAX_XML+1)
    return data

def embargo_training(records,arrays,required_formulas):
    # Full 478 original TRAIN connectivity, including censored/cross-DOI bridges.
    rows={};test=0
    for v in records:
        split=v.get("official_split")
        if split=="TEST":test+=1;continue
        if split!="TRAIN":raise ValueError("unexpected source split")
        sid=v.get("source_entry_id")
        if not isinstance(sid,str) or sid in rows:raise ValueError("invalid source TRAIN id")
        rows[sid]=v
    if len(rows)!=478 or test!=121:raise ValueError("publisher embargo population changed")
    reduced={_composition(f)[0] for f in required_formulas}
    parent={k:k for k in rows}
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(a,b):
        a,b=root(a),root(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    keys={};matched=set()
    for sid,v in sorted(rows.items()):
        raw=v.get("reported_composition")
        parsed=_composition(raw)
        z=["RAW:"+str(raw).strip().casefold()]
        if parsed:z.append("REDUCED:"+parsed[0])
        for d in v.get("reference_dois",[]):
            dd=doi(d)
            if not dd:raise ValueError("invalid original TRAIN DOI")
            z.append("DOI:"+dd)
        if (parsed and parsed[0] in reduced) or any(x=="DOI:"+d for x in z for d in DOIS):
            matched.add(sid)
        for k in set(z):
            if k in keys:union(sid,keys[k])
            else:keys[k]=sid
    excluded={root(k) for k in matched}
    source_ids=arrays["source_ids"];groups=arrays["groups"]
    if len(source_ids)!=len(groups):raise ValueError("source group join invalid")
    if any(root(s)!=g for s,g in zip(source_ids,groups)):
        raise ValueError("original 0146 source-group graph is not identical")
    mask=np.array([root(s) not in excluded for s in source_ids],dtype=bool)
    return mask,len(matched),len(excluded)

def score_sources(prior,arrays,records,old,new2022,new2020):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if (prior["original_upstream_commit"]!=SOURCE_COMMIT or prior["original_source_train_count"]!=478
        or prior["original_official_test_reserved_unread"]!=121
        or prior["original_raw_censored_upper_bounds_excluded"]!=29
        or prior["scientific_qualification_authorized"] is not False):
        raise ValueError("original source/official TEST population changed")
    a22,meta22=new2022;a20,meta20=new2020
    if (old["original_doi"]!=DOIS[0] or old["measurement_temperature_C"]!=25
        or meta22["DOI"]!=DOIS[1] or meta20["DOI"]!=DOIS[2]):
        raise ValueError("original published DOI and target source mismatch")
    old_rows=[(DOIS[0],"TA_PRISTINE",FIRST_FORMULAS[0],FIRST_VALUES[0]),
              (DOIS[0],"GA_PRISTINE",FIRST_FORMULAS[1],FIRST_VALUES[1])]
    data=old_rows+a22+a20
    if len(data)!=13 or len(set(x[0] for x in data))!=3:
        raise ValueError("original three-DOI source count changed")
    unique_compositions={_composition(x[2])[0] for x in data}
    x=np.asarray(arrays["x"]);y=np.asarray(arrays["y"])
    if x.shape!=(449,118) or y.shape!=(449,):raise ValueError("original numeric TRAIN population changed")
    mask,matched,groups=embargo_training(records,arrays,[r[2] for r in data])
    ids=np.where(mask)[0]
    oxide_ids=np.array([i for i in ids if _family_proxy(x[i])=="O_ONLY"],dtype=int)
    if len(ids)<280 or len(oxide_ids)<100:raise ValueError("source-group embargo underpowered")
    feat=np.asarray([_composition(r[2])[1] for r in data])
    if any(_family_proxy(v)!="O_ONLY" for v in feat):raise ValueError("nonoxide included")
    truth=np.log10(np.asarray([r[3] for r in data]))
    rf=RandomForestRegressor(**RF_PARAMS).fit(x[ids],y[ids])
    focus=RandomForestRegressor(**RF_PARAMS).fit(x[oxide_ids],y[oxide_ids])
    ridge=make_pipeline(StandardScaler(),Ridge(alpha=RIDGE_ALPHA)).fit(x[oxide_ids],y[oxide_ids])
    predicts={"POOLED_RF":rf.predict(feat),"O_ONLY_RF":focus.predict(feat),
        "O_ONLY_RIDGE":ridge.predict(feat),"O_ONLY_TRAIN_MEAN":np.full(len(data),float(y[oxide_ids].mean()))}
    results={}
    for m,pred in predicts.items():
        err=np.abs(pred-truth)
        if not np.isfinite(err).all():raise ValueError("untrusted model numeric output")
        groupscore=[float(np.mean(err[:2])),float(np.mean(err[2:8])),float(np.mean(err[8:]))]
        results[m]={
            "row_MAE_log10":round(float(err.mean()),8),
            "equal_DOI_group_macro_MAE_log10":round(float(np.mean(groupscore)),8),
            "source_group_MAE_log10":{k:round(v,8) for k,v in zip(DOIS,groupscore)},
            "DOI_group_count":3,
        }
    return {
        "schema_version":SCHEMA,"experiment":"SOLO_O_ONLY_3_PRIMARY_PAPER_25C_TOTAL",
        "original_sources":[{"DOI":DOIS[0],"source_JATS_SHA256":old["original_publisher_source_JATS_SHA256"],
                             "author_rows":2},meta22,meta20],
        "source_DOIs":list(DOIS),"DOI_groups":3,"experimental_condition_rows":13,
        "distinct_nominal_formulas":len(unique_compositions),
        "2022_initial_Li_theoretical_formula_not_certified_pellet":True,
        "2020_five_same_nominal_formula_different_sintering_routes":True,
        "original_papers_public_before_2026_experiment":True,
        "strict_new_untouched_blind":False,"measurement_temperature_C":25,
        "target":"AUTHOR_TOTAL_IONIC_CONDUCTIVITY_S_CM",
        "original_TRAIN":478,"original_numeric_TRAIN":449,
        "original_official_TEST_RESERVED_UNREAD":121,"original_official_TEST_parsed":False,
        "original_TRAIN_direct_source_identity_matches":matched,
        "original_TRAIN_embargoed_connected_groups":groups,
        "trained_rows_after_embargo":len(ids),
        "trained_O_ONLY_rows_after_embargo":len(oxide_ids),
        "unchanged_models":list(MODELS),
        "scores":results,
        "three_DOI_not_sufficient_for_statistical_generalization":True,
        "group_bootstrap_disabled_underpowered":True,
        "same_sample_XRD_EIS_pellet_certified":False,
        "domain_model_activated":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_external_GO":False,
        "next_action":"0188-SOLO-O_ONLY-EXPAND-INDEPENDENT-DOI-QUALIFIED-GROUPS",
    }

def run(obelix,output):
    original=obelix.resolve(strict=True)
    if output.exists() or original in output.resolve().parents:
        raise ValueError("new separate source-derived evidence directory required")
    with tempfile.TemporaryDirectory(prefix="rhombus-0187-three-doi-") as tmp:
        prior,arrays=run_official_original_oof(original,Path(tmp)/"obelix",return_internal=True)
        records,_=build_obelix_benchmark_intake(original,expected_commit=SOURCE_COMMIT)
        old=get_original()
        p2022=inspect_2022(get_jats(PMCS[1]))
        p2020=inspect_2020(get_jats(PMCS[2]))
        result=score_sources(prior,arrays,records,old,p2022,p2020)
    output.mkdir(parents=True,exist_ok=False)
    (output/"0187_three_original_doi_25C_TOTAL.json").write_bytes(_json_bytes(result)+b"\n")
    return result

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--original-obelix-checkout",type=Path,required=True)
    a.add_argument("--output-dir",type=Path,required=True)
    p=a.parse_args()
    v=run(p.original_obelix_checkout,p.output_dir)
    print("0187_SOLO_3_REAL_ORIGINAL_DOI_25C_TOTAL_NUMERIC_DIAGNOSTIC_COMPLETE")
    print(json.dumps({"DOI_groups":v["DOI_groups"],"author_conditions":v["experimental_condition_rows"],
                      "nominal_formulas":v["distinct_nominal_formulas"],
                      "scores":v["scores"],"science_GO":False},sort_keys=True))
