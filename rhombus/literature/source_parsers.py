"""Reviewed adapters for newly acquired original experimental sources.

No extrapolation of room temperature to 25 C or filling empty source cells.
"""
import hashlib
import re
import unicodedata
import xml.etree.ElementTree as ET

HOT_PRESS_DOI = '10.1002/smll.202506257'
HOT_PRESS_PMC = 'PMC12530038'
HOT_PRESS_JATS_SHA256 = 'c62b44f332a437847ccaf382c43cb8ee0ea587dc01157f0481896a0927a762dc'


def extract_hot_press_comparison(raw, doi, pmcid):
    """Extract seven reported HP/SPS cells; retain missing eighth cell.

    Run after inspect_jats has authenticated article identity/type/license.
    The pinned raw source is the API response retrieved in the bounded pilot,
    not an expected numerical table or a source-authentication fallback.
    """
    from .harvest import _source_number
    if doi != HOT_PRESS_DOI or pmcid != HOT_PRESS_PMC:
        raise ValueError('hot-press article identity mismatch')
    if hashlib.sha256(raw).hexdigest() != HOT_PRESS_JATS_SHA256:
        raise ValueError('hot-press source bytes differ from reviewed API response')
    root = ET.fromstring(raw)
    tag = lambda e: e.tag.split('}')[-1] if isinstance(e.tag, str) else ''
    def text(e):
        value = unicodedata.normalize('NFKC', ''.join(e.itertext()))
        return ' '.join(value.replace('‐', '-').replace('−', '-').split())
    methods = [text(e) for e in root.iter() if tag(e) == 'p'
               and 'Commercially available Li6.25Al0.25La3Zr2O12 powder' in text(e)]
    eis = [text(e) for e in root.iter() if tag(e) == 'p'
           and 'ionic conductivity of the samples at RT was determined' in text(e)]
    if len(methods) != 1 or len(eis) != 1:
        raise ValueError('unique manufacturing and EIS methods required')
    clauses = ('under an Ar atmosphere', 'pre-pressed into pellets at 10 MPa',
               'fixed applied pressure of 25 MPa', 'fixed holding time of 5 min',
               'heat treatment at 850 °C for 4 h in air')
    if any(c not in methods[0] for c in clauses) or 'measurement at RT' not in eis[0]:
        raise ValueError('source process or measurement context differs')
    tables = [e for e in root.iter() if tag(e) == 'table-wrap'
              and any(tag(c) == 'label' and text(c) == 'Table 3' for c in e)]
    if len(tables) != 1:
        raise ValueError('one Table 3 required')
    table = tables[0]
    if not any(tag(c) == 'caption' and 'RT ionic conductivity' in text(c) for c in table):
        raise ValueError('RT source caption missing')
    rows = [[text(c) for c in e if tag(c) in ('td', 'th')]
            for e in table.iter() if tag(e) == 'tr']
    if len(rows) != 3 or any(len(r) != 5 for r in rows):
        raise ValueError('source Table 3 shape changed')
    if rows[0] != ['Sintering temperature [°C]', '950', '1000', '1050', '1100']:
        raise ValueError('hot-press column temperatures changed')
    result = []
    for index, route in enumerate(('HP', 'SPS'), 1):
        if rows[index][0] != f'Ionic conductivity [mS cm-1] ({route})':
            raise ValueError('source conductivity units or route label changed')
        for column, raw_value in enumerate(rows[index][1:], 1):
            if not raw_value:
                continue  # not a measured failure, zero or interpolated label
            value = _source_number(raw_value)
            if value <= 0:
                raise ValueError('source conductivity must be positive')
            result.append({
                'doi': doi, 'pmcid': pmcid, 'source_sha256': HOT_PRESS_JATS_SHA256,
                'table_id': table.get('id'), 'table_label': 'Table 3',
                'row_index': index, 'column_index': column,
                'source_row_label': rows[index][0], 'source_column_label': rows[0][column],
                'source_cell': raw_value, 'source_unit': 'mS/cm',
                'nominal_formula': 'Li6.25Al0.25La3Zr2O12',
                'nominal_formula_basis': 'COMMERCIAL_STARTING_POWDER_NOT_FINAL_PELLET',
                'manufacturing_route': 'INDUCTION_HOT_PRESS' if route == 'HP' else 'SPARK_PLASMA_SINTERING',
                'process_temperature_C': int(rows[0][column]),
                'temperature_reference': 'IR_MEASUREMENT_OF_GRAPHITE_DIE_SURFACE',
                'holding_time_min': 5, 'pressure_MPa': 25,
                'pre_press_pressure_MPa': 10, 'atmosphere': 'Ar',
                'post_processing': {'temperature_C': 850, 'holding_time_min': 240, 'atmosphere': 'air'},
                'conductivity_S_cm': value * 1e-3, 'conductivity_uncertainty_S_cm': None,
                'measurement_temperature_C': None, 'measurement_temperature_text': 'RT',
                'observable_type': 'IONIC_UNRESOLVED_TOTAL_VS_BULK',
                'tier': 'EXPLORATORY',
                'reasons': ['EXACT_MEASUREMENT_TEMPERATURE_UNSPECIFIED',
                            'TOTAL_VS_BULK_NOT_EXPLICITLY_QUALIFIED',
                            'SAMPLE_SPECIMEN_CODES_UNATTESTED'],
                'method_evidence_clauses': list(clauses),
                'eligible_for_new_heldout_evaluation': False,
                'previously_public_evaluation_labels': True,
            })
    if len(result) != 7 or rows[2][4] != '':
        raise ValueError('source observed/missing-cell population changed')
    return result


DISORDER_DOI = '10.1038/s41467-025-58108-7'
DISORDER_PMC = 'PMC11972412'
DISORDER_JATS_SHA256 = 'eab9781dda47ff17ad820fe5ab58d67770620c6b18fb3a1fd7cd28db897034be'


def extract_disorder_processing(raw, doi, pmcid):
    """Recover source-prose conditions, keeping observable and temperature gaps.

    Paragraph-level source bindings distinguish pressure-free crystallization
    from the later 375 MPa hot-press experiment, and electrolyte EIS from cell
    cycling. The processing-order pair is not a blind evaluation cohort.
    """
    from .harvest import _source_number
    if (doi, pmcid) != (DISORDER_DOI, DISORDER_PMC):
        raise ValueError('disorder article identity mismatch')
    if hashlib.sha256(raw).hexdigest() != DISORDER_JATS_SHA256:
        raise ValueError('disorder source bytes differ from reviewed retained response')
    root = ET.fromstring(raw)
    tag = lambda e: e.tag.split('}')[-1] if isinstance(e.tag, str) else ''
    def text(e):
        value = unicodedata.normalize('NFKC', ''.join(e.itertext()))
        for char in ('−', '–', '‐', '‑'):
            value = value.replace(char, '-')
        return ' '.join(value.split())
    paragraphs = [text(e) for b in root.iter() if tag(b) == 'body'
                  for e in b.iter() if tag(e) == 'p']
    def unique(marker):
        matches = [(i,p) for i,p in enumerate(paragraphs) if marker.casefold() in p.casefold()]
        if len(matches) != 1:
            raise ValueError('unique disorder source paragraph missing: '+marker)
        return matches[0]
    conductivity_index, conductivity = unique('Figure 3a presents Nyquist plots captured at 25 °C')
    order_index, order = unique('first sample (denoted as pre-densification)')
    methods_index, methods = unique('pelletized under a uniaxial pressure of 1.3 GPa for 5 min')
    _, composition = unique('Li6.5La3Zr1.5Ta0.5O12 (LLZTO)')
    if ('atmosphere pressure' not in conductivity or 'air atmosphere' not in methods
            or '375 MPa' not in methods):
        raise ValueError('atmospheric annealing and hot pressing must remain distinguishable')
    notation = r'(\d+(?:\.\d+)?\s*[×x]\s*10\s*-\s*\d+)'
    def match(pattern, paragraph):
        found = list(re.finditer(pattern, paragraph))
        if len(found) != 1:
            raise ValueError('ambiguous source measurement/process binding')
        return found[0]
    first = match(r'ionic conductivity of '+notation+r' S/cm was achieved.*?at (\d+) °C for (\d+) h', conductivity)
    second = match(r'increase in temperature from \d+ °C to (\d+) °C, the ionic conductivity.*?increased to '+notation+r' S/cm', conductivity)
    third = match(r'conductivity was further increased to '+notation+r' S/cm.*?under (\d+) °C for (\d+) h', conductivity)
    reference = match(r'C-garnet heat-treated under (\d+) °C for (\d+) h.*?conductivity of '+notation+r' S/cm at 25 °C', conductivity)
    order_process = match(r'followed by crystallization at (\d+) °C for (\d+) h', order)
    before = match(r'first sample exhibited the desirable ionic conductivity of '+notation+r' S/cm', order)
    after = match(r'other one showed the significantly lower ionic conductivity of '+notation+r' S/cm', order)
    observations = [
        ('D_GARNET_LOW_T',int(first[2]),int(first[3])*60,first[1],25,conductivity_index,first[0],None),
        ('D_GARNET_HIGH_T_TIME_UNSPECIFIED',int(second[1]),None,second[2],25,conductivity_index,second[0],None),
        ('D_GARNET_EXTENDED_HOLD',int(third[2]),int(third[3])*60,third[1],25,conductivity_index,third[0],None),
        ('C_GARNET_REFERENCE',int(reference[1]),int(reference[2])*60,reference[3],25,conductivity_index,reference[0],None),
        ('PRE_DENSIFICATION',int(order_process[1]),int(order_process[2])*60,before[1],None,order_index,before[0],'pre-densification'),
        ('POST_DENSIFICATION',int(order_process[1]),int(order_process[2])*60,after[1],None,order_index,after[0],'post-densification'),
    ]
    rows = []
    for condition, temperature, minutes, value, measurement, p_index, clause, sample in observations:
        reasons = ['TOTAL_VS_BULK_NOT_EXPLICITLY_QUALIFIED', 'MEASUREMENT_UNCERTAINTY_UNSPECIFIED']
        if measurement is None:
            reasons.append('EXACT_TEMPERATURE_NOT_EXPLICITLY_BOUND_TO_ORDER_PAIR')
        if minutes is None:
            reasons.append('HOLDING_TIME_NOT_EXPLICIT_IN_SOURCE_CLAUSE')
        route = ('CRYSTALLIZE_POWDER_THEN_DENSIFY' if condition == 'POST_DENSIFICATION' else
                 'CONVENTIONAL_GARNET_REFERENCE_ANNEAL' if condition == 'C_GARNET_REFERENCE' else
                 'COLD_DENSIFY_THEN_ATMOSPHERIC_ANNEAL')
        rows.append({
            'doi': doi, 'pmcid': pmcid, 'source_sha256': DISORDER_JATS_SHA256,
            'condition_id': condition, 'condition_id_is_generated': True,
            'sample_code': sample, 'nominal_formula': 'Li6.5La3Zr1.5Ta0.5O12',
            'nominal_formula_basis': 'NOMINAL_TARGET_NOT_FINAL_PELLET_ASSAY',
            'manufacturing_route': route, 'process_temperature_C': temperature,
            'holding_time_min': minutes, 'atmosphere': None if condition == 'C_GARNET_REFERENCE' else 'air',
            'hot_press_pressure_MPa': None,
            'measurement_external_static_pressure_applied': False if condition.startswith('D_GARNET') else None,
            'conductivity_S_cm': _source_number(value), 'source_unit': 'S/cm',
            'measurement_temperature_C': measurement,
            'observable_type': 'IONIC_UNRESOLVED_TOTAL_VS_BULK',
            'source_body_paragraph_index': p_index,
            'source_paragraph_sha256': hashlib.sha256(paragraphs[p_index].encode()).hexdigest(),
            'source_clause': clause, 'method_body_paragraph_index': methods_index,
            'tier': 'EXPLORATORY', 'reasons': reasons,
            'eligible_for_new_heldout_evaluation': False,
            'previously_public_evaluation_labels': True,
        })
    return rows
