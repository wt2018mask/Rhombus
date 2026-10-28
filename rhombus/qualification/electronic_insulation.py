"""Formal-valence screening is not an electronic band-structure calculation."""
import math
from pymatgen.core import Element
from rhombus.generation.defect_engine import decorate_charges

_D_GROUP = {'Ti': 4, 'V': 5, 'Cr': 6, 'Mn': 7, 'Fe': 8, 'Co': 9,
            'Ni': 10, 'Cu': 11, 'Mo': 6, 'W': 6}
_REDUCIBLE = {('Ti', 4), ('Nb', 5), ('Ge', 4), ('Sn', 4), ('In', 3)}


def assess_electronic_insulation(structure, *, charges=None):
    host = decorate_charges(structure, charges)
    states = {}
    for site in host:
        states.setdefault(site.specie.symbol, set()).add(float(site.specie.oxi_state))
    open_d = [(s, q) for s, values in states.items() for q in values
              if s in _D_GROUP and 0 < _D_GROUP[s] - q < 10]
    mixed = [s for s, values in states.items() if len(values) > 1]
    reducible = [(s, q) for s, values in states.items() for q in values if (s, q) in _REDUCIBLE]
    unknown = [s for s in states if s not in {'Li', 'O', 'S', 'Se', 'F', 'Cl', 'Br', 'I', 'N',
                                          'Al', 'La', 'Zr', 'Ta', 'Nb', 'P', 'Ge', 'Si', 'Sn',
                                          'Ti', 'Y', 'In', 'Sc'} and s not in _D_GROUP]
    if open_d or mixed:
        verdict, decision = 'FALSIFIED_MIEC_ELECTRONIC_LEAKAGE', 'REJECT'
    elif unknown:
        verdict, decision = 'INDETERMINATE_ELECTRONIC_STRUCTURE', 'ABSTAIN'
    elif reducible:
        verdict, decision = 'FLAGGED_ANODE_REDUCTION_RISK', 'CONTINUE'
    else:
        verdict, decision = 'PASS_ELECTRONIC_INSULATOR', 'CONTINUE'
    cations = [Element(s).X for s, qs in states.items() if min(qs) > 0]
    anions = [Element(s).X for s, qs in states.items() if max(qs) < 0]
    differences = [abs(a-c) for a in anions for c in cations if math.isfinite(a) and math.isfinite(c)]
    return {'decision': decision, 'gate_verdict': verdict, 'open_d_states': open_d,
            'mixed_valence_species': mixed, 'reducible_states': reducible,
            'minimum_pauling_difference': min(differences) if differences else None,
            'estimated_bandgap_eV': None,
            'scope': 'PROVISIONAL_FORMAL_VALENCE_SCREEN_NOT_PROOF_OF_INSULATION_OR_MIEC',
            'qualification': 'ABSTAIN'}
