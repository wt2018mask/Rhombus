"""Verify the institutional publisher-VOR copy for the 0194 article.

The institution record, its declared open license and the downloaded PDF are
independent provenance checks. This route never substitutes a transcription
or a PDF hash for a DOI-bound and complete source.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pypdf import PdfReader

DOI = "10.1002/cssc.202300399"
RECORD_URL = "https://iris.unimore.it/handle/11380/1328508"
PDF_URL = ("https://iris.unimore.it/retrieve/500e772d-e2c5-4d6d-88e5-14f53ce47ac1/"
           "ChemSusChem%20-%202023%20-%20Campanella%20-%20Hexavalent%20Ions%20Insertion%20"
           "in%20Garnet%20Li7La3Zr2O12%20Toward%20a%20Low%20Temperature%20Densification.pdf")
PDF_HANDLE = "500e772d-e2c5-4d6d-88e5-14f53ce47ac1"
MAX_RECORD_BYTES = 4 * 1024 * 1024
MAX_PDF_BYTES = 40 * 1024 * 1024
EXPECTED = (
    1.21e-5, 2.95e-5, 1.61e-5, 2.33e-5, 3.88e-8, 2.64e-7,
    1.76e-5, 4.64e-5, 3.27e-5, 4.24e-5, 1.04e-7, 2.29e-6,
    1.45e-5, 5.15e-5, 4.66e-5, 4.83e-5, 3.05e-7, 6.70e-6,
)
LICENSES = frozenset({
    "https://creativecommons.org/licenses/by/4.0/",
    "https://creativecommons.org/licenses/by-nc/4.0/",
    "https://creativecommons.org/licenses/by-nc-nd/4.0/",
    "https://creativecommons.org/licenses/by-nd/4.0/",
})


class _RecordParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[str] = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        for name in ("href", "content"):
            value = values.get(name)
            if value:
                self.links.append(value)


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    for char in ("−", "–", "—", "‑"):
        value = value.replace(char, "-")
    return re.sub(r"\s+", " ", value)


class _SameInstitutionRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if (parsed.scheme != "https" or parsed.hostname != "iris.unimore.it"
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError("institutional source redirected outside its pinned host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url: str, limit: int, accept: str) -> tuple[bytes, str, int]:
    opener = build_opener(_SameInstitutionRedirects())
    with opener.open(Request(url, headers={"Accept": accept,
            "User-Agent": "Rhombus-source-verification/1.0"}), timeout=45) as response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname != "iris.unimore.it":
            raise ValueError("final institutional source host mismatch")
        length = response.headers.get("Content-Length")
        if length is not None and int(length) > limit:
            raise ValueError("institutional source exceeds byte bound")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("institutional source exceeds byte bound")
        return data, response.headers.get("Content-Type", ""), len(data)


def inspect_source(record: bytes, pdf: bytes) -> None:
    """Emit bounded, public-source excerpts for auditing, never raw PDF bytes."""
    def notice(kind, payload):
        message = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::notice title=0194 {kind}::{message}", flush=True)

    notice("download identity", {"pdf_sha256": hashlib.sha256(pdf).hexdigest(),
        "pdf_bytes": len(pdf), "record_sha256": hashlib.sha256(record).hexdigest(),
        "status": "DOWNLOADED_NOT_YET_VERIFIED"})
    html = record.decode("utf-8", errors="replace")
    excerpts = [html[max(0,m.start()-240):m.end()+360]
                for m in list(re.finditer(r"creative|licen[sz]|rights", html, re.I))[:12]]
    notice("record rights elements", excerpts)
    reader = PdfReader(io.BytesIO(pdf), strict=True)
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        for m in list(re.finditer(r"creative commons|open access article", text, re.I))[:2]:
            notice("PDF rights notice", {"page": index+1,
                "text": text[max(0,m.start()-100):m.end()+650]})
        if "1.21" in text and "2.95" in text:
            layout = page.extract_text(extraction_mode="layout") or ""
            match = re.search(r"Table\s*2", layout, re.I)
            if match:
                notice("PDF Table 2 layout", {"page": index+1,
                    "text": layout[max(0,match.start()-100):match.start()+6500]})


def verify(record_html: bytes, pdf_bytes: bytes, pdf_reader=PdfReader) -> dict:
    if not isinstance(record_html, bytes) or not 20 < len(record_html) <= MAX_RECORD_BYTES:
        raise ValueError("invalid or oversized institutional record")
    if not isinstance(pdf_bytes, bytes) or not 1000 < len(pdf_bytes) <= MAX_PDF_BYTES:
        raise ValueError("invalid or oversized VOR PDF")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("institutional file is not a PDF")

    parser = _RecordParser()
    parser.feed(record_html.decode("utf-8", errors="replace"))
    record_text = _normalized(" ".join(parser.text + parser.links))
    if DOI not in record_text:
        raise ValueError("institutional record does not bind the exact article DOI")
    if "1328508" not in record_text or PDF_HANDLE not in record_text:
        raise ValueError("institutional record does not bind the selected VOR file")
    license_uri = next((uri for uri in parser.links
                        if uri.rstrip("/") + "/" in LICENSES), None)
    if license_uri is None:
        raise ValueError("institutional record lacks a recognized Creative Commons license URI")
    license_uri = license_uri.rstrip("/") + "/"
    if not any(term in record_text for term in ("version of record", "published version", "publisher version")):
        raise ValueError("institutional record does not identify the publisher version")

    reader = pdf_reader(io.BytesIO(pdf_bytes), strict=True)
    if reader.is_encrypted:
        raise ValueError("VOR PDF is encrypted")
    if not 1 <= len(reader.pages) <= 80:
        raise ValueError("VOR PDF page count is outside bounds")
    pdf_text = _normalized("\n".join(page.extract_text() or "" for page in reader.pages))
    required_identity = (DOI, "hexavalent ions insertion", "campanella", "zhu", "girard")
    missing = [term for term in required_identity if term not in pdf_text]
    if missing:
        raise ValueError("PDF article identity is incomplete: " + ",".join(missing))
    if "wiley" not in pdf_text and "chemsuschem" not in pdf_text:
        raise ValueError("PDF does not identify the publisher or journal")

    # Read values only inside the Table 2 section. Keep the original expected
    # 18-value sequence and require an exact, unique token for every value.
    table = re.search(r"\btable\s*2\b", pdf_text)
    if table is None:
        raise ValueError("PDF Table 2 heading was not extractable")
    following = re.search(r"\btable\s*3\b", pdf_text[table.end():])
    table_text = pdf_text[table.end():table.end() + following.start()] if following else pdf_text[table.end():table.end() + 6000]
    if len(table_text) < 100:
        raise ValueError("PDF Table 2 text is incomplete")
    if (re.search(r"\b25\s*°?\s*c\b", table_text) is None
            or "conductivity" not in pdf_text or "total" not in table_text):
        raise ValueError("PDF Table 2 lacks the reported temperature or conductivity context")
    series_labels = ("te0.1", "te0.25", "te0.375", "te0.5", "al-llzo", "ta-llzo")
    if any(label not in table_text for label in series_labels):
        raise ValueError("PDF Table 2 lacks one or more of the six composition/reference labels")
    for process_temperature in (600, 650, 700):
        if re.search(rf"\b{process_temperature}\s*°?\s*c\b", table_text) is None:
            raise ValueError("PDF Table 2 lacks an expected hot-press temperature")
    if re.search(r"\bs\s*cm\s*-\s*1\b|\bs\s*/\s*cm\b", pdf_text) is None:
        raise ValueError("PDF lacks an extractable conductivity unit")
    if not any(term in pdf_text for term in ("hot press", "hot-press")) or "56 mpa" not in pdf_text:
        raise ValueError("PDF does not identify hot-press manufacturing conditions")

    scientific_tokens = re.findall(
        r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:×|x|\*)\s*10\s*\^?\s*\(?\s*(-\d+)\s*\)?",
        table_text,
    )
    observed = [float(coefficient) * 10 ** int(exponent)
                for coefficient, exponent in scientific_tokens]
    if len(observed) != len(EXPECTED):
        raise ValueError(f"PDF Table 2 yielded {len(observed)} scientific values; expected 18")
    unmatched = list(EXPECTED)
    for actual in observed:
        match = next((i for i, expected in enumerate(unmatched)
                      if math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-18)), None)
        if match is None:
            raise ValueError("PDF Table 2 scientific values differ from the frozen 18-condition record")
        unmatched.pop(match)
    if unmatched:
        raise ValueError("PDF Table 2 scientific values differ from the frozen 18-condition record")

    return {
        "schema_version": "rhombus-0194-unimore-institutional-vor-verification-v1",
        "doi": DOI,
        "source_route": "INSTITUTIONAL_VERSION_OF_RECORD",
        "record_url": RECORD_URL,
        "pdf_url": PDF_URL,
        "institution_host": "iris.unimore.it",
        "record_exact_doi_match": True,
        "record_binds_exact_pdf_handle": True,
        "record_identifies_publisher_version": True,
        "license_uri": license_uri,
        "pdf_title_author_doi_match": True,
        "pdf_page_count": len(reader.pages),
        "pdf_byte_count": len(pdf_bytes),
        "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "table_2_all_18_values_exact_match": True,
        "table_2_condition_count": len(observed),
        "table_2_conductivity_target_temperature_C": 25,
        "manufacturing_route": "HOT_PRESS_56_MPA",
        "live_wiley_html_verified": False,
        "scientific_GO": False,
        "production_enabled": False,
        "official_OBELiX_TEST_121_read": False,
        "P0_01": "BLOCKED", "P0_02": "BLOCKED", "P0_03": "BLOCKED",
    }


def run(output: Path, inspect=False) -> dict:
    if output.exists():
        raise ValueError("refuse to overwrite prior source receipt")
    record, _, _ = _fetch(RECORD_URL, MAX_RECORD_BYTES, "text/html")
    pdf, content_type, _ = _fetch(PDF_URL, MAX_PDF_BYTES, "application/pdf")
    if "pdf" not in content_type.casefold() and not pdf.startswith(b"%PDF-"):
        raise ValueError("institutional VOR endpoint did not return PDF content")
    if inspect:
        inspect_source(record, pdf)
    receipt = verify(record, pdf)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--inspect-source", action="store_true")
    args = cli.parse_args()
    result = run(args.output, args.inspect_source)
    print("0194_INSTITUTIONAL_VOR_SOURCE_VERIFIED", json.dumps(result, sort_keys=True))
