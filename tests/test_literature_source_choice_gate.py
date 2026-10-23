"""Hostile synthetic regression tests; fixtures are NOT scientific measurements."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import pytest

from rhombus.literature.source_choice_gate import gate_source_choice_report, gate_file

ROOT = Path(__file__).resolve().parents[1]
D1='10.1039/c8ra01329b'
D2='10.3390/ma13030560'


def fixture():
    records=[{'doi':d,'condition_id':prefix+str(i)} for d,prefix in [(D1,'A'),(D2,'B')] for i in range(5)]
    folds=[]
    for train,test,prefix in [(D1,D2,'B'),(D2,D1,'A')]:
        cands=[{'doi':test,'condition_id':prefix+str(i),'must_abstain':True,
                'reasons':['OUTSIDE_FINAL_DURATION_MIN'],'screen':'OUTSIDE_OR_UNKNOWN'} for i in range(5)]
        folds.append({'train_DOI':train,'test_DOI':test,'ranking_only_no_full_RF_prediction_or_MAE':True,
                      'new_predictive_win_claim':False,
                      'process_support':{'candidates':cands,'screen_grants_scientific_admission':False,
                                         'full_source_choice_must_abstain':True},
                      'policies':{'frozen_0191_rank_replay':{'uniform_tie_conditions':[prefix+'0']}}})
    return {'schema_version':'rhombus-source-process-feature-audit-v1',
            'scientific_GO':False,'production_enabled':False,'official_TEST_121_accessed':False,
            'new_strict_qualified_DOI_groups':0,'new_strict_manufacturing_comparisons':0,
            'claim_boundaries':{'checkpoint_0195_consumed':False,
                               'statistical_significance_or_model_superiority_claim':False,
                               'P0_01':'BLOCKED','P0_02':'BLOCKED','P0_03':'BLOCKED'},
            'records':records,'frozen_decision_replay':folds}


def test_release_gate_abstains_for_all_original_fold_directions():
    out=gate_source_choice_report(fixture())
    assert out['evaluated_folds']==2 and out['candidate_conditions']==10
    assert out['out_of_support_candidate_conditions']==10
    assert out['authorized_choice_count']==0
    assert out['scientifically_scoreable_model_vs_heuristic_comparisons']==0
    assert all(x['authorized_manufacturing_choice'] is None and x['status']=='ABSTAIN' for x in out['folds'])
    assert not out['model_superiority_demonstrated'] and not out['scientific_GO']


def test_even_all_marginally_in_range_cannot_be_promoted():
    f=fixture()
    for fold in f['frozen_decision_replay']:
        for c in fold['process_support']['candidates']:
            c.update(must_abstain=False,reasons=[],screen='MARGINAL_RANGES_ONLY_NOT_QUALIFIED')
        fold['process_support']['full_source_choice_must_abstain']=False
    out=gate_source_choice_report(f)
    assert out['out_of_support_candidate_conditions']==0
    assert all('MARGINAL_RANGE_IS_NOT_VALIDATED_DOMAIN' in x['reasons'] for x in out['folds'])
    assert out['authorized_choice_count']==0


@pytest.mark.parametrize('path,value',[
    (('scientific_GO',),True), (('production_enabled',),True),
    (('official_TEST_121_accessed',),True),
    (('new_strict_qualified_DOI_groups',),1), (('claim_boundaries','P0_01'),'PASS'),
    (('claim_boundaries','checkpoint_0195_consumed'),True),
    (('frozen_decision_replay',0,'ranking_only_no_full_RF_prediction_or_MAE'),False),
    (('frozen_decision_replay',0,'new_predictive_win_claim'),True),
    (('frozen_decision_replay',0,'process_support','screen_grants_scientific_admission'),True),
    (('frozen_decision_replay',0,'process_support','full_source_choice_must_abstain'),False),
    (('frozen_decision_replay',0,'process_support','candidates',0,'must_abstain'),False),
    (('frozen_decision_replay',0,'process_support','candidates',0,'condition_id'),'B1'),
    (('frozen_decision_replay',0,'policies','frozen_0191_rank_replay','uniform_tie_conditions'),['unknown']),
    (('frozen_decision_replay',0,'test_DOI'),D1),
])
def test_adversarial_promotions_rejected(path,value):
    f=fixture(); ptr=f
    for key in path[:-1]:
        ptr=ptr[key]
    ptr[path[-1]]=value
    with pytest.raises(ValueError):
        gate_source_choice_report(f)


def test_report_fingerprint_is_not_a_source_pdf_hash(tmp_path):
    f=fixture(); file=tmp_path/'prior.json'; file.write_text(json.dumps(f))
    result=gate_file(file)
    assert len(result['input_retrospective_report_sha256'])==64
    assert result['authorized_choice_count']==0


def test_real_retained_0191_replay_must_abstain_without_fabricated_win():
    report=ROOT/'data/development/process_feature_identifiability_20261021_v1.json'
    raw=report.read_bytes()
    out=gate_file(report)
    assert out['input_retrospective_report_sha256']==hashlib.sha256(raw).hexdigest()
    assert out['evaluated_folds']==2
    assert out['candidate_conditions']==out['out_of_support_candidate_conditions']==10
    assert out['authorized_choice_count']==out['scientifically_scoreable_model_vs_heuristic_comparisons']==0
    assert [x['diagnostic_rank_choice_only'] for x in out['folds']] == [['LLZALO-5'], ['SL2']]
    assert all(x['status']=='ABSTAIN' and x['authorized_manufacturing_choice'] is None for x in out['folds'])
    assert not out['original_TEST_121_accessed']
