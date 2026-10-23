"""Real four-source replay plus hostile control-plane-only authorization cases."""
import copy
import pytest
from rhombus.tools import adaptive_replay as a


def test_actual_population_and_regime_boundaries():
    pools=a.load_pools()
    assert len(pools)==4 and sum(len(p['conditions']) for p in pools)==32
    assert {p['regime'] for p in pools}=={'FROZEN_2018_SUPPORT','SHORT_DWELL_CONVENTIONAL','CATEGORICAL_POWDER_ROUTES','HOT_PRESS'}
    assert next(p for p in pools if p['regime']=='CATEGORICAL_POWDER_ROUTES')['source_overlap'] is True
    assert next(p for p in pools if p['regime']=='HOT_PRESS')['source_overlap'] is None


def test_actual_comparison_and_feedback_never_claim_material_success():
    r=a.run_adaptive_evidence_replay(authorized=True)
    assert [x['conditions_with_explicit_decision'] for x in r['comparisons']]==[5,4,18,18]
    assert all(x['replays_executed']==1 and x['measured_replay_wall_seconds']>=0 for x in r['comparisons'])
    assert all(x['material_recommendations']==x['invalid_model_dispatches']==0 for x in r['comparisons'])
    for e in r['evidence_records']:
        assert e['operational_status']=='SUCCEEDED' and e['scientific_verdict']=='INDETERMINATE'
        assert e['payload']['decision']=='ABSTAIN_REQUEST_MORE_EVIDENCE'
        assert e['payload']['material_recommendation'] is None
        assert not e['payload']['source_rejected_as_worthless']
    assert r['feedback']['next_proposal_only']!=r['feedback']['completed_candidate']
    assert not r['feedback']['second_replay_executed']
    assert r['new_STRICT_DOI_groups']==0 and not r['scientific_GO']


def test_deterministic_decisions_and_content_ids_exclude_wallclock():
    x=a.run_adaptive_evidence_replay(authorized=True);y=a.run_adaptive_evidence_replay(authorized=True)
    assert [p['candidate_id'] for p in x['comparisons']]==[p['candidate_id'] for p in y['comparisons']]
    assert x['evidence_records']==y['evidence_records']
    assert x['feedback']==y['feedback'] and x['protocol_id']==y['protocol_id']


@pytest.mark.parametrize('level',['loop','action'])
def test_unauthorized_replay_does_not_execute(level,monkeypatch):
    def forbidden(): raise AssertionError('inputs accessed before authorization')
    monkeypatch.setattr(a,'load_pools',forbidden)
    with pytest.raises(PermissionError):
        if level=='loop':a.run_adaptive_evidence_replay()
        else:a.replay_applicability({})


@pytest.mark.parametrize('change',['duplicate_pool','duplicate_condition','provenance','cost','temperature'])
def test_tampered_provenance_and_inputs_fail_closed(change):
    pools=a.load_pools()
    if change=='duplicate_pool':pools.append(copy.deepcopy(pools[0]))
    if change=='duplicate_condition':pools[0]['conditions'].append(copy.deepcopy(pools[0]['conditions'][0]))
    if change=='provenance':pools[0]['source_sha256']=''
    if change=='cost':pools[0]['replay_cost_units']=0
    if change=='temperature':pools[0]['conditions'][0]['T_C']=1
    with pytest.raises(ValueError):
        a.validate_pools(pools)
        a.replay_applicability(pools[0],authorized=True)


def test_unknown_cost_and_terminal_scientific_failure_cannot_be_scheduled():
    pools=a.load_pools()
    for p in pools:p['replay_cost_units']=None
    assert a.select_replay(pools,'adaptive') is None
    pools=a.load_pools()
    for p in pools:
        p['prior_failures']=[{'scientific_verdict':'FAIL'}];p['retry_budget']=10
    assert a.select_replay(pools,'adaptive') is None
    pools=a.load_pools()
    for p in pools:p['prior_failures']=[{'failure_class':'TIMEOUT'}]
    assert a.select_replay(pools,'adaptive') is None


def test_source_overlap_and_ood_remain_separate_from_source_authentication():
    pools=a.load_pools()
    same=a.replay_applicability(pools[0],authorized=True)
    assert 'FULL_SOURCE_FORMULA_COMPONENT_OVERLAP' in same['payload']['reasons']
    short=a.replay_applicability(pools[1],authorized=True)
    assert 'FROZEN_MODEL_OOD_OR_UNKNOWN_INPUT' in short['payload']['reasons']
    assert not short['payload']['source_rejected_as_worthless']


def test_source_hash_drift_rejects_before_any_replay(monkeypatch):
    path,sha=a.INPUTS['process'];monkeypatch.setitem(a.INPUTS,'process',(path,'0'*64))
    with pytest.raises(ValueError,match='provenance'):a.run_adaptive_evidence_replay(authorized=True)


def test_no_scientific_backend_dispatch(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('scientific execution dispatched')
    monkeypatch.setattr(a.LocalBackend,'submit',forbidden)
    r=a.run_adaptive_evidence_replay(authorized=True)
    assert all(x['status']=='BLOCKED' and x['measured_cost'] is None for x in r['unexecuted_actions'])


def test_misleading_success_is_rejected(monkeypatch):
    original=a.replay_applicability
    def forged(pool,**kwargs):
        result=original(pool,**kwargs);result['scientific_verdict']='PASS';return result
    monkeypatch.setattr(a,'replay_applicability',forged)
    with pytest.raises(ValueError,match='misleading'):a.run_adaptive_evidence_replay(authorized=True)
