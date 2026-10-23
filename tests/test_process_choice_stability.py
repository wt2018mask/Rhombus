"""Actual retained scientific inputs and adversarial sensitivity certificates."""
import copy
import hashlib
import json

import numpy as np
import pytest

from rhombus.qualification import process_choice_stability as p
from rhombus.tools.evidence_query import _verify_evidence_row


def test_actual_source_out_computation_and_negative_robustness_result():
    r = p.run_experiment(authorized=True)
    assert len(r['source_rows']) == len(r['folds']) == 2
    assert r['cost']['unique_Ridge_fits'] == 12
    assert len(r['cost']['fit_seconds']) == 12
    assert r['cost']['network_requests'] == r['new_original_bytes'] == 0
    assert r['findings']['H1_deletion_invariance'] == 'SUPPORTED_ON_TWO_EXPOSED_STUDIES'
    assert r['findings']['H2_robust_filter_zero_observed_regret'] == 'FALSIFIED'
    assert [f['full']['selected_condition'] for f in r['folds']] == ['SL2', 'LLZALO-5']
    assert all(f['changed_or_tied_deletions'] == 0 for f in r['folds'])
    assert [f['full']['label_robustness_certificate']['radius_log10'] for f in r['folds']] == pytest.approx([.1610797829796955, .41055442560228717])
    assert r['policy_summaries']['full_Ridge'] == r['policy_summaries']['robust_filter']
    assert r['policy_summaries']['robust_filter'] == r['policy_summaries']['hotter_shorter']
    assert r['policy_summaries']['full_Ridge']['correct_recommended_papers'] == 1
    assert r['policy_summaries']['composition_only_pooled_RF']['conditional_mean_regret_log10'] is None
    assert not r['TEST121_accessed'] and not r['scientific_GO'] and not r['production_enabled']
    for i, e in enumerate(r['evidence_records'], 1):
        _verify_evidence_row(e, lineno=i)
        assert e['scientific_verdict'] == 'INDETERMINATE'
        assert e['payload']['decision'].startswith('ABSTAIN')


def test_selection_never_reads_heldout_conductivity_labels():
    _, (train, test) = p.load_inputs()
    original, _ = p.fit_process_choice(train, test)
    blind = copy.deepcopy(test)
    for row in blind:
        del row['observed_TOTAL_S_cm']
    proposal, _ = p.fit_process_choice(train, blind)
    assert original == proposal


def test_certificate_changes_rank_at_exact_label_shift():
    _, (train, test) = p.load_inputs()
    full, _ = p.fit_process_choice(train, test)
    cert = full['label_robustness_certificate']
    changed = copy.deepcopy(train)
    for row, delta in zip(changed, cert['boundary_training_log10_shifts']):
        row['observed_TOTAL_S_cm'] *= 10 ** (delta * 1.01)
    after, _ = p.fit_process_choice(changed, test)
    assert after['selected_condition'] != full['selected_condition']
    for row, original, delta in zip(changed, train, cert['boundary_training_log10_shifts']):
        row['observed_TOTAL_S_cm'] = original['observed_TOTAL_S_cm'] * 10 ** (delta * .99)
    below, _ = p.fit_process_choice(changed, test)
    assert below['selected_condition'] == full['selected_condition']


def test_constant_composition_model_offsets_cannot_change_ranks():
    _, (train, test) = p.load_inputs()
    first, _ = p.fit_process_choice(train, test)
    shifted = copy.deepcopy(train)
    for row in shifted:
        row['observed_TOTAL_S_cm'] *= 100
    result, _ = p.fit_process_choice(shifted, test)
    assert result['selected_condition'] == first['selected_condition']
    assert np.asarray(result['relative_prediction_log10_scores']) - np.asarray(first['relative_prediction_log10_scores']) == pytest.approx([2] * 5)
    assert result['label_robustness_certificate']['radius_log10'] == pytest.approx(first['label_robustness_certificate']['radius_log10'])


def test_protocol_and_input_drift_fail_closed(monkeypatch):
    monkeypatch.setattr(p, 'PROTOCOL_SHA256', '0' * 64)
    with pytest.raises(ValueError, match='protocol changed'):
        p.load_inputs()


def test_unauthorized_request_cannot_even_load_inputs(monkeypatch):
    def forbidden():
        raise AssertionError('unauthorized read')
    monkeypatch.setattr(p, 'load_inputs', forbidden)
    with pytest.raises(PermissionError):
        p.run_experiment()


@pytest.mark.parametrize('change', ['same_DOI', 'duplicate', 'missing_feature', 'nonfinite_label'])
def test_wrong_folds_and_unresolved_features_are_not_scored(change):
    _, (train, test) = p.load_inputs()
    train, test = copy.deepcopy(train), copy.deepcopy(test)
    if change == 'same_DOI':
        test = copy.deepcopy(train)
    elif change == 'duplicate':
        train[1] = copy.deepcopy(train[0])
    elif change == 'missing_feature':
        train[0]['input_features']['final_duration_min'] = None
    else:
        train[0]['observed_TOTAL_S_cm'] = float('nan')
    with pytest.raises(ValueError):
        p.fit_process_choice(train, test)


def test_ties_and_nonfinite_predictions_abstain_or_reject():
    assert p.unique_maximum([1, 1], ['a', 'b']) is None
    assert p.unique_maximum([1, 1+1e-10], ['a', 'b']) is None
    with pytest.raises(ValueError):
        p.unique_maximum([1, float('nan')], ['a', 'b'])


def test_content_ids_exclude_wallclock_measurements():
    first, second = p.run_experiment(authorized=True), p.run_experiment(authorized=True)
    assert first['evidence_records'] == second['evidence_records']
    assert first['folds'] == second['folds']
