"""0166-B: an ACTUAL different first-party paper's tabulated ionic bulk resistance.

Source: Kraft et al. JACS 2018 DOI 10.1021/jacs.8b10282, original author
supplementary PDF from University of Bath, Table S17 (PDF page 20).
Non-redistribution: no source table, raw measurements, or formula values in
committed artifacts. Analyze longitudinal bulk R(T) with sample thickness
census and repeated 298 K row consistency; DO NOT call R Ohms = sigma S/cm,
a same-pellet match, or the two 298 rows independent experimental replicates.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import tempfile
from urllib.request import Request,urlopen
from urllib.parse import urlsplit

import numpy as np
def _json_bytes(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")

SCHEMA="rhombus-0166-B-kraft-actual-published-impedance-tabulation-v1"
DOI="10.1021/jacs.8b10282"
ORIGINAL_SI_URL="https://purehost.bath.ac.uk/ws/files/187666868/Supporting_Information.pdf"
ALLOWED_HOSTS=frozenset({"purehost.bath.ac.uk"})
EXPECTED_SOURCE_SHA256=None # first authentic primary-source run must pin actual byte SHA
MAX_PDF_BYTES=2_000_000
MAX_PAGE_CHARS=26000
EXPECTED_COMPOSITIONS=(.10,.15,.20,.25,.30,.40,.50,.60,.70,.80)
EXPECTED_T=(253,263,268,273,283,293,298,303,313,323,333,298)
K_B_EV_PER_K=8.617333262145e-5
NUMBER=r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
FILENAME="source_Kraft_TableS17_bulk_R_T_diagnostic_0166.json"


def retrieve_original() -> bytes:
    p=urlsplit(ORIGINAL_SI_URL)
    if p.scheme!="https" or p.hostname not in ALLOWED_HOSTS or p.username or p.password:
        raise ValueError("not the original source institutional HTTPS route")
    req=Request(ORIGINAL_SI_URL,headers={"Accept":"application/pdf","User-Agent":"Rhombus-0166-original-published-scientific-table/1.0"})
    with urlopen(req,timeout=35) as resp:
        if urlsplit(resp.geturl()).hostname not in ALLOWED_HOSTS:
            raise ValueError("original SI redirect exited pinned institutional origin")
        announced=resp.headers.get("Content-Length")
        if announced is not None and int(announced)>MAX_PDF_BYTES:
            raise ValueError("source accepted SI PDF exceeds bound")
        raw=resp.read(MAX_PDF_BYTES+1)
    if not raw.startswith(b"%PDF-") or not 1000<len(raw)<=MAX_PDF_BYTES:
        raise ValueError("not bounded authentic source supplementary PDF")
    return raw


def read_original_page(source:bytes,*,strict_sha=EXPECTED_SOURCE_SHA256)->str:
    from pypdf import PdfReader
    if not isinstance(source,bytes) or not source.startswith(b"%PDF-") or len(source)>MAX_PDF_BYTES:
        raise ValueError("non-PDF or oversized original source")
    digest=hashlib.sha256(source).hexdigest()
    if strict_sha is not None and digest!=strict_sha:
        raise ValueError("pinned original source SHA256 changed")
    pdf=PdfReader(io.BytesIO(source))
    if len(pdf.pages)!=23:
        raise ValueError("original author supplemental PDF page count drift")
    text=pdf.pages[19].extract_text() or ""
    if len(text)>MAX_PAGE_CHARS or not re.search(r"Table\s+S\s*17",text,re.I):
        raise ValueError("actual source Table S17 not on expected page 20")
    if "bulk" not in text.casefold() or "resistan" not in text.casefold():
        raise ValueError("original source does not identify resistance physical quantity")
    if not re.search(r"quasi\s*[- ]?\s*capacitance",text,re.I):
        raise ValueError("source quasi capacitance measurement caveat disappeared")
    return text


def _matching_line(text:str,pattern:str)->list[str]:
    x=[v for v in text.splitlines() if re.search(pattern,v,re.I)]
    if not x:
        # PDF pypdf sometimes text-wraps table lines; fail closed rather than
        # invent original numbers from approximate chart or nearby prose.
        raise ValueError("missing physical source Table S17 row: "+pattern)
    return x


def extract_table_s17(page_text:str)->dict:
    if not isinstance(page_text,str) or len(page_text)>MAX_PAGE_CHARS:
        raise ValueError("unbounded Table S17 text")
    pos=re.search(r"Table\s+S\s*17",page_text,re.I)
    if pos is None:
        raise ValueError("source table signature missing")
    page=page_text[pos.start():]
    if "Quasi-Capacitances" not in page:
        raise ValueError("source physical conductivity table section boundary missing")
    fit=page.split("Quasi-Capacitances",1)[0]
    x_rows=_matching_line(fit,r"Li\s*6\s*\+\s*x|Li6\+x")
    thickness_rows=_matching_line(fit,r"thickness\s+d")
    if len(x_rows)!=1 or len(thickness_rows)!=1:
        raise ValueError("source composition or geometry header ambiguous")
    def tail_floats(row:str)->list[float]:
        return [float(v) for v in re.findall(NUMBER,row)]
    xs=tail_floats(x_rows[0].split("I",1)[-1]) if "S5I" in x_rows[0] else tail_floats(x_rows[0])[-10:]
    ds=tail_floats(thickness_rows[0].split("cm",1)[-1])
    if len(xs)!=10 or len(ds)!=10 or any(abs(x-y)>1e-9 for x,y in zip(xs,EXPECTED_COMPOSITIONS)):
        raise ValueError("published original 10 composition/10 thickness columns drift")
    if any(not 0.05<=d<=1.0 for d in ds):
        raise ValueError("original published specimen thickness outside valid cm range")
    seen=[]
    for line in fit.splitlines():
        strip=line.strip()
        m=re.match(r"^([23]\d{2})\s+(.+)$",strip)
        if not m:continue
        temp=int(m.group(1))
        if temp not in EXPECTED_T:
            continue
        values=tail_floats(m.group(2))
        if len(values)!=10 or any(not math.isfinite(z) or not 0<z<1e8 for z in values):
            raise ValueError("invalid original source Rbulk Ohms row")
        seen.append((temp,values))
    if tuple(t for t,_ in seen)!=EXPECTED_T:
        raise ValueError("original Table S17 temperature row census/order drift")
    if len(set(seen[0][1]))<3:
        raise ValueError("physical series rows uninformative")
    return {"nominal_x":xs,"thickness_cm":ds,"temperature_K":list(EXPECTED_T),
            "bulk_resistances_ohm":[v for _,v in seen]}


def physical_bulk_resistance_diagnostic(table:dict)->dict:
    t=table["temperature_K"];r=table["bulk_resistances_ohm"]
    if t!=list(EXPECTED_T) or len(r)!=12 or any(len(line)!=10 for line in r):
        raise ValueError("actual source table columns/temperatures changed")
    t_inv=np.array([1./z for z in t[:-1]],dtype=float)
    slopes=[];r2=[];repeat=[]
    for col in range(10):
        vals=np.array([float(row[col]) for row in r[:-1]],dtype=float)
        if np.any(vals<=0) or not np.all(np.isfinite(vals)):
            raise ValueError("original R_bulk must be positive finite ohms")
        y=np.log(vals)
        fit=np.polyfit(t_inv,y,1)
        pred=np.polyval(fit,t_inv)
        var=float(np.sum((y-float(y.mean()))**2))
        score=1-float(np.sum((y-pred)**2))/var if var>0 else float("nan")
        ea=float(fit[0])*K_B_EV_PER_K
        if not 0<ea<2 or not -0.5<score<=1:
            raise ValueError("original Arrhenius diagnostic physically implausible")
        slopes.append(ea);r2.append(score)
        first=float(r[6][col]);second=float(r[11][col])
        if min(first,second)<=0:raise ValueError("invalid repeated original 298 K resistance")
        repeat.append(200*abs(first-second)/(first+second))
    return {
      "original_distinct_nominal_compositions":10,
      "nominal_temperature_rows":12,
      "unique_temperatures_K":11,
      "duplicate_298K_Rbulk_records":10,
      "raw_source_fit_resistance_values_read_NOT_REPUBLISHED":120,
      "source_original_thickness_column_values_read":10,
      "298K_two_table_rows_R_relative_differences_pct": {
          "median":round(float(np.median(repeat)),5),
          "maximum":round(float(max(repeat)),5),
          "minimum":round(float(min(repeat)),5),
      },
      "Arrhenius_bulk_R_only_activation_Ea_eV_DIAGNOSTIC": {
          "median":round(float(np.median(slopes)),6),
          "range_min":round(float(min(slopes)),6),
          "range_max":round(float(max(slopes)),6),
          "median_logR_fit_R2":round(float(np.median(r2)),6),
      },
      "repeat_298K_rows_not_proven_independent_pellets":True,
      "exact_measurement_pellet_roster_UNVERIFIED":True,
      "higher_nominal_x_bulk_fitting_reported_unresolved_in_SI":True,
      "R_bulk_ohm_NOT_S_per_cm":True,
      "inverse_R_or_bulk_R_direct_solid_ionic_conductivity_certified":False,
      "electrode_area_for_each_original_table_column_verified":False,
      "correlated_phase_and_crystal_to_measured_pellet_verified":False,
      "individual_true_sample_labels_qualified":0,
    }


def run_original()->dict:
    original=retrieve_original()
    doc=read_original_page(original)
    tab=extract_table_s17(doc)
    phys=physical_bulk_resistance_diagnostic(tab)
    return {
      "schema_version":SCHEMA,
      "DOI":DOI,"source_institutional_host":"purehost.bath.ac.uk",
      "source_original_SI_SHA256":hashlib.sha256(original).hexdigest(),
      "source_original_SI_bytes":len(original),"source_original_SI_pages":23,
      "source_TableS17_pdf_page_one_based":20,
      "source_metadata_notes":{"original_author_source_printing":"Table S17 from original Supporting Information",
          "separate_neutron_diffraction_tables_original_x_and_phase_present":True,
          "original_298K_duplicate_measured_pellet_identity":"NOT_ATTESTED"},
      "quantitative_physical_bulk_R_temperature_evidence":phys,
      "original_source_table_rows_republished":False,
      "source_original_pdf_or_numerical_table_uploaded":False,
      "new_independent_blind":False,"transport_MD_executed":False,
      "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
      "scientific_GO":False,
    }


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--output-dir",type=Path,required=True)
    a=arg.parse_args()
    out=a.output_dir.resolve()
    if out.exists():arg.error("new source-only report path required")
    report=run_original()
    out.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix=".rhombus-0166-",dir=out.parent))
    try:
        (temp/FILENAME).write_bytes(_json_bytes(report)+b"\n")
        temp.rename(out)
    finally:
        if temp.exists():shutil.rmtree(temp)
    print("0166_KRAFT_REAL_PUBLISHED_SI_TABLE_S17_120_ORIGINAL_BULK_R_MEASUREMENTS_ANALYZED")
    print(json.dumps(report,sort_keys=True))


if __name__=="__main__":
    main()
