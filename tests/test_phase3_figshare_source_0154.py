"""0154 Figshare exact publisher DOI/URL boundary."""
import copy
import pytest

from scripts.science import obelix_figshare_source_0154 as f

GOOD = {
    "resource_doi": "10.1021/acsami.8b00842",
    "files": [
        {"name": "sifile2.zip", "size": 3425,
         "download_url": "https://ndownloader.figshare.com/files/11111", "id": 11111},
        {"name": "sifile1.pdf", "size": 4545,
         "download_url": "https://ndownloader.figshare.com/files/22222", "id": 22222},
    ],
}


def test_only_exact_publisher_resource_doi_allows_files():
    results = f.qualified_detail(GOOD)
    assert [x["role"] for x in results] == ["experimental_cif_zip", "rietveld_si_pdf"]
    incorrect = copy.deepcopy(GOOD)
    incorrect["resource_doi"] = "10.1021/unrelated"
    with pytest.raises(ValueError):
        f.qualified_detail(incorrect)


def test_reject_unsafe_or_overlarge_member():
    for bad in ("http://ndownloader.figshare.com/files/123",
                "https://ndownloader.figshare.com.evil.test/files/123"):
        altered = copy.deepcopy(GOOD)
        altered["files"][0]["download_url"] = bad
        with pytest.raises(ValueError):
            f.qualified_detail(altered)
    alt = copy.deepcopy(GOOD)
    alt["files"][0]["size"] = f.MAX_BYTES + 1
    with pytest.raises(ValueError):
        f.qualified_detail(alt)


def test_exclude_unknown_file_formats_without_fabricating_cif():
    g = copy.deepcopy(GOOD)
    g["files"] = [{"name": "metadata.json", "download_url":"https://ndownloader.figshare.com/files/33", "size":100}]
    assert f.qualified_detail(g) == []


def test_api_endpoint_guard_does_not_allow_unapproved_requests():
    with pytest.raises(ValueError):
        f._bounded_json("https://other.example.com/v2/articles/search", {"search_for": "x"})

def test_redirect_host_gate_blocks_unrelated_cdn_before_request():
    from urllib.request import Request
    from scripts.science.obelix_supplementary_source_0154 import ScopedRedirects
    guard = ScopedRedirects()
    with pytest.raises(ValueError, match="redirect outside"):
        guard.redirect_request(
            Request("https://ndownloader.figshare.com/files/11111"),
            None, 302, "Found", {},
            "https://unknown-host.invalid/object",
        )

def test_observed_figshare_cdn_strict_exact_domain_only():
    from scripts.science.obelix_supplementary_source_0154 import checked_url, ScopedRedirects
    assert checked_url("https://s3-eu-west-1.amazonaws.com/opaque-figshare-object")
    assert not checked_url("https://s3-eu-west-1.amazonaws.com.evil.test/object")
    assert not checked_url("http://s3-eu-west-1.amazonaws.com/object")
    policy = ScopedRedirects()
    from urllib.request import Request
    redirect = policy.redirect_request(
        Request("https://ndownloader.figshare.com/files/11111"), None, 302,
        "Found", {}, "https://s3-eu-west-1.amazonaws.com/legitimate-object",
    )
    assert redirect.get_full_url().startswith("https://s3-eu-west-1.amazonaws.com/")

def test_freeze_verified_0154_real_source_identity_and_drift():
    assert f.EXPECTED_VERIFIED_SHA256["rietveld_si_pdf"] == (
        "db747a82235860cdcd21a798ad51d2fd0d22b906d3a213cd31e9ea9af72d94d3")
    assert f.EXPECTED_VERIFIED_SHA256["experimental_cif_zip"] == (
        "dc88a0a83857b172ebe7a8194eb1b50148f117d6cddb39f1adbb628ac7d1c382")
    assert len(f.EXPECTED_VERIFIED_SHA256) == 2
