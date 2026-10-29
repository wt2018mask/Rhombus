"""Provisional cross-evaluator discrepancy tests, not independence certification."""
import math


def compare_evaluators(primary, secondary, *, host_rmsd_A, host_limit_A):
    keys=('volume_A3','barrier_eV')
    for row in (primary,secondary):
        if not row.get('model_id') or any(not math.isfinite(row[k]) or row[k]<0 for k in keys) or row['volume_A3']<=0:
            raise ValueError('finite volume/barrier and model identity required')
    if not all(math.isfinite(v) and v>=0 for v in (host_rmsd_A,host_limit_A)) or host_limit_A==0:
        raise ValueError('positive finite host limit required')
    reasons=[]
    if abs(primary['volume_A3']-secondary['volume_A3'])/primary['volume_A3']>.05:reasons.append('VOLUME_DISAGREEMENT')
    if abs(primary['barrier_eV']-secondary['barrier_eV'])>.20:reasons.append('BARRIER_DISAGREEMENT')
    if primary.get('fast_diffusion') and host_rmsd_A>host_limit_A:reasons.append('FRAMEWORK_MELTING_ARTIFACT')
    verdict=('MODEL_DISAGREEMENT_OOD' if reasons else
             'INDEPENDENCE_NOT_ESTABLISHED' if primary['model_id']==secondary['model_id'] else 'NO_DISCREPANCY_DETECTED')
    return {'verdict':verdict,
            'reasons':reasons,'independent_training_lineage':'UNVERIFIED',
            'threshold_status':'PROVISIONAL','qualification':'ABSTAIN'}
