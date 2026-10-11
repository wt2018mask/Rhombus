"""0153 original PDF acquisition fail-closed and evidence scope tests."""
import io
import json
from types import SimpleNamespace

import pytest

from scripts.science import obelix_public_manuscript_0153 as m


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


def reader_with(text):
    return lambda _: SimpleNamespace(pages=[FakePage(text)])


VALID = (
    "Correlating Transport and Structural Properties in LAGP "
    "Li1+xAlxGe2-x(PO4)3 DOI 10.1021/acsami.8b00842. "
    "Experimental section. Results and Discussion. "
    "Impedance spectroscopy, synchrotron and neutron diffraction. "
    "Table 1 measured bulk conductivity S/cm by sample preparation."
)


def test_actual_document_format_and_document_scope():
    result = m.audit_manuscript(b"%PDF-" + b"x" * 128, reader_factory=reader_with(VALID))
    assert result["source_doi"] == m.DOI
    assert result["document_text_DOI_match"] is True
    assert result["text_only_context_indicators"]["impedance_method"] is True
    assert result["text_only_context_indicators"]["published_tabular_context"] is True
    assert result["full_paper_human_table_and_SI_adjudication_completed"] is False
    assert result["source_CIF_to_exact_paper_experimental_sample_matched"] == 0
    assert result["paper_measured_temperature_and_bulk_total_row_matched"] == 0
    assert result["new_independent_materials_qualified"] == 0
    assert result["scientific_GO"] is False
    assert all(result[x] == "BLOCKED" for x in ("P0_01", "P0_02", "P0_03"))
    assert not any(k in result for k in ("original_text", "raw_pdf", "raw_conductivity"))


@pytest.mark.parametrize("bad", [b"", b"not-a-pdf" * 18, b"%PDF-short"])
def test_bad_pdf_rejected(bad):
    with pytest.raises(ValueError):
        m.audit_manuscript(bad, reader_factory=reader_with(VALID))


def test_wrong_document_rejected():
    with pytest.raises(ValueError, match="DOI"):
        m.audit_manuscript(b"%PDF-" + b"x" * 128, reader_factory=reader_with(VALID.replace(m.DOI, "10.1021/wrong")))


def test_no_original_scientific_context_rejected():
    with pytest.raises(ValueError, match="scientific title"):
        m.audit_manuscript(b"%PDF-" + b"x" * 128,
                           reader_factory=reader_with("Original DOI: " + m.DOI + " " + "other " * 35))


def test_pdf_page_and_text_budget_rejected():
    too_many = lambda _: SimpleNamespace(pages=[FakePage(VALID)] * (m.MAX_PAGES + 1))
    with pytest.raises(ValueError, match="page count"):
        m.audit_manuscript(b"%PDF-" + b"x" * 128, reader_factory=too_many)
    with pytest.raises(ValueError, match="page extraction"):
        m.audit_manuscript(b"%PDF-" + b"x" * 128, reader_factory=reader_with(VALID + "x" * m.MAX_PAGE_TEXT))


@pytest.mark.parametrize("url,expected", [
    ("https://www.osti.gov/servlets/purl/1434719", True),
    ("http://www.osti.gov/servlets/purl/1434719", False),
    ("https://www.osti.gov.evil.net/servlets/purl/1434719", False),
    ("https://user:pass@www.osti.gov/servlets/purl/1434719", False),
    ("https://www.osti.gov:8443/servlets/purl/1434719", False),
])
def test_redirect_origin_gate(url, expected):
    assert m._allowed_url(url) is expected


def test_curated_prior_eight_papers_exact_doi():
    evidence = json.loads(m.PRIOR_ABSTRACT_EVIDENCE.read_text(encoding="utf-8"))
    assert m._prior_review_contains_target(evidence)
    altered = json.loads(json.dumps(evidence))
    altered["publisher_abstracts"][0]["doi"] = m.DOI
    assert not m._prior_review_contains_target(altered)
