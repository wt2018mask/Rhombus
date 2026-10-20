"""Bounded public scholarly-API intake; no inferred experimental measurements.

Discovery metadata is not original experimental evidence. Generic JATS table
cells are retained as exploratory candidates; a narrow explicit row schema and
registered source-specific parsers extract source-bound measurements. No model fitting or TEST access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOSTS = {'api.crossref.org', 'api.openalex.org', 'www.ebi.ac.uk'}
MAX_BYTES = 8_000_000
QUERIES = ('oxide solid electrolyte ionic conductivity sintering',
           'lithium garnet hot pressing processing conductivity')
API_DOCS = {
    'crossref': 'https://www.crossref.org/documentation/retrieve-metadata/rest-api/',
    'openalex': 'https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication',
    'europepmc': 'https://europepmc.org/RestfulWebService',
}


def normalize_doi(value):
    value = str(value or '').strip().lower()
    value = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', value)
    if not re.fullmatch(r'10\.\d{4,9}/[^\s<>]+', value):
        raise ValueError('invalid DOI')
    return value


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


class _PinnedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        if (new.scheme != 'https' or new.hostname != old.hostname or
                new.username or new.password or new.port not in (None, 443)):
            raise ValueError('cross-host or insecure redirect denied')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PublicClient:
    """Serial, rate-bounded requests; no credentials, retries or paid endpoints."""
    def __init__(self, directory, interval=10.0):
        if interval < 1:
            raise ValueError('request interval must be at least one second')
        self.directory = Path(directory)
        self.directory.mkdir()
        self.interval = interval
        self.last = 0.0
        self.events = []

    def fetch(self, url):
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in HOSTS or
                parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError('endpoint outside public API allowlist')
        time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
        event = {'url': url, 'started_utc': datetime.now(timezone.utc).isoformat()}
        self.last = time.monotonic()
        try:
            with build_opener(_PinnedRedirect()).open(Request(url, headers={
                'User-Agent': 'Rhombus-literature-research/0.1',
                'Accept': 'application/json, application/xml'}), timeout=30) as response:
                if response.geturl() != url:
                    raise ValueError('API response URL changed')
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError('response exceeds byte budget')
                event.update(http_status=response.status, bytes=len(raw), sha256=_digest(raw))
                # Local cache only. Never include raw full text in a commit.
                target = self.directory / event['sha256']
                if not target.exists():
                    with target.open('xb') as stream:
                        stream.write(raw)
                return raw
        except HTTPError as exc:
            event.update(http_status=exc.code, failure='HTTP_UNAVAILABLE')
            raise
        except URLError as exc:
            event.update(failure=type(exc.reason).__name__)
            raise
        except (ValueError, TimeoutError) as exc:
            event.update(failure=type(exc).__name__)
            raise
        finally:
            event['duration_seconds'] = round(time.monotonic() - self.last, 4)
            self.events.append(event)



def classify_title(title):
    """Acquisition prioritization only; never certifies elemental composition."""
    if re.search(r'\breview\b|polymer|sulfide|sulphide|Li[₆6]PS|sodium|zinc|hydrogel|biopolymer', title, re.I):
        return 'OUTSIDE_PILOT_PRIORITY'
    if re.search(r'garnet|LLZO|LLTO|LATP|LAGP|Li[₇7]La[₃3]Zr|lithium.*(?:oxide|NASICON)', title, re.I):
        return 'OXIDE_CANDIDATE_NOT_COMPOSITION_CERTIFIED'
    return 'UNVERIFIED_RELEVANCE'

def parse_discovery(provider, raw):
    """Normalize metadata, keeping provider assertions and cursor provenance."""
    doc = json.loads(raw)
    result = []
    if provider == 'crossref':
        items = doc['message']['items']
        cursor = doc['message'].get('next-cursor')
    elif provider == 'openalex':
        items = doc['results']
        cursor = doc['meta'].get('next_cursor')
    elif provider == 'europepmc':
        items = doc['resultList']['result']
        cursor = doc.get('nextCursorMark')
    else:
        raise ValueError('unsupported metadata provider')
    for item in items:
        try:
            doi = normalize_doi(item.get('DOI') or item.get('doi'))
        except ValueError:
            result.append({'rejection': 'MISSING_OR_INVALID_DOI', 'provider': provider})
            continue
        title = item.get('title') or ''
        if isinstance(title, list):
            title = ' '.join(title)
        review = bool(re.search(r'\breview\b|meta.analysis', title, re.I))
        types = item.get('pubTypeList', {}).get('pubType', [])
        review = review or any('review' in t.lower() for t in types)
        pmcid = item.get('pmcid')
        if pmcid and not re.fullmatch(r'PMC\d+', pmcid):
            pmcid = None
        result.append({'doi': doi, 'title': title, 'provider': provider,
                       'provider_record_id': item.get('id') or doi,
                       'metadata_sha256': _digest(raw), 'pmcid': pmcid,
                       'open_access_asserted': item.get('isOpenAccess') == 'Y',
                       'original_study_status': 'REVIEW_EXCLUDED' if review else 'UNVERIFIED',
                       'title_relevance': classify_title(title),
                       'independent_author_study_verified': False})
    return result, cursor


def discover_publications(client, target=1000):
    if not 1 <= target <= 1000:
        raise ValueError('discovery target must be 1..1000')
    records, failures = {}, []
    for provider in ('europepmc', 'crossref', 'openalex'):
        cursor = '*'
        seen_cursors = set()
        for _ in range(10):  # hard request bound, including duplicate-heavy results
            if cursor in seen_cursors:
                break
            seen_cursors.add(cursor)
            if provider == 'europepmc':
                query = '(oxide OR garnet OR LLZO) AND ("ionic conductivity") AND (sintering OR "hot pressing" OR synthesis)'
                url = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode({
                    'query': query, 'format': 'json', 'pageSize': 100,
                    'resultType': 'core', 'cursorMark': cursor})
            elif provider == 'crossref':
                url = 'https://api.crossref.org/works?' + urlencode({
                    'query': QUERIES[0], 'filter': 'type:journal-article',
                    'rows': 100, 'cursor': cursor})
            else:
                url = 'https://api.openalex.org/works?' + urlencode({
                    'search': QUERIES[1], 'per-page': 100, 'cursor': cursor})
            try:
                rows, next_cursor = parse_discovery(provider, client.fetch(url))
            except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
                failures.append({'provider': provider, 'stage': 'DISCOVERY',
                                 'failure': type(exc).__name__})
                break
            for row in rows:
                if 'doi' not in row:
                    failures.append(row)
                    continue
                key = row['doi']
                if key not in records and len(records) >= target:
                    continue
                records.setdefault(key, []).append(row)
            if len(records) >= target or not rows or not next_cursor:
                break
            cursor = next_cursor
        if len(records) >= target:
            break
    return records, failures



def _source_number(value):
    value = unicodedata.normalize('NFKC', value).strip().replace('−', '-').replace('×', 'x')
    # An uncertainty, inequality, range or ambiguous multiplier is not a point label.
    value = re.sub(r'\s+', '', value)
    if not re.fullmatch(r'[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+|[x*]10\^?[+-]?\d+)?', value):
        raise ValueError('non-point or ambiguous numeric source cell')
    value = re.sub(r'[x*]10\^?([+-]?\d+)', r'e\1', value)
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('nonfinite source value')
    return number


def extract_explicit_table_measurements(rows, caption, binding):
    """Parse only flat, fully explicit row schemas; never use nearby prose.

    No global full-text join of sample codes, formula, temperature and labels.
    Complex table orientations remain raw candidates for an audited adapter.
    """
    from pymatgen.core import Composition
    if len(rows) < 2:
        return []
    headers = [unicodedata.normalize('NFKC', h).lower().replace('−', '-') for h in rows[0]]
    patterns = {
        'sample': r'^(?:sample|sample code|specimen)$',
        'formula': r'^(?:nominal formula|nominal composition|chemical formula)$',
        'route': r'^(?:route|manufacturing route|synthesis route)$',
        'process_C': r'^(?:sintering|hot.press(?:ing)?) temperature.*(?:°c|\(c\))',
        'time_h': r'^(?:holding|sintering|hot.press(?:ing)?) time.*(?:\(h\)|hours)',
        'time_min': r'^(?:holding|sintering|hot.press(?:ing)?) time.*(?:\(min\)|minutes)',
        'pressure': r'^(?:applied )?pressure.*mpa',
        'atmosphere': r'^atmosphere$',
        'sigma': r'^(?:total ionic conductivity|bulk ionic conductivity|grain.boundary ionic conductivity).*s\s*(?:/\s*cm|cm\s*-1)',
        'measurement_C': r'^measurement temperature.*(?:°c|\(c\))',
        'uncertainty': r'^(?:conductivity )?uncertainty.*s\s*(?:/\s*cm|cm\s*-1)',
    }
    columns = {}
    for key, pattern in patterns.items():
        matches = [i for i, h in enumerate(headers) if re.search(pattern, h)]
        if len(matches) > 1:
            return []  # multiple observables/contexts need a reviewed adapter
        if matches:
            columns[key] = matches[0]
    if 'sigma' not in columns or 'sample' not in columns:
        return []
    sigma_header = headers[columns['sigma']]
    # Reject milli-Siemens and header scaling until an explicit adapter handles it.
    if 'ms' in sigma_header or '10' in sigma_header:
        return []
    observable = ('GRAIN_BOUNDARY' if 'grain' in sigma_header else
                  'BULK' if 'bulk' in sigma_header else 'TOTAL')
    measurements = []
    for row_index, row in enumerate(rows[1:], 1):
        if len(row) != len(headers) or not row[columns['sample']].strip():
            continue
        reasons = []
        if any(re.search(r'\bref(?:erence)?s?\b', header) for header in headers):
            reasons.append('POSSIBLE_SECONDARY_LITERATURE_TABLE')
        def field(key):
            return row[columns[key]].strip() if key in columns else None
        try:
            value = _source_number(field('sigma'))
            if value <= 0:
                raise ValueError('nonpositive conductivity')
        except ValueError:
            continue
        formula = field('formula')
        try:
            if not formula:
                raise ValueError('missing nominal formula')
            composition = Composition(formula, strict=True)
            if composition['O'] <= 0 or composition['S'] > 0 or composition['Li'] <= 0:
                reasons.append('OUTSIDE_LI_O_ONLY_COMPOSITION_PROXY')
        except (ValueError, TypeError):
            reasons.append('MISSING_OR_UNPARSEABLE_NOMINAL_FORMULA')
        route_text = (field('route') or '').casefold()
        route = {'conventional sintering': 'CONVENTIONAL_SINTERING',
                 'hot pressing': 'HOT_PRESS'}.get(route_text)
        if route is None:
            reasons.append('MANUFACTURING_ROUTE_UNVERIFIED')
        numeric = {}
        for key in ('process_C', 'time_h', 'time_min', 'measurement_C', 'pressure', 'uncertainty'):
            try:
                numeric[key] = _source_number(field(key)) if field(key) is not None else None
            except ValueError:
                numeric[key] = None
                reasons.append('AMBIGUOUS_' + key.upper())
        holding = numeric['time_min']
        if numeric['time_h'] is not None:
            if holding is not None:
                reasons.append('MULTIPLE_HOLDING_TIME_COLUMNS')
            else:
                holding = numeric['time_h'] * 60
        if numeric['process_C'] is None or numeric['process_C'] <= 0 or holding is None or holding <= 0:
            reasons.append('MISSING_VALID_PROCESS_TEMPERATURE_OR_TIME')
        if numeric['measurement_C'] != 25:
            reasons.append('MEASUREMENT_NOT_EXPLICIT_EXACT_25C')
        if observable != 'TOTAL':
            reasons.append('NON_TOTAL_OBSERVABLE')
        if route == 'HOT_PRESS' and (numeric['pressure'] is None or numeric['pressure'] <= 0):
            reasons.append('MISSING_HOT_PRESS_PRESSURE')
        if not field('atmosphere'):
            reasons.append('ATMOSPHERE_UNSPECIFIED')
        if numeric['uncertainty'] is None or numeric['uncertainty'] < 0:
            reasons.append('UNCERTAINTY_UNSPECIFIED_OR_INVALID')
        measurements.append({**binding, 'row_index': row_index,
            'sample_code': field('sample'), 'nominal_formula': formula,
            'manufacturing_route': route, 'manufacturing_route_source': field('route'),
            'process_temperature_C': numeric['process_C'], 'holding_time_min': holding,
            'pressure_MPa': numeric['pressure'], 'atmosphere': field('atmosphere'),
            'precursors': None, 'post_processing': None,
            'conductivity_S_cm': value, 'conductivity_uncertainty_S_cm': numeric['uncertainty'],
            'measurement_temperature_C': numeric['measurement_C'], 'observable_type': observable,
            'column_bindings': columns, 'headers': rows[0], 'source_cells': row,
            'tier': ('REJECTED' if 'OUTSIDE_LI_O_ONLY_COMPOSITION_PROXY' in reasons else
                     'EXPLORATORY' if reasons else 'STRICT_QUALIFIED'), 'reasons': reasons,
            'qualification_scope': 'SOURCE_REPORTED_ROW_CONTEXT_ONLY',
            'final_pellet_composition_verified': False,
            'independent_specimen_verified': False,
            'eligible_for_new_heldout_evaluation': False})
    return measurements

def inspect_jats(raw, doi, pmcid):
    """Extract table evidence without guessing numerical or sample bindings."""
    if not 0 < len(raw) <= MAX_BYTES or b'<!ENTITY' in raw.upper():
        raise ValueError('invalid XML size or entity declaration')
    raw.decode('utf-8', errors='strict')
    clean = re.sub(rb'<!DOCTYPE\s+article\b[^<>\[\]]{0,2000}>', b'', raw, flags=re.I)
    if b'<!DOCTYPE' in clean.upper():
        raise ValueError('unsafe XML DTD')
    root = ET.fromstring(clean)
    tag = lambda e: e.tag.split('}')[-1] if isinstance(e.tag, str) else ''
    text = lambda e: unicodedata.normalize('NFKC', ''.join(e.itertext())).strip()
    if tag(root) != 'article':
        raise ValueError('not JATS article')
    front = next((e for e in root if tag(e) == 'front'), None)
    if front is None:
        raise ValueError('missing article front identity')
    doi_ids = [normalize_doi(text(e)) for e in front.iter()
               if tag(e) == 'article-id' and e.get('pub-id-type') == 'doi']
    pmc_ids = [text(e).upper().removeprefix('PMC') for e in front.iter()
               if tag(e) == 'article-id' and e.get('pub-id-type') in ('pmc', 'pmcid')]
    if set(doi_ids) != {normalize_doi(doi)} or set(pmc_ids) != {pmcid.removeprefix('PMC')}:
        raise ValueError('article DOI/PMCID identity mismatch')
    licenses = [text(e) for e in front.iter() if tag(e) == 'license']
    # An API OA assertion alone does not establish document reuse permission.
    if not licenses:
        raise ValueError('document-specific license absent')
    article_type = root.get('article-type')
    if article_type != 'research-article':
        raise ValueError('original research article type not authenticated')
    candidates, measurements = [], []
    for table in root.iter():
        if tag(table) != 'table-wrap':
            continue
        label = next((text(e) for e in table if tag(e) == 'label'), None)
        caption = ' '.join(text(e) for e in table if tag(e) == 'caption')
        rows = [[text(c) for c in row if tag(c) in ('td', 'th')]
                for row in table.iter() if tag(row) == 'tr']
        if not any(re.search(r'conductiv|σ|sigma', ' '.join(row), re.I) for row in rows) and not re.search(r'conductiv', caption, re.I):
            continue
        # Spanning cells need an explicit layout adapter, never positional guessing.
        spans = any(e.get('rowspan', '1') != '1' or e.get('colspan', '1') != '1' for e in table.iter())
        if not spans:
            measurements.extend(extract_explicit_table_measurements(rows, caption, {
                'doi': doi, 'pmcid': pmcid, 'source_sha256': _digest(raw),
                'table_id': table.get('id'), 'table_label': label, 'caption': caption}))
        for number, row in enumerate(rows):
            candidates.append({'doi': normalize_doi(doi), 'pmcid': pmcid,
                'source_sha256': _digest(raw), 'table_id': table.get('id'),
                'table_label': label, 'caption': caption, 'row_index': number,
                'cells': [{'column_index': i, 'text': cell} for i, cell in enumerate(row)],
                'tier': 'EXPLORATORY',
                'reasons': ['UNVALIDATED_SAMPLE_PROCESS_MEASUREMENT_BINDING'],
                'conductivity_S_cm': None, 'measurement_temperature_C': None,
                'observable_type': None, 'nominal_formula': None,
                'manufacturing_route': None, 'uncertainty': None})
    return {'doi': doi, 'pmcid': pmcid, 'source_sha256': _digest(raw),
            'license_text': licenses, 'article_type': article_type,
            'candidates': candidates, 'measurements': measurements}



def extract_registered_measurements(raw, doi, pmcid):
    """Reuse reviewed exact-paper parsers, never fit a parser to new labels.

    These source-qualified rows retain nominal-composition and specimen
    limitations. Unregistered papers produce candidates, not guessed labels.
    """
    from .table4 import DOI as ROUTE_DOI, extract_route_comparison
    if doi == ROUTE_DOI:
        return extract_route_comparison(raw, doi, pmcid)
    from .source_parsers import (HOT_PRESS_DOI, extract_hot_press_comparison,
                                 DISORDER_DOI, extract_disorder_processing)
    if doi == DISORDER_DOI:
        return extract_disorder_processing(raw, doi, pmcid)
    if doi == HOT_PRESS_DOI:
        return extract_hot_press_comparison(raw, doi, pmcid)
    if doi == '10.1021/acsorginorgau.5c00021':
        from scripts.science.obelix_solo_oxide_original_manufacturing_0190 import read_author_table, PMC
        if pmcid != PMC:
            raise ValueError('Sn-garnet article DOI/PMC mismatch')
        rows, metadata = read_author_table(raw)
        return [{**row, 'doi': doi, 'pmcid': pmcid, 'source_sha256': _digest(raw),
                 'source_parser_metadata': metadata, 'measurement_temperature_C': row['temperature_C'],
                 'observable_type': 'TOTAL_IONIC_CONDUCTIVITY', 'process_temperature_C': None,
                 'holding_time_min': None, 'tier': 'EXPLORATORY',
                 'reasons': ['NUMERICAL_ROUTE_SCHEDULE_NOT_EXTRACTED', 'PREVIOUSLY_EXPOSED_0190_LABELS'],
                 'previously_public_evaluation_labels': True,
                 'eligible_for_new_heldout_evaluation': False} for row in rows]
    from scripts.science.obelix_solo_oxide_process_transfer_0191 import (
        DOI18, DOI20, original_process_2018, original_process_2020)
    adapters = {
        DOI18: ('PMC9079727', original_process_2018),
        DOI20: ('PMC7040616', original_process_2020),
    }
    if doi not in adapters:
        return []
    expected_pmc, parser = adapters[doi]
    if pmcid != expected_pmc:
        raise ValueError('registered source DOI/PMC mismatch')
    rows, metadata = parser(raw)
    result = []
    for paper, sample, formula, temperature, minutes, conductivity in rows:
        result.append({
            'doi': paper, 'pmcid': pmcid, 'sample_code': sample,
            'nominal_formula': formula,
            'process_temperature_C': temperature, 'holding_time_min': minutes,
            'manufacturing_route': 'CONVENTIONAL_SINTERING',
            'pressure_MPa': None, 'atmosphere': None, 'precursors': None,
            'post_processing': None, 'uncertainty': None,
            'conductivity_S_cm': conductivity,
            'author_reported_measurement_temperature_C': 25,
            'observable_type': 'TOTAL_IONIC_CONDUCTIVITY',
            'source_sha256': _digest(raw), 'source_parser_metadata': metadata,
            'source_parser': parser.__module__ + '.' + parser.__name__,
            'tier': 'EXPLORATORY',
            'reasons': ['FINAL_PELLET_AND_INDEPENDENT_SPECIMEN_IDENTITY_UNATTESTED',
                        'PRESSURE_ATMOSPHERE_AND_UNCERTAINTY_NOT_EXTRACTED'],
            'previously_public_evaluation_labels': True,
            'eligible_for_new_heldout_evaluation': False,
        })
    return result


def validate_quota_evidence(path, acquisition_limit):
    """Check a local auditable policy record before a bulk full-text request.

    This validates the record's binding and limits, not its interpretation of
    legal terms. The record must be prepared by inspecting current official
    documentation; a CLI flag alone cannot assert quota verification.
    """
    path = Path(path)
    evidence = json.loads(path.read_bytes())
    if evidence.get('provider') != 'europepmc' or evidence.get('documentation_url') != API_DOCS['europepmc']:
        raise ValueError('quota evidence must bind official Europe PMC documentation')
    document = (path.parent / evidence['documentation_file']).resolve()
    if not document.is_relative_to(path.parent.resolve()):
        raise ValueError('quota documentation must stay alongside the evidence record')
    if _digest(document.read_bytes()) != evidence.get('documentation_sha256'):
        raise ValueError('quota documentation hash differs')
    inspected = datetime.fromisoformat(evidence['verified_utc'])
    if inspected.tzinfo is None:
        raise ValueError('quota evidence needs a timezone')
    age = (datetime.now(timezone.utc) - inspected).total_seconds()
    if not 0 <= age <= 7 * 86400:
        raise ValueError('quota evidence is stale or future-dated')
    if (evidence.get('free_fulltext_access_confirmed') is not True or
            type(evidence.get('max_publications')) is not int or
            not acquisition_limit <= evidence['max_publications'] <= 100 or
            not 0 < evidence.get('requests_per_second', 0) <= 0.1 or
            not evidence.get('terms_evidence_excerpt')):
        raise ValueError('free quota and terms evidence is incomplete or outside bounded limits')
    for item in evidence.get('supporting_documents', []):
        supporting = (path.parent / item['file']).resolve()
        if not supporting.is_relative_to(path.parent.resolve()) or _digest(supporting.read_bytes()) != item['sha256']:
            raise ValueError('supporting policy document hash differs')
    return evidence



def qualify_duplicate_conditions(measurements):
    """Do not count repeated or contradictory condition identities as truth."""
    groups = {}
    fields = ('doi', 'sample_code', 'nominal_formula', 'manufacturing_route',
              'process_temperature_C', 'holding_time_min', 'pressure_MPa',
              'measurement_temperature_C', 'observable_type')
    for row in measurements:
        groups.setdefault(tuple(row.get(k) for k in fields), []).append(row)
    for rows in groups.values():
        if len(rows) <= 1:
            continue
        inconsistent = len({r['conductivity_S_cm'] for r in rows}) > 1
        reason = 'CONTRADICTORY_CONDITION_IDENTITY' if inconsistent else 'DUPLICATE_CONDITION_IDENTITY'
        for row in rows:
            row['reasons'].append(reason)
            if inconsistent:
                row['tier'] = 'REJECTED'
            elif row['tier'] == 'STRICT_QUALIFIED':
                row['tier'] = 'EXPLORATORY'
    return measurements

def acquire_publications(client, plan, output):
    """Acquire OA JATS only; preserve row evidence and explicit parser failures."""
    results, failures = [], []
    obtained = 0
    for item in plan:
        doi, pmcid = item['doi'], item['pmcid']
        url = 'https://www.ebi.ac.uk/europepmc/webservices/rest/' + pmcid + '/fullTextXML'
        try:
            raw = client.fetch(url)
            obtained += 1
            source = inspect_jats(raw, doi, pmcid)
            try:
                registered = extract_registered_measurements(raw, doi, pmcid)
            except ValueError as exc:
                # Authenticated article bytes remain authenticated. A parser
                # failure blocks its measurements, not its source identity.
                source['measurements'] = []
                source['extraction_status'] = 'FAILED_SOURCE_BINDING'
                failures.append({'doi': doi, 'stage': 'EXTRACTION',
                                 'failure': 'SOURCE_BINDING_FAILURE', 'reason': str(exc)[:300]})
            else:
                if registered:
                    source['measurements'] = registered
                qualify_duplicate_conditions(source['measurements'])
                source['extraction_status'] = 'EXTRACTED' if source['measurements'] else 'UNSUPPORTED'
                if not source['measurements']:
                    failures.append({'doi': doi, 'stage': 'EXTRACTION', 'failure':
                        'UNSUPPORTED_TABLE_EXTRACTION_SCHEMA' if source['candidates'] else 'NO_CONDUCTIVITY_TABLE_CANDIDATES'})
            results.append(source)
        except (HTTPError, URLError, TimeoutError, ValueError, ET.ParseError) as exc:
            failures.append({'doi': doi, 'pmcid': pmcid, 'stage': 'ACQUISITION_OR_QUALIFICATION',
                             'failure': type(exc).__name__, 'reason': str(exc)[:300]})
    _write_json(Path(output) / 'source-results.json', results)
    return results, failures, obtained

def run_pilot(output, target=1000, acquisition_limit=100, client_factory=PublicClient, quota_evidence=None, discovery_path=None):
    """Freeze DOI acquisition ordering before full text; never score new labels.

    No API quota is asserted as verified merely because an endpoint is public.
    On denied discovery, retain a complete bounded attempt report and stop.
    """
    if not 0 <= acquisition_limit <= 100:
        raise ValueError('acquisition limit must be 0..100')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    quota = validate_quota_evidence(quota_evidence, acquisition_limit) if quota_evidence else None
    start = time.monotonic()
    client = client_factory(output / 'raw-local-only')
    if quota:
        client.interval = max(client.interval, 1 / quota['requests_per_second'])
    if discovery_path:
        records = json.loads(Path(discovery_path).read_bytes())
        if any(normalize_doi(k) != k or not isinstance(v, list) or not v for k, v in records.items()):
            raise ValueError('invalid cached discovery records')
        failures = []
    else:
        records, failures = discover_publications(client, target)
    _write_json(output / 'discovery.json', records)
    plan = []
    ranked = sorted(records.items(), key=lambda pair: (
        not any(classify_title(r['title']) == 'OXIDE_CANDIDATE_NOT_COMPOSITION_CERTIFIED' for r in pair[1]), pair[0]))
    for doi, observations in ranked:
        eligible = [r for r in observations if r['pmcid'] and r['open_access_asserted']
                    and r['original_study_status'] != 'REVIEW_EXCLUDED'
                    and classify_title(r['title']) == 'OXIDE_CANDIDATE_NOT_COMPOSITION_CERTIFIED']
        ids = {r['pmcid'] for r in eligible}
        if len(ids) == 1:
            plan.append({'doi': doi, 'pmcid': next(iter(ids))})
        elif len(ids) > 1:
            failures.append({'doi': doi, 'failure': 'CONFLICTING_PMC_IDENTITIES'})
    plan = plan[:acquisition_limit]
    _write_json(output / 'acquisition-plan.json', {
        'cohort': plan, 'evaluation_status': 'NOT_FROZEN_FOR_MODEL_EVALUATION',
        'no_evaluation_labels_used_for_model_tuning': True})
    results, obtained = [], 0
    if plan and quota is None:
        failures.append({'stage': 'ACQUISITION', 'failure': 'CURRENT_FREE_QUOTA_TERMS_NOT_VERIFIED',
                         'eligible_publications': len(plan)})
    elif plan:
        results, acquisition_failures, obtained = acquire_publications(client, plan, output)
        failures.extend(acquisition_failures)
    measurements = [r for source in results for r in source['measurements']]
    candidates = [r for source in results for r in source['candidates']]
    report = {
        'schema_version': 'rhombus-literature-pilot-v1',
        'discovery_target': target, 'acquisition_attempt_limit': acquisition_limit,
        'unique_doi_groups_discovered': len(records),
        'relevance_and_original_study_status': 'REQUIRES_SOURCE_QUALIFICATION',
        'independent_author_studies_verified': 0,
        'full_text_attempts': len(plan) if quota else 0, 'full_text_responses_obtained': obtained,
        'full_texts_identity_license_type_validated': len(results),
        'measurement_records_extracted': len(measurements),
        'manufacturing_condition_records_extracted': sum(
            r.get('process_temperature_C') is not None and r.get('holding_time_min') is not None for r in measurements),
        'strict_qualified_records': sum(r['tier'] == 'STRICT_QUALIFIED' for r in measurements),
        'exploratory_measurement_records': sum(r['tier'] == 'EXPLORATORY' for r in measurements),
        'rejected_measurement_records': sum(r['tier'] == 'REJECTED' for r in measurements),
        'unparsed_table_row_candidates': len(candidates),
        'rejected_sources': sum(f.get('stage') == 'ACQUISITION_OR_QUALIFICATION' for f in failures), 'failures': failures,
        'api_documentation': API_DOCS, 'public_no_fee_access_terms_recorded': quota is not None,
        'provider_numeric_quota': None,
        'request_interval_seconds': client.interval,
        'cached_discovery_sha256': _digest(Path(discovery_path).read_bytes()) if discovery_path else None,
        'quota_evidence_sha256': _digest(Path(quota_evidence).read_bytes()) if quota else None,
        'http_requests': len(client.events), 'request_events': client.events,
        'runtime_seconds': round(time.monotonic() - start, 4),
        'paid_api_calls': 0, 'monetary_cost': 0,
        'heldout_model_evaluation': 'NOT_RUN_NO_QUALIFIED_NEW_COHORT',
        'scientific_GO': False, 'production_enabled': False,
        'official_OBELiX_TEST_121_read': False,
        'P0_01': 'BLOCKED', 'P0_02': 'BLOCKED', 'P0_03': 'BLOCKED',
    }
    _write_json(output / 'pilot-report.json', report)
    return report


def replay_acquisition(acquisition_directory, output):
    """Reparse verified cached API bytes without another network request.

    This is parser-development replay of exposed data, never a fresh retrieval
    or an independent heldout evaluation. Original artifacts remain unchanged.
    """
    original = Path(acquisition_directory).resolve(strict=True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report_raw = (original / 'pilot-report.json').read_bytes()
    previous = json.loads(report_raw)
    plan = json.loads((original / 'acquisition-plan.json').read_bytes())['cohort']
    responses = {e['url']: e['sha256'] for e in previous['request_events']
                 if e.get('http_status') == 200 and e.get('sha256')}
    class CachedClient:
        def fetch(self, url):
            if url not in responses:
                raise ValueError('no successful retained API response')
            digest = responses[url]
            if re.fullmatch(r'[a-f0-9]{64}', digest) is None:
                raise ValueError('invalid content-addressed source path')
            path = original / 'raw-local-only' / digest
            if path.is_symlink():
                raise ValueError('cached source must not be a symlink')
            raw = path.read_bytes()
            if _digest(raw) != digest:
                raise ValueError('cached source hash differs from retrieval event')
            return raw
    sources, failures, obtained = acquire_publications(CachedClient(), plan, output)
    rows = [r for source in sources for r in source['measurements']]
    result = {
        'schema_version': 'rhombus-literature-replay-v1',
        'original_pilot_report_sha256': _digest(report_raw),
        'fresh_network_requests': 0, 'current_live_source_verified': False,
        'full_texts_replayed': obtained, 'sources_validated': len(sources),
        'manufacturing_condition_records': len(rows),
        'strict_qualified_records': sum(r['tier'] == 'STRICT_QUALIFIED' for r in rows),
        'exploratory_records': sum(r['tier'] == 'EXPLORATORY' for r in rows),
        'rejected_records': sum(r['tier'] == 'REJECTED' for r in rows),
        'unparsed_table_row_candidates': sum(len(s['candidates']) for s in sources),
        'failures': failures, 'labels_exposed_during_parser_development': True,
        'heldout_model_evaluation': 'NOT_RUN_NO_FROZEN_NEW_QUALIFIED_COHORT',
        'scientific_GO': False, 'production_enabled': False,
        'official_OBELiX_TEST_121_read': False,
        'P0_01': 'BLOCKED', 'P0_02': 'BLOCKED', 'P0_03': 'BLOCKED',
    }
    _write_json(output / 'replay-report.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--discovery-target', type=int, default=1000)
    parser.add_argument('--acquisition-limit', type=int, default=100)
    parser.add_argument('--quota-evidence', type=Path)
    parser.add_argument('--discovery-file', type=Path)
    parser.add_argument('--replay-acquisition-dir', type=Path)
    args = parser.parse_args()
    if args.replay_acquisition_dir:
        print(json.dumps(replay_acquisition(args.replay_acquisition_dir, args.output_dir), indent=2))
        raise SystemExit(0)
    result = run_pilot(args.output_dir, args.discovery_target, args.acquisition_limit, quota_evidence=args.quota_evidence, discovery_path=args.discovery_file)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['unique_doi_groups_discovered'] else 2)
