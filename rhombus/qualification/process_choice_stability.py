"""Source-out sensitivity of the existing process Ridge, not a new predictor.

Public labels are exposed. Bounded label shifts are adversarial diagnostics,
never measured uncertainty, calibrated confidence or physical qualification.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from sklearn.linear_model import Ridge

from rhombus.evidence import (Applicability, DomainStatus, EvidenceRecord,
    OperationalStatus, ScientificVerdict, Uncertainty)
from rhombus.evidence.identity import SourceBinding
from scripts.science.obelix_solo_oxide_process_transfer_0191 import (
    ALPHA, S18, S20, features,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = 'data/development/process_choice_stability_0196_protocol_v1.json'
PROTOCOL_SHA256 = '256d176c2e9f294fa99a144c89cc6e68be149be89f2ee5fcd14cc5220e72dcd2'
INPUT = 'data/development/process_feature_identifiability_20261021_v1.json'
DOIS = ('10.1039/c8ra01329b', '10.3390/ma13030560')
SOURCE_HASHES = ('6dee69ef498243cc04c03a4d049175123cfac1b8dfa99257781da76d34979eea',
                 '51b35a6b942557d1f6cb7ab77d63ca36dbd4d3fbd44a6e44d0ad6f3557392b63')
TIE = 1e-9
DELTA = 0.1


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_inputs():
    raw = (ROOT / PROTOCOL).read_bytes()
    if sha(raw) != PROTOCOL_SHA256:
        raise ValueError('frozen protocol changed')
    protocol = json.loads(raw)
    for path, digest in protocol['inputs'].items():
        if sha((ROOT / path).read_bytes()) != digest:
            raise ValueError('historical input provenance changed')
    rows = json.loads((ROOT / INPUT).read_text())['records']
    sources = []
    for doi, expected, source_hash in zip(DOIS, (S18, S20), SOURCE_HASHES):
        selected = [r for r in rows if r['doi'] == doi]
        if len(selected) != 5 or len({r['condition_id'] for r in selected}) != 5:
            raise ValueError('incomplete or duplicate source population')
        mapped = {r['condition_id']: r for r in selected}
        ordered = [mapped[name] for name, _, _ in expected]
        formulas = {r['input_features']['nominal_formula'] for r in ordered}
        if len(formulas) != 1:
            raise ValueError('composition-only tie assumption violated')
        for r, (name, temperature, duration) in zip(ordered, expected):
            f = r['input_features']
            if (r['source_measurement_temperature_C'] != 25
                or f['final_route'] != 'CONVENTIONAL_SINTERING'
                or (f['final_temperature_C'], f['final_duration_min']) != (temperature, duration)
                or r['feature_evidence']['original_raw_sha256'] != source_hash
                or not r['measurement_evidence']):
                raise ValueError('source condition, measurement or provenance mismatch')
            if type(r['observed_TOTAL_S_cm']) not in (float, int) or not math.isfinite(r['observed_TOTAL_S_cm']) or r['observed_TOTAL_S_cm'] <= 0:
                raise ValueError('unsupported conductivity value')
        sources.append(ordered)
    return protocol, sources


def matrix(rows):
    return features([(r['doi'], r['condition_id'], r['input_features']['nominal_formula'],
        r['input_features']['final_temperature_C'], r['input_features']['final_duration_min'],
        None) for r in rows])


def unique_maximum(values, ids):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) != len(ids) or not np.isfinite(values).all():
        raise ValueError('invalid prediction vector')
    winners = np.flatnonzero(values.max() - values <= TIE)
    return ids[int(winners[0])] if len(winners) == 1 else None


def fit_process_choice(train, test):
    """Selection uses training labels and test process descriptors only."""
    if (len(train) not in (4, 5) or len(test) != 5
        or len({r['doi'] for r in train}) != 1 or len({r['doi'] for r in test}) != 1
        or train[0]['doi'] == test[0]['doi']
        or len({r['condition_id'] for r in train}) != len(train)
        or len({r['condition_id'] for r in test}) != len(test)):
        raise ValueError('invalid source-out fold')
    x, z = matrix(train), matrix(test)
    y = np.log10([r['observed_TOTAL_S_cm'] for r in train])
    if not np.isfinite(y).all():
        raise ValueError('nonfinite training labels')
    started = time.perf_counter()
    model = Ridge(alpha=ALPHA, fit_intercept=True).fit(x, y)
    predictions = model.predict(z)
    fit_seconds = time.perf_counter() - started
    centered = x - x.mean(axis=0)
    influence = np.ones((len(test), len(train))) / len(train)
    influence += (z - x.mean(axis=0)) @ np.linalg.solve(
        centered.T @ centered + ALPHA * np.eye(x.shape[1]), centered.T)
    if not np.allclose(predictions, influence @ y, atol=2e-10, rtol=0):
        raise ValueError('analytic influence does not match executed Ridge')
    ids = [r['condition_id'] for r in test]
    selected = unique_maximum(predictions, ids)
    certificate = None
    if selected is not None:
        winner = ids.index(selected)
        rivals = []
        for j, rival in enumerate(ids):
            if j == winner:
                continue
            direction = influence[winner] - influence[j]
            distance = float(np.abs(direction).sum())
            margin = float(predictions[winner] - predictions[j])
            if distance <= 1e-15 or margin <= TIE:
                raise ValueError('unidentifiable rival cannot support unique choice')
            radius = margin / distance
            perturbation = -radius * np.sign(direction)
            at_boundary = float(direction @ (y + perturbation))
            below = float(direction @ (y + .99 * perturbation))
            above = float(direction @ (y + 1.01 * perturbation))
            if abs(at_boundary) > 2e-10 or below <= 0 or above >= 0:
                raise ValueError('label robustness certificate failed explicit perturbation')
            rivals.append({'rival': rival, 'margin_log10': margin,
                'influence_L1': distance, 'radius_log10': radius,
                'boundary_training_log10_shifts': perturbation.tolist(),
                'boundary_margin_log10': at_boundary,
                'below_boundary_margin_log10': below, 'above_boundary_margin_log10': above})
        certificate = min(rivals, key=lambda r: (r['radius_log10'], r['rival']))
        certificate = {**certificate, 'all_rivals': rivals}
    return {'training_condition_ids': [r['condition_id'] for r in train],
        'relative_prediction_log10_scores': predictions.tolist(),
        'absolute_prediction_calibrated': False,
        'selected_condition': selected, 'coefficients': model.coef_.tolist(),
        'intercept': float(model.intercept_), 'design_rank': int(np.linalg.matrix_rank(centered)),
        'design_singular_values': np.linalg.svd(centered, compute_uv=False).tolist(),
        'label_robustness_certificate': certificate}, fit_seconds


def evaluate_fold(train, test):
    full, seconds = fit_process_choice(train, test)
    deletions, costs = [], [seconds]
    for i, row in enumerate(train):
        result, cost = fit_process_choice(train[:i] + train[i+1:], test)
        deletions.append({'omitted_training_condition': row['condition_id'], **result})
        costs.append(cost)
    ids = [r['condition_id'] for r in test]
    selected = full['selected_condition']
    stable = selected is not None and all(d['selected_condition'] == selected for d in deletions)
    radius = full['label_robustness_certificate']['radius_log10'] if selected else None
    robust = selected if stable and radius > DELTA else None
    def heuristic(key):
        ranks = [key(r['input_features']) for r in test]
        best = min(ranks)
        tied = [i for i, value in enumerate(ranks) if value == best]
        return ids[tied[0]] if len(tied) == 1 else None
    choices = {'full_Ridge': selected, 'robust_filter': robust,
        'hotter_shorter': heuristic(lambda f: (-f['final_temperature_C'], f['final_duration_min'])),
        'shorter_cooler': heuristic(lambda f: (f['final_duration_min'], f['final_temperature_C'])),
        'composition_only_O_ONLY_RF': None, 'composition_only_pooled_RF': None}
    # Only now are heldout labels consulted for retrospective evaluation.
    truth = np.log10([r['observed_TOTAL_S_cm'] for r in test])
    best_value = float(truth.max())
    policies = {name: {'selected_condition': choice, 'abstained': choice is None,
        'observed_regret_log10': None if choice is None else best_value - float(truth[ids.index(choice)]),
        'top_one_correct': None if choice is None else bool(best_value - truth[ids.index(choice)] <= TIE)}
        for name, choice in choices.items()}
    return {'train_DOI': train[0]['doi'], 'test_DOI': test[0]['doi'],
        'full': full, 'deletions': deletions, 'deletion_invariant': stable,
        'changed_or_tied_deletions': sum(d['selected_condition'] != selected for d in deletions),
        'policies': policies, 'observed_best_conditions': [ids[i] for i in np.flatnonzero(best_value - truth <= TIE)],
        'heldout_condition_ids': ids, 'heldout_observed_log10_S_cm': truth.tolist()}, costs


def run_experiment(*, authorized=False):
    if authorized is not True:
        raise PermissionError('trusted local diagnostic authorization required; MCP proposal is insufficient')
    wall, cpu = time.perf_counter(), time.process_time()
    protocol, sources = load_inputs()
    folds, costs = [], []
    for train, test in (sources, sources[::-1]):
        result, measured = evaluate_fold(train, test)
        folds.append(result)
        costs.extend(measured)
    if len(costs) != 12:
        raise ValueError('fit budget violated')
    summaries = {}
    for name in folds[0]['policies']:
        decisions = [f['policies'][name] for f in folds]
        scored = [d for d in decisions if not d['abstained']]
        summaries[name] = {'recommended_papers': len(scored), 'abstained_papers': 2-len(scored),
            'correct_recommended_papers': sum(d['top_one_correct'] for d in scored),
            'conditional_mean_regret_log10': float(np.mean([d['observed_regret_log10'] for d in scored])) if scored else None,
            'coverage': len(scored) / 2}
    kept = [f['policies']['robust_filter'] for f in folds if not f['policies']['robust_filter']['abstained']]
    findings = {'H1_deletion_invariance': 'SUPPORTED_ON_TWO_EXPOSED_STUDIES' if all(f['deletion_invariant'] for f in folds) else 'FALSIFIED',
        'H2_robust_filter_zero_observed_regret': 'INCONCLUSIVE_NO_RECOMMENDATIONS' if not kept else
            ('FALSIFIED' if any(d['observed_regret_log10'] > TIE for d in kept) else 'SUPPORTED_ON_RETAINED_EXPOSED_STUDIES'),
        'independent_generalization': 'INCONCLUSIVE', 'measurement_uncertainty': 'UNKNOWN',
        'model_applicability': 'UNQUALIFIED', 'new_independent_DOI_groups': 0}
    records = []
    for fold in folds:
        record = EvidenceRecord.create(candidate_id=fold['test_DOI'],
            evidence_kind='COMPUTED_PROCESS_SELECTION_SENSITIVITY', capability='assess_candidate_applicability',
            operational_status=OperationalStatus.SUCCEEDED, scientific_verdict=ScientificVerdict.INDETERMINATE,
            applicability=Applicability('source_out_process_choice_robustness', DomainStatus.UNQUALIFIED),
            uncertainty=Uncertainty(reason='Label stress is not measured EIS uncertainty; two exposed source studies, not independent specimens.',
                metrics={'diagnostic_kind': 'DETERMINISTIC_TRAINING_LABEL_STRESS_NOT_MEASURED_ERROR',
                    'stress_delta_log10': DELTA,
                    'minimum_label_shift_to_rank_tie_log10': fold['full']['label_robustness_certificate']['radius_log10'],
                    'deletion_invariant': fold['deletion_invariant'],
                    'full_Ridge_selected_condition': fold['full']['selected_condition'],
                    'observed_regret_log10': fold['policies']['full_Ridge']['observed_regret_log10'],
                    'independent_validation': False}),
            limitations=('EXPLORATORY_PUBLIC_SOURCE_DIAGNOSTIC', 'NO_BLIND_VALIDATION', 'NO_PHYSICAL_GO',
                         'STABLE_CHOICE_IS_NOT_CALIBRATED_ACCURACY', 'NO_NEW_ORIGINAL_SOURCE_ACQUIRED'),
            protocol_id=PROTOCOL_SHA256,
            source_bindings=tuple(SourceBinding('historically_authenticated_original_JATS', doi,
                uri='https://doi.org/'+doi, sha256=digest) for doi, digest in zip(DOIS, SOURCE_HASHES)),
            provenance={'input_artifact': INPUT, 'input_sha256': protocol['inputs'][INPUT],
                        'computation_code_sha256': sha(Path(__file__).read_bytes())},
            payload={'fold': fold, 'decision': 'ABSTAIN_UNQUALIFIED_SCIENTIFIC_RECOMMENDATION',
                'existence_state': 'UNKNOWN', 'dynamic_state': 'UNKNOWN',
                'transport_state': 'EXPERIMENTAL_SOURCE_REPORTED_NOT_PHYSICALLY_QUALIFIED',
                'scientific_GO': False, 'production_enabled': False})
        records.append(record.to_dict())
    elapsed = time.perf_counter() - wall
    if elapsed > protocol['budget']['wall_seconds']:
        raise ValueError('diagnostic wall budget exceeded')
    return {'schema_version': 'rhombus-process-choice-stability-result-v1', 'protocol_sha256': PROTOCOL_SHA256,
        'protocol_path': PROTOCOL, 'input_hashes': protocol['inputs'],
        'computation_code_sha256': sha(Path(__file__).read_bytes()), 'source_rows': sources,
        'folds': folds, 'policy_summaries': summaries, 'findings': findings, 'evidence_records': records,
        'cost': {'unique_Ridge_fits': 12, 'fit_seconds': costs, 'total_fit_seconds': sum(costs),
                 'wall_seconds': elapsed, 'process_cpu_seconds': time.process_time()-cpu,
                 'network_requests': 0, 'monetary_USD': 0,
                 'standalone_policy_runtimes': None, 'shared_cost_counted_once': True},
        'original_source_acquisition': 'BLOCKED_UNCHANGED_NETWORK_POLICY', 'new_original_bytes': 0,
        'new_STRICT_DOI_groups': 0, 'new_STRICT_manufacturing_comparisons': 0,
        'scientific_GO': False, 'production_enabled': False, 'TEST121_accessed': False,
        'P0_01': 'BLOCKED', 'P0_02': 'BLOCKED', 'P0_03': 'BLOCKED',
        'next_scientific_action': protocol['next_action_rule']}
