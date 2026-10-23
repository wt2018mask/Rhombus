"""Retrospective, source-level O_ONLY vs pooled RF robustness; not predictive training.

Frozen 0188 five original DOI groups and separate, unqualified 0185 cohort.
No test labels, raw structures, external papers or network are read.
Exact sign resampling is DESCRIPTIVE (lab/chemistry independence unverified).
"""
from __future__ import annotations
import hashlib
import itertools
import json
import math
from pathlib import Path

DOIS = ('10.1039/d5ra03917g', '10.3390/nano12172946',
        '10.3390/ma13030560', '10.1039/c8ra01329b',
        '10.3390/ma14226809')
MODELS = ('O_ONLY_RF', 'POOLED_RF', 'O_ONLY_RIDGE', 'O_ONLY_TRAIN_MEAN')

def _num(x):
    if type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 10:
        raise ValueError('nonfinite or unsupported frozen source metric')
    return float(x)

def _validate_0188(d):
    if (not isinstance(d, dict) or d.get('schema_version') !=
            'rhombus-0188-original-five-doi-evidence-v1' or
            d.get('checkpoint_index') != 188 or d.get('doi_groups') != list(DOIS) or
            d.get('actual_doi_groups') != 5 or d.get('actual_conditions') != 22 or
            d.get('source_workflow') != 'SUCCESS' or
            d.get('numeric_original_result') !=
            'FIVE_FIRSTPARTY_DOI_GROUPS_22_REFERENCE_STATES_MATCHED_25C_TOTAL_REAL_NUMERIC_SCORE' or
            d.get('original_obelix_test') != 'UNREAD' or
            d.get('scientific_GO') is not False or d.get('production_oxide_model') is not False or
            d.get('physical_P0') != ['BLOCKED']*3):
        raise ValueError('0188 source population or claim drift')
    models = d.get('model_results')
    if not isinstance(models, dict) or set(models) != set(MODELS):
        raise ValueError('model population drift')
    out = {}
    for name in MODELS:
        m = models[name]
        if not isinstance(m, dict) or set(m.get('per_DOI', {})) != set(DOIS):
            raise ValueError('changed author DOI score population')
        scores = [_num(m['per_DOI'][doi]) for doi in DOIS]
        _num(m.get('row_MAE_log10'))
        if abs(sum(scores)/5-_num(m.get('equal_DOI_macro_MAE_log10'))) > 1e-7:
            raise ValueError('source-group macro metric inconsistent')
        out[name] = scores
    diff = (sum(out['O_ONLY_RF'])-sum(out['POOLED_RF']))/5
    if (abs(_num(-d.get('group_macro_specialist_minus_pooled', float('nan')))-(-diff)) > 1e-7 or
            d.get('new_2018_POOLED_RF_better_than_specialist') is not True or
            out['O_ONLY_RF'][3] <= out['POOLED_RF'][3]):
        raise ValueError('frozen negative case or macro claim changed')
    return out

def _validate_0185(d):
    if (not isinstance(d, dict) or d.get('schema_version') !=
            'rhombus-0185-O_ONLY-original-external-evidence-v1' or
            d.get('checkpoint_index') != 185 or
            d.get('source_workflow') != 'SUCCESS' or
            d.get('observed_numeric_experiment') !=
            'REAL_SOURCE_EXPLORATORY_NUMERICAL_DIAGNOSTIC_NOT_QUALIFIED' or
            d.get('external_measurement_comparability') != 'UNATTESTED' or
            d.get('official_TEST_reserved') != 'UNREAD' or
            d.get('actual_external_nonblank') != 176 or d.get('actual_eligible_rows') != 164 or
            d.get('actual_connected_DOI_formula_groups') != 36 or
            d.get('scientific_GO') is not False or
            d.get('production_router_enabled') is not False or
            d.get('P0') != ['BLOCKED']*3 or d.get('physical_P0') != ['BLOCKED']*3):
        raise ValueError('0185 comparability or scientific boundary drift')
    result = {}
    for metric in ('actual_equal_group_macro_MAE_log10', 'actual_row_MAE_log10'):
        cohort = d.get(metric)
        if not isinstance(cohort, dict) or set(cohort) != set(MODELS):
            raise ValueError('secondary frozen models drift')
        result[metric] = {name: _num(cohort[name]) for name in MODELS}
    return result

def analyze_prior_model_evidence(original_five, secondary_cohort):
    original = _validate_0188(original_five)
    secondary = _validate_0185(secondary_cohort)
    diffs = [x-y for x,y in zip(original['POOLED_RF'], original['O_ONLY_RF'], strict=True)]
    n = len(diffs)
    avg = sum(diffs)/n
    ref = [sum(sign*d for sign,d in zip(signs,diffs,strict=True))/n
           for signs in itertools.product((-1,1),repeat=n)]
    tail = sum(abs(x) >= abs(avg)-1e-12 for x in ref)
    resamples = sorted(sum(diffs[i] for i in indices)/n
                       for indices in itertools.product(range(n), repeat=n))
    leave_one = [(sum(diffs)-diff)/(n-1) for diff in diffs]
    macro = secondary['actual_equal_group_macro_MAE_log10']
    row = secondary['actual_row_MAE_log10']
    return {
        'schema_version': 'rhombus-public-source-rf-paired-sensitivity-v1',
        'original_0188': {
            'doi_count': n,
            'measurement_conditions_not_independent_pellets': 22,
            'source_doi_order': list(DOIS),
            'per_doi_pooled_minus_oxide_mae_log10':
                {doi: round(v,8) for doi,v in zip(DOIS,diffs,strict=True)},
            'equal_paper_macro_mae_oxide_rf_log10':
                original_five['model_results']['O_ONLY_RF']['equal_DOI_macro_MAE_log10'],
            'equal_paper_macro_mae_pooled_rf_log10':
                original_five['model_results']['POOLED_RF']['equal_DOI_macro_MAE_log10'],
            'paired_mean_gain_log10': round(avg,8),
            'paper_wins_oxide_rf': sum(x>0 for x in diffs),
            'paper_losses_oxide_rf': sum(x<0 for x in diffs),
            'minimum_leave_one_doi_out_gain_log10': round(min(leave_one),8),
            'exact_sign_flip_descriptive_reference': {
                'combinations': len(ref), 'two_sided_tail_count': tail,
                'two_sided_tail_fraction_NOT_a_p_value': tail/len(ref),
                'independent_sign_exchangeability_verified': False,
            },
            'exhaustive_empirical_source_resampling_NOT_CI': {
                'draws': len(resamples),
                'lower_2_5_percentile': round(resamples[int(.025*(len(resamples)-1))],8),
                'upper_97_5_percentile': round(resamples[int(.975*(len(resamples)-1))],8),
                'nonpositive_gain_fraction': round(sum(v<=0 for v in resamples)/len(resamples),8),
                'independent_doi_groups_verified': False,
            },
        },
        'secondary_0185_unqualified_DO_NOT_POOL': {
            'connected_provenance_groups': 36, 'comparability': 'UNATTESTED',
            'oxide_rf_macro_mae_log10': macro['O_ONLY_RF'],
            'pooled_rf_macro_mae_log10': macro['POOLED_RF'],
            'macro_pooled_minus_oxide_log10': round(macro['POOLED_RF']-macro['O_ONLY_RF'],8),
            'row_pooled_minus_oxide_log10': round(row['POOLED_RF']-row['O_ONLY_RF'],8),
            'can_pool_with_original_0188': False,
        },
        'scientific_decision': {
            'SOLO_PUBLIC_BENCHMARK': 'INCONCLUSIVE',
            'SCIENTIFIC_EXTERNAL_PHYSICAL': 'NO-GO',
            'specialist_production_activation': False,
            'independent_model_superiority_proven': False,
            'manufacturing_top1_or_regret_measured_here': False,
            'new_STRICT_DOI_groups': 0,
            'new_STRICT_manufacturing_comparisons': 0,
            'P0_01_P0_02_P0_03': ['BLOCKED']*3,
            'OBELIX_official_TEST_121': 'UNREAD',
            'warnings': [
                'PAST_EXPOSED_MODEL_SELECTION_SOURCE_NOT_PROSPECTIVE',
                'ONLY_FIVE_AUTHOR_DOIS_WITH_POSSIBLE_LAB_AND_CHEMISTRY_OVERLAP',
                'SIGN_FLIP_AND_SOURCE_RESAMPLE_ARE_DESCRIPTIVE_NOT_CONFIRMATORY',
                'SECONDARY_0185_OBSERVABLE_AND_TEMPERATURE_UNATTESTED',
                'MAE_IS_NOT_MANUFACTURING_CANDIDATE_CHOICE',
            ],
        },
    }

def analyze_files(original_path, secondary_path):
    x,y=Path(original_path).read_bytes(),Path(secondary_path).read_bytes()
    result=analyze_prior_model_evidence(json.loads(x),json.loads(y))
    result['input_evidence_sha256']={
        'source_0188': hashlib.sha256(x).hexdigest(),
        'source_0185': hashlib.sha256(y).hexdigest()}
    return result
