"""0156: match original 0155 two candidate crystal structures to published SI CIF nominal series.

Original published CIF filename nominal x, Rietveld refined x, and paper
measurement x/T/bulk-total are distinct evidence. Never conflate them.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
import zipfile
from scripts.science.obelix_original_si_cif_0155 import (
    download_pinned_publisher_zip, compare_actual_sources,
)
from scripts.science.obelix_figshare_source_0154 import (
    _bounded_json, API_SEARCH, API_DETAIL, MAX_RESULTS,
    EXPECTED_VERIFIED_SHA256, qualified_detail,
)
from scripts.science.obelix_supplementary_source_0154 import (
    PAPER_DOI, MAX_BYTES, ScopedRedirects, checked_url, check_source_pdf,
    check_cif_archive,
)
from scripts.science.obelix_public_manuscript_0153 import (
    _fetch_original_pdf, audit_manuscript,
)

MANUSCRIPT_SHA = "e5fc22ec69db52f403f8776cbcf10e11ed771d6abf69b3c3ac610bb30edfe368"
MATCHES = {
    "0fh": ("fae697cfc24295bd154d1ee4aa9adf45404a431c684fd603b3a0944432834329",
            "b83ea0df0786c4a666c86db92eadcbacc99b6e4436fde30b51c895cbaf6ec2ee"),
    "1dm": ("c0f12d070767f7f71adfa67811c9051422a8fef4d03737cac6468bccbeff15b8",
            "a531223ee2483b89b8ae897b9d6212c0bb65bd206032e008ddf51df1e7a77e47"),
}


def nominal_x(filename: str) -> float:
    name = PurePosixPath(filename).name.casefold()
    if name == "lgp-1.0.cif":
        return 0.0
    match = re.fullmatch(r"lagp-1[.](\d)\.cif", name)
    if match is None:
        raise ValueError("CIF lacks an original explicit nominal-series filename")
    return int(match.group(1))/10.0


def indexed_publisher_cifs(raw: bytes) -> dict:
    check = check_cif_archive(raw)
    if check["source_bytes_sha256"] != EXPECTED_VERIFIED_SHA256["experimental_cif_zip"] or check["cif_member_count"] != 8:
        raise ValueError("original publisher CIF archive changed")
    ids = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for item in z.infolist():
            if not item.filename.casefold().endswith(".cif"):
                continue
            name = PurePosixPath(item.filename).name
            nominal_x(name)
            digest = hashlib.sha256(z.read(item)).hexdigest()
            if digest in ids or name in ids.values():
                raise ValueError("duplicate original CIF identity")
            ids[digest] = name
    if len(ids) != 8:
        raise ValueError("expected eight distinct published original CIF records")
    return ids


def refined_x(formula: str) -> dict:
    from pymatgen.core import Composition
    c = Composition(formula).get_el_amt_dict()
    if set(c) != {"Li","Al","Ge","P","O"} or not c["P"] > 0:
        raise ValueError("published refined CIF does not contain LAGP")
    scale = 3.0/c["P"]
    value = {
        "Al": round(scale*c["Al"],6),
        "Li": round(scale*c["Li"]-1,6),
        "Ge": round(2-scale*c["Ge"],6),
    }
    if any(not 0 <= x <= 2 for x in value.values()):
        raise ValueError("invalid refined LAGP stoichiometry")
    return value


def assign_publisher_nominal_structure_labels(prior: dict, index: dict) -> list:
    if (prior["structure_pair_attempts"] != 16 or
        prior["exact_match_original_TRAIN_rows_reexamined"] != 2 or
        prior["publisher_original_SI_CIF_members_reexamined"] != 8 or
        prior["original_public_TEST_rows_reserved_unread"] != 121 or
        prior["independent_experimental_specimens_verified"] != 0 or
        prior["scientific_GO"] is not False):
        raise ValueError("0155 original source audit unqualified or changed")
    src={r["source_entry_id"]:r for r in prior["source_records"]}
    pub={r["cif_sha256"]:r for r in prior["publisher_CIF_records"]}
    pairs=[q for q in prior["pair_diagnostics"] if q["geometry_equivalent_heuristic"] is True]
    if len(pairs)!=2 or {q["source_train_entry_id"] for q in pairs}!=set(MATCHES):
        raise ValueError("expected two source structure leads, no more")
    output=[]
    for q in sorted(pairs,key=lambda q:q["source_train_entry_id"]):
        id=q["source_train_entry_id"]
        digest=q["publisher_cif_sha256"]
        if (q["source_cif_sha256"],digest)!=MATCHES[id] or digest not in index:
            raise ValueError("original frozen crystal to publisher source identity drift")
        if not q["composition_compatible_0p02_diagnostic"]:
            raise ValueError("geometry matched but chemical identity failed")
        name=index[digest]
        x=nominal_x(name)
        refined=refined_x(pub[digest]["reduced_formula"])
        source_refined=refined_x(src[id]["reduced_formula"])
        output.append({
            "OBELiX_TRAIN_entry":id,"original_source_CIF_sha256":q["source_cif_sha256"],
            "publisher_original_CIF_sha256":digest,"published_SI_CIF_filename":name,
            "CIF_filename_nominal_series_x":x,
            "publisher_Rietveld_refined_x_Al":refined["Al"],
            "publisher_Rietveld_refined_x_Li":refined["Li"],
            "publisher_Rietveld_refined_x_Ge":refined["Ge"],
            "OBELiX_source_refined_x_Al":source_refined["Al"],
            "publisher_refined_minus_nominal_x_Al":round(refined["Al"]-x,6),
            "geometric_fit_evidence":"HEURISTIC_MATCH_ONLY",
            "published_SI_CIF_to_original_OBELiX_STRUCTURE":"SHA_BOUND",
            "original_EXPERIMENTAL_SPECIMEN_PHASE_MATCH":"NOT_ADJUDICATED",
            "original_measured_temperature_K":None,
            "original_measured_bulk_total_conductivity":None,
            "model_eligible_disordered_atomic_positions":False,
        })
    if len({z["published_SI_CIF_filename"] for z in output})!=2:
        raise ValueError("not two independent source CIF filenames")
    return output


def publisher_pdf_bytes() -> bytes:
    found=_bounded_json(API_SEARCH,{"search_for":"Correlating Transport and Structural Properties",
        "resource_doi":PAPER_DOI,"page":1,"page_size":MAX_RESULTS})
    if not isinstance(found,list) or len(found)>MAX_RESULTS:
        raise ValueError("unbounded Figshare search")
    candidates={}
    for item in found:
        if not isinstance(item,dict) or type(item.get("id")) is not int:
            continue
        details=_bounded_json(API_DETAIL+str(item["id"]))
        if not isinstance(details,dict) or str(details.get("resource_doi") or "").casefold()!=PAPER_DOI:
            continue
        for f in qualified_detail(details):
            if f["role"]=="rietveld_si_pdf":
                candidates[(f["url"],f["size"])]=f
    if len(candidates)!=1:
        raise ValueError("ambiguous original SI Rietveld PDF")
    f=next(iter(candidates.values()))
    opener=build_opener(ScopedRedirects())
    with opener.open(Request(f["url"],headers={"Accept":"application/pdf"}),timeout=35) as response:
        if not checked_url(response.geturl()):
            raise ValueError("SI PDF redirected outside source allowlist")
        raw=response.read(MAX_BYTES+1)
    if len(raw)!=f["size"]:
        raise ValueError("original SI PDF byte length changed")
    pdf=check_source_pdf(raw)
    if pdf["source_bytes_sha256"]!=EXPECTED_VERIFIED_SHA256["rietveld_si_pdf"]:
        raise ValueError("published Rietveld source SHA changed")
    return raw


def paper_page_context(raw:bytes,x_values:list[float])->dict:
    from pypdf import PdfReader
    doc=PdfReader(io.BytesIO(raw))
    if not 1<=len(doc.pages)<=80:
        raise ValueError("original PDF exceeds page limit")
    count=0
    tokens={f"1.{int(round(x*10))}":[] for x in x_values}
    methods={key:[] for key in ("impedance","conductivity","neutron","rietveld",
                               "grain_boundary","bulk","temperature")}
    patterns={"impedance":r"impedance","conductivity":r"conductivit",
              "neutron":r"neutron","rietveld":r"rietveld",
              "grain_boundary":r"grain\s+boundar","bulk":r"\bbulk\b",
              "temperature":r"temperature|kelvin"}
    for page_num,page in enumerate(doc.pages,1):
        txt=page.extract_text() or ""
        count+=len(txt)
        if len(txt)>22000 or count>250000:
            raise ValueError("original PDF extraction exceeded text caps")
        flat=" ".join(txt.lower().split())
        for k,p in patterns.items():
            if re.search(p,flat):
                methods[k].append(page_num)
        for t in tokens:
            if re.search(r"(?<!\d)"+re.escape(t)+r"(?!\d)",flat):
                tokens[t].append(page_num)
    return {"sha256":hashlib.sha256(raw).hexdigest(),"pages":len(doc.pages),
            "methods_pages_context_only":methods,
            "unscoped_nominal_digit_pages_not_sample_assignments":tokens,
            "paper_measurement_table_individually_reviewed":False}


def fetch_with_bounded_transient_retries(fetcher, max_attempts=3):
    """Retry socket interruptions only, not HTTP-denied/authenticity failures."""
    if max_attempts != 3:
        raise ValueError("original first-party source retry budget is frozen")
    for attempt in range(max_attempts):
        try:
            return fetcher()
        except HTTPError:
            raise
        except (URLError, ConnectionResetError, TimeoutError) as exc:
            if attempt == max_attempts-1:
                raise
            time.sleep(1+attempt)


def run(checkout:Path)->dict:
    original_zip=download_pinned_publisher_zip()
    previous=compare_actual_sources(checkout,original_zip,official=True)
    linked=assign_publisher_nominal_structure_labels(previous,indexed_publisher_cifs(original_zip))
    manuscript=fetch_with_bounded_transient_retries(_fetch_original_pdf)
    if hashlib.sha256(manuscript).hexdigest()!=MANUSCRIPT_SHA or not audit_manuscript(manuscript)["document_text_DOI_match"]:
        raise ValueError("original public accepted manuscript identity changed")
    si_pdf=fetch_with_bounded_transient_retries(publisher_pdf_bytes)
    series=[r["CIF_filename_nominal_series_x"] for r in linked]
    return {
        "schema_version":"rhombus-0156-original-LAGP-refined-nominal-manuscript-context-v1",
        "source_DOI":PAPER_DOI,
        "original_public_TEST_reserved_unread_count":121,
        "source_TRAIN_nominal_CIF_links":linked,
        "source_TRAIN_nominal_CIF_link_count":len(linked),
        "full_author_accepted_manuscript_page_context":paper_page_context(manuscript,series),
        "firstparty_original_SI_Rietveld_pdf_page_context":paper_page_context(si_pdf,series),
        "original_exact_specimen_phase_sample_links_qualified":0,
        "original_temperature_bulk_total_conductivity_rows_qualified":0,
        "independent_physical_materials_qualified":0,
        "MACE_MD_transport_computed":False,
        "scientific_GO":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "next":"0157-B visually adjudicate full original paper and SI measured per-sample transport claims; reject unsupported matches",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--live-original",action="store_true")
    a=p.parse_args()
    if not a.live_original or a.output_dir.exists():
        p.error("real first-party source and fresh aggregate-only output required")
    result=run(a.original_obelix_checkout)
    a.output_dir.mkdir(parents=True)
    (a.output_dir/"original_0156_nominal_Rietveld_and_paper_context.json").write_text(
        json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("0156_LIVE_NOMINAL_AND_REFINED_ORIGINAL_PUBLISHER_CIF_TO_TRAIN_JOIN")
    print(json.dumps({"links":[[
        x["OBELiX_TRAIN_entry"],x["published_SI_CIF_filename"],
        x["CIF_filename_nominal_series_x"],x["publisher_Rietveld_refined_x_Al"]]
        for x in result["source_TRAIN_nominal_CIF_links"]],
        "si_pdf_pages":result["firstparty_original_SI_Rietveld_pdf_page_context"]["pages"],
        "author_manuscript_pages":result["full_author_accepted_manuscript_page_context"]["pages"],
        "qualified_independent_materials":0,"scientific_GO":False},sort_keys=True))


if __name__=="__main__":
    main()
