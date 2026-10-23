"""Bounded O_ONLY applicability replay; never dispatch scientific TaskSpecs.

This is a four-source control-plane experiment, not a universal scheduler.
Allocation uses process metadata and coverage, never conductivity outcomes.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from rhombus.evidence.identity import SourceBinding
from rhombus.evidence.schema import (EvidenceRecord, OperationalStatus, ScientificVerdict,
                                     Applicability, DomainStatus, Uncertainty)
from rudeus.execution.contracts import TaskSpec
from rudeus.execution.scheduler import plan_attempt, order_plans
from rudeus.execution.local_backend import LocalBackend
from rudeus.science.evidence import EvidenceStore
from rudeus.science.contracts import digest, require_hash

ROOT = Path(__file__).resolve().parents[2]
INPUTS = {
    'process': ('data/development/process_feature_identifiability_20261021_v1.json',
                '8af20fd82153bf67db318d9e091610f7979d76df6689ae0de4a33ba1331d34c2'),
    'hotpress': ('data/development/0194-unimore-vor-authenticated-source-v1.json',
                 '4cce0d4b9329e369d61db5116687c7297316fbda77be63fb96f1cbac6de18b75'),
}
TRAIN_DOI = '10.1039/c8ra01329b'
MODEL = 'FROZEN_0191_2018_RIDGE_ALPHA1_T_TIME'
PROTOCOL = {'version': '0195-applicability-replay-v1', 'budget': {'replays': 1, 'input_conditions': 18},
            'objective': 'maximize condition coverage of an answerable applicability gap within budget',
            'adaptive_score': 'answerable condition count; estimated work = input condition count',
            'ties': 'lexicographic candidate identity', 'random_seed_label': '0195-uniform-control-v1',
            'model': MODEL, 'support_C': [1100, 1220], 'support_min': [600, 1200],
            'no_conductivity_scoring': True, 'physical_calculations_authorized': False}


def _read(key):
    path, sha = INPUTS[key]; raw = (ROOT/path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError('source provenance hash mismatch')
    return json.loads(raw)


def load_pools():
    audit, hot = _read('process'), _read('hotpress')
    pools = []
    for doi, regime in ((TRAIN_DOI, 'FROZEN_2018_SUPPORT'),
                        ('10.3390/ma13030560', 'SHORT_DWELL_CONVENTIONAL'),
                        ('10.3390/ma14226809', 'CATEGORICAL_POWDER_ROUTES')):
        rows = [r for r in audit['records'] if r['doi'] == doi]
        conditions = [{'id': r['condition_id'], 'formula': r['input_features']['nominal_formula'],
                       'T_C': r['input_features']['final_temperature_C'],
                       'dwell_min': r['input_features']['final_duration_min'],
                       'route': r['input_features']['final_route'],
                       'powder_route': r['input_features']['powder_route'],
                       'measurement_C': r['source_measurement_temperature_C'], 'observable': 'TOTAL'} for r in rows]
        pools.append({'id': doi, 'regime': regime, 'conditions': conditions,
                      'source_sha256': rows[0]['feature_evidence']['original_raw_sha256'],
                      'receipt_key': 'process', 'uncertainty': 'UNQUALIFIED',
                      'source_overlap': doi == TRAIN_DOI or any(c['formula'] == 'Li6.4Al0.2La3Zr2O12' for c in conditions),
                      'model_disagreement':'NOT_ASSESSED_NO_APPLICABLE_PREDICTIONS',
                      'missing': ['physical_specimen_identity', 'conductivity_uncertainty', 'qualified_model_domain'],
                      'replay_cost_units': len(conditions), 'prior_failures': [], 'retry_budget': 0})
    conditions = [{'id': f"{r['nominal_series']}@{r['hot_press_temperature_C']}C",
                   'formula': None, 'author_series': r['nominal_series'],
                   'T_C': r['hot_press_temperature_C'], 'dwell_min': None,
                   'route': 'HOT_PRESS_56_MPA', 'powder_route': None,
                   'measurement_C': r['author_reported_target_temperature_C'], 'observable': 'TOTAL'}
                  for r in hot['table_mapping']]
    pools.append({'id': hot['doi'], 'regime': 'HOT_PRESS', 'conditions': conditions,
                  'source_sha256': hot['pdf_sha256'], 'receipt_key': 'hotpress',
                  'uncertainty': 'UNQUALIFIED', 'source_overlap': None,
                  'model_disagreement':'NOT_ASSESSED_NO_APPLICABLE_PREDICTIONS',
                  'missing': ['complete_condition_formula', 'physical_specimen_identity',
                              'direct_exact25C_EIS_attestation', 'conductivity_uncertainty', 'qualified_model_domain'],
                  'replay_cost_units': len(conditions), 'prior_failures': [], 'retry_budget': 0})
    validate_pools(pools)
    return pools


def validate_pools(pools):
    if not pools or len({p['id'] for p in pools}) != len(pools):
        raise ValueError('empty or duplicate candidate identity')
    for p in pools:
        if p['receipt_key'] not in INPUTS or not isinstance(p.get('source_sha256'), str):
            raise ValueError('missing source provenance')
        require_hash(p['source_sha256'])
        if p['replay_cost_units'] is not None and (type(p['replay_cost_units']) is not int or p['replay_cost_units'] <= 0):
            raise ValueError('invalid cost information')
        ids = [r['id'] for r in p['conditions']]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError('duplicate condition identity')
        if p['replay_cost_units'] is not None and p['replay_cost_units'] != len(ids):
            raise ValueError('cost and bounded replay input disagree')


def select_replay(pools, policy):
    """Pure task allocation: estimates are row-work units, not measured seconds."""
    validate_pools(pools)
    allowed = [p for p in pools if p['replay_cost_units'] is not None
               and p['replay_cost_units'] <= PROTOCOL['budget']['input_conditions']
               and not p.get('applicability_replayed', False)
               and not any(f.get('scientific_verdict') == 'FAIL' for f in p['prior_failures'])
               and len(p['prior_failures']) <= p['retry_budget']]
    if not allowed:
        return None
    if policy == 'adaptive': key = lambda p: (-len(p['conditions']), p['id'])
    elif policy == 'cheapest': key = lambda p: (p['replay_cost_units'], p['id'])
    elif policy == 'static':
        sequence = ['FROZEN_2018_SUPPORT', 'SHORT_DWELL_CONVENTIONAL', 'CATEGORICAL_POWDER_ROUTES', 'HOT_PRESS']
        key = lambda p: (sequence.index(p['regime']), p['id'])
    elif policy == 'uniform_seeded':
        # Hash ordering is a reproducible pseudorandom permutation, one seed,
        # not an exact uniform expectation or a distributional significance test.
        key = lambda p: hashlib.sha256((PROTOCOL['random_seed_label']+p['id']).encode()).hexdigest()
    else: raise ValueError('unknown allocation policy')
    return min(allowed, key=key)['id']


def replay_applicability(pool, *, authorized=False):
    """Host-authorized offline receipt replay only; no LocalBackend.submit call."""
    if authorized is not True:
        raise PermissionError('offline replay authorization required; proposal is not execution')
    # Reload pinned inputs and require exact candidate reconstruction. A proposal
    # cannot smuggle modified costs/process metadata or remove scientific gaps.
    original = next((p for p in load_pools() if p['id'] == pool['id']), None)
    if original != pool:
        raise ValueError('candidate provenance or input changed')
    from rhombus.literature.process_features import screen_process_support
    audit = _read('process'); train = [r for r in audit['records'] if r['doi'] == TRAIN_DOI]
    candidates = [{'doi': pool['id'], 'condition_id': r['id'], 'input_features': {
        'final_temperature_C': r['T_C'], 'final_duration_min': r['dwell_min'],
        'final_route': r['route'], 'final_temperature_reference': 'AUTHOR_REPORTED_SINTERING_TEMPERATURE'}}
                  for r in pool['conditions']]
    support = screen_process_support(train, candidates)
    reasons = ['NO_QUALIFIED_INDEPENDENT_CLAIM', 'UNCERTAINTY_UNQUALIFIED']
    if pool['source_overlap'] is True: reasons.append('FULL_SOURCE_FORMULA_COMPONENT_OVERLAP')
    if pool['source_overlap'] is None: reasons.append('SOURCE_FORMULA_OVERLAP_UNRESOLVED')
    if support['full_source_choice_must_abstain']: reasons.append('FROZEN_MODEL_OOD_OR_UNKNOWN_INPUT')
    if pool['regime'] == 'CATEGORICAL_POWDER_ROUTES': reasons.append('NUMERIC_MODEL_CANNOT_RESOLVE_CATEGORICAL_ROUTE')
    domain = DomainStatus.FAR_OOD if support['full_source_choice_must_abstain'] else DomainStatus.UNQUALIFIED
    result = {'decision': 'ABSTAIN_REQUEST_MORE_EVIDENCE', 'material_recommendation': None,
              'condition_count': len(candidates), 'support': support, 'reasons': reasons,
              'next_action': 'authenticate_missing_conditions_and_uncertainty_in_this_separate_regime',
              'source_rejected_as_worthless': False, 'model_predictions_executed': 0,
              'existence_state': 'UNKNOWN', 'dynamic_state': 'UNKNOWN',
              'transport_state': 'REPORTED_EXPLORATORY_NOT_PHYSICALLY_QUALIFIED'}
    record = EvidenceRecord.create(candidate_id=pool['id'], evidence_kind='OFFLINE_APPLICABILITY_REPLAY',
        capability='assess_candidate_applicability', operational_status=OperationalStatus.SUCCEEDED,
        scientific_verdict=ScientificVerdict.INDETERMINATE,
        applicability=Applicability('manufacturing_recommendation', domain),
        uncertainty=Uncertainty(reason='No calibrated uncertainty or physical specimen authentication'),
        limitations=('HISTORICAL_PUBLIC_SOURCE_REPLAY', 'NOT_NEW_PHYSICAL_COMPUTATION',
                     'NO_SCIENTIFIC_GO_OR_MODEL_SUPERIORITY'),
        protocol_id=digest(PROTOCOL),
        source_bindings=(SourceBinding('original_scientific_document', pool['id'], sha256=pool['source_sha256']),),
        provenance={'receipt_path': INPUTS[pool['receipt_key']][0], 'receipt_sha256': INPUTS[pool['receipt_key']][1],
                    'source_authentication_is_historical_not_fresh_retrieval': True}, payload=result)
    return record.to_dict()


def run_adaptive_evidence_replay(*, authorized=False):
    if authorized is not True: raise PermissionError('explicit offline replay authorization required')
    pools = load_pools()
    capability = LocalBackend(git_root=ROOT, store=EvidenceStore(ROOT)).capabilities()
    assert capability['availability'] == 'LOCAL_CONTROL_PLANE_ONLY'
    comparisons, records = [], []
    implementation_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for policy in ('static', 'cheapest', 'uniform_seeded', 'adaptive'):
        selected = select_replay(pools, policy)
        if selected is None: raise ValueError('no eligible replay action')
        pool = next(p for p in pools if p['id'] == selected)
        task = TaskSpec(candidate_id=selected, stage='OFFLINE_EVIDENCE_REPLAY', protocol_hash=digest(PROTOCOL),
            config={'implementation_sha256': implementation_sha, 'diagnostic_only': True},
            input_artifact_hashes=(INPUTS[pool['receipt_key']][1],), dependencies=(),
            code_revision='0195-control-plane-replay', resource_requirements={'max_source_conditions':18},
            expected_outputs=('applicability.json',), retry_policy={'max_attempts':1})
        plan = plan_attempt(task, 'OFFLINE_CONTROL_PLANE_REPLAY', max_attempts=1)
        ordered = order_plans((plan['plan'],))
        started = time.perf_counter(); record = replay_applicability(pool, authorized=True)
        elapsed = time.perf_counter()-started
        if record['scientific_verdict'] != 'INDETERMINATE' or record['payload']['material_recommendation'] is not None:
            raise ValueError('misleading scientific success claim')
        records.append(record)
        comparisons.append({'policy':policy,'candidate_id':selected,'proposal_task_id':task.task_id,
            'scheduler_plan_id':ordered[0].attempt_id,'proposal_dispatch_status':'NOT_SUBMITTED',
            'scientific_execution_authorized':False,'offline_replay_authorized':True,'execution_kind':'NEW_OFFLINE_REPLAY_OF_HISTORICAL_SOURCES',
            'replays_executed':1,'estimated_cost_work_units':pool['replay_cost_units'],
            'measured_replay_wall_seconds':elapsed,'conditions_with_explicit_decision':len(pool['conditions']),
            'source_pools_decided':1,'material_recommendations':0,'evidence_record_id':record['evidence_id'],
            'invalid_model_dispatches':0,'scientific_ranking_utility':None,'physical_outcomes_gained':0})
    adaptive = next(p for p in comparisons if p['policy'] == 'adaptive')
    updated = json.loads(json.dumps(pools))
    for pool in updated:
        pool['applicability_replayed'] = pool['id'] == adaptive['candidate_id']
    feedback = {'completed_candidate':adaptive['candidate_id'],
                'conditions_now_decided':adaptive['conditions_with_explicit_decision'],
                'next_proposal_only':select_replay(updated, 'adaptive'),
                'second_replay_executed':False, 'scientific_execution_authorized':False}
    return {'schema_version':'rhombus-0195-adaptive-evidence-replay-v1', 'protocol':PROTOCOL,
        'protocol_id':digest(PROTOCOL),'implementation_sha256':implementation_sha,'candidate_pools':pools,
        'candidate_pool_count':4,'source_condition_count':32,
        'empirical_scope':'O_ONLY author-series proxy; not certified crystal phase','independent_physical_specimens_verified':0,
        'feedback':feedback,'verified_local_capability':capability,
        'unexecuted_actions':[{'candidate_id':p['id'],'action':'quantify_ionic_transport',
            'status':'BLOCKED','measured_cost':None,'reason':'No verified scientific local backend, qualified structure/model/domain or cost; proposal never dispatched'} for p in pools],
        'comparisons':comparisons,
        'unique_source_pools_replayed':len({p['candidate_id'] for p in comparisons}),
        'unique_evidence_record_count':len({r['evidence_id'] for r in records}),
        'evidence_records':list({r['evidence_id']:r for r in records}.values()),
        'scientific_GO':False,'production_enabled':False,'official_TEST121_read':False,
        'P0_01':'BLOCKED','P0_02':'BLOCKED','P0_03':'BLOCKED',
        'new_STRICT_DOI_groups':0,'new_STRICT_manufacturing_comparisons':0,
        'claim':'Deterministic budgeted applicability-replay coverage; not material discovery, calibrated information gain or a compute saving.',
        'counterfactuals':'Each selected offline action was actually replayed separately. Unexecuted physical tasks have no observed outcome/cost.',
        'timing_limits':'Observed sequential same-process replay time; import/cache/order and host effects prevent a speedup claim.',
        'domain_feasibility':{'conventional_source_DOIs':3,'conventional_source_formula_components':2,
            'categorical_route_DOIs':1,'hot_press_DOIs':1,'hot_press_reported_series':6,
            'separate_domain_model_trained':False,
            'reason':'Do not pool regimes or treat conditions as independent studies; no qualified distinct train/evaluation design for a new process model.'},
        'append_only_correction':{'prior_report':'niobium_choice_attempt_20261023_v1.json',
            'incorrect_prior_narrative':'2020training overlaps targetNb0.6',
            'correct_nominal_formula':'Li6.6La3Zr1.6Nb0.4O12; targetNb0.4',
            'effect_on_prior_code_result':'none: all target-source pools were quarantined by any-formula overlap'},
        'physical_abstention_correctness':None,'historical_outcome_exposure':True}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--authorize-offline-replay',action='store_true');args=ap.parse_args()
    result=run_adaptive_evidence_replay(authorized=args.authorize_offline_replay)
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({p['policy']:{'source':p['candidate_id'],'conditions':p['conditions_with_explicit_decision'],
          'seconds':p['measured_replay_wall_seconds']} for p in result['comparisons']},indent=2))

if __name__=='__main__':main()
