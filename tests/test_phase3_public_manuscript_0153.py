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


@pytest.fixture(autouse=True)
def clear_process_source_cache():
    m._fetch_original_pdf.cache_clear()
    yield
    m._fetch_original_pdf.cache_clear()


def scripted_download(monkeypatch, events):
    import hashlib
    from urllib.error import HTTPError
    raw=b'%PDF-'+b'bounded test-only source '*10
    monkeypatch.setattr(m,'EXPECTED_MANUSCRIPT_SHA256',hashlib.sha256(raw).hexdigest())
    audits=[]
    monkeypatch.setattr(m,'audit_manuscript',lambda data:audits.append(data))
    calls=[];sleeps=[]
    class Response(io.BytesIO):
        headers={'Content-Length':str(len(raw))}
        def geturl(self):return m.URL
    class Opener:
        def open(self,*args,**kwargs):
            calls.append(True)
            event=events.pop(0)
            if isinstance(event,Exception):raise event
            return Response(raw if event is None else event)
    monkeypatch.setattr(m,'build_opener',lambda *args:Opener())
    monkeypatch.setattr(m.time,'sleep',sleeps.append)
    return raw,calls,sleeps,audits


def test_rate_limited_then_verified_source_respects_retry_after_and_reuses_only_in_process(monkeypatch):
    from urllib.error import HTTPError
    raw,calls,sleeps,audits=scripted_download(monkeypatch,[HTTPError(m.URL,429,'limited',{'Retry-After':'7'},None),None])
    assert m._fetch_original_pdf()==raw
    assert m._fetch_original_pdf()==raw
    assert len(calls)==2 and sleeps==[7] and audits==[raw]


def test_retry_after_http_date_and_no_header_fallback():
    from datetime import datetime,timezone
    now=datetime(2026,10,20,0,0,0,tzinfo=timezone.utc)
    assert m._retry_after_seconds({'Retry-After':'Tue, 20 Oct 2026 00:00:11 GMT'},0,now)==11
    assert m._retry_after_seconds({},0)==60
    assert m._retry_after_seconds({},1)==120
    with pytest.raises(ValueError):m._retry_after_seconds({'Retry-After':'invalid'},0,now)


def test_persistent_429_remains_failure_and_is_not_cached(monkeypatch):
    from urllib.error import HTTPError
    raw,calls,sleeps,audits=scripted_download(monkeypatch,[HTTPError(m.URL,429,'limited',{},None) for _ in range(3)])
    with pytest.raises(HTTPError) as error:m._fetch_original_pdf()
    assert error.value.code==429 and len(calls)==3 and sleeps==[60,120]
    assert not audits and m._fetch_original_pdf.cache_info().currsize==0


def test_provider_delay_larger_than_budget_never_gets_shortened(monkeypatch):
    from urllib.error import HTTPError
    raw,calls,sleeps,audits=scripted_download(monkeypatch,[HTTPError(m.URL,429,'limited',{'Retry-After':'3600'},None)])
    with pytest.raises(HTTPError):m._fetch_original_pdf()
    assert len(calls)==1 and sleeps==[] and audits==[]


@pytest.mark.parametrize('code',[401,403,404,500])
def test_non_rate_limit_http_errors_are_not_retried(monkeypatch,code):
    from urllib.error import HTTPError
    raw,calls,sleeps,audits=scripted_download(monkeypatch,[HTTPError(m.URL,code,'denied',{},None)])
    with pytest.raises(HTTPError):m._fetch_original_pdf()
    assert len(calls)==1 and not sleeps


def test_changed_or_incomplete_source_is_never_cached_or_retried(monkeypatch):
    raw,calls,sleeps,audits=scripted_download(monkeypatch,[b'%PDF-incorrect bytes'])
    with pytest.raises(ValueError,match='incomplete'):m._fetch_original_pdf()
    assert len(calls)==1 and not sleeps and not audits
    assert m._fetch_original_pdf.cache_info().currsize==0


def test_same_length_changed_source_fails_exact_sha_before_pdf_audit(monkeypatch):
    raw=b'%PDF-'+b'bounded test-only source '*10
    raw,calls,sleeps,audits=scripted_download(monkeypatch,[raw[:-1]+b'X'])
    with pytest.raises(ValueError,match='SHA-256'):m._fetch_original_pdf()
    assert len(calls)==1 and not sleeps and not audits


def test_tls_verification_failure_is_never_retried(monkeypatch):
    import ssl
    from urllib.error import URLError
    raw,calls,sleeps,audits=scripted_download(monkeypatch,[URLError(ssl.SSLError('identity failure'))])
    with pytest.raises(URLError):m._fetch_original_pdf()
    assert len(calls)==1 and not sleeps
