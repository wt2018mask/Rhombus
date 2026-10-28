"""0169-B: cross-PUBLICATION process-temperature transfer, two ORIGINAL papers.

Yubuchi RSC Advances 2019 (solution route): six heat-treatment rows.
Yu et al. J Mater Chem A 2019 (solid-state route): eight annealing rows.
Identical nominal Li6PS5Br, different preparations and uncertain sample identity.
Fixed training-paper median and 1-D OLS; test-paper labels NEVER fit/tune.
Both papers inspected before protocol, exploratory NOT prospective blind.
Yu reports room temperature without a verified exact numeric measurement T.
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

from scripts.science import original_process_holdout_0168 as p168

SCHEMA = "rhombus-0169-two-independent-papers-cross-publication-process-transfer-v1"
YU_DOI = "10.1039/c9ta02126d"
YU_PDF = "https://pure.tudelft.nl/ws/portalfiles/portal/53254729/C9TA02126D.pdf"
YU_T = (250, 300, 350, 400, 450, 500, 550, 600)
YU_SIGMA_S_CM = (8.06e-5, 2.28e-4, 7.98e-4, 1.15e-3, 1.38e-3, 1.65e-3, 2.58e-3, 1.41e-3)
MAX_PDF = 15_000_000


def parse_yu_figure4_text(cover: str, original_page: str) -> tuple[list[float], list[float]]:
    """Only values explicitly printed in accepted author's Figure 4 paragraph.

    Never infer graph points from pixels and never mistake annealing temperature
    for ionic conductivity measurement temperature.
    """
    front = unicodedata.normalize("NFKC", cover).lower()
    if ("c9ta02126d" not in front or "lithium" not in front and "li6ps5br" not in front):
        raise ValueError("Yu original DOI/article identity missing")
    s = unicodedata.normalize("NFKC", original_page).replace("\u2212", "-")
    s = re.sub(r"\s+", " ", s)
    anchor = re.search(r"room temperature ionic conductivities of the samples prepared", s, re.I)
    if not anchor:
        raise ValueError("original Figure 4 room-temperature conductivity statement missing")
    end = s.find("respectively", anchor.end())
    if end < 0 or end - anchor.end() > 1400:
        raise ValueError("original Figure 4 numerical series boundary missing")
    paragraph = s[anchor.end():end]
    # PDF is author's accepted manuscript; its multiplication sign may be
    # mapped to a private-use glyph by the embedded font.
    pattern = (r"(?<!\d)(\d+(?:\.\d+)?)\s*[^A-Za-z0-9]{0,8}\s*10\s*[-−]\s*"
               r"(\d)\s*S\s*/\s*cm\s+for\s+(\d{3})\s*(?:o|°|º)\s*C")
    triples = [(int(t), float(f"{a}e-{exp}"))
               for a, exp, t in re.findall(pattern, paragraph, re.I)]
    if len(triples) != len(YU_T):
        raise ValueError("original Figure 4 all eight authored conductivity values not extracted")
    temps, values = zip(*triples)
    if temps != YU_T or any(
        not math.isclose(a,b, rel_tol=1e-10, abs_tol=1e-12)
        for a,b in zip(values, YU_SIGMA_S_CM)
    ):
        raise ValueError("original Figure 4 numerical content or annealing order drift")
    if "Figure 4" not in s and "Fig. 4" not in s:
        raise ValueError("author original Figure 4 context missing")
    return list(map(float, temps)), list(values)


def fetch_yu_original() -> tuple[list[float], list[float], str]:
    import fitz  # PyMuPDF; loaded only during actual primary PDF execution

    req = Request(YU_PDF, headers={
        "User-Agent": "Rhombus-public-primary-manuscript-audit/0169",
        "Accept": "application/pdf",
    })
    with urlopen(req, timeout=45) as response:
        resolved = urlsplit(response.geturl())
        expected = urlsplit(YU_PDF)
        if (resolved.scheme, resolved.hostname, resolved.path) != (
            expected.scheme, expected.hostname, expected.path
        ):
            raise ValueError("institutional primary manuscript URL redirected outside pinned source")
        raw = response.read(MAX_PDF+1)
    if len(raw) < 10000 or len(raw) > MAX_PDF or not raw.startswith(b"%PDF-"):
        raise ValueError("invalid original manuscript PDF bytes or size")
    digest = hashlib.sha256(raw).hexdigest()
    with fitz.open(stream=raw, filetype="pdf") as doc:
        if len(doc) != 20:
            raise ValueError("expected TU Delft accepted manuscript 20 PDF pages")
        cover = " ".join(doc[i].get_text() for i in (0, 2, 10))
        page = doc[10].get_text()
        temps, sigma = parse_yu_figure4_text(cover, page)
    return temps, sigma, digest


def fixed_paper_model(train_t: list[float], train_sigma: list[float],
                      target_t: list[float], target_sigma: list[float]) -> dict:
    """Fit on one entire training paper; no row of heldout PAPER used to fit."""
    if (len(train_t) < 3 or len(target_t) < 3 or len(train_t) != len(train_sigma)
        or len(target_t) != len(target_sigma)
        or len(set(train_t)) != len(train_t)
        or len(set(target_t)) != len(target_t)
        or any(not math.isfinite(z) for z in train_t+train_sigma+target_t+target_sigma)
        or any(z <= 0 for z in train_sigma+target_sigma)):
        raise ValueError("invalid independent source study train/heldout observations")
    yy = [math.log10(z) for z in train_sigma]
    test = [math.log10(z) for z in target_sigma]
    tx, ty = statistics.mean(train_t), statistics.mean(yy)
    denom = sum((t-tx)**2 for t in train_t)
    if denom <= 0:
        raise ValueError("training processing temperature design degenerate")
    slope = sum((t-tx)*(v-ty) for t,v in zip(train_t, yy))/denom
    c = statistics.median(yy)
    pred = [ty+slope*(x-tx) for x in target_t]
    chem = statistics.mean(abs(c-y) for y in test)
    ols = statistics.mean(abs(x-y) for x,y in zip(pred, test))
    return {
        "train_conditions": len(train_t),
        "heldout_paper_conditions": len(target_t),
        "median_train_paper_constant_log10MAE": round(chem, 8),
        "process_temperature_OLS_train_paper_log10MAE": round(ols, 8),
        "process_relative_MAE_reduction": round(1-ols/chem, 8),
        "train_paper_temperature_slope_log10_Scm_per_C": round(slope, 10),
        "no_target_paper_labels_fitted": True,
        "no_pooled_rowwise_random_split": True,
    }


def run_original() -> dict:
    original_xml, source_url = p168.y.fetch_original_public_jats()
    y = p168.y.extract_table(original_xml)
    y_t, y_log = p168._admit_original(y)
    y_sigma = [10**v for v in y_log]
    u_t, u_sigma, pdf_sha = fetch_yu_original()
    forward = fixed_paper_model(y_t, y_sigma, u_t, u_sigma)
    reverse = fixed_paper_model(u_t, u_sigma, y_t, y_sigma)
    return {
        "schema_version": SCHEMA,
        "sources": {
            "train_or_test_publication_DOIs": [p168.y.ORIGINAL_DOI, YU_DOI],
            "original_Yubuchi_JATS_download_archive": source_url,
            "original_Yubuchi_JATS_SHA256": y["original_public_jats_sha256"],
            "original_Yu_accepted_manuscript_URL": YU_PDF,
            "original_Yu_download_SHA256": pdf_sha,
            "nominal_formula_in_both": "Li6PS5Br",
            "source_different_preparation_routes": True,
            "Yubuchi_original_conductivity_measured_at_25C": True,
            "Yu_exact_numeric_conductivity_measurement_temperature_unattested": True,
            "Yu_room_temperature_only": True,
            "cross_paper_same_pellet_geometry_and_phase_unattested": True,
        },
        "Yubuchi_2019_to_Yu_2019": forward,
        "Yu_2019_to_Yubuchi_2019": reverse,
        "original_public_source_conditions_total": 14,
        "independent_publications": 2,
        "independent_material_compositions": 1,
        "independently_physical_attested_pellets": 0,
        "exact_numeric_temperature_matched_heldout_papers": False,
        "exploratory_sources_seen_before_protocol": True,
        "independently_sealed_blind": False,
        "genuine_out_of_paper_not_out_of_chemistry": True,
        "causal_processing_effect_identified": False,
        "MLIP_transport_improvement_shown": False,
        "P0_01": "BLOCKED", "P0_02": "BLOCKED", "P0_03": "BLOCKED",
        "scientific_GO": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-original", action="store_true")
    ap.add_argument('--require-live-network', action='store_true')
    ap.add_argument('--allow-source-timeout', action='store_true')
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    if args.allow_source_timeout and args.require_live_network:
        ap.error('strict and timeout-tolerant modes are mutually exclusive')
    if not args.live_original:
        ap.error("real institutional manuscript/PMC fetch must be explicitly authorized")
    target = args.output_dir.resolve()
    if target.exists():
        ap.error("new empty output directory required")
    try:
        report = run_original()
    except Exception as error:
        from scripts.science.source_outage import record_timeout
        if args.allow_source_timeout:
            # Run actual offline assertions before writing VERIFIED. This
            # never authenticates missing original bytes or swallows mismatch.
            from urllib.error import URLError
            reason=error.reason if isinstance(error,URLError) else error
            if isinstance(reason,TimeoutError) or (isinstance(reason,str) and reason.strip().lower() in ('timed out','timeout')):
                import subprocess,sys
                subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider',
                    'tests/test_phase3_original_cross_paper_transfer_0169.py',
                    'tests/test_phase3_original_process_holdout_0168.py'],check=True,cwd=Path(__file__).resolve().parents[2])
                record_timeout(error,target,resources=[YU_PDF,p168.y.SOURCE_URL],offline_regression_verified=True)
                return
        record_timeout(error, target, resources=[YU_PDF, p168.y.SOURCE_URL])
        raise
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".rhombus-0169-", dir=target.parent))
    try:
        (stage/"original_cross_paper_transfer_0169.json").write_text(
            json.dumps(report, sort_keys=True, allow_nan=False, separators=(",", ":"))+"\n",
            encoding="utf-8",
        )
        if target.exists():
            raise ValueError("science output path collision")
        stage.rename(target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print("0169_GENUINE_TWO_PRIMARY_PAPERS_CROSS_PUBLICATION_DIAGNOSTIC_PASS")
    print(json.dumps({direction: report[direction] for direction in (
        "Yubuchi_2019_to_Yu_2019", "Yu_2019_to_Yubuchi_2019"
    )}, sort_keys=True))


if __name__ == "__main__":
    main()
