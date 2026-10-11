"""0162-B: actual LAGP experiment TARGET versus crystallographic STRUCTURE scope.

A successful CIF↔publisher fit does not establish a matching experimentally
measured specimen/phase/temperature/bulk or total ionic conductivity.
This experiment measures the disagreement/ambiguity instead of fabricating
new materials or repeatedly optimizing RF on PUBLIC TRAIN.
Original publisher manuscript and SI are downloaded transiently, exact
SHA pinned, and NO PDF prose/CIF/raw source rows are republished.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import tempfile

from rhombus.qualification.obelix_benchmark_intake import (
    SOURCE_COMMIT, _json_bytes, build_obelix_benchmark_intake,
)
from scripts.science.obelix_original_si_cif_0155 import (
    compare_actual_sources, download_pinned_publisher_zip,
)
from scripts.science.obelix_lagp_nominal_series_0156 import (
    assign_publisher_nominal_structure_labels, indexed_publisher_cifs,
    fetch_with_bounded_transient_retries, _fetch_original_pdf, publisher_pdf_bytes,
    paper_page_context, MANUSCRIPT_SHA,
)
from scripts.science.obelix_public_manuscript_0153 import audit_manuscript
from scripts.science.obelix_figshare_source_0154 import EXPECTED_VERIFIED_SHA256
from scripts.science.obelix_supplementary_source_0154 import PAPER_DOI

SCHEMA="rhombus-0162-real-LAGP-physical-target-transport-method-and-measurement-gap-v1"
IDS={"0fh":0.2,"1dm":0.6}
MEASUREMENT_SCOPE="ROOM_TEMPERATURE_EXACT_K_UNSPECIFIED"


def paper_transport_method_audit(raw:bytes, *, pdf_hash=MANUSCRIPT_SHA) -> dict:
    """Real manuscript per-page *method type* audit, never 'specimen verified'.

    Every reported page number can be independently reviewed against pinned
    original PDF. Textual context cannot authenticate a numerical plot point.
    """
    from pypdf import PdfReader
    if not isinstance(raw,bytes) or hashlib.sha256(raw).hexdigest()!=pdf_hash:
        raise ValueError("author primary paper exact SHA mismatch")
    reader=PdfReader(io.BytesIO(raw))
    if len(reader.pages)!=26:
        raise ValueError("unexpected original accepted manuscript length")
    selectors={
        "impedance_spectroscopy":r"impedance\s+spectroscop|impedance\s+measur",
        "bulk_conduction":r"\bbulk\s+(?:conductivit|resistan|ion)",
        "grain_boundary":r"grain\s+boundar",
        "reciprocal_resistance":r"reciprocal\s+(?:of\s+)?(?:the\s+)?resistan|inverse\s+(?:of\s+)?(?:the\s+)?resistan",
        "not_equivalent_to_conductivity":r"(?:instead\s+of|rather\s+than)\s+(?:the\s+)?conductivit",
        "nominal_lagp_1p2":r"\bli\s*1[.]2\s*al\s*0[.]2",
        "nominal_lagp_1p6":r"\bli\s*1[.]6\s*al\s*0[.]6",
        "figure_six":r"\bfig(?:ure)?[. ]*\s*6\b",
        "temperature_25C":r"\b25\s*(?:°|º|deg(?:rees)?)?\s*c\b",
        "resistance_unit":r"(?:k|m)?\s*ohm|[ΩΩ]",
        "conductivity_unit":r"s\s*cm\s*[-−]\s*1|s\s*/\s*cm|s\s*cm",
    }
    contexts={key:[] for key in selectors}
    page_chars=0
    page_results=[]
    for n,page in enumerate(reader.pages,1):
        rawtext=page.extract_text() or ""
        if len(rawtext)>22000:
            raise ValueError("paper page unbounded extraction")
        page_chars+=len(rawtext)
        if page_chars>250000:
            raise ValueError("paper text budget exceeded")
        text=" ".join(rawtext.lower().split())
        present=[key for key,pat in selectors.items() if re.search(pat,text)]
        for key in present:
            contexts[key].append(n)
        if {"impedance_spectroscopy","grain_boundary"}<=set(present):
            page_results.append({"page":n,
                "impedance_and_boundary_method_same_page":True,
                "same_page_includes_bulk":bool("bulk_conduction" in present),
                "sample_specific_numeric_conductivity_join":False})
    return {
        "source_sha256":hashlib.sha256(raw).hexdigest(),
        "paper_pages":len(reader.pages),"bounded_extracted_chars":page_chars,
        "transport_method_indicator_pages":contexts,
        "impedance_and_grain_boundary_same_page":page_results,
        "reciprocal_resistance_must_not_be_silently_converted_to_sigma":True,
        "graph_or_page_cooccurrence_is_not_sample_specific_measurement":True,
        "full_experimental_figure_numeric_data_independently_digitized":False,
        "definite_temperature_bulk_total_sample_label_links":0,
    }


def audited_original_TRAIN_target_rows(source_rows:list, links:list)->dict:
    if not isinstance(source_rows,list) or len(source_rows)!=599:
        raise ValueError("original pinned 599 total source census changed")
    if {a["OBELiX_TRAIN_entry"] for a in links}!=set(IDS) or len(links)!=2:
        raise ValueError("original two source-CIF to publisher provenance joins changed")
    # Original inherited intake may parse TEST internally. Here we constrain
    # target row use to the TWO official TRAIN IDs; do not claim the inherited
    # generic intake never parses the official TEST partition.
    rows={r["source_entry_id"]:r for r in source_rows
          if r.get("official_split")=="TRAIN" and r.get("source_entry_id") in IDS}
    if len(rows)!=2:
        raise ValueError("original paper target rows unavailable in TRAIN")
    out=[]
    observed={}
    for link in sorted(links,key=lambda x:x["OBELiX_TRAIN_entry"]):
        rid=link["OBELiX_TRAIN_entry"]
        row=rows[rid]
        if row["source_snapshot_commit"]!=SOURCE_COMMIT or
            row["reference_dois"]!=[PAPER_DOI] or
            row["reported_ionic_conductivity_unit"]!="S/cm" or
            row["measurement_kind"]!="PROCESSED_REPORTED_POINT" or
            row["reported_temperature_scope"]!=MEASUREMENT_SCOPE or
            row["source_cif_match_status"]!="Match" or
            row["cif_content_sha256"]!=link["original_source_CIF_sha256"] or
            row["qualified_transport_truth"] is not False:
            raise ValueError("source TRAIN conductivity/structure record drift or false truth")
        try:
            raw=Decimal(row["reported_ionic_conductivity_text"])
        except (InvalidOperation,TypeError) as exc:
            raise ValueError("original source processed numeric label is invalid") from exc
        if not raw.is_finite() or raw<=0:
            raise ValueError("original source paper source label not positive")
        measured=float(raw)
        if not math.isfinite(measured):
            raise ValueError("bad source conductivity magnitude")
        observed[rid]=math.log10(measured)
        out.append({
            "original_TRAIN_entry":rid,
            "publisher_original_CIF_sha256":link["publisher_original_CIF_sha256"],
            "original_source_CIF_sha256":link["original_source_CIF_sha256"],
            "original_publisher_nominal_x":link["CIF_filename_nominal_series_x"],
            "original_publisher_refined_Al_x":link["publisher_Rietveld_refined_x_Al"],
            "source_label_kind":"OBELIX_PROCESSED_REPORTED_POINT",
            "source_label_unit":"S/cm",
            "source_nominal_temperature":"ROOM_TEMPERATURE_EXACT_K_UNSPECIFIED",
            "source_paper_DOI_bound":True,
            "same_physical_experimental_pellet_as_CIF_verified":False,
            "bulk_or_total_measurement_identity_verified":False,
            "exact_temperature_K_verified":False,
            "independently_qualified_transport_truth":False,
            "ready_for_finite_T_MD_experimental_qualification":False,
        })
    return {
        "source_label_ratio_log10_x0p6_minus_x0p2":round(observed["1dm"]-observed["0fh"],8),
        "processed_source_pair_reported_trend":(
          "HIGHER_AT_NOMINAL_0P6" if observed["1dm"]>observed["0fh"] else
          "LOWER_AT_NOMINAL_0P6" if observed["1dm"]<observed["0fh"] else "SAME"),
        "the_ratio_is_NOT_a_matched_specimen_transport_effect":True,
        "two_original_TRAIN_literature_source_records":out,
    }


def build_live_report(checkout:Path)->dict:
    # Re-verify structure pairs against actual first-party original CIF ZIP;
    # reuse exactly frozen 0155/0156 source verification, no arbitrary CIF join.
    root=Path(checkout).resolve(strict=True)
    rawzip=download_pinned_publisher_zip()
    structs=compare_actual_sources(root,rawzip,official=True)
    links=assign_publisher_nominal_structure_labels(
        structs,indexed_publisher_cifs(rawzip))
    source_rows,_=build_obelix_benchmark_intake(root,expected_commit=SOURCE_COMMIT)
    pair=audited_original_TRAIN_target_rows(source_rows,links)
    original_pdf=fetch_with_bounded_transient_retries(_fetch_original_pdf)
    if hashlib.sha256(original_pdf).hexdigest()!=MANUSCRIPT_SHA or not audit_manuscript(original_pdf)["document_text_DOI_match"]:
        raise ValueError("pinned original accepted manuscript identity changed")
    si_pdf=fetch_with_bounded_transient_retries(publisher_pdf_bytes)
    if hashlib.sha256(si_pdf).hexdigest()!=EXPECTED_VERIFIED_SHA256["rietveld_si_pdf"]:
        raise ValueError("original Rietveld PDF byte identity drift")
    methods=paper_transport_method_audit(original_pdf)
    supplement=paper_page_context(si_pdf,[0.2,0.6])
    if supplement["pages"]!=15 or supplement["sha256"]!=EXPECTED_VERIFIED_SHA256["rietveld_si_pdf"]:
        raise ValueError("original diffraction SI source scope changed")
    return {
        "schema_version":SCHEMA,"original_publication_DOI":PAPER_DOI,
        "original_OBELIX_pinned_commit":SOURCE_COMMIT,
        "original_source_total_records":599,
        "original_official_TRAIN":478,
        "original_official_TEST_not_used_as_target_or_model_comparator":121,
        "note_legacy_intake_reads_TEST_metadata_so_NOT_strong_unparsed_claim":True,
        "publisher_original_CIF_zip_sha256":hashlib.sha256(rawzip).hexdigest(),
        "author_manuscript_method_scope":methods,
        "Rietveld_SI_pdf_sha256":supplement["sha256"],
        "Rietveld_SI_is_crystallographic_not_specimen_transport_truth":True,
        "source_pair_diagnostics":pair,
        "source_CIF_to_actual_pellet_measurement_qualified":0,
        "original_exact_temperature_bulk_total_conductivity_qualified":0,
        "physically_independent_experimental_materials_qualified":0,
        "MLIP_finite_T_transport_actual_executed":False,
        "scientific_GO":False,"P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--live-original",action="store_true")
    a=p.parse_args()
    out=a.output_dir.resolve()
    if not a.live_original or out.exists():
        p.error("original-source explicit opt-in and fresh output path required")
    d=build_live_report(a.original_obelix_checkout)
    out.parent.mkdir(parents=True,exist_ok=True)
    staged=Path(tempfile.mkdtemp(prefix=".rhombus-0162-source-",dir=out.parent))
    try:
        (staged/"lagp_physical_measurement_target_audit_0162.json").write_bytes(
            _json_bytes(d)+b"\n")
        if out.exists():
            raise ValueError("original source report path collision")
        staged.rename(out)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    print("0162_REAL_EXPERIMENTAL_LABEL_VS_PHYSICAL_MEASUREMENT_TARGET_AUDITED")
    print(json.dumps({
        "source_paper_DOI":PAPER_DOI,
        "processed_TRAIN_label_pair_log10_ratio":d["source_pair_diagnostics"]["source_label_ratio_log10_x0p6_minus_x0p2"],
        "trend":d["source_pair_diagnostics"]["processed_source_pair_reported_trend"],
        "paper_pages_by_method":d["author_manuscript_method_scope"]["transport_method_indicator_pages"],
        "verified_specimen_measurements":0,
        "scientific_GO":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
