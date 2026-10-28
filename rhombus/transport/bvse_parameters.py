"""Versioned owner-supplied constants; literature attribution is not authenticated.

R_min is a Morse minimum, NOT the R_0 of an exponential bond-valence law.
Coordination-specific Shannon radii must not be treated as universal constants.
"""
import hashlib
import json
from types import MappingProxyType

# D_eV, R_min_A, b_A, radius_A, formal oxidation state.
ANIONS = MappingProxyType({
    'O': (.985, 1.960, .390, 1.40, -2),
    'S': (.820, 2.440, .440, 1.84, -2),
    'Se': (.760, 2.560, .450, 1.98, -2),
    'F': (.880, 1.880, .370, 1.33, -1),
    'Cl': (.690, 2.390, .430, 1.81, -1),
    'Br': (.640, 2.540, .450, 1.96, -1),
    'I': (.580, 2.770, .470, 2.20, -1),
    'N': (1.150, 1.940, .380, 1.46, -3),
})
CATIONS = MappingProxyType({
    'Li': (1, .76), 'Al': (3, .535), 'La': (3, 1.032),
    'Zr': (4, .72), 'Ta': (5, .64), 'Nb': (5, .64),
    'P': (5, .38), 'Ge': (4, .53), 'Si': (4, .40),
    'Sn': (4, .69), 'Ti': (4, .605), 'Y': (3, .90),
    'In': (3, .80), 'Sc': (3, .745),
})
REGISTRY_ID = 'rhombus-owner-bvse-constants-v1'
REGISTRY_SHA256 = hashlib.sha256(json.dumps(
    {'anions': dict(ANIONS), 'cations': dict(CATIONS)},
    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def parameter_identity():
    return {'registry_id': REGISTRY_ID, 'sha256': REGISTRY_SHA256,
            'source': 'OWNER_SUPPLIED_2026_10_28',
            'claimed_attribution': 'SoftBV (Adams/Rao), Shannon radii',
            'literature_table_verified': False, 'calibration_status': 'UNQUALIFIED'}


def build_site_evaluator(structure, *, screening_factor=1., effective_charge_scale=1., periodic_cutoff_A=None):
    """Construct the requested Morse + screened Coulomb model, without Pauli.

    The prompt supplies no screening factor/effective charges. Defaults are
    explicit modeling assumptions, not independently published fitted values.
    """
    import math
    from .bvse_percolation import SiteEnergyEvaluator
    if not all(math.isfinite(v) and v > 0 for v in (screening_factor, effective_charge_scale)):
        raise ValueError('positive finite screening/charge scale required')
    anions = {s: (v[1], v[2], v[0]) for s, v in ANIONS.items()}
    cations = {s: (q * effective_charge_scale**2, screening_factor * (.76 + radius), radius)
               for s, (q, radius) in CATIONS.items() if s != 'Li'}
    return SiteEnergyEvaluator(structure, anions=anions, cations=cations, pauli=False,periodic_cutoff_A=periodic_cutoff_A)


def host_radii(structure):
    return [(ANIONS[s.specie.symbol][3] if s.specie.symbol in ANIONS
             else CATIONS[s.specie.symbol][1]) for s in structure if s.specie.symbol != 'Li']


def oxidation_states():
    return {**{s: v[4] for s, v in ANIONS.items()}, **{s: v[0] for s, v in CATIONS.items()}}
