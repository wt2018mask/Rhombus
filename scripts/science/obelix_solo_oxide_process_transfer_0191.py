"""0191: genuine author-DOI-out manufacture temperature/hold-time transport test.

A two-public-paper exploratory experiment. These are NOT new blinded labels.
"""
from __future__ import annotations
import argparse, json, math, re, tempfile, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from rhombus.qualification.obelix_benchmark_intake import SOURCE_COMMIT, _json_bytes, build_obelix_benchmark_intake
from scripts.science.obelix_real_grouped_oof_0146 import _composition, run_official_original_oof
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_solo_oxide_five_doi_0188 import DOI18, FORMULA, embargo, original_2018
from scripts.science.obelix_solo_oxide_jats_three_doi_0187 import DOIS, PMCS, SERIES2020, get_jats, inspect_2020, parse_article, norm, simple, tag, flatten
from scripts.science.obelix_solo_oxide_original_manufacturing_0190 import DOI as DOI25, PMC as PMC25, read_author_table

DOI20=DOIS[2]
SCHEMA="rhombus-0191-two-original-paper-process-transfer-v1"
S18=(("LLZALO-1",1100,1200),("LLZALO-2",1150,1200),("LLZALO-3",1200,1200),("LLZALO-4",1210,900),("LLZALO-5",1220,600))
S20=(("SL1",1200,60),("SL2",1200,30),("SL3",1150,60),("SL4",1100,60),("SL5",1100,360))
ALPHA=1.0

def process_cell(s):
    s=norm(s).replace("×","x").replace(" ","")
    m=re.fullmatch(r"([0-9]{4})°?C[x*]([0-9]{1,3})(h|min)",s,flags=re.I)
    if not m:raise ValueError("unknown exact author process cell")
    t=int(m[1]);time=int(m[2])*(60 if m[3].lower()=="h" else 1)
    if not 950<=t<=1350 or not 0<time<=2400:raise ValueError("invalid process limits")
    return t,time

def original_process_2018(blob):
    # Original Table3 authenticator verifies first-party author DOI, PMCID and labels.
    conductivity,meta=original_2018(blob)
    if b"<!ENTITY" in blob.upper():raise ValueError("unsafe original XML")
    clean=re.sub(rb"<!DOCTYPE\s+article\b[^<>\[\]]{0,2000}>",b"",blob,flags=re.I)
    if b"<!DOCTYPE" in clean.upper():raise ValueError("unsafe source doctype")
    root=ET.fromstring(clean)
    tables=[x for x in root.iter() if tag(x)=="table-wrap"]
    if len(tables)!=3 or any(any(tag(c)=="label" for c in t) for t in tables):
        raise ValueError("2018 3 unlabelled tables contract changed")
    cap=" ".join(flatten(x) for x in tables[0] if tag(x)=="caption")
    if not all(z in simple(cap) for z in ("sampledenotation","sinteringconditions")):
        raise ValueError("2018 original process caption changed")
    rows=[[flatten(cell) for cell in tr if tag(cell) in ("td","th")] for tr in tables[0].iter() if tag(tr)=="tr"]
    if len([r for r in rows if len(r)>=2 and "sintering" in simple(r[1])])!=1:
        raise ValueError("2018 author process header absent")
    result=[]
    for (name,t,minutes),s in zip(S18,conductivity):
        match=[r for r in rows if len(r)>=2 and simple(r[0])==simple(name)]
        if len(match)!=1 or process_cell(match[0][1])!=(t,minutes) or s[1]!=name:
            raise ValueError("2018 author process and conductivity mismatch")
        result.append((DOI18,name,FORMULA,t,minutes,float(s[3])))
    return result,meta

def original_process_2020(blob):
    conductivity,meta=inspect_2020(blob)
    rows=parse_article(blob,DOI20,PMCS[2])["table"]["rows"]
    if len([r for r in rows if len(r)>=2 and "sinteringcondition" in simple(r[1])])!=1:
        raise ValueError("2020 original process header missing")
    result=[]
    for (name,t,minutes),s in zip(S20,conductivity):
        match=[r for r in rows if len(r)>=2 and simple(r[0])==simple(name)]
        if len(match)!=1 or process_cell(match[0][1])!=(t,minutes) or simple(s[1])!=simple(name):
            raise ValueError("2020 author process and conductivity mismatch")
        result.append((DOI20,name,SERIES2020,t,minutes,float(s[3])))
    return result,meta

def features(rows):
    vals=[]
    for row in rows:
        t,minutes=row[3:5]
        if type(t) not in (int,float) or type(minutes) not in (int,float) or not math.isfinite(t) or not math.isfinite(minutes) or minutes<=0:
            raise ValueError("missing pre-measurement process features")
        vals.append(((t-1150)/100,math.log10(minutes/60)))
    return np.asarray(vals,dtype=float)

def fold(train,test,baselines):
    from sklearn.linear_model import Ridge
    if len(train)!=5 or len(test)!=5 or {r[0] for r in train}!={train[0][0]} or {r[0] for r in test}!={test[0][0]} or train[0][0]==test[0][0]:
        raise ValueError("process fold must be entire original author DOI")
    x=features(train);z=features(test)
    y=np.log10([r[5] for r in train]);truth=np.log10([r[5] for r in test])
    residual=y-baselines[train[0][0]]
    raw=np.repeat(baselines[test[0][0]],5)
    pmean=raw+float(residual.mean())
    pproc=raw+Ridge(alpha=ALPHA,fit_intercept=True).fit(x,residual).predict(z)
    scores={}
    for name,pred in (("O_ONLY_RF",raw),("TRAIN_DOI_MEAN_RESIDUAL",pmean),("TRAIN_DOI_PROCESS_RIDGE",pproc)):
        if not np.isfinite(pred).all():raise ValueError("nonfinite heldout source predictions")
        abstain=float(np.ptp(pred))<1e-9
        choose=None if abstain else int(np.argmax(pred))
        best=int(np.argmax(truth))
        scores[name]={"mae_log10_S_cm":round(float(abs(pred-truth).mean()),8),
                      "top1_abstained":bool(abstain),"top1_selected":None if choose is None else test[choose][1],
                      "top1_correct":None if choose is None else bool(choose==best)}
    return {"train_DOI":train[0][0],"test_DOI":test[0][0],"test_conditions":5,"observed_top1":test[int(np.argmax(truth))][1],"models":scores}

def evaluate(prior,arrays,records,a,b,sn):
    from sklearn.ensemble import RandomForestRegressor
    if (prior["original_upstream_commit"]!=SOURCE_COMMIT or prior["original_source_train_count"]!=478
        or prior["original_official_test_reserved_unread"]!=121 or prior["original_raw_censored_upper_bounds_excluded"]!=29
        or prior["scientific_qualification_authorized"] is not False):
        raise ValueError("publisher TRAIN/TEST boundary changed")
    if len(a)!=5 or len(b)!=5 or len(sn)!=8 or {r[0] for r in a}!={DOI18} or {r[0] for r in b}!={DOI20}:
        raise ValueError("original paper population drift")
    if set(r["manufacturing_route"] for r in sn)!={"DUAL_STEP","MONO_STEP"} or any("temp_C" in r or "time_min" in r for r in sn):
        raise ValueError("unsupported categorical Sn route cannot be numeric imputed")
    rows=[(r[0],r[1],r[2],r[5]) for r in a+b]
    mask,matched,excluded=embargo(records,arrays,rows)
    x=np.asarray(arrays["x"]);y=np.asarray(arrays["y"])
    if x.shape!=(449,118) or y.shape!=(449,):raise ValueError("original numeric TRAIN shape changed")
    train=np.array([i for i in np.where(mask)[0] if _family_proxy(x[i])=="O_ONLY"],dtype=int)
    if len(train)<100:raise ValueError("insufficient original nonleaked O_ONLY TRAIN")
    rf=RandomForestRegressor(**RF_PARAMS).fit(x[train],y[train])
    base={}
    for paper in (a,b):
        feat=np.asarray([_composition(r[2])[1] for r in paper])
        if feat.shape!=(5,118) or not np.allclose(feat,feat[0]):
            raise ValueError("heldout paper not one nominal formula")
        predictions=rf.predict(feat)
        if float(np.ptp(predictions))>1e-9:raise ValueError("unexpected composition predictor variation")
        base[paper[0][0]]=float(predictions[0])
    folds=[fold(a,b,base),fold(b,a,base)]
    scores={}
    for m in folds[0]["models"]:
        fs=[f["models"][m] for f in folds]
        scores[m]={"paper_macro_mae":round(float(np.mean([z["mae_log10_S_cm"] for z in fs])),8),
                   "top1_successes":sum(z["top1_correct"] is True for z in fs),
                   "top1_abstentions":sum(z["top1_abstained"] for z in fs)}
    return {"schema_version":SCHEMA,"source_DOIs":[DOI18,DOI20],"paper_groups":2,
            "source_conditions":10,"nominal_formulas":2,"frozen_features":["sintering_C","holding_minutes"],
            "regression_alpha":ALPHA,"original_numeric_TRAIN":449,"original_TEST_unread":121,
            "O_ONLY_TRAIN_after_embargo":len(train),"TRAIN_source_identities_matched":matched,"TRAIN_connected_components_excluded":excluded,
            "folds":folds,"paper_macro":scores,"sn_author_DOI":DOI25,"categorical_sn_route_pairs_abstained":4,
            "no_process_label_leakage":True,"published_labels_previously_exposed":True,"external_blind":False,
            "independent_pellet_source_verified":False,"production_enabled":False,"scientific_GO":False,
            "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
            "next_action":"0192-SOLO-O_ONLY-SOURCE_COMPATIBLE_PROCESS_EVIDENCE"}

def run(checkout:Path,out:Path):
    if out.exists() or checkout.resolve(strict=True) in out.resolve().parents:raise ValueError("unsafe source/output")
    with tempfile.TemporaryDirectory(prefix="rhombus-0191-") as td:
        prior,arrays=run_official_original_oof(checkout.resolve(),Path(td)/"obelix",return_internal=True)
        records,_=build_obelix_benchmark_intake(checkout.resolve(),expected_commit=SOURCE_COMMIT)
        a,ma=original_process_2018(get_jats("PMC9079727"))
        b,mb=original_process_2020(get_jats(PMCS[2]))
        sn,ms=read_author_table(get_jats(PMC25))
        result=evaluate(prior,arrays,records,a,b,sn)
        result["source_JATS_SHA256"]=[ma["original_JATS_SHA256"],mb["xml_SHA256"],ms["original_JATS_SHA256"]]
    out.mkdir(parents=True,exist_ok=False)
    (out/"0191_process_source_transfer.json").write_bytes(_json_bytes(result)+b"\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    d=run(a.original_obelix_checkout,a.output_dir)
    print("0191_REAL_PROCESS_HELDOUT",json.dumps({"macro":d["paper_macro"],"routes_abstained":d["categorical_sn_route_pairs_abstained"],"science_GO":False},sort_keys=True))
