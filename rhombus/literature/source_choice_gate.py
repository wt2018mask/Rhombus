"""Fail-closed decision release gate for previously exposed 0191 rank replays.

Only the known 2018/2020 source-out diagnostic is covered. This pure module
never trains, predicts, inspects OBELiX TEST or admits an external benchmark.
It converts diagnostic selections to abstentions when the training support or
scientific source qualifications are insufficient.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA = 'rhombus-source-process-feature-audit-v1'
SOURCE_DOIS = frozenset({'10.1039/c8ra01329b', '10.3390/ma13030560'})


def gate_source_choice_report(report: dict) -> dict:
    """Do not release any retrospective rank as an authorized recommendation.

    The full source report is prior-exposed diagnostic evidence; even an
    in-range marginal descriptor is not sufficient for scientific deployment.
    Any contradiction in stored support flags fails rather than changing the
    scientific conclusion, which avoids silently accepting a forged receipt.
    """
    if not isinstance(report, dict) or report.get('schema_version') != SCHEMA:
        raise ValueError('unknown original process audit identity')
    for name in ('scientific_GO', 'production_enabled', 'official_TEST_121_accessed'):
        if report.get(name) is not False:
            raise ValueError('scientific safety or TEST boundary changed')
    if (report.get('new_strict_qualified_DOI_groups') != 0 or
            report.get('new_strict_manufacturing_comparisons') != 0):
        raise ValueError('unverified strict qualification promotion')
    claims = report.get('claim_boundaries')
    if (not isinstance(claims, dict) or claims.get('checkpoint_0195_consumed') is not False
            or claims.get('statistical_significance_or_model_superiority_claim') is not False
            or any(claims.get(k) != 'BLOCKED' for k in ('P0_01','P0_02','P0_03'))):
        raise ValueError('unverified scientific checkpoint or P0 promotion')
    replay = report.get('frozen_decision_replay')
    records = report.get('records')
    if not isinstance(replay, list) or len(replay) != 2 or not isinstance(records, list):
        raise ValueError('frozen source-out cohort changed')
    groups = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError('invalid source record')
        doi, condition = record.get('doi'), record.get('condition_id')
        if not isinstance(doi, str) or not isinstance(condition, str) or not condition:
            raise ValueError('missing source condition identity')
        key = (doi, condition)
        if key in groups:
            raise ValueError('duplicate physical condition label')
        groups[key] = record
    result = []
    encountered = set()
    excluded_candidates = 0
    for fold in replay:
        if not isinstance(fold, dict):
            raise ValueError('invalid frozen fold')
        train, test = fold.get('train_DOI'), fold.get('test_DOI')
        if (train == test or frozenset((train, test)) != SOURCE_DOIS or
                test in encountered or fold.get('ranking_only_no_full_RF_prediction_or_MAE') is not True
                or fold.get('new_predictive_win_claim') is not False):
            raise ValueError('source-heldout rank replay changed')
        encountered.add(test)
        support = fold.get('process_support')
        policies = fold.get('policies')
        if not isinstance(support, dict) or not isinstance(policies, dict):
            raise ValueError('missing frozen support/policy record')
        cands = support.get('candidates')
        if (not isinstance(cands, list) or len(cands) != 5 or
                support.get('screen_grants_scientific_admission') is not False):
            raise ValueError('unsupported source-choice screen')
        expected = {condition for doi, condition in groups if doi == test}
        found = set()
        reasons = set()
        for candidate in cands:
            if not isinstance(candidate, dict) or candidate.get('doi') != test:
                raise ValueError('support candidate from wrong source')
            code, blocked, why = (candidate.get('condition_id'),
                                  candidate.get('must_abstain'), candidate.get('reasons'))
            if (not isinstance(code, str) or code in found or type(blocked) is not bool or
                    not isinstance(why, list) or any(not isinstance(x, str) or not x for x in why)
                    or len(why) != len(set(why)) or blocked != bool(why)):
                raise ValueError('contradictory candidate support reasons')
            if candidate.get('screen') != ('OUTSIDE_OR_UNKNOWN' if blocked else 'MARGINAL_RANGES_ONLY_NOT_QUALIFIED'):
                raise ValueError('support candidate screen inconsistent')
            found.add(code)
            reasons.update(why)
            excluded_candidates += int(blocked)
        if found != expected or len(found) != 5:
            raise ValueError('source comparison candidate identity mismatch')
        if support.get('full_source_choice_must_abstain') is not bool(reasons):
            raise ValueError('source-level support flag inconsistent')
        frozen = policies.get('frozen_0191_rank_replay')
        if not isinstance(frozen, dict):
            raise ValueError('missing original diagnostic rank')
        choice = frozen.get('uniform_tie_conditions')
        if (not isinstance(choice, list) or not choice or len(choice) != len(set(choice))
                or not set(choice) <= found):
            raise ValueError('rank points outside original candidate pool')
        flags = (['OUTSIDE_TRAINING_PROCESS_SUPPORT'] if reasons else
                 ['MARGINAL_RANGE_IS_NOT_VALIDATED_DOMAIN'])
        flags += ['RETROSPECTIVE_EXPOSED_LABELS', 'NO_STRICT_OR_PHYSICAL_INDEPENDENT_ADMISSION']
        result.append({
            'train_DOI': train, 'test_DOI': test, 'candidate_count': 5,
            'out_of_support_candidates': sum(bool(c['must_abstain']) for c in cands),
            'diagnostic_rank_choice_only': choice,
            'authorized_manufacturing_choice': None,
            'status': 'ABSTAIN', 'reasons': flags,
            'support_failure_codes': sorted(reasons),
            'independent_model_vs_baseline_score': None,
        })
    if encountered != SOURCE_DOIS:
        raise ValueError('incomplete original source-out fold directions')
    return {
        'schema_version': 'rhombus-source-choice-release-gate-v1',
        'input': 'ALREADY_EXPOSED_0191_RETROSPECTIVE_DECISION_REPLAY',
        'evaluated_folds': len(result),
        'candidate_conditions': sum(x['candidate_count'] for x in result),
        'out_of_support_candidate_conditions': excluded_candidates,
        'authorized_choice_count': 0,
        'scientifically_scoreable_model_vs_heuristic_comparisons': 0,
        'model_superiority_demonstrated': False,
        'original_TEST_121_accessed': False,
        'scientific_GO': False, 'production_enabled': False,
        'folds': result,
    }


def gate_file(path: str | Path) -> dict:
    """Attach only the derived report's hash, never claim an original-paper SHA."""
    raw = Path(path).read_bytes()
    result = gate_source_choice_report(json.loads(raw))
    result['input_retrospective_report_sha256'] = hashlib.sha256(raw).hexdigest()
    return result
