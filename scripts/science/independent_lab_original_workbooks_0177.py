"""0177: independently observe actual published experimental source workbooks.

Source is University of Fribourg/Zenodo Li6PS5Cl0.5Br0.5 experimental data
including XRD and EIS. Published XLSX sheet-level metadata is not a same-
physical-pellet diffraction/EIS join or a prospective blind cohort.
Read-only 2 original workbooks; small provenance JSON only is retained.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit, quote
from urllib.request import Request,urlopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

SCHEMA="rhombus-0177-first-party-experimental-xrd-eis-original-workbooks-v1"
RECORD_ID=17816356
API=f"https://zenodo.org/api/records/{RECORD_ID}"
PUBLIC="https://zenodo.org/records/17816356"
SOURCES={
    "Main manuscript Data - LiOPA.xlsx":{"md5":"5d130a457055022b7b582f1473f52314","cap":55_000_000},
    "Supporting Information - LiOPA.xlsx":{"md5":"59d83f67922361c57e89af56901cdd32","cap":41_000_000},
}
MAX_API=256_000
MAX_SHEETS=400
MAX_ZIP_MEMBERS=15000
MAX_UNCOMPRESSED=4_000_000_000
MAX_WORKBOOK_XML=2_000_000
CHUNK=1024*1024


def assert_source_url(url:str, *, data:bool=False) -> None:
    u=urlsplit(url)
    if u.scheme!="https" or u.hostname!="zenodo.org" or u.username or u.password or u.fragment:
        raise ValueError("untrusted original source download host")
    if data:
        if not (u.path.startswith(f"/api/records/{RECORD_ID}/files/") and
                u.path.endswith("/content")):
            raise ValueError("dataset file URL not anchored to original record")
    elif u.path!=f"/api/records/{RECORD_ID}":
        raise ValueError("dataset metadata URL not pinned")


def no_duplicate_pairs(pairs):
    out={}
    for key,val in pairs:
        if key in out:raise ValueError("ambiguous original source JSON field")
        out[key]=val
    return out


def parse_record(meta:dict) -> list[dict]:
    if not isinstance(meta,dict) or meta.get("id")!=RECORD_ID:
        raise ValueError("original published Zenodo dataset record mismatch")
    files=meta.get("files")
    if not isinstance(files,list) or len(files)!=len(SOURCES):
        raise ValueError("original two-workbook manifest missing or drifted")
    found={}
    for entry in files:
        if not isinstance(entry,dict) or not isinstance(entry.get("key"),str):
            raise ValueError("invalid source file identity")
        key=entry["key"]
        if key not in SOURCES or key in found:
            raise ValueError("unknown/duplicated publisher file identity")
        checksum=entry.get("checksum")
        actual_size=entry.get("size")
        # InvenioRDM metadata sometimes omits links.content. Derive the exact\n        # documented pinned-record content endpoint from the verified key.\n        # Any advertised URL must match that endpoint, never an arbitrary host.\n        canonical=f"https://zenodo.org/api/records/{RECORD_ID}/files/{quote(key,safe=\u0027\u0027)}/content"\n        advertised=entry.get("links",{}).get("content")\n        if advertised is not None and advertised!=canonical:\n            raise ValueError("advertised original URL disagrees with pinned record/key")\n        link=canonical
        if (checksum!=f"md5:{SOURCES[key]['md5']}" or
            type(actual_size) is not int or not 1_000_000<=actual_size<=SOURCES[key]["cap"] or
            not isinstance(link,str)):
            raise ValueError(f"publisher file metadata mismatch key={key!r} checksum={checksum!r} size={actual_size!r} url={link!r}")
        assert_source_url(link,data=True)
        found[key]={"name":key,"official_size":actual_size,
                    "original_content_url":link,"published_MD5":SOURCES[key]["md5"]}
    return [found[key] for key in SOURCES]


def classify_title(name:str) -> list[str]:
    low=name.lower()
    out=[]
    if re.search(r"\bxrd\b|diffraction|x-ray|xray",low):out.append("XRD")
    if re.search(r"\beis\b|impedance|conductivity",low):out.append("EIS")
    if re.search(r"\braman\b",low):out.append("RAMAN")
    if re.search(r"\bnmr\b",low):out.append("NMR")
    return out


def inspect_workbook(path:Path) -> dict:
    try:
        with ZipFile(path) as z:
            names=z.namelist()
            if (len(names)>MAX_ZIP_MEMBERS or len(set(names))!=len(names) or
                "xl/workbook.xml" not in names or "[Content_Types].xml" not in names):
                raise ValueError("not bounded original xlsx OOXML file")
            total=0
            for item in z.infolist():
                total+=item.file_size
                if (total>MAX_UNCOMPRESSED or item.flag_bits & 1 or
                    item.filename.startswith("/") or
                    ".." in item.filename.split("/")):
                    raise ValueError("unexpected encrypted or unsafe source workbook")
            if z.getinfo("xl/workbook.xml").file_size>MAX_WORKBOOK_XML:
                raise ValueError("too many workbook metadata bytes")
            raw=z.read("xl/workbook.xml")
    except BadZipFile as err:
        raise ValueError("original source XLSX zip invalid") from err
    try:
        root=ET.fromstring(raw)
    except ET.ParseError as err:
        raise ValueError("malformed original sheet metadata") from err
    ns="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    if root.tag!=ns+"workbook":raise ValueError("not OOXML spreadsheet workbook")
    sheets=root.find(ns+"sheets")
    if sheets is None:raise ValueError("no source workbook sheet manifest")
    found=[x.attrib.get("name") for x in sheets if x.tag==ns+"sheet"]
    if not 1<=len(found)<=MAX_SHEETS or not all(
        isinstance(s,str) and 0<len(s)<=31 for s in found) or len(found)!=len(set(found)):
        raise ValueError("corrupt/oversize original sheet names")
    matched={typ:[s for s in found if typ in classify_title(s)]
             for typ in ("XRD","EIS","RAMAN","NMR")}
    return {"sheet_count":len(found),"public_sheet_names":found,
            "sheet_name_modality_candidates":matched,
            "same_individual_pellet_link_identified_from_sheet_names":False,
            "source_raw_cells_or_specimen_level_identifiers_opened":False,
            "no_sheet_name_cannot_prove_no_data":True}


def stream_pinned_file(asset:dict,dst:Path) -> dict:
    assert_source_url(asset["original_content_url"],data=True)
    h=hashlib.md5()
    sha=hashlib.sha256()
    count=0
    request=Request(asset["original_content_url"],headers={
        "User-Agent":"Rhombus-0177-primary-exp-original-workbook-byte-audit",
        "Accept":"application/octet-stream"})
    with urlopen(request,timeout=80) as r:
        if r.status!=200:raise ValueError("original author deposited workbook not HTTP 200")
        # Zenodo redirects to object storage; never trust the redirect alone:
        # the FULL received content must match the pinned publisher MD5.
        with dst.open("xb") as out:
            while True:
                buf=r.read(CHUNK)
                if not buf:break
                if not isinstance(buf,bytes) or len(buf)>CHUNK:
                    raise ValueError("unbounded source read")
                count+=len(buf)
                if count>asset["official_size"]:raise ValueError("source exceeds publisher size")
                h.update(buf);sha.update(buf);out.write(buf)
    if count!=asset["official_size"] or h.hexdigest()!=asset["published_MD5"]:
        raise ValueError("complete source workbook bytes mismatch official published size/md5")
    return {"observed_full_bytes":count,"observed_MD5":h.hexdigest(),
            "independently_computed_SHA256":sha.hexdigest(),
            "full_source_archive_byte_observation":True}


def execute_actual_original() -> dict:
    assert_source_url(API)
    req=Request(API,headers={"Accept":"application/json",
        "User-Agent":"Rhombus-0177-publisher-record-origin-audit"})
    with urlopen(req,timeout=40) as resp:
        if resp.status!=200:raise ValueError("Zenodo published record API unavailable")
        meta_bytes=resp.read(MAX_API+1)
    if not meta_bytes or len(meta_bytes)>MAX_API:raise ValueError("oversized source record")
    record=json.loads(meta_bytes,object_pairs_hook=no_duplicate_pairs,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    assets=parse_record(record)
    reports=[]
    with tempfile.TemporaryDirectory(prefix="rhombus-0177-") as temp:
        for idx,a in enumerate(assets):
            path=Path(temp)/f"original-{idx}.xlsx"
            observed=stream_pinned_file(a,path)
            found=inspect_workbook(path)
            reports.append({"publisher_file":a["name"],
                            "source_md5":a["published_MD5"],**observed,**found})
    return {"schema_version":SCHEMA,
            "original_dataset_doi":"10.5281/zenodo.17816356",
            "public_source":PUBLIC,
            "independent_new_laboratory":True,
            "nominal_electrolyte":"Li6PS5Cl0.5Br0.5",
            "published_source_contains_XRD_EIS_according_to_description":True,
            "two_full_publisher_spreadsheet_sources_rehashed":len(reports),
            "source_workbook_metadata":reports,
            "original_workbook_bytes_archived":False,
            "public_data_not_prospective_sealed_cohort":True,
            "matched_same_physical_pellet_EIS_XRD_identity_independently_attested":False,
            "raw_EIS_numeric_measurements_per_pellet_verified":False,
            "per_pellet_geometric_area_thickness_and_temperature_verified":False,
            "unique_independent_experimental_materials_certified":0,
            "published_metadata_is_not_original_same_specimen_join":True,
            "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
            "scientific_GO":False,
            "next_action":"0178-P0-03 inspect author dataset sample IDs in bounded worksheets and obtain authentic batch/pellet to XRD/EIS mapping"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--real-deposited-workbooks",action="store_true")
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    if not args.real_deposited_workbooks:p.error("real primary full-source experiment opt-in required")
    out=args.output_dir.resolve()
    if out.exists() or out.is_symlink():p.error("output cannot overwrite another source receipt")
    result=execute_actual_original()
    out.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".rhombus-0177-report-",dir=out.parent))
    try:
        (stage/"actual_experiment_XRD_EIS_workbook_0177.json").write_text(
            json.dumps(result,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n",
            encoding="utf-8")
        if out.exists():raise ValueError("report race")
        stage.rename(out)
    finally:
        if stage.exists():shutil.rmtree(stage)
    print("0177_TWO_REAL_PRIMARY_XRD_EIS_DATA_WORKBOOKS_SHA256_OBSERVED_PASS")
    print(json.dumps({"workbooks":len(result["source_workbook_metadata"]),
        "sheets":[x["sheet_count"] for x in result["source_workbook_metadata"]],
        "qualified_physical_samples":0,"scientific_GO":False},sort_keys=True))


if __name__=="__main__":
    main()
