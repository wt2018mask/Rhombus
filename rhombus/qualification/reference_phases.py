"""Owner-supplied 35-compound + 14-element prior, NOT verified calorimetry.

All values are formation energies per atom in a single declared prior gauge.
They must never be combined with absolute MACE/DFT or raw Ewald cell energies.
"""
import hashlib
import json
import math
from types import MappingProxyType
import numpy as np
from scipy.optimize import linprog
from pymatgen.core import Composition

DEFAULT_THERMOCHEMICAL_REFERENCES_V3 = MappingProxyType({
    **{s: 0. for s in ('Li','O','S','Cl','Al','La','Zr','Ta','P','Ge','Y','In','Sc','Co')},
    'Li2O': -2.040, 'Al2O3': -3.430, 'LiAlO2': -3.080, 'Li5AlO4': -2.460,
    'La2O3': -3.710, 'ZrO2': -3.790, 'La2Zr2O7': -3.770, 'Li2ZrO3': -3.050,
    'Ta2O5': -3.030, 'LiTaO3': -2.920, 'Li7La3Zr2O12': -3.170,
    'Li6.5La3Zr1.5Ta0.5O12': -3.165, 'LiCoO2': -1.760, 'Co3O4': -1.350, 'CoO': -1.230,
    'Li2S': -1.510, 'P2S5': -.410, 'Li3PS4': -1.150, 'GeS2': -.540,
    'Li4GeS4': -1.180, 'Li10GeP2S12': -1.165, 'Li6PS5Cl': -1.365,
    'Li3P': -.820, 'Li15Ge4': -.360, 'LiCl': -2.110,
    'YCl3': -2.590, 'Li3YCl6': -2.310, 'InCl3': -1.390, 'Li3InCl6': -1.820,
    'ScCl3': -2.400, 'Li3ScCl6': -2.230, 'ZrCl4': -2.030,
    'Li2ZrCl6': -2.085, 'LiIn': -.280, 'Li3Y': .050,
})
REFERENCE_MODEL_ID = 'OWNER_THERMOCHEMICAL_FORMATION_PRIOR_V3'
REFERENCE_SHA256 = hashlib.sha256(json.dumps(dict(DEFAULT_THERMOCHEMICAL_REFERENCES_V3), sort_keys=True).encode()).hexdigest()
DEFAULT_THERMOCHEMICAL_REFERENCES_A2 = MappingProxyType(dict(DEFAULT_THERMOCHEMICAL_REFERENCES_V3,Li6PS5Cl=-1.468))


def default_phase_inputs(candidate, *, defect_energy_eV=None, defect_energy_model_id=None, reference_revision='V3'):
    """Resolve prior entries or explicitly labeled mixture estimates.

    Mixture estimates on the supplied hull are tautological priors, not a
    candidate stability measurement. Raw Ewald is rejected as a defect offset.
    """
    comp = Composition(candidate['composition'])
    if 'energy_eV' in candidate and candidate.get('energy_model_id') is None:
        raise ValueError('an explicit energy requires its energy model gauge')
    elements = set(comp.elements)
    if reference_revision not in ('V3','A2'):raise ValueError('unknown thermochemical revision')
    table = DEFAULT_THERMOCHEMICAL_REFERENCES_V3 if reference_revision=='V3' else DEFAULT_THERMOCHEMICAL_REFERENCES_A2
    model_id=REFERENCE_MODEL_ID if reference_revision=='V3' else REFERENCE_MODEL_ID+'_A2'
    formulas = [f for f in table if set(Composition(f).elements) <= elements]
    if not elements <= {Composition(f).elements[0] for f in formulas if len(Composition(f).elements) == 1}:
        raise ValueError('default prior lacks elemental chemical space')
    refs = [{'composition': f, 'energy_eV': table[f]*Composition(f).num_atoms,
             'energy_model_id': model_id, 'reference_id': 'prior:'+f} for f in formulas]
    metadata = {'reference_source': 'LITERATURE_THERMOCHEMICAL_PRIOR_V3',
                'actual_source': 'OWNER_SUPPLIED_VALUES_NOT_INDEPENDENTLY_AUTHENTICATED',
                'reference_sha256': hashlib.sha256(json.dumps(dict(table),sort_keys=True).encode()).hexdigest(),
                'reference_revision':reference_revision,'temperature_consistency_verified': False}
    if reference_revision=='A2':metadata['revision_basis']='OWNER_REQUESTED_ENERGY_REPLACEMENT_NOT_INDEPENDENT_CALIBRATION'
    if candidate.get('energy_model_id') is not None:
        if candidate['energy_model_id'] != model_id:
            raise ValueError('cannot mix default formation prior with foreign absolute energies')
        row = dict(candidate)
        metadata['candidate_energy_basis'] = 'EXPLICIT_SAME_PRIOR_GAUGE'
    else:
        matches = [f for f in formulas if Composition(f).reduced_composition == comp.reduced_composition]
        if matches:
            energy = min(table[f] for f in matches)*comp.num_atoms
            metadata['candidate_energy_basis'] = 'OWNER_TABLE_COMPOSITION_PRIOR_NOT_POLYMORPH_ENERGY'
        else:
            els = sorted(elements, key=str)
            amounts = np.array([[Composition(f)[e] for f in formulas] for e in els])
            energies = np.array([table[f]*Composition(f).num_atoms for f in formulas])
            result = linprog(energies, A_eq=amounts, b_eq=[comp[e] for e in els], bounds=(0, None), method='highs')
            if not result.success:
                raise ValueError('no composition-balanced endmember prior')
            energy = float(result.fun)
            metadata.update(candidate_energy_basis='LOWEST_ENDMEMBER_MIXTURE_PRIOR_NOT_STABILITY_EVIDENCE',
                            mixture=[{'phase': f, 'amount': float(n)} for f, n in zip(formulas, result.x) if n > 1e-8])
        row = {'composition': comp.as_dict(), 'energy_eV': energy,
               'energy_model_id': model_id, 'reference_id': candidate.get('reference_id','candidate-prior')}
    if defect_energy_eV is not None:
        if defect_energy_model_id != model_id or not math.isfinite(defect_energy_eV):
            raise ValueError('compatible independently supplied defect energy required; raw Ewald forbidden')
        row['energy_eV'] += defect_energy_eV
        metadata['defect_energy_eV'] = defect_energy_eV
    # Avoid duplicate entry IDs when callers explicitly reuse a table entry.
    refs = [r for r in refs if r['reference_id'] != row['reference_id']]
    return row, refs, metadata
