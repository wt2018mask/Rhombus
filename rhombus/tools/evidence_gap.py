"""Bounded evidence-gap acquisition and frozen policy comparison.

No answer is inferred from failed acquisition or HTTP success. This pilot does
not implement a generic crawler or authorize physical/scientific dispatch.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from rhombus.evidence.identity import SourceBinding
from rhombus.evidence.schema import (EvidenceRecord, OperationalStatus, ScientificVerdict,
                                     Applicability, DomainStatus, Uncertainty)
from rhombus.literature.supplement import _NoRedirect
from rudeus.science.contracts import digest, require_hash
from rudeus.execution.contracts import TaskSpec
from rudeus.execution.scheduler import plan_attempt

ROOT=Path(__file__).resolve().parents[2]
PROTOCOLS=ROOT/'data/development/evidence_gap_protocols_0196_attempt_v1.json'


def load_protocols():
    rows=json.loads(PROTOCOLS.read_text())
    for row in rows:
        raw=row['frozen_json'].encode()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise ValueError('frozen protocol bytes changed')
    return {row['episode']:json.loads(row['frozen_json']) for row in rows}


def select_action(protocol, policy, *, unavailable=False):
    """Frozen pre-answer ordering; failure feedback can block, never reveal answers."""
    actions=protocol['actions']
    ids=[a['id'] for a in actions]
    if not ids or len(set(ids))!=len(ids):raise ValueError('duplicate or empty task identity')
    if unavailable:return None
    costs=[a.get('estimated_processing_seconds') for a in actions]
    if any(type(c) not in (int,float) or not math.isfinite(c) or c<=0 for c in costs):
        raise ValueError('unknown or invalid cost')
    values=[a.get('value_weight',a.get('weight')) for a in actions]
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in values):raise ValueError('invalid provisional weights')
    if policy=='static':return ids[0]
    if policy=='cheapest':key=lambda a:(a['estimated_processing_seconds'],a['id'])
    elif policy=='uniform_seeded':
        seed='0196-gap-control-v1' if ids[0].startswith('hotpress') else '0196-si-control-v1'
        key=lambda a:hashlib.sha256((seed+a['id']).encode()).hexdigest()
    elif policy=='adaptive':key=lambda a:(-a.get('value_weight',a.get('weight'))/(2+a['estimated_processing_seconds']),a['id'])
    else:raise ValueError('unknown policy')
    return min(actions,key=key)['id']


def order_actions(protocol, policy):
    remaining = dict(protocol, actions=list(protocol['actions']))
    ordered = []
    while remaining['actions']:
        selected = select_action(remaining, policy)
        ordered.append(selected)
        remaining['actions'] = [a for a in remaining['actions'] if a['id'] != selected]
    return ordered


def bounded_acquire(url, destination, *, approved_url, max_bytes, authorized=False,
                    opener=None, clock=time.monotonic):
    """One exact HTTPS request; caller must enforce protocol hard wall externally.

    Uses the inherited proxy/CA. Complete response is only RECEIVED_UNVERIFIED.
    Do not run this again until an approved prerequisite or diagnosis changes.
    """
    if authorized is not True:raise PermissionError('acquisition authorization required')
    parsed=urlsplit(url)
    if (url!=approved_url or parsed.scheme!='https' or parsed.username or parsed.password
        or parsed.port not in (None,443) or parsed.hostname not in {'iris.unimore.it','www.ebi.ac.uk','mdpi-res.com'}):
        raise ValueError('source URL or host mismatch')
    if type(max_bytes) is not int or not 0<max_bytes<=24000000:raise ValueError('byte budget')
    path=Path(destination)
    if path.exists():raise FileExistsError(path)
    t=clock();event={'url':url,'request_count':1,'bytes':0,'max_bytes':max_bytes,
                     'source_verified':False,'redirects_followed':False,'sha256':None}
    stream=None
    try:
        client=opener or build_opener(_NoRedirect())
        with client.open(Request(url,headers={'User-Agent':'Rhombus-evidence-gap/0196','Accept-Encoding':'identity'}),timeout=15) as response:
            if response.geturl()!=url:raise ValueError('redirect/final source identity changed')
            if int(response.headers.get('Content-Length','0'))>max_bytes:raise ValueError('source byte budget')
            sha=hashlib.sha256()
            with path.open('xb') as stream:
                while True:
                    block=response.read(min(65536,max_bytes+1-event['bytes']))
                    if not block:break
                    event['bytes']+=len(block)
                    if event['bytes']>max_bytes:raise ValueError('source byte budget')
                    sha.update(block);stream.write(block)
            expected_length=response.headers.get('Content-Length')
            if not event['bytes'] or (expected_length is not None and event['bytes']!=int(expected_length)):
                raise ValueError('empty or truncated original bytes')
            event.update(status='RECEIVED_UNVERIFIED',sha256=sha.hexdigest())
    except HTTPError as exc:
        event.update(status='SOURCE_UNAVAILABLE',http_status=exc.code,error='HTTP_ERROR')
    except (TimeoutError,URLError,ssl.SSLError) as exc:
        reason=getattr(exc,'reason',exc)
        category=('PROXY_CONNECT_403' if 'Tunnel connection failed: 403' in str(reason) else
                  'TLS_VERIFICATION_ERROR' if isinstance(reason,ssl.SSLError) else type(reason).__name__)
        event.update(status='ACQUISITION_FAILED',error=type(exc).__name__,reason_category=category)
    except Exception:
        if path.exists():path.unlink()
        raise  # Identity/size/integrity errors never become unavailability.
    finally:event['acquisition_seconds']=clock()-t
    if event['status']!='RECEIVED_UNVERIFIED' and path.exists():path.unlink()
    return event


def verify_known_bytes(raw, expected_sha256):
    require_hash(expected_sha256)
    if not isinstance(raw,bytes) or not raw or hashlib.sha256(raw).hexdigest()!=expected_sha256:
        raise ValueError('corrupted or unbound original bytes')
    return True


def compare_blocked_acquisitions(protocol, shared_receipts):
    """Observed source failure yields zero new facts, not four observed parsings."""
    if not shared_receipts or any(r.get('status') not in {'SOURCE_UNAVAILABLE','ACQUISITION_FAILED'} for r in shared_receipts):
        raise ValueError('blocked comparator cannot adjudicate successful or ambiguous bytes')
    costs=[r.get('acquisition_seconds') for r in shared_receipts]
    if any(type(c) not in (int,float) or not math.isfinite(c) or c<=0 for c in costs):
        raise ValueError('unknown measured acquisition cost')
    seconds=sum(costs)
    comparisons=[];records=[]
    for policy in ('static','cheapest','uniform_seeded','adaptive'):
        action_id=select_action(protocol,policy)
        task=next(a for a in protocol['actions'] if a['id']==action_id)
        task_spec=TaskSpec(candidate_id=protocol.get('parent_DOI',protocol.get('source_DOI')),
            stage='EVIDENCE_GAP_ACQUISITION',protocol_hash=digest(protocol),config={'action':action_id},
            input_artifact_hashes=(digest(protocol),),dependencies=(),code_revision='0196-frozen-gap-attempt',
            resource_requirements={'max_actions':1},expected_outputs=('source.json',),retry_policy={'max_attempts':1})
        planned=plan_attempt(task_spec,'LOCAL_CONTROL_PLANE_ACQUISITION',max_attempts=1)
        record=EvidenceRecord.create(candidate_id=task_spec.candidate_id,evidence_kind='EVIDENCE_ACQUISITION_FAILURE',
            capability='acquire_scientific_evidence',operational_status=OperationalStatus.ERROR,
            scientific_verdict=ScientificVerdict.UNKNOWN,
            applicability=Applicability('evidence_gap_resolution',DomainStatus.UNQUALIFIED),
            uncertainty=Uncertainty(reason='Original bytes unavailable; task answers and processing time unobserved'),
            protocol_id=digest(protocol),limitations=('NO_NEW_AUTHENTICATED_FACT','NO_SCIENTIFIC_CLAIM_CHANGE'),
            source_bindings=(SourceBinding('requested_original_source_not_obtained',task_spec.candidate_id),),
            provenance={'shared_retrieval_receipts_sha256':digest(shared_receipts),'task_id':task_spec.task_id},
            payload={'action_id':action_id,'question':task['question'],'outcome':'SOURCE_UNAVAILABLE',
                     'answer':None,'adjudication_executed':False,'resolved_questions':0,'new_fact_ids':[],
                     'scientific_GO':False,'existence_state':'UNKNOWN','dynamic_state':'UNKNOWN','transport_state':'UNCHANGED'})
        records.append(record.to_dict())
        comparisons.append({'policy':policy,'selected_action':action_id,'proposed_order':order_actions(protocol,policy),'task_id':task_spec.task_id,
            'plan_id':planned['plan'].attempt_id,'dispatch_status':'NOT_SUBMITTED',
            'actual_question_answer':None,'adjudication_wall_seconds':None,'resolved_questions':0,
            'diagnostic_new_fact_yield_per_shared_acquisition_second':0.0,
            'predeclared_full_action_yield_metric':None,
            'common_observed_acquisition_seconds':seconds,'full_action_runtime':None})
    return {'comparisons':comparisons,'evidence_records':records,'measured_new_information_yield':0,
            'global_shared_acquisition_seconds':seconds,'global_request_count':len(shared_receipts),
            'global_authenticated_original_bytes':0,'next_eligible_action':None,
            'feedback':'Source acquisition changed from untested to unavailable/failed; no identical retry or automatic publication.',
            'next_request':{'action':'apply_reviewed_source_network_configuration_then_reassess_access',
                            'status':'NOT_EXECUTED','answers_or_processing_counterfactuals':'UNKNOWN'},
            'scientific_GO':False,'production_enabled':False,'new_STRICT_DOI_groups':0,
            'new_STRICT_manufacturing_comparisons':0,'scientific_ranking_utility':None,
            'cost_accounting':'Shared failed acquisitions counted once globally; common basis perpolicy, not independent downloads.'}
