"""Hostile transport controls, frozen selections, and actual failed observations."""
import copy
import hashlib
import io
import json
import ssl
from urllib.error import HTTPError, URLError

import pytest

from rhombus.tools import evidence_gap as g

URL='https://mdpi-res.com/d_attachment/materials/materials-14-06809/article_deploy/materials-14-06809-s001.zip'


class Response(io.BytesIO):
    def __init__(self, raw=b'original', url=URL, headers=None):
        super().__init__(raw)
        self.url=url
        self.headers=headers or {}

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, response=None, error=None):
        self.response=response
        self.error=error
        self.calls=0

    def open(self, *args, **kwargs):
        self.calls+=1
        if self.error:
            raise self.error
        return self.response


def acquire(tmp_path, opener, **kwargs):
    return g.bounded_acquire(URL,tmp_path/'source',approved_url=URL,max_bytes=100,
                             authorized=True,opener=opener,**kwargs)


def test_received_bytes_are_not_authenticated_or_scientific_pass(tmp_path):
    result=acquire(tmp_path,Opener(Response()))
    assert result['status']=='RECEIVED_UNVERIFIED' and not result['source_verified']
    assert result['sha256']==hashlib.sha256(b'original').hexdigest()
    assert result['request_count']==1
    with pytest.raises(ValueError):
        g.compare_blocked_acquisitions(g.load_protocols()['successor'],[result])


def test_unauthorized_or_wrong_source_never_opens(tmp_path):
    opener=Opener(error=AssertionError('unauthorized I/O'))
    with pytest.raises(PermissionError):
        g.bounded_acquire(URL,tmp_path/'source',approved_url=URL,max_bytes=10,opener=opener)
    for url in ('http://mdpi-res.com/a','https://evil.example/a','https://user@mdpi-res.com/a',URL+'?other=1'):
        with pytest.raises(ValueError):
            g.bounded_acquire(url,tmp_path/'source',approved_url=URL,max_bytes=10,authorized=True,opener=opener)
    assert opener.calls==0


@pytest.mark.parametrize('response',[
    Response(url='https://evil.example/redirect'),
    Response(b'x'*101),
    Response(headers={'Content-Length':'101'}),
    Response(b'partial',headers={'Content-Length':'80'}),
    Response(b''),
])
def test_redirect_size_and_integrity_failure_leave_no_artifact(tmp_path,response):
    with pytest.raises(ValueError):
        acquire(tmp_path,Opener(response))
    assert not (tmp_path/'source').exists()


@pytest.mark.parametrize('error,status',[
    (HTTPError(URL,403,'denied',{},None),'SOURCE_UNAVAILABLE'),
    (HTTPError(URL,302,'redirect',{},None),'SOURCE_UNAVAILABLE'),
    (TimeoutError(),'ACQUISITION_FAILED'),
    (URLError(ssl.SSLCertVerificationError('untrusted')),'ACQUISITION_FAILED'),
])
def test_transport_failures_do_not_become_scientific_failures(tmp_path,error,status):
    result=acquire(tmp_path,Opener(error=error))
    assert result['status']==status and not result['source_verified']
    assert not (tmp_path/'source').exists()
    r=g.compare_blocked_acquisitions(g.load_protocols()['successor'],[result])
    assert all(e['scientific_verdict']=='UNKNOWN' for e in r['evidence_records'])


def test_corruption_and_frozen_protocol_drift_fail_closed(tmp_path,monkeypatch):
    sha=hashlib.sha256(b'original').hexdigest()
    assert g.verify_known_bytes(b'original',sha)
    with pytest.raises(ValueError):
        g.verify_known_bytes(b'corrupt',sha)
    rows=json.loads(g.PROTOCOLS.read_text())
    rows[0]['frozen_json']+=' '
    path=tmp_path/'protocols.json'
    path.write_text(json.dumps(rows))
    monkeypatch.setattr(g,'PROTOCOLS',path)
    with pytest.raises(ValueError,match='frozen protocol'):
        g.load_protocols()


@pytest.mark.parametrize('cost',[None,0,-1,float('nan'),float('inf'),True])
def test_unknown_cost_cannot_support_policy_or_yield(cost):
    p=copy.deepcopy(g.load_protocols()['successor'])
    p['actions'][0]['estimated_processing_seconds']=cost
    with pytest.raises(ValueError):
        g.select_action(p,'adaptive')
    with pytest.raises(ValueError):
        g.compare_blocked_acquisitions(p,[{'status':'ACQUISITION_FAILED','acquisition_seconds':cost}])


def test_duplicate_tasks_and_prior_exposure_cannot_inflate_observed_resolution():
    p=copy.deepcopy(g.load_protocols()['successor'])
    p['actions'].append(copy.deepcopy(p['actions'][0]))
    with pytest.raises(ValueError):
        g.select_action(p,'adaptive')
    for status in ('ALREADY_KNOWN_EVIDENCE','PARTIAL_OR_AMBIGUOUS_EVIDENCE','NEW_AUTHENTICATED_FACT'):
        with pytest.raises(ValueError):
            g.compare_blocked_acquisitions(p,[{'status':status,'acquisition_seconds':1}])


def test_deterministic_proposals_shared_cost_and_feedback():
    p=g.load_protocols()['successor']
    receipts=[{'status':'ACQUISITION_FAILED','acquisition_seconds':2}]
    x=g.compare_blocked_acquisitions(p,receipts)
    assert x==g.compare_blocked_acquisitions(p,receipts)
    assert x['global_request_count']==1 and x['global_shared_acquisition_seconds']==2
    assert x['global_authenticated_original_bytes']==x['measured_new_information_yield']==0
    assert not x['scientific_GO'] and x['scientific_ranking_utility'] is None
    assert x['next_request']['status']=='NOT_EXECUTED'
    assert g.select_action(p,'adaptive',unavailable=True) is None
    assert [c['selected_action'] for c in x['comparisons']][:2]==['si-uncertainty']*2
    assert x['comparisons'][-1]['selected_action']=='si-geometry'
    for c in x['comparisons']:
        assert c['adjudication_wall_seconds'] is None and c['full_action_runtime'] is None
        assert c['predeclared_full_action_yield_metric'] is None
        assert len(c['proposed_order'])==4 and c['dispatch_status']=='NOT_SUBMITTED'
    for e in x['evidence_records']:
        assert e['scientific_verdict']=='UNKNOWN'
        assert e['payload']['new_fact_ids']==[] and not e['payload']['adjudication_executed']
        assert e['payload']['answer'] is None and e['payload']['transport_state']=='UNCHANGED'


def test_retained_real_attempt_reproduces_blocked_comparisons():
    r=json.loads((g.ROOT/'data/development/evidence_gap_attempt_0196_v1.json').read_text())
    assert hashlib.sha256(g.PROTOCOLS.read_bytes()).hexdigest()==r['frozen_protocol_artifact_sha256']
    raw=r['metadata_raw_json'].encode()
    assert hashlib.sha256(raw).hexdigest()==r['raw_receipts']['europepmc_metadata']['sha256']
    assert len(raw)==r['aggregate']['metadata_bytes']==7340
    for name,episode in r['episodes'].items():
        receipts=r['raw_receipts']
        if name=='hotpress':
            metadata=receipts['europepmc_metadata']
            shared=[receipts['institutional_pdf'],{**metadata,'status':'SOURCE_UNAVAILABLE',
                'acquisition_seconds':metadata['duration_seconds'],
                'interpretation':'HTTP200 metadata only; exact DOI has no PMC identifier/OA text. Not original article bytes and not a scientific negative finding.'}]
        else:
            shared=[receipts['europepmc_supplement'],receipts['publisher_supplement']]
        expected=g.compare_blocked_acquisitions(g.load_protocols()[name],shared)
        assert episode['comparisons']==expected['comparisons']
        unique=list({e['evidence_id']:e for e in expected['evidence_records']}.values())
        assert episode['evidence_records']==unique
        assert episode['policy_evidence_ids']==[e['evidence_id'] for e in expected['evidence_records']]
    assert r['aggregate']['network_requests']==4
    assert r['aggregate']['measured_shared_acquisition_seconds']==pytest.approx(18.88909550600839)
    assert not r['checkpoint_0196_consumed'] and not r['acceptance']['original_scientific_evidence_acquired']
    assert all(v=='UNKNOWN' for v in r['coverage'].values())
    assert r['aggregate']['new_authenticated_fact_count']==r['aggregate']['resolved_questions']==0
