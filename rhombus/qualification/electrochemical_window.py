"""Zero-temperature chemical-potential stability polytope vs Li/Li+."""
import numpy as np
from scipy.optimize import linprog
from pymatgen.core import Element
from rhombus.atomistics.phase_stability_p1 import build_phase_diagram

_PASSIVATING = {'Li2O', 'Li2S', 'Li3N', 'LiCl', 'LiBr', 'LiF'}
_ALLOY_METALS = {'Ge', 'Ti', 'Sn', 'In'}


def assess_electrochemical_window(candidate, references):
    diagram, entry, entries = build_phase_diagram(candidate, references)
    if Element('Li') not in entry.composition.elements:
        raise ValueError('Li electrolyte required')
    if diagram.get_e_above_hull(entry) > 1e-8:
        return {'decision': 'REJECT', 'gate_verdict': 'NO_EQUILIBRIUM_STABILITY_WINDOW',
                'voltage_window_V': None, 'qualification': 'ABSTAIN'}
    elements = sorted(entry.composition.elements, key=str)
    li = elements.index(Element('Li'))
    a = np.array([[e.composition[el] for el in elements] for e in entries])
    b = np.array([e.energy for e in entries])
    objective = np.zeros(len(elements)); objective[li] = 1.
    solutions = [linprog(sign*objective, A_ub=a, b_ub=b, A_eq=a[-1:], b_eq=b[-1:],
                         bounds=[(None, None)]*len(elements), method='highs') for sign in (1, -1)]
    if any(s.status != 0 for s in solutions):
        return {'decision': 'ABSTAIN', 'gate_verdict': 'UNBOUNDED_OR_UNRESOLVED_CHEMICAL_POTENTIAL',
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
    return {'decision': 'REJECT' if hazard else 'CONTINUE', 'gate_verdict': category,
            'voltage_window_V': [mu_ref-mu_max, mu_ref-mu_min],
            'reduction_products': products, 'energy_model_id': candidate['energy_model_id'],
            'scope': 'THERMODYNAMIC_SUPPLIED_PHASES_NO_KINETIC_PASSIVATION_OR_INTERFACE_CONDUCTIVITY_PROOF',
            'qualification': 'ABSTAIN'}
