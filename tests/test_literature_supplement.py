"""Synthetic transport/PDF fixtures plus a real derived bbox regression extract.

The bbox fixture alone does not authenticate raw PDF bytes or qualify labels.
"""
import hashlib
import io
import ssl
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError

import pytest

from rhombus.literature import harvest, supplement as s


class Response(io.BytesIO):
    status = 200

    def __init__(self, data=b'%PDF-example', *, url=s.PDF_URL, headers=None):
        super().__init__(data)
        self.url = url
        self.headers = headers if headers is not None else {'Content-Type': 'application/pdf'}

    def geturl(self):
        return self.url


def install_opener(monkeypatch, actions):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            action = actions.pop(0)
            if isinstance(action, Exception):
                raise action
            return action

    monkeypatch.setattr(s, 'build_opener', lambda handler: Opener())
    return calls


def test_bounded_stream_keeps_hash_without_claiming_pdf_verification(monkeypatch, tmp_path):
    raw = b'%PDF-' + b'x' * (s.CHUNK_BYTES * 3)
    calls = install_opener(monkeypatch, [Response(raw, headers={
        'Content-Type': 'application/pdf', 'Content-Length': str(len(raw))})])
    event = {}
    target = s.stream_source(s.PDF_URL, 'pdf', tmp_path/'raw', event)
    assert target.read_bytes() == raw
    assert event['sha256'] == hashlib.sha256(raw).hexdigest()
    assert event['complete_body'] and not event['source_verified']
    assert len(calls) == 1 and calls[0][1] <= 30
    assert calls[0][0].get_header('Accept-encoding') == 'identity'
    assert harvest.MAX_BYTES == 8_000_000
    assert s.PDF_MAX_BYTES == 40 * 1024 * 1024


@pytest.mark.parametrize('url', [
    s.PDF_URL.replace('https:', 'http:'),
    s.PDF_URL.replace('static-content.springer-cdn.com', 'evil.example'),
    s.PDF_URL.replace('https://', 'https://user:password@'),
    s.PDF_URL + '?download=other',
    s.PDF_URL.replace('MOESM1', 'MOESM2'),
    s.PDF_URL.replace('.com/', '.com:8443/'),
    s.ARCHIVE_URL,
])
def test_unapproved_initial_url_never_contacts_network(monkeypatch, tmp_path, url):
    calls = install_opener(monkeypatch, [])
    with pytest.raises(ValueError, match='unapproved'):
        s.stream_source(url, 'pdf', tmp_path/'raw', {})
    assert not calls and not (tmp_path/'raw').exists()


def redirect(url):
    return HTTPError(s.PDF_URL, 302, 'redirect', {'Location': url}, io.BytesIO())


def test_publisher_redirect_is_verified_before_second_request(monkeypatch, tmp_path):
    calls = install_opener(monkeypatch, [redirect(s.MEDIA_URL), Response(url=s.MEDIA_URL)])
    event = {}
    s.stream_source(s.PDF_URL, 'pdf', tmp_path/'raw', event)
    assert len(calls) == 2 and event['final_url'] == s.MEDIA_URL
    assert event['redirects'] == [{'from': s.PDF_URL, 'to': s.MEDIA_URL}]


@pytest.mark.parametrize('target', ['http://media.springernature.com/file',
                                 'https://evil.example/file',
                                 s.MEDIA_URL.replace('MOESM1', 'MOESM5')])
def test_unapproved_redirect_never_followed(monkeypatch, tmp_path, target):
    calls = install_opener(monkeypatch, [redirect(target)])
    with pytest.raises(ValueError, match='unapproved'):
        s.stream_source(s.PDF_URL, 'pdf', tmp_path/'raw', {})
    assert len(calls) == 1


def test_redirect_loop_is_bounded(monkeypatch, tmp_path):
    calls = install_opener(monkeypatch, [redirect(s.PDF_URL) for _ in range(4)])
    with pytest.raises(ValueError, match='redirect budget'):
        s.stream_source(s.PDF_URL, 'pdf', tmp_path/'raw', {})
    assert len(calls) == 4


@pytest.mark.parametrize('headers', [
    {'Content-Type': 'text/html'},
    {'Content-Type': 'application/pdf', 'Content-Encoding': 'gzip'},
    {'Content-Type': 'application/pdf', 'Content-Length': '-1'},
    {'Content-Type': 'application/pdf', 'Content-Length': str(s.PDF_MAX_BYTES+1)},
    {'Content-Type': 'application/pdf', 'Content-Length': '500'},
])
def test_invalid_headers_or_truncation_remove_output(monkeypatch, tmp_path, headers):
    install_opener(monkeypatch, [Response(headers=headers)])
    event = {}
    with pytest.raises(ValueError):
        s.stream_source(s.PDF_URL, 'pdf', tmp_path/'raw', event)
    assert not (tmp_path/'raw').exists() and event['sha256'] is None
    assert not event['complete_body'] and not event['source_verified']


def test_chunked_oversize_detected_without_content_length(monkeypatch, tmp_path):
    monkeypatch.setattr(s, 'PDF_MAX_BYTES', 10)
    install_opener(monkeypatch, [Response(b'x' * 100)])
    event = {}
    with pytest.raises(ValueError, match='byte budget'):
        s.stream_source(s.PDF_URL, 'pdf', tmp_path/'raw', event)
    assert event['bytes'] == 11 and not (tmp_path/'raw').exists()


@pytest.mark.parametrize('error', [
    URLError('Tunnel connection failed: 403 Forbidden'),
    URLError(ssl.SSLCertVerificationError('certificate failed')),
    TimeoutError('read timed out'),
    HTTPError(s.PDF_URL, 403, 'denied', {}, io.BytesIO()),
    HTTPError(s.PDF_URL, 429, 'rate limited', {}, io.BytesIO()),
])
def test_access_tls_timeout_fail_without_retries(monkeypatch, tmp_path, error):
    calls = install_opener(monkeypatch, [error])
    event = {}
    with pytest.raises(type(error)):
        s.stream_source(s.PDF_URL, 'pdf', tmp_path/'raw', event)
    assert len(calls) == 1 and not event['source_verified']
    assert event['sha256'] is None and not (tmp_path/'raw').exists()


def test_total_deadline_removes_partial_body(monkeypatch, tmp_path):
    clock = [0.0]
    monkeypatch.setattr(s.time, 'monotonic', lambda: clock[0])

    class Slow(Response):
        def read(self, n):
            clock[0] += s.TOTAL_SECONDS + 1
            return super().read(n)

    install_opener(monkeypatch, [Slow()])
    with pytest.raises(TimeoutError):
        s.stream_source(s.PDF_URL, 'pdf', tmp_path/'raw', {})
    assert not (tmp_path/'raw').exists()


def test_partial_timeout_and_existing_file_are_preserved_correctly(monkeypatch, tmp_path):
    class Broken(Response):
        def read(self, n):
            if self.tell():
                raise TimeoutError('read timed out')
            return super().read(5)

    install_opener(monkeypatch, [Broken()])
    with pytest.raises(TimeoutError):
        s.stream_source(s.PDF_URL, 'pdf', tmp_path/'raw', {})
    assert not (tmp_path/'raw').exists()
    (tmp_path/'raw').write_bytes(b'existing evidence')
    with pytest.raises(FileExistsError):
        s.stream_source(s.PDF_URL, 'pdf', tmp_path/'raw', {})
    assert (tmp_path/'raw').read_bytes() == b'existing evidence'


def make_pdf(path, *, title=s.TITLE, table='Supplementary Table 5', encrypted=False):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
        DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    content = DecodedStreamObject()
    content.set_data(f'BT /F1 10 Tf 10 700 Td ({title}) Tj 0 -20 Td '
                     f'(Supplementary Information) Tj 0 -20 Td ({table}) Tj ET'.encode())
    page[NameObject('/Contents')] = writer._add_object(content)
    if encrypted:
        writer.encrypt('fixture-password')
    writer.write(path)


def test_complete_pdf_integrity_identity_is_not_cell_authentication(tmp_path):
    path = tmp_path/'fixture.pdf'
    make_pdf(path)
    result = s.validate_pdf(path)
    assert result['pdf_integrity_verified'] and result['cover_title_verified']
    assert result['table_5_candidate_pages'] == [1]
    assert not result['table_cells_verified'] and result['strict_qualified_rows'] == 0
    assert result['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('kwargs', [{'title': 'different study'}, {'table': 'Table 6'},
                                    {'encrypted': True}])
def test_pdf_wrong_identity_missing_table_and_encryption_denied(tmp_path, kwargs):
    path = tmp_path/'fixture.pdf'
    make_pdf(path, **kwargs)
    with pytest.raises(ValueError):
        s.validate_pdf(path)


@pytest.mark.parametrize('mutation', ['truncate', 'html', 'xref'])
def test_malformed_pdf_denied(tmp_path, mutation):
    path = tmp_path/'fixture.pdf'
    make_pdf(path)
    raw = path.read_bytes()
    if mutation == 'truncate': raw = raw[:-10]
    if mutation == 'html': raw = b'<html>denied</html>'
    if mutation == 'xref': raw = raw.replace(b'startxref\n', b'startxref\n999999999')
    path.write_bytes(raw)
    with pytest.raises(Exception):
        s.validate_pdf(path)


def test_archive_reads_only_exact_member_without_extracting_paths(tmp_path):
    archive = tmp_path/'bundle.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('../folder/'+s.FILENAME, b'pdf bytes for later verification')
        bundle.writestr('other.pdf', b'wrong source')
    out = s.select_archive_pdf(archive, tmp_path/'selected.pdf')
    assert out.read_bytes() == b'pdf bytes for later verification'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['bundle.zip','selected.pdf']


@pytest.mark.parametrize('names', [[], ['other.pdf'], [s.FILENAME, 'other/'+s.FILENAME]])
def test_archive_missing_or_ambiguous_filename_denied(tmp_path, names):
    archive = tmp_path/'bundle.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        for name in names: bundle.writestr(name, b'fixture')
    with pytest.raises(ValueError, match='missing or ambiguous'):
        s.select_archive_pdf(archive, tmp_path/'selected.pdf')
    assert not (tmp_path/'selected.pdf').exists()


def test_archive_expanded_size_denied(monkeypatch, tmp_path):
    archive = tmp_path/'bundle.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(s.FILENAME, b'x' * 1000)
    monkeypatch.setattr(s, 'PDF_MAX_BYTES', 100)
    with pytest.raises(ValueError, match='oversized'):
        s.select_archive_pdf(archive, tmp_path/'selected.pdf')


def test_article_hash_cannot_be_replaced_by_doi_in_arbitrary_xml():
    with pytest.raises(ValueError, match='hash mismatch'):
        s.authenticate_article(f'<article>{s.DOI}</article>'.encode())


BBOX = Path(__file__).resolve().parents[1]/'data/development/table5_74887_bbox_20261020_v1.xml'


def test_original_derived_bbox_preserves_sample_continuation_and_no_conductivity():
    rows = s.parse_impedance_bbox(BBOX.read_bytes())
    assert len(rows) == 24
    last_r1, = [r for r in rows if r['sample']=='Annealed SF-LLZO' and r['parameter']=='R1']
    assert last_r1['page'] == 37 and last_r1['fit_value'] == 35.3
    assert all(r['conductivity_S_cm'] is None and r['reported_unit'] is None
               and not r['strict_qualified'] for r in rows)
    assert [sum(r['sample']==sample for r in rows)
            for sample in ('S-LLZO','SF-LLZO','Annealed SF-LLZO')] == [9,6,9]


@pytest.mark.parametrize('old,new', [
    (b'>471<',b'>537<'), (b'>SF-LLZO<',b'>S-LLZO<'),
    (b'>values<',b'>values (S/cm)<'),
    (b'>8.05E-11<',b'>8.05E11<'), (b'>0.96%<',b'>96%<'),
    (b'>Annealed<',b'>Independent<'), (b'>35.3<',b'>25.5<'),
])
def test_changed_fit_cell_sample_unit_and_errors_fail_closed(old,new):
    raw = BBOX.read_bytes()
    assert old in raw
    with pytest.raises(ValueError):
        s.parse_impedance_bbox(raw.replace(old,new))


def test_swapping_values_between_samples_is_rejected():
    raw = BBOX.read_bytes().replace(b'>471<',b'>TEMP<').replace(b'>537<',b'>471<').replace(b'>TEMP<',b'>537<')
    with pytest.raises(ValueError, match='keyed fit cells'):
        s.parse_impedance_bbox(raw)


def test_ambiguous_column_position_or_missing_cell_is_rejected():
    root = ET.fromstring(BBOX.read_bytes())
    line, = [l for l in root.findall('.//line') if ''.join(l.itertext()).strip()=='52.1']
    line.set('xMin','200')
    with pytest.raises(ValueError, match='missing or ambiguous'):
        s.parse_impedance_bbox(ET.tostring(root))


def test_different_raw_pdf_cannot_use_reviewed_bbox(tmp_path):
    path=tmp_path/'fake.pdf';path.write_bytes(b'%PDF-fake')
    with pytest.raises(ValueError, match='original source'):
        s.extract_impedance_cells(path)


def test_archive_replay_rejects_non_complete_receipt(tmp_path):
    with pytest.raises(ValueError, match='receipt'):
        s.verify_retained_archive(tmp_path/'missing.zip', {'event':{'url':s.ARCHIVE_URL}}, tmp_path/'out')


def test_scientific_receipt_binds_real_extract_and_keeps_missing_conditions_unknown():
    import json
    report = json.loads((BBOX.parent/'supplementary_table5_74887_20261020_v1.json').read_text())
    for name, digest in report['artifact_bindings'].items():
        assert hashlib.sha256((BBOX.parents[2]/name).read_bytes()).hexdigest() == digest
    expected = s.parse_impedance_bbox(BBOX.read_bytes())
    for actual, cell in zip(report['extraction']['cells'],expected,strict=True):
        assert all(actual[k]==v for k,v in cell.items())
        assert actual['sample_context_ref'] in report['sample_contexts']
        assert actual['measurement_temperature_C'] == 25
        assert actual['reported_unit'] is None and actual['conductivity_S_cm'] is None
    sf = report['sample_contexts']['SF-LLZO']
    assert sf['processing_pressure_MPa']==53 and sf['green_press_MPa']==50
    assert sf['fixed_peak_temperature_C'] is None and sf['fixed_hold_min'] is None
    assert report['qualification']['new_strict_qualified_doi_groups']==0
    assert report['qualification']['new_strict_manufacturing_comparisons']==0
    assert not report['qualification']['independent_blind_evaluation']
