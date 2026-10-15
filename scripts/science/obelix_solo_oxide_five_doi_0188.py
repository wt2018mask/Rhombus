"""0188: actual original author 25C TOTAL O_ONLY measurements, 5 DOI groups.

Five paper groups are not 22 independent materials. Two new papers each use
one nominal Al-LLZO formula for multiple manufacturing conditions.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from rhombus.qualification.obelix_benchmark_intake import SOURCE_COMMIT,_json_bytes,build_obelix_benchmark_intake
from scripts.science.obelix_real_grouped_oof_0146 import _composition,run_official_original_oof
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_solo_family_specialists_0184 import RIDGE_ALPHA
from scripts.science.obelix_solo_oxide_jats_three_doi_0187 import (
    DOIS as OLD_DOIS,PMCS as OLD_PMCS,FIRST_FORMULAS,FIRST_VALUES,
    get_original,get_jats,inspect_2022,inspect_2020,tag,flatten,norm,simple,MODELS)
from scripts.science.obelix_solo_oxide_external_0185 import doi

DOI18="10.1039/c8ra01329b"
DOI21="10.3390/ma14226809"
ALL_DOIS=OLD_DOIS+(DOI18,DOI21)
FORMULA="Li6.4Al0.2La3Zr2O12"
T18=(8.78e-5,1.54e-5,2.80e-5,2.10e-4,1.32e-4)
T21=(3.14e-4,2.64e-4,2.02e-4,3.28e-4)
S18=tuple("LLZALO-"+str(i) for i in range(1,6))
S21=("SSR","SASSR","CP","SD")
SCHEMA="rhombus-0188-solo-original-five-DOI-25C-total-v1"


def table_source(blob,source_doi,pmc,number):
    if not isinstance(blob,bytes) or not 0<len(blob)<=8_000_000:
        raise ValueError("original JATS bytes missing or oversized")
    if b"<!ENTITY" in blob.upper():raise ValueError("JATS entity forbidden")
    clean=blob
    if b"<!DOCTYPE" in blob.upper():
        clean,n=re.subn(rb"<!DOCTYPE\s+article\b[^<>\[\]]{0,2000}>",b"",blob,flags=re.I)
        if n!=1 or b"<!DOCTYPE" in clean.upper():raise ValueError("JATS DTD unsafe")
    try:root=ET.fromstring(clean)
    except ET.ParseError as exc:raise ValueError("original JATS parse failed") from exc
    if tag(root)!="article":raise ValueError("not original article")
    dois={flatten(n).lower() for n in root.iter() if tag(n)=="article-id" and n.attrib.get("pub-id-type")=="doi"}
    pmcs={flatten(n).upper().removeprefix("PMC") for n in root.iter() if tag(n)=="article-id" and n.attrib.get("pub-id-type") in ("pmc","pmcid")}
    if source_doi not in dois or pmc.removeprefix("PMC") not in pmcs:raise ValueError("original DOI/PMC mismatch")
    body=[n for n in root.iter() if tag(n)=="body"]
    if len(body)!=1:raise ValueError("invalid original science body")
    science=" ".join(flatten(n) for n in body[0].iter() if tag(n)=="p")
    tables=[]
    for tw in root.iter():
        if tag(tw)!="table-wrap":continue
        labels=[flatten(n) for n in tw if tag(n)=="label"]
        if not labels or simple(labels[0]).rstrip(".")!="table"+str(number):continue
        headers=" ".join(flatten(n) for n in tw if tag(n)=="caption")
        rows=[]
        for tr in tw.iter():
            if tag(tr)=="tr":
                cells=[flatten(c) for c in tr if tag(c) in ("td","th")]
                if cells:rows.append(cells)
        tables.append((headers,rows))
    if len(tables)!=1:raise ValueError("missing/duplicate first-party original table")
    return science,tables[0][0],tables[0][1],{
        "DOI":source_doi,"PMCID":pmc,"original_JATS_SHA256":hashlib.sha256(blob).hexdigest(),
        "original_table_number":number,"nominal_composition_not_final_pellet_identity":True}


def original_2018(blob):
    science,caption,rows,meta=table_source(blob,DOI18,"PMC9079727",3)
    if simple(FORMULA) not in simple(science) or "25" not in science:
        raise ValueError("2018 original 25C Al-LLZO context missing")
    if not ("total" in simple(caption+" "+rows[0][1]) and "bulk" in simple(" ".join(rows[0]))):
        raise ValueError("Table3 total and bulk columns not differentiated")
    output=[]
    for label,expected in zip(S18,T18):
        match=[r for r in rows if r and simple(r[0])==simple(label)]
        if len(match)!=1 or len(match[0])<3:raise ValueError("2018 source state missing")
        number=norm(match[0][1]).lower().replace(" ","").replace("×","x").replace("·","x")
        m=re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)x10\^?\(?-?([0-9]+)\)?",number)
        if m:found=float(m.group(1))*10**(-int(m.group(2)))
        else:
            try:found=float(number)
            except ValueError as exc:raise ValueError("2018 source total cell corrupted") from exc
        if not math.isclose(found,expected,rel_tol=1e-4):raise ValueError("2018 source total conductivity altered")
        output.append((DOI18,label,FORMULA,found))
    return output,meta


def original_2021(blob):
    science,caption,rows,meta=table_source(blob,DOI21,"PMC8620275",4)
    if simple(FORMULA) not in simple(science) or "25" not in science or "total" not in science.lower():
        raise ValueError("2021 original 25C total Al-LLZO evidence missing")
    if "total" not in simple(caption):raise ValueError("Table4 total conductivity identity missing")
    hdr=next((r for r in rows if len(r)>=5 and all(k.lower() in [simple(x) for x in r[1:]] for k in S21)),None)
    if hdr is None:raise ValueError("Table4 synthesis header missing")
    indices={simple(x):i for i,x in enumerate(hdr)}
    table=[r for r in rows if r and "total" in simple(r[0]) and "10-4" in norm(r[0])]
    if len(table)!=1:raise ValueError("Table4 total (10^-4) row missing or ambiguous")
    output=[]
    for label,expected in zip(S21,T21):
        idx=indices[label.lower()]
        if idx>=len(table[0]):raise ValueError("Table4 insufficient total cells")
        cell=norm(table[0][idx]).replace(" ","")
        match=re.fullmatch(r"([0-9]+\.[0-9]+)\(([0-9]+)\)",cell)
        if not match:raise ValueError("original uncertainty notation missing")
        value=float(match.group(1))*1e-4
        if not math.isclose(value,expected,rel_tol=1e-5):raise ValueError("source 2021 value/route changed")
        output.append((DOI21,label,FORMULA,value))
    return output,meta


def embargo(records,arrays,conditions):
    rows={};reserved=0
    for rec in records:
        split=rec.get("official_split")
        if split=="TEST":reserved+=1;continue
        if split!="TRAIN":raise ValueError("official split invalid")
        sid=rec.get("source_entry_id")
        if not isinstance(sid,str) or sid in rows:raise ValueError("original ID duplicate/missing")
        rows[sid]=rec
    if (len(rows),reserved)!=(478,121):raise ValueError("publisher TRAIN/TEST drift")
    formulas={_composition(r[2])[0] for r in conditions}
    dois={r[0] for r in conditions}
    parent={sid:sid for sid in rows}
    def root(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    def union(a,b):
        a,b=root(a),root(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    seen={};matches=set()
    for sid,rec in sorted(rows.items()):
        raw=rec.get("reported_composition");parsed=_composition(raw)
        keys=["RAW:"+str(raw).strip().casefold()]
        if parsed:keys.append("FORM:"+parsed[0])
        original_dois=[]
        for raw_doi in rec.get("reference_dois",[]):
            d=doi(raw_doi)
            if not d:raise ValueError("source TRAIN DOI malformed")
            original_dois.append(d);keys.append("DOI:"+d)
        if (parsed and parsed[0] in formulas) or any(d in dois for d in original_dois):
            matches.add(sid)
        for key in set(keys):
            if key in seen:union(sid,seen[key])
            else:seen[key]=sid
    quarantined={root(v) for v in matches}
    if len(arrays["source_ids"])!=len(arrays["groups"]):raise ValueError("original groups shape invalid")
    if any(root(sid)!=grp for sid,grp in zip(arrays["source_ids"],arrays["groups"])):
        raise ValueError("original connected group graph mismatch")
    mask=np.array([root(sid) not in quarantined for sid in arrays["source_ids"]],dtype=bool)
    return mask,len(matches),len(quarantined)


def evaluate(prior,arrays,records,first,second,third,fourth,fifth):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    if (prior["original_upstream_commit"]!=SOURCE_COMMIT or prior["original_source_train_count"]!=478
        or prior["original_official_test_reserved_unread"]!=121
        or prior["original_raw_censored_upper_bounds_excluded"]!=29
        or prior["scientific_qualification_authorized"] is not False):
        raise ValueError("source training contract changed")
    if first["original_doi"]!=OLD_DOIS[0]:raise ValueError("first paper identity wrong")
    part=[
        [(OLD_DOIS[0],"TA0.5",FIRST_FORMULAS[0],FIRST_VALUES[0]),
         (OLD_DOIS[0],"GA0.2",FIRST_FORMULAS[1],FIRST_VALUES[1])],
        second[0],third[0],fourth[0],fifth[0]]
    metadata=[
        {"DOI":OLD_DOIS[0],"original_JATS_SHA256":first["original_publisher_source_JATS_SHA256"]},
        second[1],third[1],fourth[1],fifth[1]]
    if any(m["DOI"]!=v for m,v in zip(metadata,ALL_DOIS)):raise ValueError("source ordered DOI mismatch")
    cond=sum(part,[])
    if [len(a) for a in part]!=[2,6,5,5,4]:raise ValueError("source observation population drift")
    x=np.asarray(arrays["x"]);y=np.asarray(arrays["y"])
    if x.shape!=(449,118) or y.shape!=(449,):raise ValueError("original numeric TRAIN drift")
    mask,matched,quarantined=embargo(records,arrays,cond)
    good=np.where(mask)[0];focus=np.array([i for i in good if _family_proxy(x[i])=="O_ONLY"],dtype=int)
    if len(good)<250 or len(focus)<100:raise ValueError("insufficient source-separated model training records")
    feat=np.array([_composition(r[2])[1] for r in cond])
    if any(_family_proxy(z)!="O_ONLY" for z in feat):raise ValueError("non O_ONLY source included")
    ytrue=np.log10(np.array([r[3] for r in cond]))
    models={
        "POOLED_RF":RandomForestRegressor(**RF_PARAMS).fit(x[good],y[good]).predict(feat),
        "O_ONLY_RF":RandomForestRegressor(**RF_PARAMS).fit(x[focus],y[focus]).predict(feat),
        "O_ONLY_RIDGE":make_pipeline(StandardScaler(),Ridge(alpha=RIDGE_ALPHA)).fit(x[focus],y[focus]).predict(feat),
        "O_ONLY_TRAIN_MEAN":np.full(len(cond),float(y[focus].mean())),
    }
    scores={}
    for key,pred in models.items():
        err=np.abs(ytrue-pred);start=0;groups={}
        if not np.isfinite(err).all():raise ValueError("nonfinite external output")
        for d,n in zip(ALL_DOIS,(2,6,5,5,4)):
            groups[d]=round(float(err[start:start+n].mean()),8)
            start+=n
        if start!=22:raise ValueError("score accounting drift")
        scores[key]={
            "row_MAE_log10":round(float(err.mean()),8),
            "equal_DOI_macro_MAE_log10":round(float(np.mean(list(groups.values()))),8),
            "source_DOI_MAE_log10":groups}
    return {
        "schema_version":"rhombus-0188-solo-five-original-DOI-25C-total-v1",
        "sources":metadata,"source_DOIs":list(ALL_DOIS),"distinct_DOI_groups":5,
        "actual_reference_conditions":22,
        "distinct_nominal_compositions":len({_composition(r[2])[0] for r in cond}),
        "source_new_processing_conditions_share_nominal_formula":True,
        "2022_nominal_precursor_is_not_measured_final_pellet":True,
        "measurement_temperature_C":25,"measured_observable":"TOTAL_IONIC_CONDUCTIVITY_S_CM",
        "original_TRAIN":478,"numeric_TRAIN_before_embargo":449,
        "original_official_TEST_reserved_UNREAD":121,"original_TEST_fields_parsed":False,
        "original_TRAIN_matched":matched,"original_TRAIN_connected_components_quarantined":quarantined,
        "numeric_TRAIN_after_embargo":len(good),"O_ONLY_TRAIN_after_embargo":len(focus),
        "frozen_models":list(MODELS),"model_scores":scores,
        "source_group_bootstrap_or_scientific_generalization_GO":False,
        "five_DOI_labels_public_previously_exposed":True,
        "original_measured_pellet_composition_authenticated":False,
        "production_O_ONLY_router_enabled":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_GO":False,"next_action":"0189-SOLO-O_ONLY-NEW_INDEPENDENT_SOURCE_GROUPS_AND_PROCESS_METADATA",
    }


def run(checkout,out):
    original=checkout.resolve(strict=True)
    if out.exists() or original in out.resolve().parents:raise ValueError("source and result must be different immutable paths")
    with tempfile.TemporaryDirectory(prefix="rhombus-0188-") as d:
        prior,arr=run_official_original_oof(original,Path(d)/"original",return_internal=True)
        records,_=build_obelix_benchmark_intake(original,expected_commit=SOURCE_COMMIT)
        p1=get_original();p2=inspect_2022(get_jats(OLD_PMCS[1]))
        p3=inspect_2020(get_jats(OLD_PMCS[2]))
        p4=original_2018(get_jats("PMC9079727"))
        p5=original_2021(get_jats("PMC8620275"))
        result=evaluate(prior,arr,records,p1,p2,p3,p4,p5)
    out.mkdir(parents=True,exist_ok=False)
    (out/"0188_five_original_DOI_25C_total.json").write_bytes(_json_bytes(result)+b"\n")
    return result


if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--original-obelix-checkout",type=Path,required=True)
    a.add_argument("--output-dir",type=Path,required=True)
    q=a.parse_args()
    r=run(q.original_obelix_checkout,q.output_dir)
    print("0188_FIVE_ORIGINAL_SOURCE_REAL_SCIENCE_EXECUTED",json.dumps(
        {"sources":r["distinct_DOI_groups"],"conditions":r["actual_reference_conditions"],
         "scores":r["model_scores"],"science_GO":False},sort_keys=True))
