"""Process provenance, missingness, extrapolation and decision-only replay."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from rhombus.literature import process_features as p

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'data/development/process_feature_identifiability_20261021_v1.json'


def report(): return json.loads(REPORT.read_text())
def rows(): return report()['records']
def source(records, doi): return [r for r in records if r['doi'] == doi]


def test_input_classes_and_missingness_are_not_predictive_gain():
    result = p.summarize_process_identifiability(rows())
    assert result == report()['identifiability']
    assert result['condition_rows'] == 17 and result['source_DOI_groups'] == 4
    assert result['frozen_composition_temperature_dwell_classes'] == 14
    assert result['expanded_source_reported_input_classes'] == 17
    assert result['DOIs_with_two_known_reported_excess_levels'] == 0
    assert result['missing_parameter_rows']['lithium_excess'] == 6
    assert result['missing_parameter_rows']['normalized_elemental_Li_excess_fraction'] == 17
    assert not result['lithium_effect_training_identifiable']
    assert not result['new_feature_model_trained'] and not result['independent_predictive_claim']


def test_distinct_precursor_bases_not_collapsed_and_unknown_not_zero():
    records = rows()
    a, b = [source(records, doi)[0]['input_features']['lithium_excess']
            for doi in tuple(p.RECIPE_HASHES)]
    assert a['reported_percent'] == b['reported_percent'] == 10
    assert a['precursor'] == 'Li2CO3' and b['precursor'] == 'LiOH·H2O'
    assert a != b
    for r in records:
        f = r['input_features']; assert f['lithium_excess']['normalized_elemental_Li_excess_fraction'] is None
        assert f['lithium_excess']['denominator_definition'] is None
        assert not {'density', 'measured_final_composition', 'conductivity_S_cm', 'condition_id'} & f.keys()
    cp = next(r for r in records if r['doi'] == '10.3390/ma14226809' and r['condition_id'] == 'CP')
    assert cp['input_features']['lithium_excess']['author_unit'] == '%'


def test_route_order_cold_press_and_mold_reference_remain_separate():
    records = rows(); routes = source(records, '10.3390/ma14226809')
    assert len({r['input_features']['powder_route'] for r in routes}) == 4
    assert [[s['duration_min'] for s in r['input_features']['calcination_stages']] for r in routes] == [
        [1200, 1200], [60, 1200], [60], [60]]
    for r in routes:
        f = r['input_features']
        assert f['precursor_cold_press_MPa'] == 120 and f['final_applied_pressure_MPa'] is None
    for r in source(records, '10.3390/ma14164737'):
        f = r['input_features']
        assert f['final_applied_pressure_MPa'] == 25 and f['precursor_cold_press_MPa'] is None
        assert f['final_temperature_reference'] == 'PREHEATED_MOLD_TARGET'


def test_source_wrappers_refuse_unobserved_rsc_and_changed_bytes():
    for doi, (pmc, digest) in p.SOURCES.items():
        with pytest.raises(ValueError, match='source bytes or DOI/PMC'):
            p.bind_process_conditions(b'not original JATS', doi, pmc)
        with pytest.raises(ValueError): p.bind_process_conditions(b'x', doi, 'PMC1')
    with pytest.raises(ValueError):
        p.bind_process_conditions(b'<html>challenge</html>', '10.1039/d2ta09250f', '')
    assert all(p._receipt(k) for k in p.RECEIPTS)


def test_route_adapter_with_explicit_derived_fixture_hash(monkeypatch):
    """Unit fixture only; this does not authenticate the different original bytes."""
    from rhombus.literature import table4
    doi = table4.DOI
    raw = (ROOT/'data/development/table4_6809_source_excerpt_20261020_v1.xml').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest != p.SOURCES[doi][1]
    monkeypatch.setitem(p.SOURCES, doi, (table4.PMC, digest))
    monkeypatch.setattr(table4, 'JATS_SHA256', digest)
    bound = p.bind_process_conditions(raw, doi, table4.PMC)
    originals = source(rows(), doi)
    assert [r['input_features'] for r in bound] == [r['input_features'] for r in originals]
    assert [r['condition_id'] for r in bound] == ['SSR', 'SASSR', 'CP', 'SD']


def test_labels_and_ids_are_not_new_process_features():
    records = rows(); expected = p.summarize_process_identifiability(records)
    for i, r in enumerate(records):
        r['observed_TOTAL_S_cm'] = 10**(-i-3)
        r['condition_id'] = 'unit-test-condition-'+str(i)
    assert p.summarize_process_identifiability(records) == expected
    records.append(copy.deepcopy(records[0]))
    with pytest.raises(ValueError, match='duplicate'): p.summarize_process_identifiability(records)


def test_all_ten_old_transfer_rows_are_outside_fold_dwell_support():
    records = rows()
    for doi in p.RECIPE_HASHES:
        train_doi = next(d for d in p.RECIPE_HASHES if d != doi)
        screen = p.screen_process_support(source(records, train_doi), source(records, doi))
        assert screen['full_source_choice_must_abstain']
        assert len(screen['candidates']) == 5
        assert all('OUTSIDE_FINAL_DURATION_MIN' in r['reasons'] for r in screen['candidates'])
        assert not screen['screen_grants_scientific_admission']


@pytest.mark.parametrize('value', [None, 0, -1, True, float('nan'), float('inf')])
def test_unknown_and_invalid_candidate_time_abstains_without_imputation(value):
    train = source(rows(), '10.3390/ma13030560'); candidates = copy.deepcopy(train[:1])
    candidates[0]['input_features']['final_duration_min'] = value
    screen = p.screen_process_support(train, candidates)
    assert screen['candidates'][0]['reasons'] == ['UNKNOWN_FINAL_DURATION_MIN']
    with pytest.raises(ValueError, match='unknown training'):
        p.screen_process_support(candidates, train)


def test_marginal_bounds_are_inclusive_and_cannot_grant_qualified_domain():
    records = source(rows(), '10.3390/ma13030560')
    screen = p.screen_process_support(records, records)
    assert not screen['full_source_choice_must_abstain']
    assert all(r['screen'] == 'MARGINAL_RANGES_ONLY_NOT_QUALIFIED' for r in screen['candidates'])
    assert not screen['screen_grants_scientific_admission']
    cold = source(rows(), '10.3390/ma14164737')
    screened = p.screen_process_support(records, cold)
    assert all('UNSUPPORTED_FINAL_ROUTE' in r['reasons'] for r in screened['candidates'])


def test_frozen_rank_replay_has_no_choice_advantage_over_shortest_dwell():
    output = p.evaluate_frozen_process_choices(rows())
    expected = report()['frozen_decision_replay']
    for result, old in zip(output, expected, strict=True):
        assert result['policies'] == old['policies']
        assert result['process_support'] == old['process_support']
        policies = result['policies']
        assert policies['frozen_0191_rank_replay'] == policies['shortest_dwell']
        assert result['alpha'] == 1 and result['common_candidate_pool_size'] == 5
        assert result['ranking_only_no_full_RF_prediction_or_MAE']
        assert not result['new_predictive_win_claim']
    assert [r['policies']['frozen_0191_rank_replay']['uniform_tie_conditions'] for r in output] == [
        ['LLZALO-5'], ['SL2']]
    assert [r['policies']['frozen_0191_rank_replay']['point_oracle_regret_S_cm'] for r in output] == pytest.approx([7.8e-5, 0])


def test_heldout_truth_cannot_choose_frozen_model_recommendation():
    records = rows(); old = p.evaluate_frozen_process_choices(records)[0]
    for r in source(records, old['test_DOI']): r['observed_TOTAL_S_cm'] = 1e-5
    out = p.evaluate_frozen_process_choices(records)[0]
    assert out['policies']['frozen_0191_rank_replay']['uniform_tie_conditions'] == old['policies']['frozen_0191_rank_replay']['uniform_tie_conditions']
    assert out['replayed_rank_order'] == old['replayed_rank_order']


def test_rank_replay_matches_original_frozen_fold_with_different_constant_rf_baselines():
    from scripts.science.obelix_solo_oxide_process_transfer_0191 import fold
    records = rows()
    for result in p.evaluate_frozen_process_choices(records):
        def tuples(doi):
            return [(r['doi'], r['condition_id'], r['input_features']['nominal_formula'],
                     r['input_features']['final_temperature_C'], r['input_features']['final_duration_min'],
                     r['observed_TOTAL_S_cm']) for r in source(records, doi)]
        a, b = tuples(result['train_DOI']), tuples(result['test_DOI'])
        for train_constant, test_constant in [(0, 0), (-1.2, 3.4)]:
            old = fold(a, b, {result['train_DOI']: train_constant, result['test_DOI']: test_constant})
            selected = old['models']['TRAIN_DOI_PROCESS_RIDGE']['top1_selected']
            assert result['policies']['frozen_0191_rank_replay']['uniform_tie_conditions'] == [selected]


@pytest.mark.parametrize('change', ['duplicate', 'temperature', 'formula_overlap'])
def test_frozen_replay_refuses_changed_cohort_identity(change):
    records = rows(); a = source(records, '10.1039/c8ra01329b')
    if change == 'duplicate': a[1]['condition_id'] = a[0]['condition_id']
    if change == 'temperature': a[0]['source_measurement_temperature_C'] = None
    if change == 'formula_overlap':
        for r in a: r['input_features']['nominal_formula'] = 'Li6.6La3Zr1.6Nb0.4O12'
        other = source(records, '10.3390/ma13030560')
        for r in other: r['input_features']['nominal_formula'] = 'Li6.6La3Zr1.6Nb0.4O12'
    with pytest.raises(ValueError): p.evaluate_frozen_process_choices(records)


def test_rsc_http200_challenge_is_not_an_authenticated_pdf():
    r = report(); success = next(x for x in r['rsc_access'] if x.get('http_status') == 200)
    assert success['bytes'] == 248 and success['failure'] == 'NON_PDF_JAVASCRIPT_CHALLENGE_HTML'
    assert success['sha256'] == '4681fa6e4303ecc351521fa1c7c836c9f3d6774b11725d39885ec3bf8ff16561'
    assert success['original_document_sha256'] is None and not success['original_document_authenticated']
    assert not success['challenge_executed_or_bypassed']
    policies = r['rsc_exposed_lead_arithmetic']['heuristic_policy_consequences']
    assert [policies[k]['expected_mS_cm'] for k in ('uniform_all_16',
            'minimum_lithium_excess_uniform_dwell', 'longest_dwell_uniform_excess',
            'minimum_excess_shortest_dwell', 'minimum_excess_longest_dwell')] == [.221875, .63, .2025, .42, .45]
    assert not r['claim_boundaries']['checkpoint_0195_consumed']
    assert r['new_strict_qualified_DOI_groups'] == r['new_strict_manufacturing_comparisons'] == 0
