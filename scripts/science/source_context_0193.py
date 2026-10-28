"""Conservative context extraction from supplied JATS; no origin authentication.

Passing this parser is a diagnostic, not a publisher receipt or qualification.
Real source compatibility must be established separately with acquired bytes.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

from scripts.science.obelix_solo_oxide_five_doi_0188 import DOI18, table_source
from scripts.science.obelix_solo_oxide_jats_three_doi_0187 import (
    DOIS, PMCS, flatten, norm, parse_article, simple, tag,
)
from scripts.science.obelix_solo_oxide_process_transfer_0191 import (
    original_process_2018, original_process_2020,
)

SCHEMA = 'rhombus-0193-jats-context-diagnostic-v1'


def _has_si_per_cm(text):
    text = norm(text).lower().replace(' ', '')
    return bool(re.search(r'(?<![a-z])s(?:/cm|cm(?:\^?-1|−1))', text))


def _measurement_context_2018(blob, table):
    if b'<!ENTITY' in blob.upper():
        raise ValueError('unsafe entity')
    clean = re.sub(rb'<!DOCTYPE\s+article\b[^<>\[\]]{0,2000}>', b'', blob, flags=re.I)
    if b'<!DOCTYPE' in clean.upper():
        raise ValueError('unsafe doctype')
    root = ET.fromstring(clean)
    bodies = [node for node in root.iter() if tag(node) == 'body']
    if len(bodies) != 1:
        raise ValueError('article body missing or ambiguous')
    def body_paragraphs(node):
        if tag(node) in ('table-wrap', 'fig', 'ref-list'):
            return
        if tag(node) == 'p':
            yield norm(flatten(node))
            return
        for child in node:
            yield from body_paragraphs(child)
    paragraphs = list(body_paragraphs(bodies[0]))
    relevant = [p for p in paragraphs if re.search(r'conductivity|impedance', p, re.I)
                and (re.search(r'measur|record|perform|collect|conducted|obtained', p, re.I)
                     or (re.search(r'listed|reported', p, re.I) and re.search(r'table\s*3\b', p, re.I)))
                and re.search(r'(?<![\d.])25\s*(?:°\s*)?c\b', p, re.I)]
    if len(relevant) != 1:
        raise ValueError('missing or ambiguous 25 C measurement paragraph')
    text = relevant[0]
    # Do not infer measurement temperature from a heating/dwell statement.
    if re.search(r'sinter|anneal|heating|dwell|synthes|prepar', text, re.I):
        raise ValueError('measurement and processing temperature context mixed')
    other = re.findall(r'(?<![\d.])(\d+(?:\.\d+)?)\s*(?:°\s*)?c\b', text, re.I)
    if not other or any(float(value) != 25 for value in other):
        raise ValueError('contradictory Celsius measurement context')
    kelvin = re.findall(r'(?<![\d.])(\d+(?:\.\d+)?)\s*k\b', text, re.I)
    if any(float(value) != 298 for value in kelvin):
        raise ValueError('contradictory Kelvin context')
    # A 298 K column can be paired with a 25 C prose statement only when it
    # explicitly identifies Table 3 and both total/bulk headers say 298 K.
    headers = table[0]
    header_kelvin = [re.findall(r'(?<![\d.])(\d+(?:\.\d+)?)\s*k\b', norm(h), re.I)
                     for h in headers[1:3]]
    if any(header_kelvin):
        if header_kelvin != [['298'], ['298']] or not re.search(r'table\s*3\b', text, re.I):
            raise ValueError('unpaired or contradictory Table 3 Kelvin headers')
        kelvin = ['298']
    return ('KELVIN_298K_PAIRED_WITH_25C_TEXT' if kelvin else 'EXACT_25C_STATED'), text


def inspect_jats(blob, doi):
    """Bind fixed known sample rows; output is explicitly untrusted diagnostic."""
    if doi == DOI18:
        rows, _ = original_process_2018(blob)
        _, _, table, _ = table_source(blob, DOI18, 'PMC9079727', 3)
        if not table or len(table[0]) < 3 or not _has_si_per_cm(table[0][1]):
            raise ValueError('2018 total conductivity S/cm column missing')
        temperature, span = _measurement_context_2018(blob, table)
        table_id, process_table = 'Table 3 total conductivity', 'Table 1'
    elif doi == DOIS[2]:
        rows, _ = original_process_2020(blob)
        table = parse_article(blob, doi, PMCS[2])['table']
        total_headers = [cell for row in table['rows'] for cell in row
                         if 'total' in simple(cell) and
                         ('conductivity' in simple(cell) or 'σ' in cell.lower() or 'sigma' in cell.lower())]
        if len(total_headers) != 1 or not _has_si_per_cm(total_headers[0]):
            raise ValueError('2020 total conductivity S/cm column missing or ambiguous')
        temperature, span = 'EXACT_25C_STATED', table['caption']
        table_id, process_table = 'Table 2 total conductivity', 'Table 2'
    else:
        raise ValueError('unsupported DOI')
    return {'schema_version': SCHEMA, 'doi': doi, 'representation': 'CALLER_SUPPLIED_JATS',
            'bytes_sha256': hashlib.sha256(blob).hexdigest(), 'source_authentication': 'NOT_PERFORMED',
            'evidence_status': 'DIAGNOSTIC_ONLY', 'admitted': False, 'scientific_GO': False,
            'production_enabled': False, 'scientific_verdict': 'INCONCLUSIVE',
            'measurement_temperature_context': temperature, 'measurement_span': span,
            'measurement_mode': 'DIRECT_VS_FITTED_UNVERIFIED',
            'limitations': ['RETROSPECTIVE_EXPOSURE', 'TEMPERATURE_ONLY_CONFOUNDED_WITH_DWELL',
                            'UNAUTHENTICATED_CALLER_BYTES'],
            'rows': [{'sample': name, 'sintering_temperature_C': temp, 'dwell_min': dwell,
                      'total_conductivity_S_cm': value, 'conductivity_table': table_id,
                      'processing_table': process_table} for _, name, _, temp, dwell, value in rows]}
