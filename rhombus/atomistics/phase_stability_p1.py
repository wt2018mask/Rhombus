"""Reference-bound convex-hull arithmetic; no implicit DFT or MLIP energies."""
import math
from pymatgen.analysis.phase_diagram import PhaseDiagram
from pymatgen.core import Composition
from pymatgen.entries.computed_entries import ComputedEntry


def build_phase_diagram(candidate, references):
    if not references or len(references) > 1000:
        raise ValueError('bounded nonempty competing phase inventory required')
    model = candidate.get('energy_model_id')
    if not isinstance(model, str) or not model:
        raise ValueError('explicit energy model identity required')
    entries = []
    for row in [*references, candidate]:
        if row.get('energy_model_id') != model or not row.get('reference_id'):
            raise ValueError('consistent energy model and reference identities required')
        energy = row.get('energy_eV')
        comp = Composition(row['composition'])
        if (not isinstance(energy, (float, int)) or not math.isfinite(energy)
            or any(v <= 0 for v in comp.values()) or comp.num_atoms <= 0):
            raise ValueError('finite total energies and positive compositions required')
        entries.append(ComputedEntry(comp, energy, entry_id=row['reference_id']))
    elements = set(entries[-1].composition.elements)
    if any(not set(e.composition.elements) <= elements for e in entries):
        raise ValueError('references outside candidate chemical space')
    endpoints = {e.composition.elements[0] for e in entries[:-1] if e.is_element}
    if not elements <= endpoints:
        raise ValueError('elemental reference endpoints missing')
    if len({e.entry_id for e in entries}) != len(entries):
        raise ValueError('duplicate phase reference identity')
    return PhaseDiagram(entries), entries[-1], entries


def assess_phase_stability(candidate, references=None, *, reference_revision='V3'):
    prior = {}
    if references is None:
        from rhombus.qualification.reference_phases import default_phase_inputs
        candidate, references, prior = default_phase_inputs(candidate,reference_revision=reference_revision)
    diagram, entry, _ = build_phase_diagram(candidate, references)
    products, above = diagram.get_decomp_and_e_above_hull(entry)
    mev = max(0., float(above) * 1000)
    if mev <= 30 + 1e-7:
        verdict, decision = 'PASS_THERMODYNAMICALLY_STABLE', 'CONTINUE'
    elif mev <= 80 + 1e-7:
        verdict, decision = 'PASS_METASTABLE_SYNTHESIZABLE', 'CONTINUE'
    elif mev > 100 + 1e-7:
        verdict, decision = 'FALSIFIED_HIGH_HULL_ENERGY', 'REJECT'
    else:
        verdict, decision = 'INDETERMINATE_HULL_MARGIN', 'ABSTAIN'
    return {**prior, 'decision': decision, 'gate_verdict': verdict, 'energy_above_hull_meV_atom': mev,
            'energy_model_id': candidate['energy_model_id'],
            'decomposition': [{'reference_id': e.entry_id, 'fraction': float(v)} for e, v in products.items()],
            'reference_ids': [r['reference_id'] for r in references],
            'scope': 'CONDITIONAL_SUPPLIED_PHASE_INVENTORY_NOT_REFERENCE_COMPLETENESS_OR_SYNTHESIS_PROOF',
            'qualification': 'ABSTAIN'}
