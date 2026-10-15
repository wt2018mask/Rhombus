"""0178: actual original Zenodo LiOPA XRD/EIS worksheet cell-label audit.

Reads public author-deposited supporting XLSX source *after* independent
publisher MD5 + observed 0177 full SHA-256. Does not execute formulas,
calculate new conductivity, or infer pellet identity from labels.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import posixpath
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from scripts.science.independent_lab_original_workbooks_0177 import (
    API, SOURCES, parse_record, stream_pinned_file, inspect_workbook,
    no_duplicate_pairs, MAX_API,
)
from urllib.request import Request,urlopen

SCHEMA="rhombus-0178-original-eis-xrd-worksheet-label-provenance-v1"
SOURCE="Supporting Information - LiOPA.xlsx"
SOURCE_SHA256="22640fa76a00d90626cfe8fc2f3d4fc20ee71c3f87aba865f064960f1e3cd05e"
TARGETS=("XRD S3","EIS S5","EIS humidity test S5","XRD & FTIR humid test S6")
NS="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL="{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG="{http://schemas.openxmlformats.org/package/2006/relationships}"
MAX_STRINGS=160_000
MAX_SHARED_BYTES=100_000_000
MAX_SHEET_BYTES=400_000_000
MAX_ROWS=96
MAX_COLUMNS=64
MAX_LABELS=32
MAX_TEXT=110


def _safe_rel_target(target:str) -> str:
    if not isinstance(target,str) or not target or "://" in target or "\\" in target:
        raise ValueError("external/invalid worksheet relation")
    if target.startswith("/"):
        out=posixpath.normpath(target).lstrip("/")
    else:
        out=posixpath.normpath(posixpath.join("xl",target))
    if not out.startswith("xl/worksheets/") or not out.endswith(".xml"):
        raise ValueError("unexpected source sheet path target")
    return out


def parse_source_sheet_paths(z:ZipFile) -> dict[str,str]:
    workbook=ET.fromstring(z.read("xl/workbook.xml"))
    relroot=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    if workbook.tag!=NS+"workbook" or relroot.tag!=PKG+"Relationships":
        raise ValueError("wrong original OOXML workbook relations")
    rels={}
    for node in relroot:
        ident=node.attrib.get("Id")
        if ident in rels:raise ValueError("duplicate original OOXML relationship ID")
        if node.attrib.get("Type","").endswith("/worksheet"):
            if node.attrib.get("TargetMode")=="External":
                raise ValueError("external workbook worksheet relation")
            rels[ident]=_safe_rel_target(node.attrib.get("Target"))
    sheets=workbook.find(NS+"sheets")
    if sheets is None:raise ValueError("no source book sheets")
    mapping={}
    for n in sheets:
        if n.tag!=NS+"sheet":continue
        title=n.attrib.get("name")
        rid=n.attrib.get(REL+"id")
        if title in mapping or rid not in rels:
            raise ValueError("ambiguous or unresolved source sheet path")
        mapping[title]=rels[rid]
    if not all(s in mapping for s in TARGETS):
        raise ValueError("four actual original XRD/EIS named source sheets not all present")
    if not all(name in z.namelist() for name in (mapping[s] for s in TARGETS)):
        raise ValueError("target worksheet XML absent")
    return {s:mapping[s] for s in TARGETS}


def parse_shared_strings(z:ZipFile) -> list[str]:
    name="xl/sharedStrings.xml"
    if name not in z.namelist():return []
    if z.getinfo(name).file_size>MAX_SHARED_BYTES:
        raise ValueError("unbounded original shared-string dictionary")
    items=[]
    with z.open(name) as stream:
        for event,node in ET.iterparse(stream,events=("end",)):
            if node.tag!=NS+"si":continue
            chunks=[n.text or "" for n in node.iter() if n.tag==NS+"t"]
            val="".join(chunks)
            if len(val)>4096:val=val[:4096]
            items.append(val)
            if len(items)>MAX_STRINGS:
                raise ValueError("unbounded source strings")
            node.clear()
    return items


def _cell_text(cell,strings:list[str]) -> str | None:
    typ=cell.get("t")
    if typ=="s":
        v=cell.find(NS+"v")
        if v is None or not (v.text or "").isdigit():
            raise ValueError("invalid shared string index")
        idx=int(v.text)
        if idx>=len(strings):raise ValueError("unresolved shared string index")
        return strings[idx]
    if typ=="inlineStr":
        part=cell.find(NS+"is")
        return None if part is None else "".join(x.text or "" for x in part.iter() if x.tag==NS+"t")
    if typ in ("str","e"):
        v=cell.find(NS+"v")
        return None if v is None else v.text
    # Numeric & formulas are not read or evaluated for identity evidence.
    return None


def _label(raw:str) -> str | None:
    clean=re.sub(r"\s+"," ",raw).strip()
    if len(clean)>MAX_TEXT:clean=clean[:MAX_TEXT]
    if not clean or not re.search(r"[A-Za-z]",clean):return None
    if "@" in clean or clean.lower().startswith(("https:","http:")):return None
    if re.fullmatch(r"[-+0-9.,eE\s]+",clean):return None
    return clean


def first_text_rows(z:ZipFile,path:str,shared:list[str]) -> dict:
    if z.getinfo(path).file_size>MAX_SHEET_BYTES:
        raise ValueError("excessive published worksheet source XML size")
    by_row=[]
    reached=False
    with z.open(path) as stream:
        for event,node in ET.iterparse(stream,events=("end",)):
            if node.tag!=NS+"row":continue
            index=node.attrib.get("r")
            if not index or not index.isdigit():
                raise ValueError("invalid original worksheet row index")
            ix=int(index)
            if ix>MAX_ROWS:
                reached=True
                break
            cells=node.findall(NS+"c")
            if len(cells)>100_000:raise ValueError("maliciously overwide original row")
            labels=[]
            for cell in cells:
                ref=cell.get("r","")
                match=re.match(r"^([A-Z]{1,3})(\d+)$",ref)
                if not match:continue
                number=0
                for ch in match.group(1):number=number*26+ord(ch)-64
                if number>MAX_COLUMNS:continue
                raw=_cell_text(cell,shared)
                if raw is None:continue
                label=_label(raw)
                if label and len(labels)<MAX_LABELS:
                    labels.append({"cell":ref,"label":label})
            if labels:by_row.append({"row":ix,"texts":labels})
            node.clear()
    return {"scanned_first_rows_up_to":MAX_ROWS,
            "last_row_scan_cutoff_encountered":reached,
            "text_row_count":len(by_row),
            "public_literal_text_rows":by_row[:MAX_ROWS],
            "all_source_numeric_measurement_values_read":False,
            "sheet_formulae_executed":False}


def evaluate_original_labels(source_sha:str,sheet_data:dict) -> dict:
    if source_sha!=SOURCE_SHA256 or set(sheet_data)!=set(TARGETS):
        raise ValueError("original author workbook identity or target sheet set drift")
    for k,v in sheet_data.items():
        if not isinstance(v,dict) or not isinstance(v.get("public_literal_text_rows"),list):
            raise ValueError("unverified raw worksheet result")
    all_labels={}
    for sheet,p in sheet_data.items():
        all_labels[sheet]=set(
            text["label"].strip().lower()
            for row in p["public_literal_text_rows"] for text in row["texts"]
            if len(text["label"].strip())>=4)
    xrd=all_labels["XRD S3"]|all_labels["XRD & FTIR humid test S6"]
    eis=all_labels["EIS S5"]|all_labels["EIS humidity test S5"]
    overlap=sorted((xrd & eis))[:50]
    return {
        "schema_version":SCHEMA,
        "original_source_DOI":"10.5281/zenodo.17816356",
        "original_supporting_workbook_SHA256_independently_rehashed":source_sha,
        "public_source_workbook":"Supporting Information - LiOPA.xlsx",
        "actual_source_XRD_EIS_sheets_inspected":list(TARGETS),
        "actual_original_worksheet_text_rows":sheet_data,
        "exact_identical_literal_texts_across_XRD_and_EIS":overlap,
        "overlapping_labels_are_NOT_same_physical_pellet_authentication":True,
        "same_physical_pellet_structure_EIS_traceable_source_ID_certified":False,
        "same_pellet_geometry_temperature_resistance_CIF_verified":False,
        "legally_independent_prospective_blind_steward_recruited":False,
        "new_authenticated_individual_physical_materials":0,
        "public_original_spreadsheet_not_sealed_blind":True,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_GO":False,
        "next_action":"0179-P0-03 seek lab-confirmed individual-pellet structural EIS sample bridge; verify original raw measurement semantics",
    }


def source_execute():
    with urlopen(Request(API,headers={
        "Accept":"application/json",
        "User-Agent":"Rhombus-0178-cell-level-source-data-science-audit"}),timeout=40) as resp:
        if resp.status!=200:raise ValueError("pinned Zenodo API unavailable")
        raw=resp.read(MAX_API+1)
    if not raw or len(raw)>MAX_API:raise ValueError("published record metadata exceeds limit")
    record=json.loads(raw,object_pairs_hook=no_duplicate_pairs)
    manifest=parse_record(record)
    asset=next(x for x in manifest if x["name"]==SOURCE)
    with tempfile.TemporaryDirectory(prefix="rhombus-0178-original-") as work:
        src=Path(work)/"actual-first-party-supporting.xlsx"
        observed=stream_pinned_file(asset,src)
        if observed["independently_computed_SHA256"]!=SOURCE_SHA256:
            raise ValueError("observed author original supporting-data byte SHA256 drift")
        # 0177 prior admission bounded real workbook identity. Check again.
        inv=inspect_workbook(src)
        if inv["sheet_count"]!=17 or not all(s in inv["public_sheet_names"] for s in TARGETS):
            raise ValueError("source publisher worksheet layout mismatch")
        with ZipFile(src) as z:
            mapping=parse_source_sheet_paths(z)
            shared=parse_shared_strings(z)
            sheets={s:first_text_rows(z,mapping[s],shared) for s in TARGETS}
    return evaluate_original_labels(SOURCE_SHA256,sheets)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--live-original-cells",action="store_true")
    ap.add_argument("--output-dir",type=Path,required=True)
    a=ap.parse_args()
    if not a.live_original_cells:ap.error("requires actual new original publisher XLSX scan")
    target=a.output_dir.resolve()
    if target.exists() or target.is_symlink():ap.error("new output directory required")
    r=source_execute()
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".rhombus-0178-out-",dir=target.parent))
    try:
        (stage/"real_original_eis_xrd_labels_0178.json").write_text(
            json.dumps(r,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n",encoding="utf-8")
        if target.exists():raise ValueError("race while saving scientific provenance")
        stage.rename(target)
    finally:
        if stage.exists():shutil.rmtree(stage)
    print("0178_ACTUAL_XRD_EIS_WORKSHEET_TEXT_EVIDENCE_NO_FALSE_PELLET_PASS")
    print(json.dumps({
        "sheets":list(r["actual_original_worksheet_text_rows"]),
        "rows":{k:v["text_row_count"] for k,v in r["actual_original_worksheet_text_rows"].items()},
        "overlap_labels":r["exact_identical_literal_texts_across_XRD_and_EIS"][:15],
        "physical_pellets":r["new_authenticated_individual_physical_materials"],
        "scientific_GO":False},sort_keys=True))


if __name__=="__main__":
    main()
