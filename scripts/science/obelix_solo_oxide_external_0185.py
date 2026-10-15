"""0185 SOLO O_ONLY original LLZO external compilation diagnostic; not physical GO."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,math,re,subprocess,tempfile
from collections import Counter
from pathlib import Path
import numpy as np
from rhombus.qualification.obelix_benchmark_intake import SOURCE_COMMIT,build_obelix_benchmark_intake,_json_bytes
from scripts.science.obelix_real_grouped_oof_0146 import _composition,run_official_original_oof
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_solo_family_specialists_0184 import source_scores,paired_group_delta,RIDGE_ALPHA

EXT_COMMIT="e65ac023b0613185666ad492cedce79a86633614"
EXT_BLOB="5293f717aebcc2c1396db335f9ac2a250d5567eb"
EXPECTED_EXTERNAL_ROWS=176
MODELS=("POOLED_RF","O_ONLY_RF","O_ONLY_RIDGE","O_ONLY_TRAIN_MEAN")
SITE=(("li_sto","li_dop_sto","li_dopant","Li"),("la_sto","la_dop_sto","la_dopant","La"),("zr_sto","zr_dop_sto","zr_dopant","Zr"))
FIELDS=("source","li_sto","la_sto","zr_sto","li_dop_sto","la_dop_sto","zr_dop_sto","li_dopant","la_dopant","zr_dopant","conductivity","log_cond")

def git_blob(b):
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def doi(s):
    s=str(s or "").strip().lower()
    for p in ("https://doi.org/","http://dx.doi.org/","doi:"):
        if s.startswith(p):s=s[len(p):]
    return s if re.fullmatch(r"10\.\d{4,9}/[^\s,;]{1,180}",s) else ""

def source_formula(row):
    from pymatgen.core.periodic_table import Element
    species={"O":12.}
    for bk,dk,ek,base in SITE:
        a=float(row[bk]); d=float(row[dk])
        if not all(math.isfinite(v) and 0<=v<=24 for v in (a,d)): raise ValueError("invalid stoichiometry")
        species[base]=species.get(base,0.)+a
        if d:
            el=str(row[ek]).strip().capitalize()
            if not re.fullmatch(r"[A-Z][a-z]?",el):raise ValueError("missing dopant identity")
            try:Element(el)
            except (KeyError,ValueError) as exc:raise ValueError("bad element") from exc
            species[el]=species.get(el,0.)+d
    if not 4<=sum(v for e,v in species.items() if e!="O")<=15:raise ValueError("bad total")
    parsed=_composition("".join(f"{e}{v:.10g}" for e,v in sorted(species.items()) if v>0))
    if parsed is None: raise ValueError("unparseable formula")
    if _family_proxy(parsed[1])!="O_ONLY":raise ValueError("NON_O_ONLY")
    return parsed

def original_train_signatures(records):
    ds=set(); fs=set(); n=0;reserved=0
    for row in records:
        split=row.get("official_split")
        if split=="TEST":
            reserved+=1
            continue # DO NOT read any other TEST field
        if split!="TRAIN":raise ValueError("unexpected publisher split")
        n+=1
        for v in row.get("reference_dois",[]):
            t=doi(v)
            if not t:raise ValueError("malformed original DOI")
            ds.add(t)
        p=_composition(row.get("reported_composition"))
        if p is not None:fs.add(p[0])
    if (n,reserved)!=(478,121):raise ValueError("official source boundary drift")
    return ds,fs

def intake_external(blob,train_dois,train_formulas,*,pinned=True):
    if not isinstance(blob,bytes) or not 0<len(blob)<=100000:raise ValueError("external byte limit")
    if pinned and git_blob(blob)!=EXT_BLOB:raise ValueError("pinned Git source bytes mismatch")
    reader=csv.DictReader(io.StringIO(blob.decode("utf-8-sig")))
    if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames):raise ValueError("wrong external CSV headers")
    good=[];fail=Counter();n=0
    for row in reader:
        if all(not (v or "").strip() for v in row.values()):continue
        n+=1
        if n>1000:raise ValueError("external source unbounded")
        d=doi(row["source"])
        if not d:fail["INVALID_DOI"]+=1;continue
        try:
            f,x=source_formula(row)
        except (ValueError,TypeError):
            fail["INVALID_OR_NON_O_ONLY_FORMULA"]+=1;continue
        if d in train_dois:fail["OVERLAP_ORIGINAL_TRAIN_DOI"]+=1;continue
        if f in train_formulas:fail["OVERLAP_ORIGINAL_TRAIN_FORMULA"]+=1;continue
        try:sig=float(row["conductivity"]);ly=float(row["log_cond"])
        except (ValueError,TypeError):fail["NONNUMERIC"]+=1;continue
        if not math.isfinite(sig) or not 0<sig<=1 or not math.isfinite(ly):
            fail["NONPOSITIVE_OR_NONFINITE"]+=1;continue
        if abs(math.log10(sig)-ly)>.02:fail["SOURCE_LOG_MISMATCH"]+=1;continue
        good.append((d,f,x,math.log10(sig)))
    if pinned and n!=EXPECTED_EXTERNAL_ROWS:raise ValueError("original external nonblank record drift")
    if sum(fail.values())+len(good)!=n:raise ValueError("incomplete excluded source accounting")
    parent=list(range(len(good))); seen={}
    def root(i):
        while i!=parent[i]:
            parent[i]=parent[parent[i]]
            i=parent[i]
        return i
    def union(a,b):
        a,b=root(a),root(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    for i,(d,f,_,_) in enumerate(good):
        for key in ("DOI:"+d,"FORMULA:"+f):
            if key in seen:union(i,seen[key])
            else:seen[key]=i
    groups=tuple("g"+str(root(i)) for i in range(len(good)))
    return {
        "nonempty":n,"eligible":len(good),"connected_groups":len(set(groups)),"excluded":dict(sorted(fail.items())),
        "x":np.asarray([g[2] for g in good],dtype=float).reshape(-1,118),
        "y":np.asarray([g[3] for g in good],dtype=float),
        "groups":groups,
    }

def experiment(prior,arrays,records,external):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if prior["original_upstream_commit"]!=SOURCE_COMMIT or prior["original_source_train_count"]!=478 or prior["original_official_test_reserved_unread"]!=121 or prior["original_raw_censored_upper_bounds_excluded"]!=29 or prior["scientific_qualification_authorized"] is not False:
        raise ValueError("original TRAIN protection drift")
    x=np.asarray(arrays["x"]);y=np.asarray(arrays["y"])
    if x.shape!=(449,118) or y.shape!=(449,) or len(set(arrays["groups"]))!=102:raise ValueError("original source mismatch")
    ids=np.asarray([i for i,v in enumerate(x) if _family_proxy(v)=="O_ONLY"],dtype=int)
    if len(ids)!=307:raise ValueError("O_ONLY training drift")
    # All models frozen and fitted BEFORE external source outcomes are accessed.
    models={
        "POOLED_RF":RandomForestRegressor(**RF_PARAMS).fit(x,y),
        "O_ONLY_RF":RandomForestRegressor(**RF_PARAMS).fit(x[ids],y[ids]),
        "O_ONLY_RIDGE":make_pipeline(StandardScaler(),Ridge(alpha=RIDGE_ALPHA)).fit(x[ids],y[ids]),
    }
    mean=float(np.mean(y[ids]))
    train_dois,train_formulas=original_train_signatures(records)
    other=intake_external(external,train_dois,train_formulas)
    report={
        "schema":"rhombus-0185-solo-oxide-real-external-source-v1",
        "original_OBELIX_commit":SOURCE_COMMIT,"original_TRAIN_rows":478,
        "original_TRAIN_numeric":449,"original_O_ONLY_TRAIN":307,
        "original_official_TEST_reserved_UNREAD":121,"original_TEST_used":False,
        "external_repo":"abd-adhyatma/llzo-improvement","external_commit":EXT_COMMIT,
        "external_git_blob_SHA1":EXT_BLOB,"external_file_SHA256":hashlib.sha256(external).hexdigest(),
        "external_nonempty_rows":other["nonempty"],"external_eligible_rows":other["eligible"],
        "external_connected_source_groups":other["connected_groups"],"external_exclusions":other["excluded"],
        "predeclared_models":list(MODELS),"frozen_RF_hyperparameters":dict(RF_PARAMS),
        "no_external_training_or_tuning":True,
        "external_older_secondary_compilation_not_new_chronological_blind":True,
        "external_source_labels_already_publicly_exposed":True,
        "external_uncontrolled_measurement_temperature":True,"external_bulk_total_unspecified":True,
        "external_formula_implicitly_assumes_O12":True,"possible_OBELIX_TEST_overlap_not_inspected":True,
        "trained_source_DOI_and_exact_formula_overlap_excluded":True,
        "qualified_individual_physical_pellets":0,"O_ONLY_production_router_enabled":False,
        "physical_P0_01":"BLOCKED","physical_P0_02":"BLOCKED","physical_P0_03":"BLOCKED",
        "scientific_GO":False,"scores":None,
        "status":"BLOCKED_TOO_FEW_NONOVERLAPPING_SOURCE_GROUPS",
    }
    if other["eligible"]>=10 and other["connected_groups"]>=5:
        xe,ye,groups=other["x"],other["y"],other["groups"]
        predictions={k:m.predict(xe) for k,m in models.items()}
        predictions["O_ONLY_TRAIN_MEAN"]=np.full(len(ye),mean)
        report["scores"]={
            "metrics":{k:source_scores(ye,v,groups) for k,v in predictions.items()},
            "specialist_minus_pooled":paired_group_delta(ye,predictions["O_ONLY_RF"],predictions["POOLED_RF"],groups),
            "specialist_minus_train_mean":paired_group_delta(ye,predictions["O_ONLY_RF"],predictions["O_ONLY_TRAIN_MEAN"],groups),
        }
        report["status"]="REAL_SOURCE_EXPLORATORY_NUMERICAL_DIAGNOSTIC_NOT_QUALIFIED"
    return report

def run(obelix,external,output):
    if output.exists():raise ValueError("report output must be a new directory")
    obelix,external=obelix.resolve(strict=True),external.resolve(strict=True)
    if obelix==external or obelix in output.resolve().parents or external in output.resolve().parents:
        raise ValueError("source output overlap")
    if subprocess.check_output(["git","-C",str(external),"rev-parse","HEAD"],text=True).strip()!=EXT_COMMIT:
        raise ValueError("unfrozen external source HEAD")
    source=external/"llzo_dataset_clean.csv"
    if source.is_symlink() or not source.is_file():raise ValueError("source file missing or symlink")
    with tempfile.TemporaryDirectory(prefix="rhombus-0185-") as work:
        prior,arrays=run_official_original_oof(obelix,Path(work)/"obelix",return_internal=True)
        records,_=build_obelix_benchmark_intake(obelix,expected_commit=SOURCE_COMMIT)
        receipt=experiment(prior,arrays,records,source.read_bytes())
    output.mkdir(parents=True,exist_ok=False)
    (output/"0185_external_oxide_source_diagnostic.json").write_bytes(_json_bytes(receipt)+b"\n")
    return receipt

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--original-obelix-checkout",required=True,type=Path)
    parser.add_argument("--external-llzo-checkout",required=True,type=Path)
    parser.add_argument("--output-dir",required=True,type=Path)
    opt=parser.parse_args()
    result=run(opt.original_obelix_checkout,opt.external_llzo_checkout,opt.output_dir)
    print("0185_REAL_O_ONLY_EXTERNAL_DIAGNOSTIC",json.dumps({
        "status":result["status"],"external_rows":result["external_nonempty_rows"],
        "eligible":result["external_eligible_rows"],"groups":result["external_connected_source_groups"],
        "exclusions":result["external_exclusions"],
        "scores":result["scores"]["metrics"] if result["scores"] else None,
        "physical_GO":False},sort_keys=True))
