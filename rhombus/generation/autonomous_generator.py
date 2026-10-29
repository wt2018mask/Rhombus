"""Deterministic template/defect proposals, not a learned or qualified generator."""
import hashlib
import json
import math
from pathlib import Path
from pymatgen.core import Lattice, Structure
from .defect_engine import expand_supercell, substitute_aliovalent

DOMAINS = ('O_ONLY', 'S_ONLY', 'HALIDE')


def reference_templates():
    root = Path(__file__).resolve().parents[2] / 'data/benchmarks/known_material/structures'
    result = []
    for domain, name in [('O_ONLY', 'literature/tetragonal-llzo-awaka-2009-nd-v1.cif'),
                         ('S_ONLY', 'cod/9009060-latest-freeze-v1.cif')]:
        path = root / name
        result.append({'domain': domain, 'template_id': name, 'structure': Structure.from_file(path),
                       'origin': 'RETAINED_CIF', 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    # No sourced Li3MCl6 fractional coordinates were supplied. These are
    # deliberately labeled hypothetical octahedral prototypes, never real CIFs.
    for metal in ('Y', 'Sc', 'In', 'Er'):
        species = ['Li']*3 + [metal] + ['Cl']*6
        coords = [[0, 0, 0], [0, .5, 0], [.5, 0, 0], [.5, .5, .5],
                  [.2, .5, .5], [.8, .5, .5], [.5, .2, .5], [.5, .8, .5], [.5, .5, .2], [.5, .5, .8]]
        result.append({'domain': 'HALIDE', 'template_id': f'hypothetical-Li3{metal}Cl6-v1',
                       'origin': 'HYPOTHETICAL_COORDINATES_NOT_CRYSTALLOGRAPHIC_BENCHMARK',
                       'structure': Structure(Lattice.cubic(8.), species, coords),
                       'source_sha256': None})
    return result


def selection_utility(*, atom_count, static_barrier_eV=None, hull_meV_atom=None,
                      window_width_V=None, epistemic_uncertainty=1.):
    if not 1 <= atom_count <= 1024 or not math.isfinite(epistemic_uncertainty) or not 0 <= epistemic_uncertainty <= 1:
        raise ValueError('bounded atom cost and uncertainty required')
    metrics = (static_barrier_eV, hull_meV_atom, window_width_V)
    if any(v is not None and (not math.isfinite(v) or v < 0) for v in metrics):
        raise ValueError('finite nonnegative supplied selection metrics required')
    channel = 0 if static_barrier_eV is None else 1/(1+static_barrier_eV)
    hull = 0 if hull_meV_atom is None else 1/(1+hull_meV_atom/30)
    window = 0 if window_width_V is None else min(window_width_V/5, 1)
    return {'score': channel + .5*hull + .5*window + .25*epistemic_uncertainty - atom_count/512,
            'missing_metrics': [k for k, v in zip(('static_barrier_eV', 'hull_meV_atom', 'window_width_V'), metrics) if v is None],
            'scope': 'EXPLICIT_HEURISTIC_SELECTION_NOT_SCIENTIFIC_FITNESS',
            'weights': {'channel': 1., 'hull': .5, 'window': .5, 'uncertainty': .25, 'atoms': -1/512}}


class AutonomousCandidateGenerator:
    def __init__(self, templates=None):
        self.templates = reference_templates() if templates is None else list(templates)
        if len(self.templates) > 32:
            raise ValueError('template budget exceeded')

    def generate(self, *, domains=DOMAINS, top_k=6, minimum_length_A=9.5):
        if not 1 <= top_k <= 32 or set(domains)-set(DOMAINS):
            raise ValueError('bounded known domains required')
        candidates = []
        for template in self.templates:
            domain = template['domain']
            if domain not in domains:
                continue
            parent = expand_supercell(template['structure'], minimum_length_A=minimum_length_A)
            if domain == 'O_ONLY':
                old, new, charge = 'Zr', 'Ta', 5
            elif domain == 'S_ONLY':
                old, new, charge = 'S', 'Cl', -1
            else:
                old = next((s.specie.symbol for s in parent if s.specie.symbol not in ('Li', 'Cl')), None)
                new, charge = 'Zr', 4
            index = next((i for i, s in enumerate(parent) if s.specie.symbol == old), None)
            if index is None:
                raise ValueError('template lacks declared substitution site')
            from rhombus.transport.bvse_parameters import oxidation_states
            charges = dict(oxidation_states(), Er=3)
            defect = substitute_aliovalent(parent, site_index=index, dopant=new,
                                           dopant_charge=charge, charges=charges)[0]
            identity = {'template_id': template['template_id'], 'domain': domain,
                        'defect': defect, 'origin': template['origin'], 'source_sha256': template.get('source_sha256')}
            digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            candidates.append(dict(identity, candidate_id='v3-'+digest,
                                   structure=defect['structure'], qualification='ABSTAIN',
                                   selection_utility=selection_utility(atom_count=len(parent)-1)))
        return sorted(candidates, key=lambda c: (-c['selection_utility']['score'], c['candidate_id']))[:top_k]
