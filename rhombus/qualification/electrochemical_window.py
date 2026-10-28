"""Zero-temperature chemical-potential stability polytope vs Li/Li+."""
import numpy as np
from scipy.optimize import linprog
from pymatgen.core import Element
from rhombus.atomistics.phase_stability_p1 import build_phase_diagram

_PASSIVATING = {'Li2O', 'Li2S', 'Li3N', 'LiCl', 'LiBr', 'LiF'}
_ALLOY_METALS = {'Ge', 'Ti', 'Sn', 'In'}


def assess_electrochemical_window(candidate, references=None, *, include_intrinsic=False,
                                reference_revision='V3', projection_offset_eV_atom=0., dilute_parent_limit=False):
    if dilute_parent_limit and not include_intrinsic:
        raise ValueError('dilute parent approximation requires intrinsic diagnostic')
    prior = {}
    if references is None:
        from .reference_phases import default_phase_inputs
        candidate, references, prior = default_phase_inputs(candidate,reference_revision=reference_revision)
    diagram, entry, entries = build_phase_diagram(candidate, references)
    if Element('Li') not in entry.composition.elements:
        raise ValueError('Li electrolyte required')
    if include_intrinsic:
        if not np.isfinite(projection_offset_eV_atom) or not 0<=projection_offset_eV_atom<=.005:
            raise ValueError('explicit bounded hull projection offset required')
        strict=assess_electrochemical_window(candidate,references)
        above=max(0.,float(diagram.get_e_above_hull(entry)))
        elements=sorted(entry.composition.elements,key=str);li=elements.index(Element('Li'))
        a=np.array([[e.composition[el] for el in elements] for e in entries]);b=np.array([e.energy for e in entries])
        projected=entry.energy-(above+projection_offset_eV_atom)*entry.composition.num_atoms
        objective=np.zeros(len(elements));objective[li]=1
        solutions=[linprog(sign*objective,A_ub=a,b_ub=b,A_eq=a[-1:],b_eq=[projected],
                           bounds=[(None,None)]*len(elements),method='highs') for sign in (1,-1)]
        mu_ref=float(diagram.el_refs[Element('Li')].energy_per_atom)
        intrinsic=([mu_ref-float(solutions[1].x[li]),mu_ref-float(solutions[0].x[li])]
                   if all(s.success for s in solutions) else None)
        equilibrium=strict['voltage_window_V']
        if strict.get('gate_verdict')=='NO_EQUILIBRIUM_STABILITY_WINDOW':equilibrium=[]
        width=(intrinsic[1]-intrinsic[0]) if intrinsic else None
        if width is not None and abs(width)<1e-7:intrinsic=[sum(intrinsic)/2]*2
        parent_metadata={}
        if dilute_parent_limit and len(entry.composition.elements)>1:
            from pymatgen.core import Composition
            comp=entry.composition;hosts=[e for e in comp.elements if str(e)!='Li'];parents=[]
            for row in references:
                pc=Composition(row['composition'])
                if set(pc.elements)!=set(comp.elements):continue
                scale=comp[hosts[0]]/pc[hosts[0]]
                if any(abs(comp[e]-scale*pc[e])>1e-8*max(1,comp[e]) for e in hosts):continue
                deficiency=1-comp['Li']/(scale*pc['Li'])
                if 1e-8<deficiency<=.05+1e-10:
                    # Parent must be a stable vertex, in the SAME energy gauge.
                    pd,pe,_=build_phase_diagram(row,[r for r in references if r['reference_id']!=row['reference_id']])
                    if pd.get_e_above_hull(pe)<=1e-8:parents.append((deficiency,row))
            if parents:
                deficiency,parent=min(parents,key=lambda p:(p[0],p[1]['reference_id']))
                parent_result=assess_electrochemical_window(parent,
                    [r for r in references if r['reference_id']!=parent['reference_id']],include_intrinsic=True)
                parent_window=parent_result['intrinsic_esw_volts']
                if parent_window is not None:
                    parent_metadata={'esw_evaluation_basis':'PARENT_PHASE_DILUTE_DEFECT_LIMIT',
                        'off_stoichiometric_tieline_window_volts':intrinsic,
                        'parent_reference_id':parent['reference_id'],'parent_composition':parent['composition'],
                        'parent_mobile_deficiency_fraction':deficiency,
                        'approximation_scope':'DILUTE_PARENT_LIMIT_NOT_POINT_DEFECT_REDOX_OR_EQUILIBRIUM_STABILITY'}
                    intrinsic=parent_window;width=intrinsic[1]-intrinsic[0]
        return {**prior,**strict,'equilibrium_esw_volts':equilibrium,'intrinsic_esw_volts':intrinsic,
                **parent_metadata,
                'voltage_window_V':intrinsic if above<=.08 else equilibrium,
                'intrinsic_status':'ZERO_WIDTH_HULL_FACET' if width is not None and abs(width)<1e-7 else 'PROJECTED_HULL_MODEL' if intrinsic else 'UNRESOLVED',
                'projection_energy_eV':projected,'removed_self_decomposition_eV':above*entry.composition.num_atoms,
                'projection_offset_eV_atom':projection_offset_eV_atom,'decision':'ABSTAIN',
                'scope':'HULL_PROJECTION_SENSITIVITY_NOT_INTRINSIC_KINETICS_OR_INDEPENDENT_PHASE_STABILITY',
                'solver_status':[int(s.status) for s in solutions],'qualification':'ABSTAIN'}
    if diagram.get_e_above_hull(entry) > 1e-8:
        return {**prior, 'decision': 'REJECT', 'gate_verdict': 'NO_EQUILIBRIUM_STABILITY_WINDOW',
                'voltage_window_V': [] if prior else None, 'stability_interval_status':'EMPTY_UNSTABLE_PHASE', 'qualification': 'ABSTAIN'}
    elements = sorted(entry.composition.elements, key=str)
    li = elements.index(Element('Li'))
    a = np.array([[e.composition[el] for el in elements] for e in entries])
    b = np.array([e.energy for e in entries])
    objective = np.zeros(len(elements)); objective[li] = 1.
    solutions = [linprog(sign*objective, A_ub=a, b_ub=b, A_eq=a[-1:], b_eq=b[-1:],
                         bounds=[(None, None)]*len(elements), method='highs') for sign in (1, -1)]
    if any(s.status != 0 for s in solutions):
        return {**prior, 'decision': 'ABSTAIN', 'gate_verdict': 'UNBOUNDED_OR_UNRESOLVED_CHEMICAL_POTENTIAL',
                'solver_status': [int(s.status) for s in solutions],
                'voltage_window_V': None, 'qualification': 'ABSTAIN'}
    mu_min, mu_max = [float(s.x[li]) for s in solutions]
    mu_ref = float(diagram.el_refs[Element('Li')].energy_per_atom)
    profile = diagram.get_element_profile(Element('Li'), entry.composition)
    reduction = next((p for p in profile if p['chempot'] >= mu_max-1e-6
                      and p['reaction'].get_coeff(entry.composition) < 0), None)
    # Inventory exactly the stable Li-rich endpoint products. Notebook-supplied
    # product names are not accepted as proof of a passivating interface.
    products = []
    if reduction is not None:
        products = [str(c.reduced_formula) for c in reduction['reaction'].products
                    if c.reduced_composition != entry.composition.reduced_composition and str(c.reduced_formula) != 'Li']
    hazard = any(any(m in c.get_el_amt_dict() and set(c.get_el_amt_dict()) <= {'Li', m}
                     for m in _ALLOY_METALS)
                 for c in reduction['reaction'].products
                 if c.reduced_composition != entry.composition.reduced_composition) if reduction else False
    passivating = bool(products) and all(p in _PASSIVATING for p in products)
    category = ('MIEC_ALLOY_DECOMPOSITION_HAZARD' if hazard else
                'PASSIVATING_SEI' if passivating else 'INTERFACE_PRODUCTS_UNQUALIFIED')
    return {**prior, 'decision': 'REJECT' if hazard else 'CONTINUE', 'gate_verdict': category,
            'voltage_window_V': [mu_ref-mu_max, mu_ref-mu_min],
            'reduction_products': products, 'energy_model_id': candidate['energy_model_id'],
            'scope': 'THERMODYNAMIC_SUPPLIED_PHASES_NO_KINETIC_PASSIVATION_OR_INTERFACE_CONDUCTIVITY_PROOF',
            'qualification': 'ABSTAIN'}
