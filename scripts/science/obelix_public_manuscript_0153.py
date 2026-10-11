"""0153-B: bounded original manuscript acquisition, NOT sample qualification.

The OSTI-hosted accepted manuscript for one of the eight 0152-reviewed
publisher DOIs is a candidate original scientific text source. Do not
promote source accessibility or PDF text extraction to a per-CIF phase,
experimental specimen, temperature, or conductivity match.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

DOI = "10.1021/acsami.8b00842"
URL = "https://www.osti.gov/servlets/purl/1434719"
ALLOWED_HOSTS = frozenset({"www.osti.gov", "osti.gov"})
MAX_PDF_BYTES = 12 * 1024 * 1024
MAX_PAGES = 60
MAX_PAGE_TEXT = 22000
MAX_TEXT = 250000
ROOT = Path(__file__).resolve().parents[2]
PRIOR_ABSTRACT_EVIDENCE = (
    ROOT / "data/development/phase3_original_paper_abstract_review_0152_v1.json"
)
OUTPUT_NAME = "original_author_manuscript_access_audit.json"


def _allowed_url(url: str) -> bool:
    u = urlsplit(url)
    return (u.scheme == "https" and (u.hostname or "").lower() in ALLOWED_HOSTS
            and u.username is None and u.password is None and u.port in (None, 443))


class PinnedHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed_url(newurl):
            raise ValueError("original manuscript redirected outside allowlist")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_original_pdf(url: str = URL) -> bytes:
    if url != URL or not _allowed_url(url):
        raise ValueError("unapproved original manuscript URL")
    opener = build_opener(PinnedHostRedirect)
    request = Request(url, headers={"User-Agent": "Rhombus-0153-academic-source-audit/1.0",
                                    "Accept": "application/pdf"})
    with opener.open(request, timeout=35) as response:
        size_hint = response.headers.get("Content-Length")
        if size_hint is not None and int(size_hint) > MAX_PDF_BYTES:
            raise ValueError("original manuscript exceeds download budget")
        data = response.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("original manuscript exceeds download budget")
    return data


def _prior_review_contains_target(evidence: dict) -> bool:
    papers = evidence.get("publisher_abstracts", [])
    return (len(papers) == 8 and
            sum(p.get("doi") == DOI for p in papers if isinstance(p, dict)) == 1 and
            evidence.get("evidence_method") ==
            "MANUAL_REVIEW_OF_PUBLISHER_PUBLIC_INDEXED_TITLE_AND_ABSTRACT_NOT_FULL_PAPER")


def audit_manuscript(raw: bytes, reader_factory=None) -> dict:
    if not isinstance(raw, bytes) or not raw.startswith(b"%PDF-"):
        raise ValueError("not a PDF header")
    if not 100 <= len(raw) <= MAX_PDF_BYTES:
        raise ValueError("invalid bounded original manuscript size")
    if reader_factory is None:
        from pypdf import PdfReader
        reader_factory = PdfReader
    reader = reader_factory(io.BytesIO(raw))
    n = len(reader.pages)
    if not 1 <= n <= MAX_PAGES:
        raise ValueError("unbounded original PDF page count")
    text_parts = []
    for page in reader.pages:
        piece = page.extract_text() or ""
        if len(piece) > MAX_PAGE_TEXT:
            raise ValueError("unbounded page extraction")
        text_parts.append(piece)
    text = "\n".join(text_parts)
    if not 100 <= len(text) <= MAX_TEXT:
        raise ValueError("original PDF text not reliably extractable")
    folded = " ".join(text.lower().split())
    if not re.search(r"10[.]1021\s*/\s*acsami[.]8b00842", folded):
        raise ValueError("exact 0152 publisher DOI absent from original text")
    if not ("transport" in folded and "structural" in folded
            and "ge" in folded and "al" in folded):
        raise ValueError("original manuscript scientific title markers absent")
    observed = {key: bool(re.search(pattern, folded)) for key, pattern in {
        "experiment_section": r"experimental",
        "discussion_section": r"results\s+and\s+discussion",
        "impedance_method": r"impedance",
        "neutron_method": r"neutron",
        "synchrotron_method": r"synchrotron",
        "composition_series": r"al.{0,30}ge|ge.{0,30}al",
        "conductivity_unit_context": r"s\s*(?:/|cm|[.])\s*cm|conductivity",
        "bulk_vs_boundary_context": r"grain\s+boundar|bulk",
        "published_tabular_context": r"table\s+[1-9]",
    }.items()}
    return {
        "schema_version": "rhombus-0153-original-manuscript-actual-pdf-audit-v1",
        "source_doi": DOI,
        "source_url": URL,
        "repository": "US_DOE_OSTI_PUBLIC_ACCEPTED_AUTHOR_MANUSCRIPT",
        "version_of_record_independently_confirmed": False,
        "bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "bytes_size": len(raw),
        "pages_extracted": n,
        "text_extracted_characters": len(text),
        "document_text_DOI_match": True,
        "document_text_science_topic_match": True,
        "text_only_context_indicators": observed,
        "full_paper_human_table_and_SI_adjudication_completed": False,
        "supplementary_CIF_bytes_verified": False,
        "original_OBELiX_0152_10_CIF_queue_requalified": False,
        "source_CIF_to_exact_paper_experimental_sample_matched": 0,
        "paper_measured_temperature_and_bulk_total_row_matched": 0,
        "new_independent_materials_qualified": 0,
        "P0_01": "BLOCKED",
        "P0_02": "BLOCKED",
        "P0_03": "BLOCKED",
        "scientific_GO": False,
    }


def run_live(out_dir: Path) -> dict:
    evidence = json.loads(PRIOR_ABSTRACT_EVIDENCE.read_text(encoding="utf-8"))
    if not _prior_review_contains_target(evidence):
        raise ValueError("0152 source DOI evidence changed or cannot be confirmed")
    data = _fetch_original_pdf()
    result = audit_manuscript(data)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / OUTPUT_NAME
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--live-original", action="store_true")
    p.add_argument("--output-dir", type=Path)
    args = p.parse_args()
    if not args.live_original or args.output_dir is None:
        p.error("explicit --live-original and --output-dir are required")
    result = run_live(args.output_dir)
    print("0153_ORIGINAL_PUBLIC_AUTHOR_MANUSCRIPT_BYTES_AND_DOI_VERIFIED")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
