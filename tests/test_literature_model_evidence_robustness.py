"""Hostile historical source-group sensitivity tests; no new physical measurements."""
import copy
import json
from pathlib import Path
import pytest
from rhombus.literature.model_evidence_robustness import analyze_files, analyze_prior_model_evidence

ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'data/development/phase3_solo_oxide_five_doi_0188_evidence_v1.json'
B=ROOT/'data/development/phase3_solo_oxide_external_0185_evidence_v1.json'

def fixture():
    return json.loads(A.read_text()),json.loads(B.read_text())

def test_existing_real_source_receipts_calculate_exhaustive_group_sensitivity():
    r=analyze_files(A,B)
    a=r['original_0188'];s=r['secondary_0185_unqualified_DO_NOT_POOL']
    assert a['doi_count']==5 and a['measurement_conditions_not_independent_pellets']==22
    assert a['paper_wins_oxide_rf']==4 and a['paper_losses_oxide_rf']==1
    assert a['paired_mean_gain_log10']==.07572068
    assert a['minimum_leave_one_doi_out_gain_log10']==.03228278
    assert a['exact_sign_flip_descriptive_reference']['combinations']==32
    assert a['exact_sign_flip_descriptive_reference']['two_sided_tail_count']==8
    assert a['exact_sign_flip_descriptive_reference']['two_sided_tail_fraction_NOT_a_p_value']==.25
    b=a['exhaustive_empirical_source_resampling_NOT_CI']
    assert b['draws']==3125 and b['lower_2_5_percentile']==-.00263295
    assert b['upper_97_5_percentile']==.1757359 and b['nonpositive_gain_fraction']==.03072
    assert s['macro_pooled_minus_oxide_log10']==-.02589242
    assert s['row_pooled_minus_oxide_log10']==.00300697
    assert not s['can_pool_with_original_0188']
    assert r['scientific_decision']['SOLO_PUBLIC_BENCHMARK']=='INCONCLUSIVE'
    assert r['scientific_decision']['SCIENTIFIC_EXTERNAL_PHYSICAL']=='NO-GO'
    assert not r['scientific_decision']['specialist_production_activation']
    assert all(len(v)==64 for v in r['input_evidence_sha256'].values())

@pytest.mark.parametrize('where,field,value',[
    ('a','original_obelix_test','SEEN'),
    ('a','scientific_GO',True),
    ('a','actual_conditions',25),
    ('a','physical_P0',['PASS']*3),
    ('a','doi_groups',['bad']*5),
    ('b','external_measurement_comparability','ATTESTED'),
    ('b','actual_connected_DOI_formula_groups',37),
    ('b','scientific_GO',True),
    ('b','official_TEST_reserved','SEEN'),
])
def test_scientific_promotion_or_cohort_mutation_is_rejected(where,field,value):
    a,b=fixture()
    (a if where=='a' else b)[field]=value
    with pytest.raises(ValueError):
        analyze_prior_model_evidence(a,b)

def test_forged_per_paper_metric_rejected():
    a,b=fixture();a['model_results']['O_ONLY_RF']['per_DOI']['10.1039/c8ra01329b']=.01
    with pytest.raises(ValueError):analyze_prior_model_evidence(a,b)

def test_nan_or_additional_doi_group_rejected():
    a,b=fixture();a['model_results']['O_ONLY_RF']['per_DOI']['10.1039/c8ra01329b']=float('nan')
    with pytest.raises(ValueError):analyze_prior_model_evidence(a,b)
    a,b=fixture();a['model_results']['POOLED_RF']['per_DOI']['10.1039/new']=.4
    with pytest.raises(ValueError):analyze_prior_model_evidence(a,b)

def test_secondary_metrics_nonfinite_rejected():
    a,b=fixture();b['actual_equal_group_macro_MAE_log10']['POOLED_RF']=float('inf')
    with pytest.raises(ValueError):analyze_prior_model_evidence(a,b)

def test_macro_label_tamper_rejected():
    a,b=fixture();a['model_results']['POOLED_RF']['equal_DOI_macro_MAE_log10']=.42
    with pytest.raises(ValueError):analyze_prior_model_evidence(a,b)
