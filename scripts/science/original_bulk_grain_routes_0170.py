"""0170-B actual Yu 2017 Li6PS5Br original bulk-versus-grain transport audit.

Source: primary RSC open-access 2017 journal publication as archived at
TU Delft, DOI 10.1039/C7TA05031C, 12-page PDF, physical page index 4.
This third source reports three DISTINCT processing pathways (milled,
annealed, annealed+re-milled), not three heat-treatment temperatures.
It cannot be pooled as a third 0169 temperature-OLS paper.

Derived total-series conductivity is a constrained *diagnostic proxy*
from originally fitted R_bulk / R_gb and reported sigma_bulk; it is
NOT author tabulated or independently measured total conductivity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import tempfile
import unicodedata
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SCHEMA = "rhombus-0170-actual-publisher-bulk-grain-process-pathway-v1"
DOI = "10.1039/c7ta05031c"
ORIGINAL_PDF = "https://repository.tudelft.nl/file/File_9dd14ba3-3c77-4f77-8383-0918de3062a6"
MAX_PDF_BYTES = 20_000_000
# Original journal paragraph: 2017 Yu et al Figure 1c / PDF page index 4.
# Anchors are checks for primary scientific source, not output data.
STATES = ("BALL_MILLED", "ANNEALED_300C_5H", "ANNEALED_RE_MILLED_450RPM_4H")
RB_OHM = (924.8, 516.8, 381.7)
RB_PLUS_MINUS_OHM = (16.58, 32.28, 10.81)
RGB_OHM = (3.02e6, 619.9, 686.8)
RGB_PLUS_MINUS_OHM = (0.64e6, 22.26, 35.88)
BULK_SIGMA_SCM = (6.20e-4, 1.11e-3, 1.38e-3)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("\u00ad", "").replace("\u2212", "-")
    text = text.replace("\u00d7", "x").replace("\u2060", "")
    text = re.sub(r"\s+", " ", text)
    return text


def check_original_paragraph(cover: str, methods: str, page: str) -> dict:
    a, m, p = (normalize(v) for v in (cover, methods, page))
    if DOI not in a or not ("li6ps5br" in a or "li 6 ps 5 br" in a):
        raise ValueError("third original paper DOI and nominal formula mismatch")
    if not re.search(r"stainless.steel disks", m) or not re.search(
        r"10 mm diameter powder", m
    ):
        raise ValueError("original pellet-diameter/electrode evidence missing")
    if not ("300" in m and re.search(r"5 hours|5 h", m)
            and "450 rpm" in m and re.search(r"4 hours|4 h", m)):
        raise ValueError("author original processing routes missing")
    if not re.search(r"bulk and grain boundary resistances of", p):
        raise ValueError("original source R_bulk/R_gb measurement passage absent")
    start = p.index("bulk and grain boundary resistances of")
    tail = p[start:start+2000]
    if not re.search(r"corresponding room temperature bulk conductivities", tail):
        raise ValueError("conductivity measurement is BULK at room T, not total or 25C")
    end = tail.index("the annealing process")
    passage = tail[:end]
    # The original 3 states must appear in correct order in the SAME short
    # authored scientific paragraph. Values are source identity checks,
    # not a license to fabricate independent experimental pellets.
    vals = ("924.8", "16.58", "3.02", "0.64",
            "516.8", "32.28", "619.9", "22.26",
            "381.7", "10.81", "686.8", "35.88",
            "6.20", "1.11", "1.38")
    pos = 0
    for val in vals:
        match = re.search(r"(?<!\d)" + re.escape(val) + r"(?!\d)", passage[pos:])
        if not match:
            raise ValueError("original journal source numeric/sequence mismatch: " + val)
        pos += match.end()
    if not re.search(r"s\s*cm", passage):
        raise ValueError("source original BULK conductivity S/cm units absent")
    # For each source quantity, check the FIRST exponent that follows it.
    # A later value must never make an altered upstream 10^-2 appear valid.
    def assert_first_power(coeff: str, expected: int, max_after: int = 75):
        i = passage.index(coeff) + len(coeff)
        match = re.search(r"(?<![0-9])10[^0-9]{0,5}([0-9])(?![0-9])",
                          passage[i:i+max_after])
        if match is None or int(match.group(1)) != expected:
            raise ValueError("original numeric power-of-ten drift: " + coeff)
    assert_first_power("0.64", 6)
    assert_first_power("6.20", 4)
    assert_first_power("1.11", 3)
    assert_first_power("1.38", 3)
    return {
        "original_paper_DOI_verified": True,
        "experimental_electrode_configuration_10mm_stainless": True,
        "processing_identity_three_paths": True,
        "exact_author_bulk_and_grain_source_values_verified": True,
        "author_measured_room_temperature_but_exact_numeric_T_not_verified": True,
        "sample_numbers_pellet_phase_and_thickness_unattested": True,
    }


def physical_unit_audit(
    bulk: tuple[float, ...] = RB_OHM,
    gb: tuple[float, ...] = RGB_OHM,
    sigma: tuple[float, ...] = BULK_SIGMA_SCM,
    delta_bulk: tuple[float, ...] = RB_PLUS_MINUS_OHM,
    delta_gb: tuple[float, ...] = RGB_PLUS_MINUS_OHM,
) -> dict:
    if not all(len(v) == 3 for v in (bulk, gb, sigma, delta_bulk, delta_gb)):
        raise ValueError("three uniquely named source preparation pathways required")
    for b, g, s, db, dg in zip(bulk, gb, sigma, delta_bulk, delta_gb):
        if not all(type(v) in (float,int) and math.isfinite(v) for v in (b,g,s,db,dg)):
            raise ValueError("all original physical quantities must be finite")
        if min(b,g,s) <= 0 or db < 0 or dg < 0 or db >= b or dg >= g:
            raise ValueError("unphysical resistance, sigma or fit error bars")
    proxy=[];lower=[];upper=[];ratios=[]
    for b, g, s, db, dg in zip(bulk, gb, sigma, delta_bulk, delta_gb):
        # Series-equivalent-circuit algebra, **not** an author-measured
        # sigma_total. Geometric factors cancel only within each sample
        # under identical current path, electrode area and thickness.
        multiplier=b/(b+g)
        ratios.append(g/b)
        proxy.append(s*multiplier)
        # R-only propagated endpoint envelopes; conductivity's uncertainty
        # is UNKNOWN and not included. Never treat as statistical CI.
        lower.append(s*(b-db)/(b-db+g+dg))
        upper.append(s*(b+db)/(b+db+g-dg))
    # Bulk-only ranking: annealed-re-milled > annealed.
    # Constrained *proxy* ranking: annealed > re-milled.
    # Overlapping resistance-only endpoint ranges reject significance.
    if not (sigma[2] > sigma[1] and proxy[1] > proxy[2]):
        raise ValueError("frozen source-pathway bulk/series-proxy ordering changed")
    overlap = max(lower[1],lower[2]) <= min(upper[1],upper[2])
    if not overlap:
        raise ValueError("published fit-resistance bounds no longer overlap; re-review")
    return {
        "source_bulk_sigma_S_per_cm_unit": True,
        "fitted_bulk_and_grain_resistances_ohm": True,
        "source_observation_units": "THREE_DIFFERENT_PREPARATION_PATHWAYS_NOT_THREE_NUMERIC_ANNEALING_TEMPERATURES",
        "source_processing_pathways": 3,
        "source_original_bulk_sigma_max_to_min_ratio": round(max(sigma)/min(sigma),8),
        "initial_milled_grain_to_bulk_resistance_ratio": round(ratios[0],6),
        "annealed_grain_to_bulk_resistance_ratio": round(ratios[1],6),
        "re_milled_grain_to_bulk_resistance_ratio": round(ratios[2],6),
        "initial_milled_grain_boundary_resistance_reduction_after_annealing": round(gb[0]/gb[1],6),
        "annealed_nominal_series_transport_proxy_S_per_cm": round(proxy[1],11),
        "re_milled_nominal_series_transport_proxy_S_per_cm": round(proxy[2],11),
        "bulk_sigma_ranking_re_milled_above_annealed": True,
        "nominal_series_proxy_ranking_annealed_above_re_milled": True,
        "resistance_only_endpoint_bands_overlap": overlap,
        "all_sigma_bulk_uncertainty_unreported_so_no_significance": True,
        "proxy_NOT_author_published_sigma_total": True,
        "actual_author_reported_total_sigma_S_per_cm_certified": False,
        "is_third_numeric_anneal_temp_transfer_paper": False,
    }


def run_original() -> dict:
    import pymupdf
    request=Request(ORIGINAL_PDF, headers={
        "User-Agent": "Rhombus-original-publisher-physical-unit-study/0170",
        "Accept": "application/pdf",
    })
    with urlopen(request, timeout=40) as reply:
        u=urlsplit(reply.geturl())
        allowed=urlsplit(ORIGINAL_PDF)
        if (u.scheme,u.hostname,u.path)!=(allowed.scheme,allowed.hostname,allowed.path):
            raise ValueError("unapproved institutional original publication redirect")
        raw=reply.read(MAX_PDF_BYTES+1)
    if not raw.startswith(b"%PDF-") or len(raw)<20000 or len(raw)>MAX_PDF_BYTES:
        raise ValueError("invalid oversized or non-PDF author original")
    pdf_hash=hashlib.sha256(raw).hexdigest()
    with pymupdf.open(stream=raw,filetype="pdf") as doc:
        if len(doc)!=12:
            raise ValueError("original RSC open access paper page count drift")
        observed=check_original_paragraph(
            doc[0].get_text()+" "+doc[1].get_text(),
            doc[2].get_text(),
            doc[4].get_text(),
        )
    return {
        "schema_version": SCHEMA,
        "original_primary_source_DOI": DOI,
        "original_institutional_publication_URL": ORIGINAL_PDF,
        "downloaded_original_PDF_SHA256": pdf_hash,
        "publisher_original_pdf_pages": 12,
        "original_science_source_admission": observed,
        "real_original_quantitative_diagnostics": physical_unit_audit(),
        "third_original_publication": True,
        "same_first_author_as_2019_Yu_so_research_team_not_independent": True,
        "total_original_papers_including_0169": 3,
        "third_paper_heldout_temperature_regression_scoreable": False,
        "new_independently_attested_individual_pellets": 0,
        "new_independent_blind_materials": 0,
        "independent_MLIP_finite_temperature_transport_gain": False,
        "P0_01":"BLOCKED", "P0_02":"BLOCKED", "P0_03":"BLOCKED",
        "scientific_GO": False,
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--live-original",action="store_true")
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    if not args.live_original:
        p.error("opt-in to real original public publication PDF verification required")
    target=args.output_dir.resolve()
    if target.exists():
        p.error("new empty output target required")
    result=run_original()
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".rhombus-0170-",dir=target.parent))
    try:
        (stage/"original_bulk_grain_0170.json").write_text(
            json.dumps(result,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n",
            encoding="utf-8",
        )
        if target.exists():raise ValueError("original output collision")
        stage.rename(target)
    finally:
        if stage.exists():shutil.rmtree(stage)
    print("0170_THIRD_ORIGINAL_REAL_BULK_GRAIN_SOURCE_PASS")
    print(json.dumps(result["real_original_quantitative_diagnostics"],sort_keys=True))


if __name__=="__main__":
    main()
