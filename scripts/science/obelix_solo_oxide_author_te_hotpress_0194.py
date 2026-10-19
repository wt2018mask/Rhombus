"""0194: original 2023 Te garnet 25 C author hot-press source and OOD gate.

One first-party DOI, six chemical series, 18 reference conditions. No
out-of-range extrapolation of conventional-sintering process predictor.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import unicodedata
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
# Serialize a diagnostic JSON without importing the heavy OBELiX / pymatgen stack.

SCHEMA="rhombus-0194-new-author-te-hotpress-25c-v1"
DOI="10.1002/cssc.202300399"
PUBLISHER="https://chemistry-europe.onlinelibrary.wiley.com/doi/"+DOI
SERIES=("Te0.1","Te0.25","Te0.375","Te0.5","Al-LLZO","Ta-LLZO")
TEMPS=(600,650,700)
# Original ChemSusChem 2023 author Table 2: S/cm at 25 C, frozen.
AUTHOR=(
 (1.21e-5,2.95e-5,1.61e-5,2.33e-5,3.88e-8,2.64e-7),
 (1.76e-5,4.64e-5,3.27e-5,4.24e-5,1.04e-7,2.29e-6),
 (1.45e-5,5.15e-5,4.66e-5,4.83e-5,3.05e-7,6.70e-6),
)

def simplify(s):
    s=unicodedata.normalize("NFKC",s)
    for x in ("−","–","—","‑"):s=s.replace(x,"-")
    return re.sub(r"\s+","",s).lower()

def conductivity(s):
    s=simplify(s).replace(",",".").replace("×","x").replace("⋅","x")
    m=re.fullmatch(r"(\d+(?:\.\d+)?)[x*]10\^?\(?-(0?[1-9]\d?)\)?",s)
    if m is None:raise ValueError("invalid author scientific notation S/cm")
    v=float(m[1])*10**(-int(m[2]))
    if not math.isfinite(v) or not 0<v<1:raise ValueError("nonphysical author value")
    return v

def temp(s):
    m=re.fullmatch(r"(600|650|700)c",simplify(s).replace("°",""))
    if m is None:raise ValueError("unknown hot-pressing source temperature")
    return int(m[1])

def original_html(blob):
    if not isinstance(blob,bytes) or not 20<len(blob)<=4_000_000:
        raise ValueError("source HTML invalid or too large")
    soup=BeautifulSoup(blob,"html.parser")
    text=soup.get_text(" ",strip=True)
    meta=" ".join(str(x.get("content","")) for x in soup.find_all("meta"))
    full=simplify(text+" "+meta)
    if simplify(DOI) not in full or not all(x in full for x in ("campanella","zhu","girard")):
        raise ValueError("not publisher's first-party 2023 DOI and authors")
    if "totalionicconductivity" not in full or "hot-press" not in text.lower():
        raise ValueError("total ion conductivity or hot-pressing method missing")
    matching=[]
    for table in soup.find_all("table"):
        desc=simplify(table.get_text(" ",strip=True))
        if not all(simplify(x) in desc for x in SERIES):continue
        if "25" not in desc or not ("σ" in desc or "conductivity" in desc):
            continue
        if "mscm" in desc:raise ValueError("milli siemens unit not allowed")
        readings=[]
        for tr in table.find_all("tr"):
            cells=tr.find_all(["td","th"],recursive=False)
            cells=[c.get_text(" ",strip=True) for c in cells]
            if not cells:continue
            try: t=temp(cells[0])
            except ValueError:continue
            if len(cells)!=7:raise ValueError("author row truncated or mislabeled")
            readings.append((t,tuple(conductivity(s) for s in cells[1:])))
        if readings:matching.append(readings)
    if len(matching)!=1 or len(matching[0])!=3:
        raise ValueError("source Table2 duplicate, missing or unsupported")
    rows=sorted(matching[0],key=lambda r:r[0])
    if tuple(r[0] for r in rows)!=TEMPS:raise ValueError("original source temperatures differ")
    for i,(_,vals) in enumerate(rows):
        for j,v in enumerate(vals):
            if not math.isclose(v,AUTHOR[i][j],rel_tol=1e-8,abs_tol=1e-15):
                raise ValueError("original Table2 value or S/cm unit mutated")
    return {"rows":rows,"sha256":hashlib.sha256(blob).hexdigest()}

def evaluate(author):
    rows=author["rows"]
    if tuple(r[0] for r in rows)!=TEMPS:raise ValueError("invalid source ordering")
    out=[]
    for j,name in enumerate(SERIES):
        vals=[float(r[1][j]) for r in rows]
        idx=max(range(3),key=lambda i:vals[i])
        out.append({"series":name,"25C_TOTAL_S_cm":vals,"hotpress_temp_C":list(TEMPS),
                    "best_source_temp_C":TEMPS[idx],"always_hottest_correct":idx==2,
                    "nonmonotonic_vs_700C":idx<2,
                    "best_over_700_ratio":round(vals[idx]/vals[2],8)})
    exceptions=[x for x in out if x["nonmonotonic_vs_700C"]]
    if len(exceptions)!=1 or exceptions[0]["series"]!="Te0.1":
        raise ValueError("source nonmonotonic cohort changed")
    return {"schema_version":SCHEMA,"doi":DOI,"first_party_html_sha256":author["sha256"],
            "author_original_DOI_count":1,"author_conditions":18,
            "nominal_series_count":6,"author_reported_target_temperature_C":25,
            "EIS_measured_in_range_C":"20 to 80",
            "single_directly_measured_25C_EIS_label_unattested":True,
            "author_process":"HOT_PRESS_56_MPA",
            "rows":out,"always_hottest_successes":sum(x["always_hottest_correct"] for x in out),
            "always_hottest_failures":len(exceptions),
            "nonmonotonic_series":[x["series"] for x in exceptions],
            "original_0191_conventional_process_train_temp_C":[1100,1220],
            "0191_process_model_compatible":False,
            "0191_model_route_abstentions":6,
            "new_original_DOI_evidence":1,"new_independent_papers":1,
            "source_truth_previously_public":True,
            "prospective_blind":False,"model_choice_outperformance_proven":False,
            "production_enabled":False,"scientific_GO":False,
            "original_OBELiX_official_TEST_121_unread":True,
            "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
            "next_action":"0195-SOLO-O_ONLY-SAME_PROCESS_NEW_AUTHOR_TRAIN_SOURCE"}

def fetch_publisher():
    errors=[]
    for url in (PUBLISHER,"https://onlinelibrary.wiley.com/doi/full/"+DOI):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=35) as r:
                blob=r.read(4_000_001)
            return original_html(blob)
        except Exception as exc:
            errors.append(type(exc).__name__+":"+str(exc)[:120])
    raise ValueError("publisher original HTML inaccessible; no evidence promotion: "+"; ".join(errors))

def run(output,source_html=None):
    output=Path(output)
    if output.exists():raise ValueError("cannot overwrite science artifact")
    parsed=original_html(Path(source_html).read_bytes()) if source_html else fetch_publisher()
    result=evaluate(parsed)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")+b"\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--original-html",type=Path)
    a=p.parse_args()
    d=run(a.output,a.original_html)
    print("0194_ORIGINAL_NEW_HOT_PRESS_SOURCE",json.dumps({"author_conditions":d["author_conditions"],
        "hotter_correct":d["always_hottest_successes"],"nonmonotonic":d["nonmonotonic_series"],
        "OOD_model_abstentions":d["0191_model_route_abstentions"],
        "scientific_GO":d["scientific_GO"]},sort_keys=True))
