"""0166-B: extract an ACTUAL open-access primary paper numeric conductivity table.

Scientific scope is six sample-*processing* conditions in a 2019 paper,
not six independently discovered materials, not six neutron-CIF-matched pellets,
not sealed blind; do not train/tune RF on this exploratory public source.

Primary source: original publisher deposited JATS XML mirrored at Europe PMC,
DOI 10.1039/C9RA00949C, PMCID PMC9064144.
The actual table includes 25 C sigma (mS/cm), activation E (kJ/mol) and
HEAT-TREATMENT temperatures (C), which are NOT measurement temperatures.
No paper text, raw XML, plots, original table reproduction, or source values
from other publication material are committed to Rhombus.
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
from urllib.parse import urlparse
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET


SCHEMA="rhombus-0166-real-primary-table-process-condition-transport-v1"
ORIGINAL_DOI="10.1039/c9ra00949c"
SOURCE_PMCID="PMC9064144"
SOURCE_URL="https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9064144/fullTextXML"
NCBI_EFETCH_URL="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=9064144&rettype=xml"
MAX_BYTES=12_000_000
EXPECTED_PROCESS_T_C=[150,200,300,400,500,550]
EXPECTED_SIGMA_MSCM=[0.19,0.20,0.53,1.49,1.23,1.94]
EXPECTED_EA_KJMOL=[42.3,40.3,38.3,31.2,27.7,34.9]
_SOURCE_COLUMNS=3


def fetch_original_public_jats()->tuple[bytes,str]:
    """Try two exact official archived FULL-TEXT JATS sources, no arbitrary mirrors.

    EBI may return transient 503; NCBI E-utilities eFetch is an independent
    official PMC route to the deposited XML, not an independent experimental
    source. Provenance reports exactly which archive delivered original XML.
    """
    errors=[]
    for url in (SOURCE_URL,NCBI_EFETCH_URL):
        p=urlparse(url)
        if url==SOURCE_URL:
            approved=(p.scheme,p.hostname,p.path)==(
                "https","www.ebi.ac.uk",
                "/europepmc/webservices/rest/PMC9064144/fullTextXML")
        else:
            approved=(p.scheme,p.hostname,p.path,p.query)==(
                "https","eutils.ncbi.nlm.nih.gov",
                "/entrez/eutils/efetch.fcgi",
                "db=pmc&id=9064144&rettype=xml")
        if not approved:
            raise ValueError("original article archive host/path/ID changed")
        for attempt in range(2):
            try:
                request=Request(url,headers={
                   "User-Agent":"Rhombus-scientific-primary-public-source/0166",
                   "Accept":"application/xml,text/xml"})
                with urlopen(request,timeout=30) as response:
                    final=urlparse(response.geturl())
                    if final.scheme!=p.scheme or final.hostname!=p.hostname or final.path!=p.path:
                        raise ValueError("unexpected primary scientific archive redirect")
                    data=response.read(MAX_BYTES+1)
                if not data or len(data)>MAX_BYTES:
                    raise ValueError("original publication fulltext XML size invalid")
                # Some archives return HTTP 200 with a human-facing HTML
                # interstitial, which is NOT the requested JATS XML.
                # Detect before treating it as a valid scientific source;
                # try the independent official PMC eFetch route instead.
                prefix=data[:2500].lstrip()
                if (re.search(br"<!DOCTYPE\\s+html\\b|<html(?:\\s|>)",prefix,re.I)
                    or not (prefix.startswith(b"<?xml") or prefix.startswith(b"<article") or prefix.startswith(b"<!DOCTYPE article"))):
                    raise ValueError("official archive returned HTML/interstitial instead of original JATS")
                return data,url
            except (OSError,ValueError) as err:
                errors.append(type(err).__name__)
    raise ValueError("original deposited JATS primary source currently not retrievable from either approved archive: "+
                     ",".join(errors))


def clean(x)->str:
    return " ".join("".join(x.itertext()).split()) if isinstance(x,ET.Element) else ""


def numbers(values:list[str],*,expected:list[float],field:str)->list[float]:
    if len(values)!=len(expected):
        raise ValueError(f"{field}: missing/extra independent processing conditions")
    out=[]
    for s in values:
        # Numeric cells only; does not permit inequalities, ±, arbitrary extra
        # text, exponent lost to a digitized graph or Unicode dash ambiguity.
        text=s.strip().replace("\u2212","-")
        if not re.fullmatch(r"[+]?(?:[0-9]+(?:[.][0-9]+)?|[.][0-9]+)(?:[eE][+-]?[0-9]+)?",text):
            raise ValueError(f"{field}: source field not a definite numeric point")
        val=float(text)
        if not math.isfinite(val) or val<=0:
            raise ValueError(f"{field}: invalid experimental positive")
        out.append(val)
    if any(not math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9)
           for a,b in zip(out,expected)):
        raise ValueError(f"{field}: upstream original 2019 numeric table row drift")
    return out


def extract_table(raw:bytes)->dict:
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES or not raw:
        raise ValueError("invalid or oversized primary XML")
    # NCBI original JATS XML conventionally declares an EXTERNAL DTD.
    # ElementTree does not resolve external entities. Permit only a bounded
    # standard article-level external DOCTYPE, never internal definitions,
    # unknown roots, arbitrary entity substitution or any repeated DOCTYPE.
    if re.search(br"<!ENTITY",raw,re.I):
        raise ValueError("custom XML entities forbidden in publisher XML")
    doctype_count=len(re.findall(br"<!DOCTYPE",raw,re.I))
    # NCBI/JATS DTD public identifier syntax differs between deposited DTD
    # versions. No custom ENTITY allowed, no unknown DOCTYPE root, and
    # stdlib ElementTree never dereferences external DTD references.
    if doctype_count>1 or (doctype_count and
        not re.search(br"<!DOCTYPE\s+article\b",raw,re.I)):
        raise ValueError("unsafe or nonstandard publisher XML DTD declaration")
    root=ET.fromstring(raw)
    if root.tag!="article":
        raise ValueError("expected original JATS article root")
    ids=[clean(el).lower() for el in root.findall(".//article-id")
         if el.get("pub-id-type")=="doi"]
    if ORIGINAL_DOI not in ids:
        raise ValueError("paper DOI missing from original JATS front matter")
    title=" ".join(clean(x) for x in root.findall(".//article-title")).lower()
    if "quantitative analysis of crystallinity" not in title or "argyrodite" not in title:
        raise ValueError("original primary scientific publication title mismatch")
    candidates=[]
    for tw in root.findall(".//table-wrap"):
        caption=" ".join(clean(x) for x in tw.findall("./caption"))
        normalized=caption.casefold()
        if "conductivit" not in normalized or "activation energ" not in normalized:
            continue
        tables=tw.findall("./table")
        if len(tables)!=1:
            raise ValueError("original table wrap ambiguous")
        rows=[]
        # JATS table may put rows directly or inside thead/tbody.
        for tr in tables[0].findall(".//tr"):
            cells=[clean(cell) for cell in tr if cell.tag in ("td","th")]
            if cells:
                rows.append(cells)
        candidates.append((caption,rows))
    if len(candidates)!=1:
        raise ValueError("source original conductivity/activation energy table unavailable or ambiguous")
    caption,rows=candidates[0]
    lower=caption.casefold()
    if "720" not in lower or "mpa" not in lower:
        raise ValueError("source 720 MPa compact pressing method not in actual table caption")
    if len(rows)!=_SOURCE_COLUMNS or any(len(row)!=7 for row in rows):
        raise ValueError("original table not the expected three 6-condition rows")
    headers=[" ".join(re.findall(r"[a-z]+",r[0].casefold())) for r in rows]
    if (not ("ht" in headers[0] or "heat" in headers[0])
       or "conductivit" not in headers[1] or "activation" not in headers[2]):
        raise ValueError("table row measurement/processing type drift")
    if "25" not in rows[1][0] or not any(x in rows[1][0].lower() for x in ("ms","mS","ms cm")):
        raise ValueError("conductivity at 25 C in mS/cm not verified")
    if not ("kj" in rows[2][0].casefold() or "kj" in caption.casefold()):
        raise ValueError("activation energy kJ/mol unit not verified")
    temp=numbers(rows[0][1:],expected=EXPECTED_PROCESS_T_C,field="heat_treatment_C")
    sigma=numbers(rows[1][1:],expected=EXPECTED_SIGMA_MSCM,field="observed_25C_sigma_mS_per_cm")
    ea=numbers(rows[2][1:],expected=EXPECTED_EA_KJMOL,field="activation_energy_kJ_per_mol")
    # These are paper-original reported real numbers, not target model
    # performance: the source's values are independently inspectable.
    points=[]
    for i,(t,v,energy) in enumerate(zip(temp,sigma,ea)):
        points.append({
            "source_condition_index":i+1,
            "heat_treatment_C_not_measurement_temperature":int(t),
            "original_measurement_temperature_C":25,
            "source_ionic_conductivity_mS_per_cm":v,
            "normalized_ionic_conductivity_S_per_cm":round(v/1000,9),
            "source_activation_energy_kJ_per_mol":energy,
            "green_compact_pressing_MPa":720,
            "individual_sample_identifier_verified":False,
            "crystal_phase_to_exact_pellet_and_CIF_verified":False,
            "sample_bulk_total_definition_verified":False,
            "independently_blind_material":False,
            "admitted_as_material_level_transport_truth":False,
        })
    return {
        "schema_version":SCHEMA,
        "source_DOI":ORIGINAL_DOI,
        "source_PMCID":SOURCE_PMCID,
        "source_original_public_JATS_URL":SOURCE_URL,
        "original_public_jats_sha256":hashlib.sha256(raw).hexdigest(),
        "original_source_publisher_deposited_XML":True,
        "table_caption_has_green_compact_720_MPa":True,
        "experiment_observation_unit":"HEAT_TREATMENT_PROCESS_CONDITION_OF_Li6PS5Br_MATERIAL",
        "conductivity_temperature_C":25,
        "heat_treatment_temperature_IS_NOT_measurement_temperature":True,
        "six_original_public_process_condition_points":points,
        "actual_quantitative_table_condition_rows":len(points),
        "actual_independent_qualified_materials":0,
        "original_specific_pellet_CIF_physical_join_verified":0,
        "public_source_NOT_external_sealed_blind":True,
        "not_automatically_comparable_to_OBELIX_MLIP_single_CIF":True,
        "new_physical_MLIP_MD_executed":False,
        "scientific_GO":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--live-original",action="store_true")
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    if not a.live_original:
        p.error("real publisher-deposited original JATS source opt-in required")
    out=a.output_dir.resolve()
    if out.exists():
        p.error("fresh evidence destination required")
    xml_bytes,actual_archive_url=fetch_original_public_jats()
    result=extract_table(xml_bytes)
    result["source_original_public_JATS_URL"]=actual_archive_url
    result["archive_used_exact_DOI_JATS_verified"]=True
    out.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix=".rhombus-0166-",dir=out.parent))
    try:
        (staging/"original_public_sulfide_condition_table_0166.json").write_bytes(
            json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")+b"\n")
        if out.exists():raise ValueError("source evidence output already exists")
        staging.rename(out)
    finally:
        if staging.exists():shutil.rmtree(staging)
    print("0166_REAL_ORIGINAL_PUBLIC_NUMERIC_SULFIDE_CONDITION_TABLE_EXTRACTED")
    print(json.dumps({
        "source_DOI":result["source_DOI"],
        "measured_condition_rows":result["actual_quantitative_table_condition_rows"],
        "independent_verified_materials":0,"scientific_GO":False},sort_keys=True))


if __name__=="__main__":main()
