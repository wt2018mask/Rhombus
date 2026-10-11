"""0154 complementary first-party Figshare API search by EXACT resource DOI.

The public ACS-hosted supplementary listing is distinct from a DOI route.
Never trust search-title similarity as source identity or copy publisher text.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen, build_opener
from scripts.science.obelix_supplementary_source_0154 import (
    PAPER_DOI, MAX_BYTES, checked_url, check_cif_archive, check_source_pdf, ScopedRedirects,
)

API_SEARCH = "https://api.figshare.com/v2/articles/search"
API_DETAIL = "https://api.figshare.com/v2/articles/"
MAX_META = 512 * 1024
MAX_RESULTS = 10
MAX_FILES = 3
EXPECTED_VERIFIED_SHA256 = {
    "rietveld_si_pdf": "db747a82235860cdcd21a798ad51d2fd0d22b906d3a213cd31e9ea9af72d94d3",
    "experimental_cif_zip": "dc88a0a83857b172ebe7a8194eb1b50148f117d6cddb39f1adbb628ac7d1c382",
}


def _bounded_json(url: str, payload: dict | None = None):
    if not url.startswith("https://api.figshare.com/v2/articles/"):
        raise ValueError("not an approved Figshare API article endpoint")
    if payload is not None:
        raw = json.dumps(payload, sort_keys=True).encode()
        req = Request(url, data=raw, headers={"Content-Type": "application/json",
                       "Accept": "application/json"}, method="POST")
    else:
        req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=25) as response:
        body = response.read(MAX_META + 1)
    if len(body) > MAX_META:
        raise ValueError("Figshare metadata exceeded byte limit")
    return json.loads(body)


def qualified_detail(detail: dict) -> list[dict]:
    if not isinstance(detail, dict) or detail.get("resource_doi", "").casefold() != PAPER_DOI.casefold():
        raise ValueError("Figshare article does not bind exact original publisher resource DOI")
    files = detail.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= 30:
        raise ValueError("unknown Figshare supplementary metadata file list")
    out = []
    for f in files:
        if not isinstance(f, dict):
            raise ValueError("malformed Figshare metadata member")
        name = str(f.get("name", ""))
        role = "experimental_cif_zip" if name.casefold().endswith(".zip") else (
            "rietveld_si_pdf" if name.casefold().endswith(".pdf") else None)
        if role is None:
            continue
        size = f.get("size")
        url = f.get("download_url")
        if not isinstance(size, int) or not 100 <= size <= MAX_BYTES:
            raise ValueError("Figshare member not within size budget")
        if not isinstance(url, str) or not checked_url(url):
            raise ValueError("Figshare source file URL outside official host allowlist")
        out.append({"role": role, "size": size, "url": url, "file_id": f.get("id")})
    return out[:MAX_FILES]


def live() -> dict:
    result = {"schema_version": "rhombus-0154-figshare-exact-resource-doi-public-source-probe-v1",
              "resource_DOI_requested": PAPER_DOI, "search_state": "NOT_EXECUTED",
              "exact_resource_DOI_metadata_entries": 0, "verified_original_source_file_count": 0,
              "source_file_observations": [], "scientific_GO": False,
              "P0_01": "BLOCKED", "P0_02": "BLOCKED", "P0_03": "BLOCKED",
              "original_CIF_to_specific_sample_phase_verified": 0}
    try:
        found = _bounded_json(API_SEARCH, {
            "search_for": "Correlating Transport and Structural Properties",
            "resource_doi": PAPER_DOI, "page": 1, "page_size": MAX_RESULTS})
        if not isinstance(found, list) or len(found) > MAX_RESULTS:
            raise ValueError("unbounded search output")
        for item in found:
            if not isinstance(item, dict) or type(item.get("id")) is not int:
                continue
            details = _bounded_json(API_DETAIL + str(item["id"]))
            if not isinstance(details, dict) or str(details.get("resource_doi") or "").casefold() != PAPER_DOI.casefold():
                continue
            result["exact_resource_DOI_metadata_entries"] += 1
            for f in qualified_detail(details):
                try:
                    # Even a publisher-metadata URL can redirect: enforce
                    # the same host policy BEFORE sending the next GET.
                    redirects = ScopedRedirects()
                    opener = build_opener(redirects)
                    with opener.open(Request(f["url"], headers={"Accept":"application/octet-stream"}), timeout=35) as response:
                        if not checked_url(response.geturl()):
                            raise ValueError("original Figshare file redirected out of host allowlist")
                        data = response.read(MAX_BYTES + 1)
                    if len(data) != f["size"]:
                        raise ValueError("publisher SI file byte count differs from official Figshare metadata")
                    checked = (check_cif_archive(data) if f["role"] == "experimental_cif_zip"
                               else check_source_pdf(data))
                    if checked["source_bytes_sha256"] != EXPECTED_VERIFIED_SHA256[f["role"]]:
                        raise ValueError("previously verified original publisher SI SHA256 drift")
                    result["verified_original_source_file_count"] += 1
                    result["source_file_observations"].append({
                        "role": f["role"], "state": "SOURCE_BYTES_VERIFIED",
                        "source_sha256": checked["source_bytes_sha256"],
                        "source_size": checked["source_bytes_size"],
                        "CIF_member_count_if_applicable": checked.get("cif_member_count"),
                    })
                except (HTTPError, URLError, ValueError, OSError) as exc:
                    # Whitelisted, bounded error categories; no signed URLs or
                    # source metadata bytes are emitted to public CI artifacts.
                    reason = str(exc) if isinstance(exc, ValueError) else ""
                    code = (
                        "REDIRECT_ORIGIN_REJECTED"
                        if "redirect outside bounded official hosts" in reason else
                        "FINAL_ORIGIN_REJECTED"
                        if "redirected out of host allowlist" in reason else
                        "PINNED_ORIGINAL_SOURCE_DIGEST_CHANGED"
                        if "publisher SI SHA256 drift" in reason else
                        "METADATA_SIZE_MISMATCH"
                        if "file byte count differs" in reason else
                        "PDF_SOURCE_FORMAT_REJECTED"
                        if "supplementary PDF" in reason else
                        "CIF_ARCHIVE_FORMAT_REJECTED"
                        if "SI ZIP" in reason or "CIF" in reason else
                        "UNCLASSIFIED_SOURCE_ACCESS_FAILURE"
                    )
                    result["source_file_observations"].append({
                        "role": f["role"], "state": "INACCESSIBLE_OR_REJECTED",
                        "error_type": type(exc).__name__, "failure_code": code,
                        "denied_redirect_hostname": getattr(redirects, "denied_hostname", None),
                    })
        result["search_state"] = ("FOUND_EXACT_RESOURCE_DOI" if
                                  result["exact_resource_DOI_metadata_entries"] else
                                  "NO_EXACT_RESOURCE_DOI")
    except (HTTPError, URLError, ValueError, TypeError, OSError, KeyError) as e:
        result["search_state"] = "FIGSHARE_API_FAILED_CLOSED"
        result["api_error_type"] = type(e).__name__
    if any(x.get("failure_code") == "PINNED_ORIGINAL_SOURCE_DIGEST_CHANGED"
           for x in result["source_file_observations"]):
        raise ValueError("frozen original supplementary source identity changed; science halted")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--live-original", action="store_true")
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    if not a.live_original or a.output_dir.exists():
        p.error("explicit source opt-in and unused output directory required")
    report = live()
    a.output_dir.mkdir(parents=True)
    (a.output_dir / "original_figshare_supplementary_exact_resource_doi.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("0154_FIGSHARE_EXACT_RESOURCE_DOI_SEARCH_EXECUTED")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
