"""Original LATP source-prose bindings; no figure digitization or strict admission."""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

DOI = '10.3390/ma14164737'
PMC = 'PMC8398119'
JATS_SHA256 = '7db94eed9538162373148b144aa10ef716d97d39d5c0e2439c619f4e65fedd03'
TITLE = 'Densification of a NASICON-Type LATP Electrolyte Sheet by a Cold-Sintering Process'
AUTHORS = ('Naoki Hamao', 'Yuki Yamaguchi', 'Koichi Hamamoto')
# SHA-256 of whitespace-normalized original body paragraphs.
CONTEXT_HASHES = {
    'powder': '0969629a1bf7b78e6c24f0007de07f1375cc0c2a33d1baa3d58155694ce8e2ab',
    'tape': '7c3d68a5ad6f70c7752aa2a478eaace7eacabcad2bd55f45d3f2e6496745111a',
    'cold_sintering': '8b73fa2d7d17757cca2c09a23816f97377b0de639325ed8ca8c7943d0c7a8fa6',
    'eis': 'c88d4f425a307bfeaaa11311f5a6b39410c9cc435b7ed7b05b4d8a785dc429ab',
    'phase': '1a88a758ea83fa7f2b37c0b071ee674333400453f64ce63f3a50bf7e74805dd8',
    'conductivity': '87bbeca65955967dc3c1aaad184d4d6613fe162ee2fc812972762bdf4a7937c4',
}


def text(element):
    return ' '.join(''.join(element.itertext()).split())


def parse_cold_sintering_tree(root):
    """Parse reviewed, attributed excerpts; this alone is NOT byte authentication."""
    front = root.find('front')
    if front is None or root.get('article-type') != 'research-article':
        raise ValueError('original source identity absent')
    ids = front.findall('.//article-id[@pub-id-type="doi"]')
    pmcs = front.findall('.//article-id[@pub-id-type="pmcid"]')
    authors = tuple(text(c.find('given-names'))+' '+text(c.find('surname'))
                    for c in front.findall('.//contrib[@contrib-type="author"]/name'))
    rights = [x.get('{http://www.w3.org/1999/xlink}href')
              for x in front.findall('.//permissions/license//ext-link')]
    if (len(ids) != 1 or text(ids[0]) != DOI or len(pmcs) != 1 or text(pmcs[0]) != PMC
            or front.findtext('.//article-title') != TITLE or authors != AUTHORS
            or 'https://creativecommons.org/licenses/by/4.0/' not in rights):
        raise ValueError('original source identity or rights changed')
    paragraphs = root.findall('.//body//p')
    contexts = {}
    for key, digest in CONTEXT_HASHES.items():
        hits = [(p, text(p)) for p in paragraphs
                if hashlib.sha256(text(p).encode()).hexdigest() == digest]
        if len(hits) != 1:
            raise ValueError('reviewed source context missing or changed: '+key)
        contexts[key] = hits[0][1]
    process = contexts['cold_sintering']
    # Associate times and conductivities using the original ordered sentence,
    # including its explicit 'respectively', observable, units and temperature.
    pattern = (r'total conductivities of the LATP sheets prepared by CSP for '
               r'(\d+), (\d+), and (\d+) min were calculated from the resistances '
               r'of the high frequency equivalent circuits, '
               r'(\d+\.\d+ × 10−\d+), (\d+\.\d+ × 10−\d+), '
               r'(\d+\.\d+ × 10−\d+) S/cm at (\d+) °C, respectively\.')
    matches = list(re.finditer(pattern, contexts['conductivity']))
    if len(matches) != 1:
        raise ValueError('ambiguous original time/value association')
    match = matches[0]
    times = tuple(map(int, match.group(1, 2, 3)))
    from .harvest import _source_number
    values = tuple(_source_number(v) for v in match.group(4, 5, 6))
    if (times != (5, 10, 30) or values != (1.4e-4, 1.8e-4, 3.0e-4)
            or int(match[7]) != 25 or '25 MPa' not in process or '200 °C' not in process):
        raise ValueError('reviewed manufacturing comparison changed')
    return [{
        'doi': DOI, 'pmcid': PMC, 'source_sha256': JATS_SHA256,
        'condition_id': f'CSP_WATER_{minutes}_MIN', 'condition_id_is_generated': True,
        'sample_code': None, 'individual_specimen_id': None,
        'independent_replicate_count': None,
        'nominal_formula': 'Li1.3Al0.3Ti1.7(PO4)3',
        'final_measured_composition': None,
        'manufacturing_route': 'WATER_ASSISTED_COLD_SINTERING',
        'process_temperature_C': 200, 'temperature_reference': 'PREHEATED_MOLD_TARGET',
        'isothermal_sample_hold_at_200_C_verified': False,
        'holding_time_min': minutes, 'pressure_MPa': 25, 'atmosphere': None,
        'water_to_sheet_mass_ratio': 0.3,
        'conductivity_S_cm': value, 'conductivity_uncertainty_S_cm': None,
        'measurement_temperature_C': 25, 'measurement_methods_temperature_text': 'room temperature',
        'observable_type': 'TOTAL', 'source_unit': 'S/cm',
        'source_literal': match[4+i], 'source_clause': match[0],
        'source_kind': 'ORIGINAL_RESULTS_PROSE', 'table_id': None, 'original_cell': None,
        'source_context_sha256': CONTEXT_HASHES['conductivity'],
        'method_context_sha256': dict(CONTEXT_HASHES),
        'tier': 'EXPLORATORY',
        'reasons': ['UNCERTAINTY_UNSPECIFIED_OR_INVALID', 'ATMOSPHERE_UNSPECIFIED',
                    'COLD_SINTERING_OUTSIDE_REGISTERED_STRICT_ROUTE_DOMAIN',
                    'INDIVIDUAL_SPECIMEN_AND_REPLICATE_COUNTS_UNSPECIFIED'],
        'eligible_for_new_heldout_evaluation': False,
        'previously_public_evaluation_labels': True,
    } for i, (minutes, value) in enumerate(zip(times, values, strict=True))]


def extract_cold_sintering_comparison(raw, doi=DOI, pmcid=PMC):
    """Require the exact retained original response before inspecting any labels."""
    if (doi, pmcid) != (DOI, PMC):
        raise ValueError('original DOI/PMC mismatch')
    if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != JATS_SHA256:
        raise ValueError('original raw bytes differ from reviewed source')
    from .harvest import inspect_jats
    inspect_jats(raw, doi, pmcid)
    return parse_cold_sintering_tree(ET.fromstring(raw))
