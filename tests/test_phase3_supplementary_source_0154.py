"""0154 actual ACS SI source acquisition/censorship safety regression."""
import io
from types import SimpleNamespace
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

import pytest
from scripts.science import obelix_supplementary_source_0154 as m


def sample_zip(name="lagp-1.4.cif", text="data_lagp\n_cell_length_a 8.1\n"):
    b = io.BytesIO()
    with ZipFile(b, "w", compression=ZIP_DEFLATED) as z:
        z.writestr(name, text)
    return b.getvalue()


def test_realistic_cif_zip_census_uses_only_digest():
    data = sample_zip()
    result = m.check_cif_archive(data)
    assert result["cif_member_count"] == 1
    assert "lagp-1.4.cif" not in str(result)
    assert "data_lagp" not in str(result)
    assert result["exact_OBELiX_CIF_to_SI_member_phase_match"] == "NOT_ADJUDICATED"
    assert result["no_fractional_occupancies_rounded"] is True
    assert result["source_bytes_size"] == len(data)


@pytest.mark.parametrize("path", ["../escape.cif", "/abs.cif", r"c:\escape.cif", "bad.zip"])
def test_archive_rejects_traversal_or_nested(path):
    with pytest.raises(ValueError):
        m.check_cif_archive(sample_zip(name=path))


def test_archive_rejects_invalid_crystal():
    with pytest.raises(ValueError, match="not a crystallographic CIF"):
        m.check_cif_archive(sample_zip(text="totally false contents"))


def test_archive_rejects_zip_bomb():
    with pytest.raises(ValueError, match="expansion"):
        m.check_cif_archive(sample_zip(text="data_test\n_cell_length_a 7\n" + "x" * 200000))


def test_html_never_qualifies_as_si_pdf_or_zip():
    for role in m.ROUTES:
        x = m.assess(role, b"<html>publisher gated</html>", {
            "source_route": role, "access_state": "DOWNLOADED_UNVERIFIED",
        })
        assert x["scientifically_usable_source"] is False
        assert x["access_state"] == "SOURCE_CONTENT_REJECTED"


def test_network_denial_not_promoted_to_missing_data():
    r = m.assess("experimental_cif_zip", None, {
        "access_state": "HTTP_UNAVAILABLE",
        "source_route": "experimental_cif_zip",
        "http_status": 403,
    })
    assert not r["scientifically_usable_source"]
    assert r["http_status"] == 403
    with pytest.raises(ValueError):
        m.assess("rietveld_si_pdf", None, {
            "source_route": "rietveld_si_pdf",
            "access_state": "DOWNLOADED_UNVERIFIED",
        })


@pytest.mark.parametrize("url", [
    "http://doi.org/10.1021/acsami.8b00842.s002",
    "https://doi.org.evil.test/10.1021/acsami.8b00842.s002",
    "https://evil@doi.org/10.1021/acsami.8b00842.s002",
])
def test_invalid_network_origins_rejected(url):
    assert not m.checked_url(url)


def test_pdf_bounded_pages_only_no_measurement_claim():
    raw = b"%PDF-1.7" + b"x" * 300
    factory = lambda fp: SimpleNamespace(pages=[object(), object()])
    d = m.check_source_pdf(raw, reader_factory=factory)
    assert d["pages_structurally_decoded"] == 2
    assert d["text_or_tables_human_adjudicated"] is False
