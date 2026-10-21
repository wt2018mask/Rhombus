"""Bound reviewed process inputs and screen frozen-model applicability.

Only four already exposed original sources are supported. This is a descriptive
input/decision audit, not a new training set, strict admission or model upgrade.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET

SOURCES = {
    '10.1039/c8ra01329b': ('PMC9079727', '6dee69ef498243cc04c03a4d049175123cfac1b8dfa99257781da76d34979eea'),
    '10.3390/ma13030560': ('PMC7040616', '51b35a6b942557d1f6cb7ab77d63ca36dbd4d3fbd44a6e44d0ad6f3557392b63'),
    '10.3390/ma14226809': ('PMC8620275', '0da4f7639daec04bf41c0a96e952a7ec8846eb5034ae531f60694e415d6350c3'),
    '10.3390/ma14164737': ('PMC8398119', '7db94eed9538162373148b144aa10ef716d97d39d5c0e2439c619f4e65fedd03'),
}
RECIPE_HASHES = {
    '10.1039/c8ra01329b': '0486b8e31cdcfbbce77c5d4b7edef548ea85a5a0a0c478374ede3c4e777071d4',
    '10.3390/ma13030560': '4b24e9ccb597f5e80308142817ec39dcaea8688f9a83b813a7d2ad4bee59ea0e',
}
RECEIPTS = {
    'routes': ('data/development/table4_6809_qualification_20261020_v1.json',
               '46a9d680ee0bfda3ca9b47ec137213f0c20ea91236cb847dab5099c19151c448'),
    'latp': ('data/development/rsc_access_latp_qualification_20261021_v1.json',
             '6b41768b204c525f5e4b5c90de2786ebf395c197712d7d6b7681f2901f5c8c93'),
}
EXCESS_UNKNOWN = {'reported_percent': None, 'author_unit': None, 'precursor': None,
                  'denominator_definition': None, 'normalized_elemental_Li_excess_fraction': None}


def _receipt(key):
    path, digest = RECEIPTS[key]
    raw = (Path(__file__).resolve().parents[2]/path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('immutable process receipt changed')
    return json.loads(raw)


def bind_process_conditions(raw, doi, pmcid):
    """Preserve precursor basis, process order and UNKNOWN without label features."""
    if (doi not in SOURCES or SOURCES[doi][0] != pmcid or not isinstance(raw, bytes)
            or hashlib.sha256(raw).hexdigest() != SOURCES[doi][1]):
        raise ValueError('unreviewed original process source bytes or DOI/PMC')
    from .harvest import extract_registered_measurements
    rows = extract_registered_measurements(raw, doi, pmcid)
    recipe, anchor = None, None
    if doi in RECIPE_HASHES:
        root = ET.fromstring(raw)
        matches = [(i, ' '.join(''.join(p.itertext()).split()))
                   for i, p in enumerate(root.findall('.//body//p'))
                   if '10 wt%' in ''.join(p.itertext())]
        if len(matches) != 1 or hashlib.sha256(matches[0][1].encode()).hexdigest() != RECIPE_HASHES[doi]:
            raise ValueError('reviewed precursor process context changed')
        index, recipe = matches[0]
        anchor = {'body_paragraph_index': index, 'normalized_text_sha256': RECIPE_HASHES[doi]}
    result = []
    for row in rows:
        fields = {'nominal_formula': row['nominal_formula'],
                  'final_route': row['manufacturing_route'],
                  'final_temperature_C': row['process_temperature_C'],
                  'final_duration_min': row['holding_time_min'],
                  'final_temperature_reference': 'AUTHOR_REPORTED_SINTERING_TEMPERATURE',
                  'powder_route': None, 'lithium_excess': dict(EXCESS_UNKNOWN),
                  'calcination_stages': None, 'final_applied_pressure_MPa': None,
                  'precursor_cold_press_MPa': None, 'sintering_atmosphere': None,
                  'heating_rate_K_min': None, 'cooling_rate_K_min': None,
                  'post_processing_sequence': None}
        evidence = {'original_raw_sha256': SOURCES[doi][1], 'recipe': anchor}
        if doi in RECIPE_HASHES:
            older = doi == '10.1039/c8ra01329b'
            pattern = (r'An excessive amount of (\d+) wt% (Li2CO3)' if older else
                       r'(\d+) wt% excess of (LiOH·H2O)')
            found = re.search(pattern, recipe)
            if not found: raise ValueError('explicit precursor excess association absent')
            fields.update(powder_route='SOLID_STATE_REACTION',
                          lithium_excess={**EXCESS_UNKNOWN, 'reported_percent': int(found[1]),
                                          'author_unit': 'wt%', 'precursor': found[2]},
                          calcination_stages=[{'temperature_C': 900 if older else 950,
                                               'duration_min': 600 if older else 720,
                                               'atmosphere': None if older else 'air'}],
                          precursor_cold_press_MPa=160 if older else 200)
            evidence['lithium_excess_literal'] = found[0]
        elif doi == '10.3390/ma14226809':
            history = _receipt('routes')['manufacturing_histories'][row['powder_synthesis_route']]
            common = history['common_final_process']
            # Preserve stage order; SD shares only the precursor solution with
            # SASSR, not its later seven-day drying and two calcinations.
            route = row['powder_synthesis_route']
            fields.update(powder_route={'SSR': 'SOLID_STATE_REACTION',
                                       'SASSR': 'SOLUTION_ASSISTED_SOLID_STATE_REACTION',
                                       'CP': 'CO_PRECIPITATION', 'SD': 'SPRAY_DRYING'}[route],
                          calcination_stages=[{'temperature_C': s['temperature_C'],
                                               'duration_min': s['time_h']*60,
                                               'atmosphere': s.get('atmosphere')}
                                              for s in history['steps']
                                              if s['stage'] in ('calcination 1', 'calcination 2',
                                                                'decompose nitrates/hydroxides',
                                                                'recalcination', 'calcination')],
                          precursor_cold_press_MPa=common['prepress_pressure_MPa'],
                          sintering_atmosphere=common['sinter_atmosphere'],
                          heating_rate_K_min=common['calcination_and_sintering_heating_ramp_K_min'],
                          post_processing_sequence=common['post_processing'])
            if route == 'CP':
                fields['lithium_excess'].update(reported_percent=10, author_unit='%', precursor='LiOH')
            evidence['recipe'] = {'section': history['section'],
                                  'normalized_text_sha256': history['source_section_sha256'],
                                  'common_final_section': common['sinter_evidence']}
            evidence['receipt_sha256'] = RECEIPTS['routes'][1]
        else:
            history = _receipt('latp')['latp']['manufacturing_history']
            fields.update(powder_route='SOLID_STATE_REACTION_THEN_TAPE_CASTING',
                          calcination_stages=[{'temperature_C': s['temperature_C'],
                                               'duration_min': s['time_min'], 'atmosphere': s['atmosphere']}
                                              for s in history['calcination']+[history['porous_sheet_calcination']]],
                          final_applied_pressure_MPa=row['pressure_MPa'],
                          final_temperature_reference=row['temperature_reference'])
            evidence['recipe'] = {'normalized_paragraph_hashes': row['method_context_sha256']}
            evidence['receipt_sha256'] = RECEIPTS['latp'][1]
        # Deliberately exclude final assayed Li, density and phase purity: these
        # are characterization outcomes, not preselection inputs in this audit.
        result.append({'doi': doi, 'pmcid': pmcid,
                       'condition_id': row.get('sample_code') or row.get('condition_id'),
                       'input_features': fields, 'feature_evidence': evidence,
                       'measurement_evidence': {k: row[k] for k in
                           ('original_cell', 'table_label', 'source_cell', 'source_clause',
                            'source_context_sha256', 'source_parser_metadata') if k in row},
                       'observed_TOTAL_S_cm': row['conductivity_S_cm'],
                       'source_measurement_temperature_C': row.get('measurement_temperature_C',
                           row.get('author_reported_measurement_temperature_C')),
                       'source_row_tier': row['tier'], 'new_strict_admission_authorized': False})
    return result


def summarize_process_identifiability(records):
    """Count representable input classes; UNKNOWN equality is not physical identity."""
    if not records or len({(r['doi'], r['condition_id']) for r in records}) != len(records):
        raise ValueError('empty or duplicate source conditions')
    from scripts.science.obelix_real_grouped_oof_0146 import _composition
    old, expanded = set(), set()
    per_source = {}
    for r in records:
        f = r['input_features']
        composition = _composition(f['nominal_formula'])
        if composition is None: raise ValueError('invalid nominal input formula')
        old.add((tuple(composition[1]), f['final_temperature_C'], f['final_duration_min']))
        expanded.add(json.dumps(f, sort_keys=True))
        per_source.setdefault(r['doi'], []).append(r)
    missing = {k: sum((r['input_features'][k]['reported_percent'] is None
                      if k == 'lithium_excess' else r['input_features'][k] is None) for r in records)
               for k in records[0]['input_features']}
    missing['lithium_excess_reported_percent'] = sum(
        r['input_features']['lithium_excess']['reported_percent'] is None for r in records)
    missing['normalized_elemental_Li_excess_fraction'] = sum(
        r['input_features']['lithium_excess']['normalized_elemental_Li_excess_fraction'] is None for r in records)
    levels = {doi: sorted({r['input_features']['lithium_excess']['reported_percent'] for r in rows
                          if r['input_features']['lithium_excess']['reported_percent'] is not None})
              for doi, rows in per_source.items()}
    return {'condition_rows': len(records), 'source_DOI_groups': len(per_source),
            'missingness_scope': 'UNKNOWN_OR_NOT_EXTRACTED_UNDER_REVIEWED_BINDINGS; not proof that a parameter is absent everywhere in the original paper',
            'frozen_composition_temperature_dwell_classes': len(old),
            'expanded_source_reported_input_classes': len(expanded),
            'missing_parameter_rows': missing, 'reported_excess_levels_by_DOI': levels,
            'DOIs_with_two_known_reported_excess_levels': sum(len(v) >= 2 for v in levels.values()),
            'lithium_effect_training_identifiable': False,
            'reason': 'No within-source excess contrast; no source-normalized elemental-Li excess. Do not impute UNKNOWN to zero or equate precursor wt% bases.',
            'measured_final_composition_used_as_feature': False,
            'new_feature_model_trained': False,
            'independent_predictive_claim': False}


def screen_process_support(training, candidates):
    """Necessary marginal support screen, not calibrated applicability qualification."""
    if not training or not candidates: raise ValueError('empty process support cohort')
    numeric = ('final_temperature_C', 'final_duration_min')
    def valid(value): return type(value) in (int, float) and math.isfinite(value) and value > 0
    bounds = {}
    for k in numeric:
        values = [r['input_features'][k] for r in training]
        if not all(valid(v) for v in values): raise ValueError('unknown training process support')
        bounds[k] = [min(values), max(values)]
    outputs = []
    for r in candidates:
        f = r['input_features']; reasons = []
        for k in numeric:
            if not valid(f[k]): reasons.append('UNKNOWN_'+k.upper())
            elif not bounds[k][0] <= f[k] <= bounds[k][1]: reasons.append('OUTSIDE_'+k.upper())
        for k in ('final_route', 'final_temperature_reference'):
            if f[k] is None or f[k] not in {x['input_features'][k] for x in training}:
                reasons.append('UNSUPPORTED_'+k.upper())
        outputs.append({'doi': r['doi'], 'condition_id': r['condition_id'],
                        'must_abstain': bool(reasons), 'reasons': reasons,
                        'screen': 'OUTSIDE_OR_UNKNOWN' if reasons else 'MARGINAL_RANGES_ONLY_NOT_QUALIFIED'})
    return {'training_bounds': bounds, 'candidates': outputs,
            'full_source_choice_must_abstain': any(x['must_abstain'] for x in outputs),
            'screen_grants_scientific_admission': False}


def evaluate_frozen_process_choices(records):
    """Replay 0191 decision ranking and heuristics, keeping OOD fits diagnostic.

    Each source has one nominal formula. Its composition-RF baseline is constant,
    so omitting that unknown constant preserves the 0191 residual-Ridge ranking.
    These are NOT calibrated full-Rhombus predictions or independent new scores.
    """
    from sklearn.linear_model import Ridge
    import numpy as np
    from scripts.science.obelix_solo_oxide_process_transfer_0191 import ALPHA, features
    dois = tuple(RECIPE_HASHES)
    groups = {doi: [r for r in records if r['doi'] == doi] for doi in dois}
    if any(len(v) != 5 for v in groups.values()): raise ValueError('frozen two-source population changed')
    for rows in groups.values():
        if (len({r['condition_id'] for r in rows}) != 5
                or len({r['input_features']['nominal_formula'] for r in rows}) != 1
                or any(r['source_measurement_temperature_C'] != 25 for r in rows)):
            raise ValueError('frozen source sample/formula/temperature boundary changed')
    if set(r['input_features']['nominal_formula'] for r in groups[dois[0]]) & set(
            r['input_features']['nominal_formula'] for r in groups[dois[1]]):
        raise ValueError('source-heldout nominal formula overlap')
    output = []
    for test_doi in dois:
        train_doi = next(x for x in dois if x != test_doi)
        train, test = groups[train_doi], groups[test_doi]
        def tuples(rows):
            return [(r['doi'], r['condition_id'], r['input_features']['nominal_formula'],
                     r['input_features']['final_temperature_C'], r['input_features']['final_duration_min'],
                     r['observed_TOTAL_S_cm']) for r in rows]
        a, b = tuples(train), tuples(test)
        truth = np.array([r['observed_TOTAL_S_cm'] for r in test])
        started = time.perf_counter()
        prediction = Ridge(alpha=ALPHA, fit_intercept=True).fit(features(a), np.log10([x[5] for x in a])).predict(features(b))
        elapsed = time.perf_counter()-started
        selectors = {'uniform': list(range(5))}
        started = time.perf_counter()
        for name, key, fn in [('hottest', 'final_temperature_C', max),
                              ('longest_dwell', 'final_duration_min', max),
                              ('shortest_dwell', 'final_duration_min', min)]:
            vals = [r['input_features'][key] for r in test]
            selectors[name] = [i for i, v in enumerate(vals) if v == fn(vals)]
        selector_elapsed = time.perf_counter()-started
        selectors['frozen_0191_rank_replay'] = list(np.flatnonzero(
            np.isclose(prediction, max(prediction), rtol=0, atol=1e-12)))
        policies = {name: {'uniform_tie_conditions': [test[i]['condition_id'] for i in indices],
                           'expected_observed_S_cm': float(truth[indices].mean()),
                           'point_oracle_regret_S_cm': float(max(truth)-truth[indices].mean()),
                           'top1_probability_under_uniform_ties': float(np.mean(truth[indices] == max(truth)))}
                    for name, indices in selectors.items()}
        output.append({'train_DOI': train_doi, 'test_DOI': test_doi,
                       'alpha': ALPHA, 'policies': policies, 'ridge_fit_predict_seconds': elapsed,
                       'three_heuristic_selectors_seconds': selector_elapsed,
                       'common_candidate_pool_size': len(test),
                       'replayed_rank_order': [test[i]['condition_id'] for i in np.argsort(-prediction)],
                       'process_support': screen_process_support(train, test),
                       'ranking_only_no_full_RF_prediction_or_MAE': True,
                       'source_labels_already_exposed': True,
                       'new_predictive_win_claim': False})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-directory', action='append', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    rows = []
    for doi, (pmc, digest) in SOURCES.items():
        paths = [Path(d)/digest for d in args.source_directory if (Path(d)/digest).is_file()]
        if not paths: raise ValueError('retained original missing: '+doi)
        rows.extend(bind_process_conditions(paths[0].read_bytes(), doi, pmc))
    result = {'schema_version': 'rhombus-source-process-feature-audit-v1',
              'records': rows, 'identifiability': summarize_process_identifiability(rows),
              'frozen_decision_replay': evaluate_frozen_process_choices(rows),
              'new_strict_qualified_DOI_groups': 0, 'new_strict_manufacturing_comparisons': 0,
              'scientific_GO': False, 'production_enabled': False,
              'official_TEST_121_accessed': False}
    with Path(args.output).open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
