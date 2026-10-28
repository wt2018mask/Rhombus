"""Default V3 stages; missing energies/trajectories stop without computation."""
import numpy as np
from pymatgen.core import Structure
from rhombus.generation.defect_engine import seed_vacancies, decorate_charges
from rhombus.qualification.electronic_insulation import assess_electronic_insulation
from rhombus.atomistics.phase_stability_p1 import assess_phase_stability
from rhombus.qualification.electrochemical_window import assess_electrochemical_window
from rhombus.qualification.cross_falsifier import compare_evaluators
from rhombus.transport.static_assessment import assess_static_transport
from rhombus.transport.arrhenius_ensemble import quantify_arrhenius

V3_STAGES = ('G', 'P0', 'P0_5', 'P1', 'P1_5', 'P2', 'P2_5', 'P3', 'X', 'S')


def current_structure(context):
    raw = context.get('P1', {}).get('structure', context.get('G', {}).get('structure', context.get('structure')))
    if not isinstance(raw, dict) or len(raw.get('sites', [])) > 512:
        raise ValueError('bounded structure required')
    structure = Structure.from_dict(raw)
    if len(structure) < 2 or not structure.is_ordered or structure.volume <= 0:
        raise ValueError('ordered periodic structure required')
    return structure


def hopping_defect(context):
    structure = current_structure(context)
    defect = context.get('G', {}).get('defect', context.get('defect', {}))
    parent = np.asarray(defect.get('parent_mobile_fractional', []), float)
    if parent.ndim != 2 or parent.shape[1:] != (3,) or not len(parent) or not np.isfinite(parent).all():
        return False
    for point in defect.get('vacant_fractional_targets', []):
        p = np.asarray(point, float)
        if p.shape != (3,) or not np.isfinite(p).all():
            raise ValueError('invalid vacancy coordinates')
        if (structure.lattice.get_all_distances([p], structure.frac_coords).min() > .25
            and structure.lattice.get_all_distances([p], parent).min() < 1e-6):
            return True
    li = [s.frac_coords for s in structure if s.specie.symbol == 'Li']
    for point in defect.get('interstitial_fractional_sites', []):
        p = np.asarray(point, float)
        if p.shape != (3,) or not np.isfinite(p).all():
            raise ValueError('invalid interstitial coordinates')
        if (li and structure.lattice.get_all_distances([p], li).min() < 1e-6
            and structure.lattice.get_all_distances([p], parent).min() > .25):
            return True
    return False


def _missing(reason):
    return {'decision': 'ABSTAIN', 'gate_verdict': reason, 'qualification': 'ABSTAIN'}


def _generate(context):
    structure = current_structure(context)
    if context.get('_spectator_static_model'):
        return {'decision':'CONTINUE','structure':structure.as_dict(),'defect':context.get('defect',{}),
                'scope':'PRESERVE_PRISTINE_STRUCTURE_FOR_INTRINSIC_STATIC_PROBE'}
    if hopping_defect(context):
        return {'decision': 'CONTINUE', 'structure': structure.as_dict(), 'defect': context['defect']}
    defect = seed_vacancies(structure)[0]
    return {'decision': 'CONTINUE', 'structure': defect['structure'], 'defect': defect}


def _electronic(context):
    structure = decorate_charges(current_structure(context))
    symbols = {s.specie.symbol for s in structure}
    domain = context['domain']
    valid = (domain == 'O_ONLY' and 'O' in symbols and 'S' not in symbols
             or domain == 'S_ONLY' and 'S' in symbols and 'O' not in symbols
             or domain == 'HALIDE' and bool(symbols & {'F','Cl','Br','I'}) and not symbols & {'O','S'})
    if not valid:
        return {'decision': 'REJECT', 'gate_verdict': 'DOMAIN_COMPOSITION_MISMATCH'}
    result = assess_electronic_insulation(structure)
    result['formal_charge_e'] = float(structure.charge)
    distance = structure.distance_matrix + np.eye(len(structure))*1e6
    if not np.isfinite(distance).all() or distance.min() < .5:
        return {'decision': 'REJECT', 'gate_verdict': 'STRUCTURAL_OVERLAP'}
    if abs(structure.charge) > 1e-8 and result['decision'] != 'REJECT':
        result['decision'] = 'ABSTAIN'
        result['gate_verdict'] = 'CHARGED_INTRINSIC_PROBE_REQUIRES_EXPLICIT_COMPENSATION'
    return result


def _static(context):
    if context.get('_spectator_static_model'):
        from rhombus.transport.static_assessment import assess_caged_transport,assess_vacancy_transport_a2
        targets=context['G']['defect'].get('vacant_fractional_targets',[])
        if context.get('_softbv_a3_model'):
            from rhombus.transport.static_assessment import assess_vacancy_transport_a3
            result=assess_vacancy_transport_a3(current_structure(context),defect=context['G']['defect'])
        elif context.get('_endpoint_relaxed_vacancy_model'):
            result=assess_vacancy_transport_a2(current_structure(context),defect=context['G']['defect'])
        else:result=assess_caged_transport(current_structure(context),vacancy_targets=targets)
        high=result['effective_activation_barrier_ev']>.85 and result['mep']['converged']
        result.update(decision='REJECT' if high else 'CONTINUE',
                      gate_verdict='FALSIFIED_HIGH_STATIC_BARRIER' if high else 'PROVISIONAL_STATIC_THRESHOLD_CONTINUE',
                      threshold_scope='OWNER_REQUESTED_UNCALIBRATED_STATIC_MODEL_POLICY')
        return result
    return assess_static_transport(current_structure(context), run_mep=False)


def _phase(context):
    row, refs = context.get('phase_energy'), context.get('phase_references')
    if context.get('_default_thermochemical_prior') and refs is None:
        row=row or {'composition':current_structure(context).composition.element_composition.as_dict()}
        revision='A2' if context.get('_endpoint_relaxed_vacancy_model') else 'V3'
        result=assess_phase_stability(row,reference_revision=revision)
        result['electrochemical_prior']=assess_electrochemical_window(row,reference_revision=revision,
                       include_intrinsic=context.get('_endpoint_relaxed_vacancy_model',False),
                       dilute_parent_limit=context.get('_softbv_a3_model',False))
        result['relaxation_status']='NOT_ASSERTED_FROM_THERMOCHEMICAL_PRIOR'
        return result
    if not row or not refs:
        return _missing('COMPATIBLE_COMPETING_PHASE_ENERGIES_UNAVAILABLE')
    structure = current_structure(context)
    from pymatgen.core import Composition
    if Composition(row['composition']).reduced_composition != structure.composition.element_composition.reduced_composition:
        raise ValueError('candidate phase energy composition mismatch')
    result = assess_phase_stability(row, refs)
    if result['decision'] == 'CONTINUE' and context.get('relaxation_verdict') != 'PASS':
        result['decision'] = 'ABSTAIN'
        result['relaxation_status'] = 'MEASURED_RELAXATION_EVIDENCE_REQUIRED'
    return result


def _mep(context):
    if context.get('_spectator_static_model'):
        result=dict(context['P0_5']['mep'])
        result['decision']='CONTINUE' if result['converged'] else 'ABSTAIN'
        return result
    defect = context['G']['defect']
    targets = defect.get('vacant_fractional_targets', [])
    if not targets:
        return _missing('EXPLICIT_VACANCY_HOP_TARGET_REQUIRED')
    result = assess_static_transport(current_structure(context), grid_dimension=8,
                                     vacancy_fractional_target=targets[0])['mep']
    result['decision'] = 'CONTINUE' if result['converged'] else 'ABSTAIN'
    if result['barrier_ev'] > 1. and result['converged']:
        result['decision'] = 'REJECT'
        result['gate_verdict'] = 'FALSIFIED_HIGH_BARRIER'
    result['threshold_status'] = 'PROVISIONAL_1_EV_FIXED_HOST_MODEL'
    return result


def _thermal(context):
    if not context.get('thermal_records'):
        return _missing('REMOTE_THERMAL_TRACES_REQUIRED')
    # Import authenticated or explicitly manual outputs through the existing
    # importer first. Claimed labels alone do not authorize final qualification.
    records = context['thermal_records']
    if any(r.get('p2_verdict') != 'PASS' for r in records):
        return {'decision': 'REJECT', 'gate_verdict': 'THERMAL_STABILITY_NOT_PASSED'}
    return {'decision': 'CONTINUE', 'gate_verdict': 'CALLER_SUPPLIED_P2_LABELS',
            'independent_evidence_verified': False}


def _regime(context):
    records = context.get('P2', {}).get('thermal_records', context.get('thermal_records', []))
    if not records or any(r.get('regime') != 'DIFFUSIVE_FICKIAN' for r in records):
        return _missing('DIFFUSIVE_FICKIAN_SAMPLING_REQUIRED')
    return {'decision': 'CONTINUE', 'gate_verdict': 'CALLER_SUPPLIED_P2_5_LABELS'}


def _transport(context):
    structure = current_structure(context)
    result = quantify_arrhenius(context.get('P2', {}).get('thermal_records', context.get('thermal_records', [])), carrier_count=sum(s.specie.symbol == 'Li' for s in structure),
                                volume_A3=structure.volume)
    result['decision'] = 'CONTINUE' if 'activation_energy_ev' in result else 'ABSTAIN'
    return result


def _cross(context):
    row = context.get('cross_model')
    if not row:
        return _missing('INDEPENDENT_MODEL_EVIDENCE_REQUIRED')
    result = compare_evaluators(**row)
    result['decision'] = ('REJECT' if result['verdict'] == 'MODEL_DISAGREEMENT_OOD' else
                          'ABSTAIN' if result['verdict'] == 'INDEPENDENCE_NOT_ESTABLISHED' else 'CONTINUE')
    return result


def _electrochemical(context):
    energy = context.get('P1', {}).get('phase_energy', context.get('phase_energy'))
    if not energy or not context.get('phase_references'):
        return _missing('ELECTROCHEMICAL_REFERENCE_ENERGIES_REQUIRED')
    return assess_electrochemical_window(energy, context['phase_references'])


def default_adapters():
    return dict(zip(V3_STAGES, (_generate, _electronic, _static, _phase, _mep,
                                _thermal, _regime, _transport, _cross, _electrochemical)))
