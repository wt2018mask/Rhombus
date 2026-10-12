"""0165-B: First-party LAGP Figure 7 *quantitative extraction readiness*.

A source figure caption reporting several specimens' composition-group
mean±SD is not a CSV and not a single-neutron-CIF pellet. Inspect the real
pinned accepted manuscript PDF drawing resources for Figure 7 and distinguish
graphic objects, textual numerical tokens, and genuine calibrated data points.
No axis ticks or raster-pixel estimates are silently promoted to observations.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tempfile

from rhombus.qualification.obelix_benchmark_intake import _json_bytes, SOURCE_COMMIT
from scripts.science.obelix_train_only_transport_0163 import strict_train_physical_targets
from scripts.science.obelix_lagp_figure_population_0164 import inspect_original_paper_figures
from scripts.science.obelix_lagp_nominal_series_0156 import (
    MANUSCRIPT_SHA, _fetch_original_pdf, fetch_with_bounded_transient_retries,
)
from scripts.science.obelix_public_manuscript_0153 import audit_manuscript
from scripts.science.obelix_supplementary_source_0154 import PAPER_DOI

SCHEMA="rhombus-0165-original-LAGP-figure7-numerical-readiness-v1"
PAGES=(15,16,17) # one-based original accepted author PDF
MAX_PAGE_CONTENT=4_000_000
MAX_OPS=160_000
MAX_SOURCE_PDF=15_000_000
TEXT_NUMBER=re.compile(r"(?<![A-Za-z])[-+]?(?:\d+[.]\d+|\d+)(?:[eE][-+]?\d+)?")
GRAPHICS=frozenset(("m","l","c","v","y","h","re","S","s","f","F","f*","B","B*","b","b*"))
COLORS=frozenset(("RG","rg","K","k","G","g","SCN","scn"))


def page_graphics_diagnostic(original_pdf:bytes, *, expected_sha=MANUSCRIPT_SHA)->dict:
    from pypdf import PdfReader
    from pypdf.generic import ContentStream
    if (not isinstance(original_pdf,bytes) or len(original_pdf)>MAX_SOURCE_PDF or
            hashlib.sha256(original_pdf).hexdigest()!=expected_sha):
        raise ValueError("original 0165 accepted manuscript PDF SHA or size drift")
    reader=PdfReader(io.BytesIO(original_pdf))
    if len(reader.pages)!=26:
        raise ValueError("original manuscript number of pages changed")
    out=[]
    for number in PAGES:
        page=reader.pages[number-1]
        raw_content=page.get_contents()
        if raw_content is None:
            raise ValueError("missing Figure6/7 adjacent PDF source content")
        data=raw_content.get_data()
        if len(data)>MAX_PAGE_CONTENT:
            raise ValueError("PDF figure page contents exceed limit")
        stream=ContentStream(raw_content, reader)
        n_ops=len(stream.operations)
        if n_ops>MAX_OPS:
            raise ValueError("PDF figure page graphics operations exceed limit")
        kinds=Counter()
        for _,operator in stream.operations:
            op=operator.decode("ascii") if isinstance(operator,bytes) else str(operator)
            if op in GRAPHICS:kinds["vector_paths"]+=1
            if op in COLORS:kinds["graphics_color_ops"]+=1
            if op=="Do":kinds["xobject_paint_operations"]+=1
            if op in ("Tj","TJ","'","\""):kinds["text_render_operations"]+=1
        resources=page.get("/Resources")
        resources=resources.get_object() if resources else {}
        xrefs=resources.get("/XObject") if resources else {}
        xrefs=xrefs.get_object() if xrefs else {}
        image_objects=0
        form_objects=0
        for _,obj in xrefs.items():
            resolved=obj.get_object()
            subtype=str(resolved.get("/Subtype",""))
            if subtype=="/Image":image_objects+=1
            if subtype=="/Form":form_objects+=1
        text=page.extract_text() or ""
        if len(text)>22000:
            raise ValueError("oversized extracted Figure page text")
        # These are unclassified typography/numeric tokens; NOT digitized points.
        tokens=TEXT_NUMBER.findall(text)
        out.append({
            "pdf_page_one_based":number,
            "source_content_bytes":len(data),"pdf_operations":n_ops,
            "vector_drawing_operations":kinds["vector_paths"],
            "graphics_color_operations":kinds["graphics_color_ops"],
            "xobject_paint_operations":kinds["xobject_paint_operations"],
            "resource_image_xobjects":image_objects,
            "resource_form_xobjects":form_objects,
            "text_render_operations":kinds["text_render_operations"],
            "unclassified_page_number_like_tokens":len(tokens),
            "original_source_data_series_recovered":0,
            "numeric_axis_ticks_are_not_measurement_points":True,
        })
    return {"original_sha256":hashlib.sha256(original_pdf).hexdigest(),
            "original_pages":26,"figure_neighborhood_graphics":out,
            "per_point_figure7_numeric_data_extracted":0,
            "figure7_mean_errorbar_digitization":False,
            "coordinate_axis_calibration_independently_verified":False,
            "underlying_replicate_measurement_table_verified":False}


def decide_population_target(*,graph_axis_calibrated:bool,
                             source_mean_numeric:float|None,
                             source_sd_numeric:float|None,
                             replicate_count:int|None,
                             bulk_total_defined:bool,
                             individual_pellet_ids_verified:bool)->dict:
    """A numerical series needs calibration, uncertainty and population unit.

    Even perfect group summaries are never individual physical pellet labels.
    """
    vals=(source_mean_numeric,source_sd_numeric)
    if any(v is not None and (type(v) not in (float,int) or
                               not __import__("math").isfinite(v) or v<0)
           for v in vals):
        raise ValueError("invalid inferred numerical figure value")
    if replicate_count is not None and (type(replicate_count) is not int or replicate_count<2):
        raise ValueError("Figure 7 reports multiple experimental samples per group")
    qualified_group=bool(graph_axis_calibrated and
                         source_mean_numeric is not None and
                         source_sd_numeric is not None and
                         replicate_count is not None and bulk_total_defined)
    blockers=[]
    if not graph_axis_calibrated:blockers.append("FIGURE7_AXIS_GRAPH_NOT_CALIBRATED")
    if source_mean_numeric is None:blockers.append("SOURCE_MEAN_VALUE_NOT_DIGITIZED")
    if source_sd_numeric is None:blockers.append("SOURCE_SD_ERROR_BAR_NOT_DIGITIZED")
    if replicate_count is None:blockers.append("EXACT_INDEPENDENT_PELLET_N_UNKNOWN")
    if not bulk_total_defined:blockers.append("ORIGINAL_BULK_VS_TOTAL_NUMERICAL_POINT_UNMAPPED")
    if not individual_pellet_ids_verified:blockers.append("INDIVIDUAL_PELLET_IDENTITIES_UNVERIFIED")
    blockers.append("INDIVIDUAL_CIF_TO_PELLET_EXPERIMENTAL_IDENTITY_UNVERIFIED")
    return {"observation_unit":"NOMINAL_COMPOSITION_PELLET_GROUP_MEAN_SD",
            "group_summary_numerically_ready":qualified_group,
            "individual_pellet_truth_ready":False,
            "independent_blind_qualified":False,"blockers":blockers}


def build_original_source_report(checkout:Path)->dict:
    p=Path(checkout).resolve(strict=True)
    source=strict_train_physical_targets(p)
    if source["original_SOURCE_git_commit"]!=SOURCE_COMMIT:
        raise ValueError("original source TRAIN pin changed")
    manuscript=fetch_with_bounded_transient_retries(_fetch_original_pdf)
    if hashlib.sha256(manuscript).hexdigest()!=MANUSCRIPT_SHA or not audit_manuscript(manuscript)["document_text_DOI_match"]:
        raise ValueError("original accepted manuscript author DOI or SHA drift")
    fig=inspect_original_paper_figures(manuscript)
    if (fig["figure7_anchor_pages"]!=[16] or
        fig["figure7_population_word_cue_pages_NOT_a_singular_sample"]!=[17]):
        raise ValueError("Figure 7 caption/replicate/standard-deviation source changed")
    graphics=page_graphics_diagnostic(manuscript)
    eligibility=decide_population_target(
        graph_axis_calibrated=False,source_mean_numeric=None,source_sd_numeric=None,
        replicate_count=None,bulk_total_defined=False,individual_pellet_ids_verified=False)
    return {"schema_version":SCHEMA,"original_DOI":PAPER_DOI,
            "original_OBELIX_TRAIN_pinned_sha":SOURCE_COMMIT,
            "firstparty_accepted_manuscript_pdf_sha":MANUSCRIPT_SHA,
            "original_pdf_figure7_caption_page":17,
            "original_fig7_caption_reported_multiple_samples_with_SD":True,
            "true_original_TRAIN_LAGP_CIF_leads":2,
            "original_figure6_vs_figure7_data_ambiguity_unresolved":True,
            "processed_original_TRAIN_2_CIF_log10_contrast":
                source["processed_source_TRAIN_label_log10_ratio_1dm_minus_0fh"],
            "PDF_graphics_readiness":graphics,
            "physical_experimental_target_eligibility":eligibility,
            "actual_raw_experimental_replicate_count_verified":None,
            "individual_experimental_pellet_truths_qualified":0,
            "actual_group_mean_and_SD_numeric_points_qualified":0,
            "original_TEST_composition_DOI_conductivity_cells_parsed":0,
            "original_mixed_CSV_TEST_raw_bytes_passed_over":True,
            "new_finite_T_MD":False,"scientific_GO":False,
            "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    out=a.output_dir.resolve()
    source=a.original_obelix_checkout.resolve(strict=True)
    if out.exists() or out==source or source in out.parents:
        p.error("fresh output outside original source required")
    report=build_original_source_report(source)
    out.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".rhombus-0165-",dir=out.parent))
    try:
        (stage/"original_figure7_quantitative_readiness_0165.json").write_bytes(_json_bytes(report)+b"\n")
        if out.exists():raise ValueError("output path collision")
        stage.rename(out)
    finally:
        if stage.exists():shutil.rmtree(stage)
    print("0165_REAL_ORIGINAL_PDF_FIGURE7_GRAPHICS_QUANTITATIVE_RETRIEVAL_DIAGNOSTIC_PASS")
    print(json.dumps({
      "pdf_graphics":report["PDF_graphics_readiness"]["figure_neighborhood_graphics"],
      "actual_raw_replicate_count":None,
      "physically_qualified":0,"scientific_GO":False},sort_keys=True))


if __name__=="__main__":
    main()
