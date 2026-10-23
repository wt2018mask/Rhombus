"""Fixed-source, bounded SI acquisition for DOI 10.1038/s41467-026-74887-z.

Acquisition and PDF identity are separate from scientific table qualification.
No table values are guessed and this module never admits measurement rows.
Uses the inherited HTTPS proxy and default TLS trust; no access-control retries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .harvest import inspect_jats

DOI = '10.1038/s41467-026-74887-z'
PMCID = 'PMC13490533'
TITLE = 'Elimination of detrimental grain boundary segregation in garnets'
JATS_SHA256 = '34442ba7d2b6509701ba0347f249ed0fe275b7c2d0350c12b40264f4c1eb123d'
FILENAME = '41467_2026_74887_MOESM1_ESM.pdf'
PDF_SHA256 = '20b2410bb9f2c4188b0f9e8ffe3215a2c27053f7af97151ee64fff687a2d601a'
ARTICLE_URL = 'https://www.nature.com/articles/s41467-026-74887-z'
ESM_PATH = '/esm/art%3A10.1038%2Fs41467-026-74887-z/MediaObjects/' + FILENAME
PDF_URL = 'https://static-content.springer-cdn.com' + ESM_PATH
MEDIA_URL = 'https://media.springernature.com/full/springer-static' + ESM_PATH
ARCHIVE_URL = 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13490533/supplementaryFiles'
PDF_MAX_BYTES = 40 * 1024 * 1024
ARCHIVE_MAX_BYTES = 80 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
SOCKET_TIMEOUT = 30
TOTAL_SECONDS = 180


def authenticate_article(raw):
    """Bind the filename to the retained original article, not a guessed DOI URL."""
    if hashlib.sha256(raw).hexdigest() != JATS_SHA256:
        raise ValueError('retained article hash mismatch')
    inspect_jats(raw, DOI, PMCID)
    root = ET.fromstring(raw)
    media = root.findall(".//supplementary-material[@id='MOESM1']/media")
    if (len(media) != 1 or media[0].get('{http://www.w3.org/1999/xlink}href') != FILENAME
            or ''.join(media[0].itertext()).strip() != 'Supplementary Information'):
        raise ValueError('supplement filename/caption binding mismatch')
    return {'doi': DOI, 'pmcid': PMCID, 'jats_sha256': JATS_SHA256,
            'supplement_id': 'MOESM1', 'filename': FILENAME}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_url(url, kind):
    allowed = {'article': {ARTICLE_URL}, 'pdf': {PDF_URL, MEDIA_URL},
               'archive': {ARCHIVE_URL}}[kind]
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.port not in (None, 443) or url not in allowed):
        raise ValueError('unapproved source URL or redirect')


def stream_source(url, kind, destination, event):
    """Stream to a new local-only file; failed/partial bodies are never retained.

    Exact URL allowlists are checked before every request including redirects.
    The larger caps are reachable only for this DOI's fixed SI resources.
    At most four HTTPS requests, 30 s socket timeout and 180 s total budget.
    """
    cap = {'article': 2_000_000, 'pdf': PDF_MAX_BYTES, 'archive': ARCHIVE_MAX_BYTES}[kind]
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    event.update(url=url, kind=kind, max_bytes=cap, redirects=[],
                 started_utc=datetime.now(timezone.utc).isoformat(),
                 complete_body=False, source_verified=False, bytes=0, sha256=None)
    started = time.monotonic()
    digest = hashlib.sha256()
    opener = build_opener(_NoRedirect())
    written = False
    try:
        for redirect_count in range(4):
            _validate_url(url, kind)
            remaining = TOTAL_SECONDS - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError('total acquisition deadline')
            request = Request(url, headers={'User-Agent': 'Rhombus-literature-research/0.1',
                                           'Accept-Encoding': 'identity'})
            try:
                response = opener.open(request, timeout=min(SOCKET_TIMEOUT, remaining))
            except HTTPError as exc:
                event['http_status'] = exc.code
                if exc.code not in (301, 302, 303, 307, 308):
                    exc.close()
                    raise
                location = exc.headers.get('Location')
                exc.close()
                if not location or redirect_count == 3:
                    raise ValueError('missing redirect target or redirect budget exceeded')
                new = urljoin(url, location)
                # Verify before contacting the redirect target, even for HTTPS.
                _validate_url(new, kind)
                event['redirects'].append({'from': url, 'to': new})
                url = new
                continue
            with response:
                if response.status != 200 or response.geturl() != url:
                    raise ValueError('unexpected response status or URL')
                event.update(http_status=response.status, final_url=url)
                if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                    raise ValueError('encoded response denied')
                mime = response.headers.get('Content-Type', '').split(';')[0].lower().strip()
                expected = {'article': {'text/html'}, 'pdf': {'application/pdf'},
                            'archive': {'application/zip', 'application/x-zip-compressed'}}[kind]
                if mime not in expected:
                    raise ValueError('unexpected source content type')
                length = response.headers.get('Content-Length')
                if length is not None and (not re.fullmatch(r'[0-9]+', length)
                                           or not 0 < int(length) <= cap):
                    raise ValueError('invalid or excessive Content-Length')
                event.update(content_type=mime, declared_bytes=int(length) if length else None)
                with destination.open('xb') as output:
                    written = True
                    while True:
                        if time.monotonic() - started >= TOTAL_SECONDS:
                            raise TimeoutError('total acquisition deadline')
                        block = response.read(min(CHUNK_BYTES, cap - event['bytes'] + 1))
                        if time.monotonic() - started >= TOTAL_SECONDS:
                            raise TimeoutError('total acquisition deadline')
                        if not block:
                            break
                        event['bytes'] += len(block)
                        if event['bytes'] > cap:
                            raise ValueError('stream exceeds source-specific byte budget')
                        digest.update(block)
                        output.write(block)
                if not event['bytes'] or (length is not None and event['bytes'] != int(length)):
                    raise ValueError('empty or truncated response')
                event.update(complete_body=True, sha256=digest.hexdigest())
                return destination
        raise ValueError('redirect budget exceeded')
    except Exception as exc:
        if written:
            destination.unlink(missing_ok=True)
        event['failure_type'] = type(exc).__name__
        # Do not serialize arbitrary URLs or proxy headers from exception strings.
        if isinstance(exc, URLError):
            event['failure_detail'] = ('PROXY_CONNECT_403' if
                'Tunnel connection failed: 403 Forbidden' in str(exc.reason) else type(exc.reason).__name__)
        elif isinstance(exc, (ValueError, TimeoutError)):
            event['failure_detail'] = str(exc)
        raise
    finally:
        event['duration_seconds'] = round(time.monotonic() - started, 4)


def validate_pdf(path):
    """Check actual complete PDF objects and SI identity; does not parse table cells."""
    from pypdf import PdfReader
    path = Path(path)
    size = path.stat().st_size
    if not 0 < size <= PDF_MAX_BYTES:
        raise ValueError('PDF size outside fixed-source budget')
    with path.open('rb') as stream:
        if stream.read(5) != b'%PDF-':
            raise ValueError('not a PDF')
        stream.seek(max(0, size - 1024))
        if not stream.read().rstrip().endswith(b'%%EOF'):
            raise ValueError('PDF lacks terminal EOF')
        stream.seek(0)
        reader = PdfReader(stream, strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 250:
            raise ValueError('encrypted PDF or page budget exceeded')
        # Decode all page-content streams, without expensive text interpretation
        # of every vector plot. Table 5 in this fixed SI spans pages 37--38.
        # Cover/target extraction stays separate from visual cell adjudication.
        decoded = 0
        for page in reader.pages:
            content = page.get_contents()
            decoded += len(content.get_data()) if content is not None else 0
            if decoded > 128 * 1024 * 1024:
                raise ValueError('PDF decoded-content budget exceeded')
        page_count = len(reader.pages)
        targets = sorted({0, *[i for i in (36, 37) if i < page_count]})
        texts = {i + 1: reader.pages[i].extract_text() or '' for i in targets}
        if sum(map(len, texts.values())) > 2_000_000:
            raise ValueError('PDF text budget exceeded')
    first = re.sub(r'\s+', ' ', texts[1]).casefold()
    if TITLE.casefold() not in first or 'supplementary' not in first:
        raise ValueError('SI cover title/source identity mismatch')
    tables = [i for i, text in texts.items()
              if re.search(r'Supplementary\s+Tab(?:le|\.)\s+5\b', text, re.I)]
    if not tables:
        raise ValueError('Supplementary Table 5 not found in PDF text')
    return {'bytes': size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'pages': page_count, 'table_5_candidate_pages': tables,
            'pdf_integrity_verified': True, 'cover_title_verified': True,
            'table_cells_verified': False, 'strict_qualified_rows': 0}


def select_archive_pdf(archive, destination):
    """Read only the exact linked basename, with member/expanded-byte bounds."""
    archive = Path(archive)
    if archive.stat().st_size > ARCHIVE_MAX_BYTES:
        raise ValueError('archive exceeds source-specific budget')
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if len(members) > 100 or sum(x.file_size for x in members) > 128 * 1024 * 1024:
            raise ValueError('archive member or expanded-byte budget exceeded')
        matches = [x for x in members if Path(x.filename).name == FILENAME]
        if len(matches) != 1:
            raise ValueError('missing or ambiguous linked supplementary PDF')
        member = matches[0]
        if (member.flag_bits & 1 or not 0 < member.file_size <= PDF_MAX_BYTES
                or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
            raise ValueError('unsupported or oversized archive member')
        destination = Path(destination)
        written = False
        try:
            with bundle.open(member) as source, destination.open('xb') as output:
                written = True
                count = 0
                while block := source.read(CHUNK_BYTES):
                    count += len(block)
                    if count > PDF_MAX_BYTES:
                        raise ValueError('expanded PDF byte budget exceeded')
                    output.write(block)
            if count != member.file_size:
                raise ValueError('archive PDF length mismatch')
        except Exception:
            if written:
                destination.unlink(missing_ok=True)
            raise
    return destination


def verify_retained_archive(archive, receipt, destination):
    """Replay original HTTPS bytes after an extraction failure; no fresh GET claim."""
    event = receipt['event']
    if (event.get('url') != ARCHIVE_URL or event.get('final_url') != ARCHIVE_URL
            or event.get('http_status') != 200 or not event.get('complete_body')
            or event.get('content_type') != 'application/zip'
            or event.get('article', {}).get('jats_sha256') != JATS_SHA256):
        raise ValueError('unverified archive acquisition receipt')
    archive = Path(archive)
    if (archive.stat().st_size != event['bytes'] or archive.stat().st_size > ARCHIVE_MAX_BYTES
            or hashlib.sha256(archive.read_bytes()).hexdigest() != event['sha256']):
        raise ValueError('retained archive differs from original HTTPS body')
    path = select_archive_pdf(archive, destination)
    result = validate_pdf(path)
    if result['sha256'] != PDF_SHA256:
        raise ValueError('retained PDF differs from visually reviewed source')
    return {'operational_status': 'REPLAY_ACQUIRED_PENDING_TABLE_REVIEW',
            'fresh_network_request': False, 'original_event': event,
            'pdf': result, 'source_verified': True}


def parse_impedance_bbox(raw):
    """Read fixed, visually adjudicated cell regions, never conductivity labels.

    Coordinates are Poppler points on pages 37--38 of PDF_SHA256. The page-37
    R1 at y=737 belongs to the annealed sample continued on page 38. This
    explicit visual adjudication prevents a preceding-label forward fill.
    """
    root = ET.fromstring(raw)
    pages = root.findall('.//{*}page')
    if len(pages) != 2 or any(abs(float(p.get('width')) - 595.5) > .1 or
                             abs(float(p.get('height')) - 842) > .1 for p in pages):
        raise ValueError('unexpected table page geometry')
    lines = []
    for number, page in enumerate(pages, 37):
        for line in page.findall('.//{*}line'):
            lines.append({'page': number, 'text': ' '.join(w.text or '' for w in line.findall('{*}word')),
                          'bbox': [float(line.get(k)) for k in ('xMin','yMin','xMax','yMax')]})

    def label(text, page, x, y):
        return any(l['page'] == page and l['text'] == text and
                   abs(l['bbox'][0]-x) < 1 and abs(l['bbox'][1]-y) < 1 for l in lines)

    required = [('Samples',37,178.65,417.92), ('Elements',37,294.75,417.92),
                ('Fit values',37,342.3,417.92), ('Fit errors',37,390.33,417.92),
                ('S-LLZO',37,173.15,494.46), ('SF-LLZO',37,177.65,652.57),
                ('Annealed',38,177.65,110.25), ('SF-LLZO',38,177.65,125.75)]
    if not all(label(*args) for args in required):
        raise ValueError('table header or sample-label binding mismatch')
    rows = []
    for line in lines:
        page, (x,y,_,_) = line['page'], line['bbox']
        if not 289 < x < 306 or not re.fullmatch(r'R[123]|CPE (?:Q|Alpha)[123]', line['text']):
            continue
        if page == 37 and 440 < y < 615: sample = 'S-LLZO'
        elif page == 37 and 615 < y < 730: sample = 'SF-LLZO'
        elif (page == 37 and 730 < y < 750) or (page == 38 and 70 < y < 220): sample = 'Annealed SF-LLZO'
        else: continue
        cells = []
        for lo,hi in [(340,375),(390,420)]:
            matches = [l for l in lines if l['page'] == page and lo < l['bbox'][0] < hi
                       and abs(l['bbox'][1]-y) < .5]
            if len(matches) != 1:
                raise ValueError('missing or ambiguous fit cell')
            cells.append(matches[0])
        value,error = (c['text'] for c in cells)
        if not re.fullmatch(r'\d+(?:\.\d+)?(?:E-\d+)?',value) or not re.fullmatch(r'\d+(?:\.\d+)?%',error):
            raise ValueError('unsupported fit value/error notation')
        rows.append({'sample':sample, 'parameter':line['text'], 'fit_value_text':value,
                     'fit_error_text':error, 'fit_value':float(value),
                     'fit_error_percent':float(error[:-1]), 'page':page,
                     'element_bbox':line['bbox'], 'value_bbox':cells[0]['bbox'],
                     'error_bbox':cells[1]['bbox'], 'source_pdf_sha256':PDF_SHA256,
                     'table':'Supplementary Tab. 5', 'observable_type':'IMPEDANCE_FIT_PARAMETER',
                     'reported_unit':None, 'conductivity_S_cm':None,
                     'strict_qualified':False})
    expected = {
        'S-LLZO': [('R1','52.1','8.8%'),('R2','471','1.5%'),('CPE Q1','8.05E-11','15%'),
                   ('CPE Alpha1','1','0.96%'),('R3','86.2','14%'),('CPE Q2','3.64E-8','20%'),
                   ('CPE Alpha2','0.958','6.7%'),('CPE Q3','3.99E-6','13%'),('CPE Alpha3','0.634','2.2%')],
        'SF-LLZO': [('R1','25.5','5.4%'),('R2','537','2.6%'),('CPE Q1','4.57E-11','13%'),
                    ('CPE Alpha1','0.984','1%'),('CPE Q2','3.91E-6','2.5%'),('CPE Alpha2','0.735','0.4%')],
        'Annealed SF-LLZO': [('R1','35.3','13%'),('R2','447','1.6%'),('CPE Q1','8.7E-11','15%'),
                    ('CPE Alpha1','0.994','0.97%'),('R3','104','4.5%'),('CPE Q2','1.98E-8','38%'),
                    ('CPE Alpha2','0.977','3.2%'),('CPE Q3','1.26E-6','2.2%'),('CPE Alpha3','0.782','0.33%')]}
    # Compare only after independent geometric cell association.
    observed = {key: [(r['parameter'],r['fit_value_text'],r['fit_error_text'])
                      for r in rows if r['sample']==key] for key in expected}
    if len(rows) != 24 or observed != expected:
        raise ValueError('keyed fit cells differ from visually reviewed original table')
    return rows


def extract_impedance_cells(path):
    """Extract from actual frozen PDF bytes with a bounded Poppler subprocess."""
    path = Path(path)
    if path.stat().st_size > PDF_MAX_BYTES or hashlib.sha256(path.read_bytes()).hexdigest() != PDF_SHA256:
        raise ValueError('PDF does not match visually reviewed original source')
    with tempfile.TemporaryDirectory() as scratch:
        bbox = Path(scratch)/'table.html'
        subprocess.run(['pdftotext','-f','37','-l','38','-bbox-layout',str(path),str(bbox)],
                       check=True, timeout=30, capture_output=True)
        if bbox.stat().st_size > 1_000_000:
            raise ValueError('bbox extraction exceeds byte budget')
        raw = bbox.read_bytes()
    return {'bbox_sha256':hashlib.sha256(raw).hexdigest(),
            'cells':parse_impedance_bbox(raw), 'new_strict_qualified_doi_groups':0,
            'new_strict_manufacturing_comparisons':0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--article-jats', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--source', choices=('publisher', 'archive'), required=True)
    args = parser.parse_args()
    identity = authenticate_article(args.article_jats.read_bytes())
    args.output_dir.mkdir()  # New directory only; never overwrite source evidence.
    event = {'article': identity}
    report = {'schema_version': 'rhombus-fixed-supplement-acquisition-v1',
              'event': event, 'new_strict_qualified_doi_groups': 0,
              'new_strict_manufacturing_comparisons': 0, 'scientific_GO': False}
    try:
        with tempfile.TemporaryDirectory(dir=args.output_dir) as scratch:
            path = Path(scratch) / ('archive.zip' if args.source == 'archive' else FILENAME)
            stream_source(ARCHIVE_URL if args.source == 'archive' else PDF_URL,
                          'archive' if args.source == 'archive' else 'pdf', path, event)
            if args.source == 'archive':
                path = select_archive_pdf(path, Path(scratch) / FILENAME)
            report['pdf'] = validate_pdf(path)
            # Retain raw bytes only after PDF identity and integrity succeed.
            path.rename(args.output_dir / FILENAME)
            event['source_verified'] = True
            report['operational_status'] = 'ACQUIRED_PENDING_TABLE_REVIEW'
    except Exception as exc:
        report.update(operational_status='BLOCKED', verification_failure=type(exc).__name__)
    (args.output_dir / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if event['source_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
