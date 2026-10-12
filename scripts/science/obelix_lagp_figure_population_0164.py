"""0164-B: original 2018 LAGP figure MEASUREMENT population/observable audit.

Actual source challenge: Figure 6 documents a representative nominal x=.6
pellet; Arrhenius curves use reciprocal resistance (NOT conductivity).
Figure 7 documents bulk/total room-temperature conductivities averaged
across multiple experimental pellets with standard-deviation uncertainty.

Neither a population summary nor a representative Figure 6 sample can be
promoted as conductivity measured from the exact neutron-refined source CIF
under a single-pellet sample/phase/method/temp identity proof.

Provenance: strict 0163 official TRAIN-only scanner + publisher original
PDF/checksums. Never decode original TEST cells, use model, or emit PDF text.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tempfile

from rhombus.qualification.obelix_benchmark_intake import _json_bytes, SOURCE_COMMIT
from scripts.science.obelix_train_only_transport_0163 import strict_train_physical_targets
from scripts.science.obelix_lagp_nominal_series_0156 import (
    fetch_with_bounded_transient_retries,_fetch_original_pdf, MANUSCRIPT_SHA,
)
from scripts.science.obelix_public_manuscript_0153 import audit_manuscript
from scripts.science.obelix_supplementary_source_0154 import PAPER_DOI

SCHEMA="rhombus-0164-LAGP-real-publisher-figure-population-versus-sample-truth-v1"
MAX_EXTRACTED_CHARS=250000
MAX_PAGE_CHARS=22000
ALLOWED_IDS=frozenset(("0fh","1dm"))
# These only identify PDF text *topics*, never identify a real specimen.
INDICATORS={
    "figure_6_anchor":r"\bfig(?:ure)?[. ]*\s*6\b",
    "figure_7_anchor":r"\bfig(?:ure)?[. ]*\s*7\b",
    "nominal_x0p6":r"\bli\s*1[.]6\s*al\s*0[.]6",
    "temperature_25C":r"\b25\s*(?:°|º|deg(?:rees)?)?\s*c\b",
    "sintered_800C":r"(?:sinter(?:ed|ing)?)(?:.{0,100})\b800\s*(?:°|º|deg(?:rees)?)?\s*c\b",
    "reciprocal_resistance":r"reciprocal\s+(?:of\s+)?(?:the\s+)?resistan",
    "instead_of_conductivity":r"instead\s+of\s+(?:the\s+)?conductivit",
    "population_multiple_samples":r"multiple\s+samples|several\s+(?:different\s+)?samples",
    "population_identical_nominal_composition":r"identical\s+nominal\s+composition",
    "population_average_values":r"average\s+values|averaged\s+(?:values|over|across)",
    "uncertainty_standard_deviation":r"standard\s+deviation|standard\s+deviations",
    "bulk_total_conductivity":r"total\s+(?:ionic\s+)?conductivit|bulk\s+(?:ionic\s+)?conductivit",
    "phase_fraction_decreases":r"phase\s+fraction|side\s+phases",
    "solubility_limit":r"solubility\s+limit",
}


def inspect_original_paper_figures(original_pdf:bytes,*,expected_sha=MANUSCRIPT_SHA)->dict:
    """Bounded source PDF indicator locations; no text extracts in artifact."""
    from pypdf import PdfReader
    if not isinstance(original_pdf,bytes) or hashlib.sha256(original_pdf).hexdigest()!=expected_sha:
        raise ValueError("pinned original publisher author paper SHA changed")
    reader=PdfReader(io.BytesIO(original_pdf))
    if len(reader.pages)!=26:
        raise ValueError("original manuscript page census drift")
    found={k:[] for k in INDICATORS}
    lines=[]
    total=0
    for idx,page in enumerate(reader.pages,1):
        body=page.extract_text() or ""
        if len(body)>MAX_PAGE_CHARS:
            raise ValueError("oversized extracted primary PDF page")
        total+=len(body)
        if total>MAX_EXTRACTED_CHARS:
            raise ValueError("source PDF extraction budget exceeded")
        norm=" ".join(body.casefold().split())
        indicators=[key for key,pattern in INDICATORS.items() if re.search(pattern,norm)]
        for key in indicators:
            found[key].append(idx)
        lines.append(set(indicators))
    # Even when each word is in the paper, mere cross-page occurrence is
    # NOT evidence they belong to the same figure or physical specimen.
    fig6_pages=set(found["figure_6_anchor"])
    fig7_pages=set(found["figure_7_anchor"])
    repeated=set(found["population_multiple_samples"])
    same_nominal=set(found["population_identical_nominal_composition"])
    mean=set(found["population_average_values"])
    std=set(found["uncertainty_standard_deviation"])
    # Page-level primary leads only; a separate review of the figure caption
    # remains necessary to claim a single bound measurement.
    fig7_population_cue_pages=sorted(fig7_pages & (repeated | same_nominal | mean | std))
    fig6_reciprocal_cue_pages=sorted(
        fig6_pages & (set(found["reciprocal_resistance"]) | set(found["instead_of_conductivity"]))
    )
    return {
        "original_manuscript_SHA256":hashlib.sha256(original_pdf).hexdigest(),
        "original_manuscript_pages":26,
        "bounded_PDF_page_indicator_index":found,
        "figure7_population_word_cue_pages_NOT_a_singular_sample":fig7_population_cue_pages,
        "figure6_reciprocal_R_cue_pages_NOT_a_S_per_cm":fig6_reciprocal_cue_pages,
        "original_primary_PDF_words_do_NOT_digitize_any_figure":True,
        "original_replicate_count_NOT_published_here":None,
        "uncertainty_numeric_SD_NOT_digitized":True,
        "exact_per_sample_figure7_sigma_S_per_cm_NOT_extracted":True,
    }


def classify_figure_source_unit(*,fig:int, observable:str, mean_over_samples:bool,
                                physical_pellet_id:str|None, exact_temperature_k:float|None,
                                original_CIF_same_pellet_verified:bool,
                                bulk_total_method_traceable:bool)->dict:
    """A rejection-first scientific unit declaration, never acceptance.

    Values never turn into sample-level labeled truths without independently
    sealed custodian and source-specific original numeric measurement review.
    """
    if fig not in (6,7) or observable not in ("RECIPROCAL_RESISTANCE","BULK_SIGMA","TOTAL_SIGMA"):
        raise ValueError("unknown original figure/physical observable")
    if fig==6 and observable!="RECIPROCAL_RESISTANCE":
        raise ValueError("Figure 6 Arrhenius inverse resistance is not σ")
    if fig==7 and observable=="RECIPROCAL_RESISTANCE":
        raise ValueError("Figure 7 room-temperature σ is not inverse R")
    if fig==7 and not mean_over_samples:
        raise ValueError("Figure 7 original captions average multiple pellets")
    if fig==6 and mean_over_samples:
        raise ValueError("Figure 6 representative sample is not mean series")
    if exact_temperature_k is not None and (
        type(exact_temperature_k) not in (int,float) or
        not 0<exact_temperature_k<1000
    ):
        raise ValueError("invalid claimed exact original sample temperature")
    if physical_pellet_id is not None and (
        not isinstance(physical_pellet_id,str) or
        not 1<=len(physical_pellet_id)<=128
    ):
        raise ValueError("invalid physical pellet source identity")
    blockers=[]
    if observable=="RECIPROCAL_RESISTANCE":
        blockers.append("INVERSE_R_NOT_CONDUCTIVITY_S_PER_CM")
    if mean_over_samples:
        blockers.append("FIGURE7_POPULATION_MEAN_NOT_AN_INDIVIDUAL_SPECIMEN")
    if not physical_pellet_id:
        blockers.append("NO_UNIQUE_PELLET_IDENTIFIER_IN_original_SOURCE")
    if exact_temperature_k is None:
        blockers.append("EXACT_MEASURED_PELLET_T_NOT_SOURCE_ATTESTED")
    if not original_CIF_same_pellet_verified:
        blockers.append("NEUTRON_CIF_NOT_ATTESTED_AS_THE_MEASURED_PELLET")
    if not bulk_total_method_traceable:
        blockers.append("BULK_VS_TOTAL_SAMPLE_MEASUREMENT_UNATTESTED")
    # Even artificially populated metadata cannot self-certify original source
    # or sign a prospectively blinded experimental truth.
    blockers.append("INDEPENDENT_EXPERIMENTAL_CUSTODIAN_ATTESTATION_ABSENT")
    return {
        "source_figure":fig,
        "source_figure_semantics":(
           "REPRESENTATIVE_ONE_SAMPLE_INVERSE_R" if fig==6 else
           "COMPOSITION_GROUP_MEAN_BULK_OR_TOTAL_CONDUCTIVITY"
        ),
        "source_observable":observable,
        "scientific_unit":"NOMINAL_COMPOSITION_PELLET_POPULATION" if mean_over_samples else "UNATTESTED_REPRESENTATIVE_PELLET",
        "population_means_NOT_independent_pellets":mean_over_samples,
        "individual_sample_cond_S_per_cm_qualified":False,
        "blockers":blockers,
    }


def actual_original_paper_adjudication(root:Path)->dict:
    source=strict_train_physical_targets(root)
    if source["original_SOURCE_git_commit"]!=SOURCE_COMMIT:
        raise ValueError("pinned OBELiX commit drift")
    paper=fetch_with_bounded_transient_retries(_fetch_original_pdf)
    if hashlib.sha256(paper).hexdigest()!=MANUSCRIPT_SHA:
        raise ValueError("author PDF original SHA drift")
    if not audit_manuscript(paper)["document_text_DOI_match"]:
        raise ValueError("original DOI missing from primary accepted author PDF")
    fig=inspect_original_paper_figures(paper)
    if len(source["original_TWO_source_TRAIN_structure_and_label_leads"])!=2 or {
        x["original_TRAIN_id"] for x in source["original_TWO_source_TRAIN_structure_and_label_leads"]
    }!=ALLOWED_IDS:
        raise ValueError("expected 2 originally pinned TRAIN experimental structure leads")
    q=[]
    for sample in source["original_TWO_source_TRAIN_structure_and_label_leads"]:
        rid=sample["original_TRAIN_id"]
        # FIG6 is only described as representative nominal x=.6, not same
        # specific physical pellet as the diffraction-refined source CIF.
        related6 = rid=="1dm"
        d6=classify_figure_source_unit(
            fig=6,observable="RECIPROCAL_RESISTANCE",mean_over_samples=False,
            physical_pellet_id=None,exact_temperature_k=None,
            original_CIF_same_pellet_verified=False,bulk_total_method_traceable=False)
        d7b=classify_figure_source_unit(
            fig=7,observable="BULK_SIGMA",mean_over_samples=True,
            physical_pellet_id=None,exact_temperature_k=None,
            original_CIF_same_pellet_verified=False,bulk_total_method_traceable=False)
        d7t=classify_figure_source_unit(
            fig=7,observable="TOTAL_SIGMA",mean_over_samples=True,
            physical_pellet_id=None,exact_temperature_k=None,
            original_CIF_same_pellet_verified=False,bulk_total_method_traceable=False)
        q.append({
            "original_TRAIN_id":rid,
            "nominal_composition_x":sample["publisher_nominal_Al_x"],
            "refined_Al_x":sample["publisher_refined_Al_x"],
            "source_CIF_is_neutron_refinement_not_a_pellet_sample_ID":True,
            "figure6_representative_nominal_x0p6_chemistry_context_only":related6,
            "figure6":d6,
            "figure7_bulk":d7b,
            "figure7_total":d7t,
            "original_processed_source_label_kind":"UNVERIFIED_PHYSICAL_OBSERVABLE_RAW_CENSORING_NOT_RECONCILED",
            "source_row_qualified_to_any_figure_point":False,
            "physical_transport_model_input_admitted":False,
        })
    return {
        "schema_version":SCHEMA,
        "original_DOI":PAPER_DOI,
        "pinned_OBELIX_commit":SOURCE_COMMIT,
        "original_author_pdf_sha256":MANUSCRIPT_SHA,
        "figure_audit":fig,
        "figure6_semantics":"REPRESENTATIVE_x0p6_ARRHENIUS_INVERSE_RESISTANCE",
        "figure7_semantics":"NOMINAL_x_SERIES_MULTI_SAMPLE_MEAN_ROOM_TEMPERATURE_BULK_AND_TOTAL_SIGMA_WITH_SD",
        "nominal_x0p6_has_solubility_or_phase_fraction_risk":True,
        "pellet_to_neutron_CIF_to_exact_measurement_JOIN_UNVERIFIED":True,
        "original_TRAIN_CIF_contexts":q,
        "original_processed_TRAIN_log10_label_contrast_x0p6_minus_x0p2":
            source["processed_source_TRAIN_label_log10_ratio_1dm_minus_0fh"],
        "TEST_original_CSV_formula_DOI_conductivity_fields_parsed":0,
        "TEST_source_raw_bytes_passed_over_in_mixed_original_file":True,
        "original_measured_physical_pellets_qualified":0,
        "original_fig7_group_means_digitized_qualified":0,
        "independent_blinded_materials":0,
        "actual_transport_MD_executed":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_GO":False,
    }


def run_original(root:Path,output_dir:Path)->dict:
    out=Path(output_dir).resolve()
    source=Path(root).resolve(strict=True)
    if out==source or source in out.parents or out.exists():
        raise ValueError("outside checkout unique fresh output directory required")
    result=actual_original_paper_adjudication(source)
    out.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".rhombus-0164-",dir=out.parent))
    try:
        (stage/"original_LAGP_figure_population_truth_0164.json").write_bytes(
            _json_bytes(result)+b"\n")
        if out.exists():
            raise ValueError("original numerical report output race")
        stage.rename(out)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    report=run_original(args.original_obelix_checkout,args.output_dir)
    print("0164_ORIGINAL_PRIMARY_PAPER_FIG6_R_INVERSE_V_FIG7_POPULATION_SIGMA_AUDITED")
    print(json.dumps({
        "figure_population_page_evidence":report["figure_audit"]["figure7_population_word_cue_pages_NOT_a_singular_sample"],
        "figure6_R_inverse_page_evidence":report["figure_audit"]["figure6_reciprocal_R_cue_pages_NOT_a_S_per_cm"],
        "original_CIF_leads":len(report["original_TRAIN_CIF_contexts"]),
        "physical_pellets_qualified":report["original_measured_physical_pellets_qualified"],
        "scientific_GO":False},sort_keys=True))


if __name__=="__main__":main()
