"""Compose host-selected bounded adapters and content-address a research dossier.

Adapters are trusted host code. Their output is not independent scientific
evidence. No default local MLIP or cloud provider is invoked here.
"""
import hashlib
import json

STAGES=('G_P0','P0_5','P1','P1_5','P2','P2_5','P3','X')


class RhombusDiscoveryFunnel:
    def __init__(self, adapters=None):
        from .scientific_adapters import V3_STAGES, default_adapters
        self.stages=V3_STAGES if adapters is None else STAGES
        if adapters is None:
            adapters=default_adapters()
        if set(adapters)-set(self.stages) or any(not callable(v) for v in adapters.values()):
            raise ValueError('known stages and explicit host adapters required')
        self.adapters=dict(adapters)

    def run(self, candidate):
        if not isinstance(candidate,dict) or not candidate.get('candidate_id') or not candidate.get('domain'):
            raise ValueError('candidate identity and domain required')
        candidate=json.loads(json.dumps(candidate,allow_nan=False))
        context=json.loads(json.dumps(candidate,allow_nan=False));observations=[];decision='ABSTAIN';saved=[]
        for stage in self.stages:
            if self.stages!=STAGES and stage in ('P1_5','P2'):
                from .scientific_adapters import hopping_defect
                if not hopping_defect(context):
                    observations.append({'stage':stage,'decision':'ABSTAIN','reason':'NO_VERIFIED_HOPPING_DEFECT'})
                    break
            if stage not in self.adapters:
                observations.append({'stage':stage,'decision':'UNAVAILABLE'});break
            result=self.adapters[stage](json.loads(json.dumps(context,allow_nan=False)))
            if not isinstance(result,dict) or result.get('decision') not in ('CONTINUE','REJECT','ABSTAIN'):
                raise ValueError('adapter must return explicit conservative decision')
            result=json.loads(json.dumps(result,allow_nan=False))
            observations.append({'stage':stage,'result':result});context[stage]=result
            if result['decision']=='REJECT':
                decision='FALSIFIED_BY_SUPPLIED_DIAGNOSTIC'
                if stage in ('G_P0','G','P0','P0_5','P1','P1_5'):saved=['P2_MD','P3_ARRHENIUS']
                break
            if result['decision']=='ABSTAIN':break
        dossier={'schema_version':'rhombus-discovery-dossier-v1','candidate':candidate,
                 'decision':decision,'observations':observations,'compute_saved_stages':saved,
                 'execution_authorized':False,'scientific_GO':False,'qualification':'ABSTAIN',
                 'scope':'Host adapter diagnostic decisions, not independent scientific acceptance'}
        raw=json.dumps(dossier,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        return dict(dossier,dossier_sha256=hashlib.sha256(raw).hexdigest())
