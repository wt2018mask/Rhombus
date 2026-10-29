"""Repository-local, unqualified static screening with explicit failures."""
import hashlib
import json
from pathlib import Path

import numpy as np
from pymatgen.core import Structure

from .bvse_parameters import ANIONS, build_charge_scaled_evaluator
from .bvse_percolation import percolation_thresholds
from .cif_probe import prepare_cif_evaluation_probe
from rhombus.qualification.electronic_insulation import assess_electronic_insulation


def inventory(root, *, limit=40):
    """Return bounded unique byte-identity structures and explicit input failures."""
    root = Path(root)
    if not 1 <= limit <= 50:
        raise ValueError('limit must be between 1 and 50')
    paths = [(p, 'VERIFIED_BENCHMARK_CIF_OR_JSON') for p in sorted((root / 'data/benchmarks/known_material/structures').rglob('*.cif'))]
    paths += [(p, 'ARCHETYPE_OR_ORDERED_PROBE') for p in sorted((root / 'data/benchmarks/v3_static/step_a_inputs').glob('*.cif'))]
    for name in ('pending_topcond20_ordered', 'done_ordered_expansion_wave1_v1', 'p2_ordered_expansion_wave1_v1'):
        paths += [(p, 'ORDERED_EXPANSION_OR_BATCH_CANDIDATE') for p in sorted((root / 'data/batches' / name).glob('*.json'))]
    rows, failures, seen = [], [], set()
    for path, category in paths:
        relative = str(path.relative_to(root))
        try:
            if path.suffix == '.cif':
                probe = prepare_cif_evaluation_probe(path)
                structure, defect = probe['structure'], probe['defect']
                if probe['structure_status'] != 'RAW_ORDERED_CIF':
                    category = 'ARCHETYPE_OR_ORDERED_PROBE'
            else:
                data = json.loads(path.read_text())
                structure = Structure.from_dict(data['structure_dict'])
                defect = data.get('defect', {})
            if not structure.is_ordered or len(structure) < 2 or structure.volume <= 0:
                raise ValueError('ordered periodic structure required')
            serial = json.dumps(structure.as_dict(), sort_keys=True, separators=(',', ':'), allow_nan=False)
            digest = hashlib.sha256(serial.encode()).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            rows.append({'path': relative, 'category': category, 'structure_sha256': digest,
                         'structure': structure, 'defect': defect})
            if len(rows) >= limit:
                break
        except Exception as error:
            failures.append({'path': relative, 'error': str(error)})
    return rows, failures


def assess(row):
    """Evaluate the existing host Hamiltonian without implying a transport verdict."""
    s = row['structure']
    result = {k: v for k, v in row.items() if k not in ('structure', 'defect')}
    result.update(formula=s.composition.reduced_formula, sites=len(s), qualification='ABSTAIN',
                  x_vac=row['defect'].get('stoichiometric_vacancy_fraction'),
                  static_verdict='STATIC_SCREENING_INCONCLUSIVE')
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    try:
        result['spacegroup'] = SpacegroupAnalyzer(s).get_space_group_symbol()
    except Exception:
        result['spacegroup'] = None
    mobile = [i for i, site in enumerate(s) if site.specie.symbol == 'Li']
    anions = [i for i, site in enumerate(s) if site.specie.symbol in ANIONS]
    result['minimum_li_anion_distance_A'] = (
        float(s.distance_matrix[np.ix_(mobile, anions)].min()) if mobile and anions else None)
    try:
        result['electronic_gate'] = assess_electronic_insulation(s)['gate_verdict']
        host = build_charge_scaled_evaluator(s)
        field = host.grid(.35, min_dimension=12, max_dimension=28)
        channel = percolation_thresholds(field)['barriers_eV']['3D']
        result.update(q_Li=host.charge_metadata['q_Li'], grid_shape=list(field.shape),
                      host_channel_barrier_3d_ev=channel,
                      normalized_channel_ev=.5 * channel,
                      actual_spacing_A=(np.array(s.lattice.abc) / np.array(field.shape)).tolist())
        result['status'] = 'COMPUTED_UNQUALIFIED'
    except Exception as error:
        result.update(status='FAILED', error=repr(error))
    return result
