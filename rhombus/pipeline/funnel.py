"""Compose host-selected bounded adapters and content-address a research dossier.

Adapters are trusted host code. Their output is not independent scientific
evidence. No default local MLIP or cloud provider is invoked here.
"""
import hashlib
import json

STAGES=('G_P0','P0_5','P1','P1_5','P2','P2_5','P3','X')


class RhombusDiscoveryFunnel:
    def __init__(self, adapters=None, *, use_default_literature_references=False, use_spectator_model=False,
                 use_endpoint_relaxed_vacancy_model=False):
        from .scientific_adapters import V3_STAGES, default_adapters
        self.stages=V3_STAGES if adapters is None else STAGES
        if adapters is None:
            adapters=default_adapters()
        if set(adapters)-set(self.stages) or any(not callable(v) for v in adapters.values()):
            raise ValueError('known stages and explicit host adapters required')
        self.adapters=dict(adapters)
        self.use_default_prior=use_default_literature_references
        self.use_spectator_model=use_spectator_model or use_endpoint_relaxed_vacancy_model
        self.use_endpoint_relaxed_vacancy_model=use_endpoint_relaxed_vacancy_model

    def run(self, candidate):
        if not isinstance(candidate,dict) or not candidate.get('candidate_id') or not candidate.get('domain'):
            raise ValueError('candidate identity and domain required')
        candidate=json.loads(json.dumps(candidate,allow_nan=False))
        context=json.loads(json.dumps(candidate,allow_nan=False));observations=[];decision='ABSTAIN';saved=[]
        context['_default_thermochemical_prior']=self.use_default_prior
        context['_spectator_static_model']=self.use_spectator_model
        context['_endpoint_relaxed_vacancy_model']=self.use_endpoint_relaxed_vacancy_model
        for stage in self.stages:
            if self.stages!=STAGES and stage in ('P1_5','P2') and not (stage=='P1_5' and self.use_spectator_model):
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
        dossier['final_qualification_verdict']='ABSTAIN'
        dossier['static_tier1_verdict']=self._static_verdict(context)
        dossier['static_tier1_authority']='PROVISIONAL_MODEL_SCREEN_NOT_VALIDATED_MATERIAL_QUALIFICATION'
        raw=json.dumps(dossier,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        return dict(dossier,dossier_sha256=hashlib.sha256(raw).hexdigest())

    @staticmethod
    def _static_verdict(context):
        if context.get('P0',{}).get('gate_verdict')=='FALSIFIED_MIEC_ELECTRONIC_LEAKAGE':
            return 'FALSIFIED_STATIC_P0_ELECTRONIC_LEAKAGE'
        phase=context.get('P1',{})
        if phase.get('energy_above_hull_meV_atom',0)>100:
            return 'FALSIFIED_STATIC_P1_UNSTABLE_HULL'
        static=context.get('P0_5',{})
        barrier=static.get('effective_activation_barrier_ev')
        mep=static.get('mep',{}) or {}
        frenkel=static.get('frenkel',{})
        if frenkel.get('required'):
            if frenkel.get('site_energy_difference_eV',0)<-1e-6:
                return 'STATIC_MODEL_INAPPLICABLE_NEGATIVE_FRENKEL_ENERGY'
            if frenkel.get('stationary') is not True:return 'STATIC_SCREENING_INCONCLUSIVE'
        if barrier is not None and barrier>.85 and mep.get('converged') is True:
            return 'FALSIFIED_STATIC_P0_5_HIGH_BARRIER'
        if (barrier is not None and barrier<=.65 and mep.get('converged') is True
            and mep.get('endpoints_stationary') is True
            and mep.get('dense_path_barrier_ev',mep.get('barrier_ev',float('inf')))<=.65
            and phase.get('energy_above_hull_meV_atom',float('inf'))<=80
            and context.get('P0',{}).get('gate_verdict')=='PASS_ELECTRONIC_INSULATOR'):
            return 'PROVISIONAL_STATIC_TIER1_CANDIDATE'
        return 'STATIC_SCREENING_INCONCLUSIVE'
