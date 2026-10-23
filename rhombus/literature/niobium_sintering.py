"""Original Nb-LLZO Table 1: RT is unknown exact temperature, never 25 C."""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from decimal import Decimal

DOI = '10.3390/ma14071671'
PMC = 'PMC8036760'
RAW_SHA256 = '52ac2dc013439c2ac18c0dcd432449c8a556696932035e284c504f4f75ee447c'
TRAINING_REPORT_SHA256 = '8af20fd82153bf67db318d9e091610f7979d76df6689ae0de4a33ba1331d34c2'
TABLE_ID = 'materials-14-01671-t001'
TITLE = 'Effect of Sintering Process on Ionic Conductivity of Li7-xLa3Zr2-xNbxO12 (x = 0, 0.2, 0.4, 0.6) Solid Electrolytes'
CONTEXT_HASHES = {
    3: '7681838f5399e349c453964d8cf97c85ca80742058d3551192832985ece49634',
    4: '185ec93dd8caf85ac520ea212f2dde3e7fe4e6c0979ac67b0c3f6e5caabb6e58',
    5: 'd58423f4e31e2615a67325e8e58ebfb95b35e07a1a9d332e1bbd855363b5c2f5',
    7: '190b71968e466cdfb63a1bc823bd07bb3cf1ba52181ae4059f33de9cb9085389',
    13: '981d2b7abf873584256c8a777f70373cca5f6584d329f5907c8940ede84a2148',
    14: '76c5befe4ae701f30619878f31f5e1957d99fffe69268eb6d38ce9d41cae38ec',
    18: '250b8ed76b635fc85eb50a79ff907f8a3faad7fb08ffd55e1913bccb438fff1a',
}


def _text(element):
    if element is None:
        raise ValueError('missing original element')
    return ' '.join(''.join(element.itertext()).split())


def parse_original_table(root):
    """Independently key each paired cell by its own x and dwell label."""
    from .harvest import _source_number
    tables = root.findall(f'.//table-wrap[@id="{TABLE_ID}"]')
    if len(tables) != 1:
        raise ValueError('missing or duplicate original Table 1')
    t = tables[0]
    if (_text(t.find('label')) != 'Table 1' or _text(t.find('caption')) !=
            'Total ionic conductivity of LLZNxO (x = 0, 0.2, 0.4, 0.6) ceramics at different sintering time.'):
        raise ValueError('original total-conductivity identity changed')
    if any(e.get('rowspan', '1') != '1' or e.get('colspan', '1') != '1' for e in t.iter()):
        raise ValueError('ambiguous spanning cell')
    rows = [[_text(c) for c in tr if c.tag in ('td', 'th')] for tr in t.findall('.//tr')]
    header = ['CompositionSintering Time (h)', 'Conductivity(S·cm−1)'] * 3
    if len(rows) != 5 or rows[0] != header or any(len(r) != 6 for r in rows):
        raise ValueError('table population or units changed')
    expected = {'0.2': [1.09e-4, 1.43e-4, 2.37e-4, 2.49e-4],
                '0.4': [1.56e-4, 3.56e-4, 3.86e-4, 2.62e-4],
                '0.6': [1.49e-4, 1.92e-4, 2.36e-4, 2.42e-4]}
    seen, result = set(), []
    for row_number, row in enumerate(rows[1:], 2):
        for col in (0, 2, 4):
            match = re.fullmatch(r'x = (0\.[246]), ([2345]) h', row[col])
            if match is None:
                raise ValueError('unreviewed sample/process label')
            x, hours = match[1], int(match[2]); key = (x, hours)
            value = _source_number(row[col + 1])
            if key in seen or value != expected[x][hours - 2]:
                raise ValueError('duplicate or remapped original value')
            seen.add(key)
            result.append({'condition_id': f'Nb{x}-{hours}h', 'Nb_x': x,
                           'holding_time_min': hours * 60, 'conductivity_S_cm': value,
                           'source_condition_cell': row[col], 'source_value_cell': row[col + 1],
                           'original_cell': f'R{row_number}C{col+2}',
                           'original_condition_cell': f'R{row_number}C{col+1}'})
    return sorted(result, key=lambda r: (r['Nb_x'], r['holding_time_min']))


def extract_niobium_sintering(raw, doi=DOI, pmcid=PMC):
    from .harvest import inspect_jats
    if (doi != DOI or pmcid != PMC or not isinstance(raw, bytes) or
            not 0 < len(raw) <= 8_000_000 or hashlib.sha256(raw).hexdigest() != RAW_SHA256):
        raise ValueError('unreviewed original source bytes or DOI/PMC')
    inspect_jats(raw, doi, pmcid)
    root = ET.fromstring(raw)
    if (_text(root.find('.//front//article-title')) != TITLE or
            'creativecommons.org/licenses/by/4.0/' not in _text(root.find('.//front//permissions'))):
        raise ValueError('original title/license identity changed')
    paragraphs = root.findall('.//body//p')
    for index, digest in CONTEXT_HASHES.items():
        if index >= len(paragraphs) or hashlib.sha256(_text(paragraphs[index]).encode()).hexdigest() != digest:
            raise ValueError('manufacturing/measurement context changed')
    rows = parse_original_table(root)
    for r in rows:
        x = Decimal(r['Nb_x'])
        # Explicit author series Li7-xLa3Zr2-xNbxO12, not final assayed chemistry.
        r.update(doi=DOI, pmcid=PMC, source_sha256=RAW_SHA256,
                 original_table_id=TABLE_ID,
                 nominal_formula=f'Li{7-x}La3Zr{2-x}Nb{x}O12',
                 nominal_formula_basis='AUTHOR_EXPLICIT_SERIES_SUBSTITUTION',
                 manufacturing_route='CONVENTIONAL_SINTERING', process_temperature_C=1250,
                 powder_synthesis_route='SOLID_STATE_REACTION',
                 observable_type='TOTAL', source_unit='S/cm', measurement_temperature_C=None,
                 source_temperature_literal='room temperature', measurement_methods_range_C=[25, 50],
                 conductivity_uncertainty_S_cm=None, atmosphere=None,
                 calcination={'temperature_C': 850, 'time_min': 600, 'atmosphere': None},
                 precursor_cold_press_MPa=100, sintering_pressure_MPa=None,
                 lithium_excess={'reported_percent': 10, 'author_unit': 'wt%', 'precursor': 'Li2CO3',
                                 'denominator_definition': None, 'normalized_elemental_fraction': None},
                 post_sinter_density_used_as_feature=False, physical_specimen_id=None,
                 independent_conductivity_replicates=None,
                 tier='EXPLORATORY', eligible_for_new_heldout_evaluation=False,
                 reasons=['EXACT_MEASUREMENT_TEMPERATURE_UNSPECIFIED',
                          'UNCERTAINTY_UNSPECIFIED_OR_INVALID', 'ATMOSPHERE_UNSPECIFIED'],
                 source_license='CC BY 4.0', manufacturing_context_body_indices=[3, 5, 7],
                 measurement_context_body_indices=[4, 13, 14, 18])
    return rows


def assess_frozen_choice_feasibility(raw, training_report_raw):
    """Execute necessary support checks; reject before fitting or scoring labels."""
    import json
    from .process_features import screen_process_support
    from pymatgen.core import Composition
    if (not isinstance(training_report_raw, bytes) or
            hashlib.sha256(training_report_raw).hexdigest() != TRAINING_REPORT_SHA256):
        raise ValueError('frozen training receipt changed')
    training_records = json.loads(training_report_raw)['records']
    rows = extract_niobium_sintering(raw)
    target_formulas = [Composition(r['nominal_formula']).fractional_composition for r in rows]
    expected_train = {'10.1039/c8ra01329b', '10.3390/ma13030560'}
    groups = {d: [r for r in training_records if r['doi'] == d] for d in expected_train}
    if any(len(g) != 5 or len({r['condition_id'] for r in g}) != 5 for g in groups.values()):
        raise ValueError('frozen training population changed')
    folds = []
    for doi, train in sorted(groups.items()):
        # Embargo the ENTIRE training source if any target-source formula overlaps.
        # A disjoint formula pool within the same target DOI does not undo that link.
        embargo = any(Composition(r['input_features']['nominal_formula']).fractional_composition in target_formulas for r in train)
        for x in ('0.2', '0.4', '0.6'):
            pool = [r for r in rows if r['Nb_x'] == x]
            candidates = [{'doi': DOI, 'condition_id': r['condition_id'], 'input_features': {
                'final_temperature_C': r['process_temperature_C'], 'final_duration_min': r['holding_time_min'],
                'final_route': r['manufacturing_route'],
                'final_temperature_reference': 'AUTHOR_REPORTED_SINTERING_TEMPERATURE'}} for r in pool]
            support = screen_process_support(train, candidates)
            folds.append({'train_DOI': doi, 'target_DOI': DOI, 'target_Nb_x': x,
                          'candidate_count': len(pool), 'process_support': support,
                          'training_source_quarantined_by_formula_component': embargo,
                          'status': 'ABSTAIN', 'authorized_choice': None,
                          'reasons': sorted(set(reason for r in pool for reason in r['reasons']) |
                                            {'PHYSICAL_SPECIMEN_RELATIONSHIP_UNKNOWN', 'NO_STRICT_ADMISSION'} |
                                            ({'TRAIN_SOURCE_FORMULA_COMPONENT_OVERLAP'} if embargo else set()) |
                                            ({'OUTSIDE_TRAINING_PROCESS_SUPPORT'} if support['full_source_choice_must_abstain'] else set())),
                          'model_fitted': False, 'model_vs_baseline_score': None})
    return {'schema_version': 'rhombus-niobium-choice-feasibility-v1',
            'target_DOI_groups': 1, 'distinct_manufacturing_conditions': 12,
            'formula_candidate_pools': 3, 'model_by_pool_attempts': len(folds),
            'source_choice_abstentions': len(folds),
            'formula_embargo_blocked_attempts': sum(f['training_source_quarantined_by_formula_component'] for f in folds),
            'candidate_evaluations': sum(f['candidate_count'] for f in folds),
            'out_of_support_candidate_evaluations': sum(c['must_abstain'] for f in folds for c in f['process_support']['candidates']),
            'model_fits_or_predictions_executed': 0, 'authorized_choices': 0,
            'new_strict_DOI_groups': 0, 'new_strict_manufacturing_comparisons': 0,
            'scientifically_scoreable_model_vs_baseline_comparisons': 0,
            'scientific_GO': False, 'production_enabled': False, 'official_TEST121_accessed': False,
            'folds': folds}
