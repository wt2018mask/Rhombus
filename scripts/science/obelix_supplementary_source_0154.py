"""0154-B: real ACS freely listed supplementary PDF + crystal CIF ZIP evidence.

Access is a live experiment, NOT assumed from a publisher landing page.
Only digest/aggregate structural diagnostics are uploaded; source file bytes
and measured labels are never copied to the repository or Actions artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
import zipfile

PAPER_DOI = "10.1021/acsami.8b00842"
# Conventional SI suffix routes are candidates, NOT verified source URLs.
ROUTES = {
    "rietveld_si_pdf": "https://doi.org/10.1021/acsami.8b00842.s001",
    "experimental_cif_zip": "https://doi.org/10.1021/acsami.8b00842.s002",
}
HOSTS = frozenset({
    "doi.org", "pubs.acs.org", "acs.figshare.com",
    "api.figshare.com", "ndownloader.figshare.com",
    "download.figshare.com", "figshare.com",
})
MAX_BYTES = 16 * 1024 * 1024
MAX_ZIP_MEMBERS = 40
MAX_MEMBER_BYTES = 2 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 10 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250
MAX_PDF_PAGES = 80
SOURCE_REVIEW = (Path(__file__).resolve().parents[2] /
                 "data/development/phase3_original_paper_abstract_review_0152_v1.json")
ALLOWED_ZIP_EXTENSIONS = {".cif", ".txt", ".md", ".pdf"}


def checked_url(url: str) -> bool:
    p = urlsplit(url)
    return (p.scheme == "https" and (p.hostname or "").lower() in HOSTS
            and not p.username and not p.password and p.port in (None, 443)
            and not p.fragment)


class ScopedRedirects(HTTPRedirectHandler):
    def __init__(self):
        super().__init__()
        self.visited = []
        self.denied_hostname = None

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not checked_url(newurl) or len(self.visited) >= 5:
            self.denied_hostname = (urlsplit(newurl).hostname or "").lower()[:160]
            raise ValueError("supplementary source redirect outside bounded official hosts")
        self.visited.append((urlsplit(newurl).hostname or "").lower())
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def retrieve(route: str) -> tuple[bytes | None, dict]:
    if route not in ROUTES:
        raise ValueError("unapproved SI route")
    url = ROUTES[route]
    if not checked_url(url):
        raise ValueError("invalid SI source route")
    redirects = ScopedRedirects()
    opener = build_opener(redirects)
    try:
        with opener.open(Request(url, headers={
            "User-Agent": "Rhombus-0154-academic-original-source/1.0",
            "Accept": "application/pdf, application/zip, application/octet-stream",
        }), timeout=35) as response:
            final_url = response.geturl()
            if not checked_url(final_url):
                raise ValueError("untrusted official SI final host")
            size = response.headers.get("Content-Length")
            if size is not None and int(size) > MAX_BYTES:
                raise ValueError("SI source exceeds byte budget")
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("SI source exceeds byte budget")
        return raw, {"access_state": "DOWNLOADED_UNVERIFIED", "source_route": route,
                     "original_route": url, "final_hostname": urlsplit(final_url).hostname,
                     "redirect_hostnames": redirects.visited}
    except HTTPError as e:
        # Do not promote unavailable paid or blocked publisher bytes to a review.
        return None, {"access_state": "HTTP_UNAVAILABLE", "source_route": route,
                      "original_route": url, "http_status": e.code,
                      "redirect_hostnames": redirects.visited}
    except URLError as e:
        return None, {"access_state": "NETWORK_UNAVAILABLE", "source_route": route,
                      "original_route": url, "error_type": type(e.reason).__name__,
                      "redirect_hostnames": redirects.visited}


def check_source_pdf(raw: bytes, reader_factory=None) -> dict:
    if len(raw) < 200 or len(raw) > MAX_BYTES or not raw.startswith(b"%PDF-"):
        raise ValueError("not a bounded original supplementary PDF")
    if reader_factory is None:
        from pypdf import PdfReader
        reader_factory = PdfReader
    reader = reader_factory(io.BytesIO(raw))
    count = len(reader.pages)
    if not 1 <= count <= MAX_PDF_PAGES:
        raise ValueError("invalid supplementary PDF page count")
    return {"source_bytes_sha256": hashlib.sha256(raw).hexdigest(),
            "source_bytes_size": len(raw), "pages_structurally_decoded": count,
            "text_or_tables_human_adjudicated": False}


def check_cif_archive(raw: bytes) -> dict:
    if len(raw) < 100 or len(raw) > MAX_BYTES or not zipfile.is_zipfile(io.BytesIO(raw)):
        raise ValueError("not a genuine bounded original SI ZIP")
    cif_data = []
    total = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members = z.infolist()
        if not 1 <= len(members) <= MAX_ZIP_MEMBERS:
            raise ValueError("unbounded SI ZIP file count")
        for info in members:
            name = info.filename
            # ZIP contents remain transient. Disallow links, nested archives, traversal.
            posix = name.replace("\\", "/")
            pieces = posix.split("/")
            if (not posix or posix.startswith("/") or
                ".." in pieces or name != posix or
                "\x00" in posix or (info.external_attr >> 16) & 0o170000 == 0o120000 or
                (not info.is_dir() and Path(posix).suffix.lower() not in ALLOWED_ZIP_EXTENSIONS)):
                raise ValueError("disallowed original SI archive member")
            if info.is_dir():
                continue
            if info.flag_bits & 1:
                raise ValueError("encrypted SI member disallowed")
            if (info.file_size < 0 or info.file_size > MAX_MEMBER_BYTES
                or info.compress_size < 0 or
                info.file_size > MAX_COMPRESSION_RATIO * max(1, info.compress_size)):
                raise ValueError("unsafe SI archive expansion")
            total += info.file_size
            if total > MAX_TOTAL_UNCOMPRESSED:
                raise ValueError("unsafe cumulative SI ZIP expansion")
            with z.open(info) as f:
                blob = f.read(MAX_MEMBER_BYTES + 1)
            if len(blob) != info.file_size:
                raise ValueError("SI archive member read is incomplete")
            if posix.casefold().endswith(".cif"):
                text = blob.decode("utf-8-sig")
                if not (re.search(r"(?m)^\s*data_[^\r\n]*", text) and
                        re.search(r"(?m)^\s*_cell_length_[abc]\s+", text)):
                    raise ValueError("archive member is not a crystallographic CIF")
                cif_data.append({"member_sha256": hashlib.sha256(blob).hexdigest(),
                                 "member_length": len(blob),
                                 "has_fractional_site_tokens":
                                    bool(re.search(r"_atom_site_occupancy", text, re.I))})
    if not cif_data:
        raise ValueError("the claimed original SI CIF ZIP contained no CIF members")
    return {"source_bytes_sha256": hashlib.sha256(raw).hexdigest(),
            "source_bytes_size": len(raw),
            "total_archive_members": len(members),
            "cif_member_count": len(cif_data),
            "cif_member_digests_and_parse_indicators_ONLY": cif_data,
            "uncompressed_bytes_read_with_caps": total,
            "exact_OBELiX_CIF_to_SI_member_phase_match": "NOT_ADJUDICATED",
            "no_fractional_occupancies_rounded": True}


def assess(route: str, raw: bytes | None, provenance: dict) -> dict:
    if route not in ROUTES or provenance.get("source_route") != route:
        raise ValueError("mismatched SI provenance")
    result = dict(provenance)
    if raw is None:
        if result["access_state"] not in ("HTTP_UNAVAILABLE", "NETWORK_UNAVAILABLE"):
            raise ValueError("unverified source has no authenticated bytes")
        result["scientifically_usable_source"] = False
        return result
    try:
        values = check_source_pdf(raw) if route == "rietveld_si_pdf" else check_cif_archive(raw)
    except (ValueError, UnicodeError, zipfile.BadZipFile, RuntimeError, EOFError) as e:
        result["access_state"] = "SOURCE_CONTENT_REJECTED"
        result["rejection_code"] = type(e).__name__
        result["scientifically_usable_source"] = False
        return result
    result.update(values)
    result["access_state"] = "ORIGINAL_SUPPLEMENTARY_BYTES_PARSED_NOT_SAMPLE_QUALIFIED"
    result["scientifically_usable_source"] = True
    return result


def run() -> dict:
    prior = json.loads(SOURCE_REVIEW.read_text(encoding="utf-8"))
    if (prior.get("evidence_method") !=
        "MANUAL_REVIEW_OF_PUBLISHER_PUBLIC_INDEXED_TITLE_AND_ABSTRACT_NOT_FULL_PAPER"
        or sum(p.get("doi") == PAPER_DOI for p in prior.get("publisher_abstracts", [])) != 1):
        raise ValueError("original 0152 paper identity not source-bound")
    audits = []
    for route in ROUTES:
        payload, provenance = retrieve(route)
        audits.append(assess(route, payload, provenance))
    return {
        "schema_version": "rhombus-0154-actual-original-supplementary-bytes-census-v1",
        "source_publisher_DOI": PAPER_DOI,
        "source_evidence_0152_required": True,
        "routes_explored": len(audits),
        "real_source_results": audits,
        "source_bytes_verified_count": sum(x["scientifically_usable_source"] for x in audits),
        "original_train_CIF_rows_linked_to_DOI_in_prior_0152": 2,
        "original_public_TEST_121_rows_inspected": 0,
        "source_to_exact_sample_composition_phase_matched": 0,
        "row_specific_measured_temperature_bulk_total_conductivity_matched": 0,
        "independent_physical_samples_verified": 0,
        "MD_transport_computed": False,
        "P0_01": "BLOCKED", "P0_02": "BLOCKED", "P0_03": "BLOCKED",
        "scientific_GO": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-original", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.live_original:
        parser.error("live source must be explicitly enabled")
    out = args.output_dir
    if out.exists():
        parser.error("cannot overwrite prior source artifact")
    result = run()
    out.mkdir(parents=True)
    (out / "actual_supplementary_access_audit.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("0154_ORIGINAL_SI_PROBE_COMPLETED_WITH_ACTUAL_ACCESS_STATE")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
