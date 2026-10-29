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
    'H': (.750, 1.750, .380, 1.30, -1),
})
CATIONS = MappingProxyType({
    'Li': (1, .76), 'Al': (3, .535), 'La': (3, 1.032),
    'Zr': (4, .72), 'Ta': (5, .64), 'Nb': (5, .64),
    'P': (5, .38), 'Ge': (4, .53), 'Si': (4, .40),
    'Sn': (4, .69), 'Ti': (4, .605), 'Y': (3, .90),
    'In': (3, .80), 'Sc': (3, .745),
    'B': (3, .27), 'Ga': (3, .62), 'V': (5, .54),
    'Sb': (5, .60), 'Bi': (3, 1.03), 'Cr': (3, .615),
    'Mo': (6, .59), 'W': (6, .60), 'Mn': (4, .53),
    'Fe': (3, .645), 'Co': (3, .545), 'Ni': (3, .56),
    'Cu': (2, .73), 'Zn': (2, .60), 'Mg': (2, .72),
    'Ca': (2, 1.00), 'Na': (1, 1.02), 'K': (1, 1.38),
    'Hf': (4, .71), 'Ba': (2, 1.35), 'Sr': (2, 1.18),
    'Ce': (4, .87), 'Nd': (3, .983), 'Sm': (3, .958),
    'Gd': (3, .938), 'Er': (3, .890), 'Lu': (3, .861),
})
REGISTRY_ID = 'rhombus-owner-bvse-constants-v3'
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


def proposed_occupancy_weighted_charges(structure):
    """Evaluate the owner-proposed charge scaling, without asserting literature provenance.

    Returns species-resolved values and supports disordered sites. Formal
    oxidation states must be supplied; charge neutrality and force-field
    applicability are not inferred from this scaling.
    """
    import math
    from pymatgen.core import Species

    positive = negative = 0.0
    species = set()
    for site in structure:
        for sp, occupancy in site.species.items():
            if not isinstance(sp, Species) or not math.isfinite(float(sp.oxi_state)):
                raise ValueError('explicit finite oxidation states required')
            if not math.isfinite(float(occupancy)) or occupancy <= 0:
                raise ValueError('positive finite site occupancy required')
            charge = float(sp.oxi_state)
            if charge == 0:
                raise ValueError('nonzero ionic oxidation states required')
            contribution = float(occupancy) * charge**2 / sp.element.row
            if charge > 0:
                positive += contribution
            else:
                negative += contribution
            species.add(sp)
    if positive <= 0 or negative <= 0:
        raise ValueError('both cations and anions required')
    return {str(sp): float(sp.oxi_state) / math.sqrt(sp.element.row) *
            ((negative / positive) if sp.oxi_state > 0 else (positive / negative))**.25
            for sp in sorted(species, key=str)}



def coordination_summary(structure, *, cutoff_A=3.2):
    """Count periodic anion neighbors of occupied Li; retain raw and clamped means."""
    import math
    if not structure.is_ordered or not math.isfinite(cutoff_A) or cutoff_A<=0:
        raise ValueError('ordered structure and positive finite cutoff required')
    mobile=[site for site in structure if site.specie.symbol=='Li']
    if not mobile:raise ValueError('occupied Li sites required')
    counts=[sum(n.specie.symbol in ANIONS for n in structure.get_neighbors(site,cutoff_A)) for site in mobile]
    if not all(counts):raise ValueError('each Li needs at least one recognized anion neighbor')
    mean=sum(counts)/len(counts)
    return {'counts':counts,'raw_mean':mean,'effective':min(6.,max(4.,mean)),
            'cutoff_A':cutoff_A,'scope':'FIXED_RADIUS_COUNTS_NOT_AUTHENTICATED_FIRST_SHELL'}

def build_charge_scaled_evaluator(structure, *, charge_reference=None, periodic_cutoff_A=8., valence_sum=False, coordination=None):
    """Owner-proposed charge-scaled model, opt-in and not literature-validated.

    The reference composition is frozen across a temporary vacancy probe.
    Distinct oxidation states of one element are rejected by the symbol-keyed
    host kernel rather than silently combining them.
    """
    from .bvse_percolation import SiteEnergyEvaluator,ValenceSumSiteEnergyEvaluator
    from rhombus.generation.defect_engine import decorate_charges
    reference=decorate_charges(structure if charge_reference is None else charge_reference)
    charges=proposed_occupancy_weighted_charges(reference)
    mobile=[sp for site in reference for sp in site.species if sp.symbol=='Li']
    if not mobile or len({str(sp) for sp in mobile})!=1:
        raise ValueError('one explicit Li oxidation state required')
    qli=charges[str(mobile[0])]
    params=dict(CATIONS,Co=(3,.545)); cations={}
    for site in reference:
        sp=site.specie;symbol=sp.symbol
        if sp.oxi_state<=0 or symbol=='Li':continue
        if symbol not in params:raise ValueError('missing cation radius: '+symbol)
        pair=(qli*charges[str(sp)],.74*(.76+params[symbol][1]),params[symbol][1])
        if symbol in cations and cations[symbol]!=pair:raise ValueError('mixed valence requires species-resolved kernel')
        cations[symbol]=pair
    import math
    if coordination is not None and (valence_sum or not math.isfinite(coordination) or not 4<=coordination<=6):
        raise ValueError('coordination in [4,6] requires pairwise model')
    # Coordination is reporting metadata, not a change to the f5ce26ab Hamiltonian.
    # Apply any positive valence-share scalar to the output energies only.
    factor=1.
    anions={s:(v[1],v[2],v[0]) for s,v in ANIONS.items()}
    cations={s:(q,rho,radius) for s,(q,rho,radius) in cations.items()}
    cls=ValenceSumSiteEnergyEvaluator if valence_sum else SiteEnergyEvaluator
    evaluator=cls(structure,anions=anions,
                                  cations=cations,pauli=False,periodic_cutoff_A=periodic_cutoff_A)
    evaluator.charge_metadata={'q_Li':qli,'effective_charges':charges,'screening_factor':.74,
                               'literature_attribution_verified':False,
                               'anion_model':'OWNER_PROPOSED_VALENCE_SUM_REFERENCE_4' if valence_sum else 'PAIRWISE_MORSE',
                               'coordination_effective':coordination,'pair_scale':factor}
    return evaluator
