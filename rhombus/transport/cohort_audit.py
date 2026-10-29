"""Repository-local, unqualified static screening with explicit failures."""
import hashlib
import json
from pathlib import Path

import numpy as np
from pymatgen.core import Structure

from .bvse_parameters import ANIONS, build_charge_scaled_evaluator, host_radii
from .bvse_percolation import percolation_thresholds
from .cif_probe import prepare_cif_evaluation_probe
from rhombus.qualification.electronic_insulation import assess_electronic_insulation


def geometric_percolation_radius(structure, *, spacing_A=.35, min_dimension=12, max_dimension=28):
    """Maximin clearance on a 26-neighbor voxel graph; radii are model inputs."""
    from pymatgen.util.coord import pbc_shortest_vectors
    if not structure.is_ordered or not 0 < spacing_A or not 2 <= min_dimension <= max_dimension <= 64:
        raise ValueError('ordered structure and bounded grid required')
    hosts = [site.frac_coords for site in structure if site.specie.symbol != 'Li']
    radii = np.asarray(host_radii(structure), float)
    if not hosts:
        raise ValueError('host required')
    shape = np.clip(np.ceil(np.asarray(structure.lattice.abc) / spacing_A).astype(int), min_dimension, max_dimension)
    fractions = np.stack(np.meshgrid(*[np.arange(n) / n for n in shape], indexing='ij'), axis=-1).reshape(-1, 3)
    clearance = []
    for i in range(0, len(fractions), 128):
        vectors = pbc_shortest_vectors(structure.lattice, fractions[i:i+128], hosts)
        clearance.append((np.linalg.norm(vectors, axis=2) - radii).min(axis=1))
    field = -np.concatenate(clearance).reshape(tuple(shape))
    graph = percolation_thresholds(field)
    threshold = graph['minimum_energy_eV'] + graph['barriers_eV']['3D']
    return {'radius_A': -threshold, 'grid_shape': shape.tolist(),
            'actual_spacing_A': (np.array(structure.lattice.abc) / shape).tolist(),
            'scope': 'VOXEL_GRAPH_MAXIMIN_NOT_CONTINUUM_CONVERGENCE',
            'radii_source': 'OWNER_SUPPLIED_UNVERIFIED_IONIC_RADII', 'qualification': 'ABSTAIN'}


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
        if result['electronic_gate'] == 'FALSIFIED_MIEC_ELECTRONIC_LEAKAGE':
            result['grid_channel_tier'] = 'REJECT_P0_ELECTRONIC'
        elif channel > 1.10:
            result['grid_channel_tier'] = 'HIGH_3D_CHANNEL_BARRIER'
        elif .5 * channel <= .55 and result['electronic_gate'] == 'PASS_ELECTRONIC_INSULATOR':
            result['grid_channel_tier'] = 'LOW_3D_CHANNEL_CANDIDATE'
        else:
            result['grid_channel_tier'] = 'GRID_SCREENING_INCONCLUSIVE'
        result['status'] = 'COMPUTED_UNQUALIFIED'
    except Exception as error:
        result.update(status='FAILED', error=repr(error))
    return result


def related_batch_records(root, rows):
    """Link retained records by batch ID; do not claim trajectory identity."""
    root = Path(root)
    wanted = {Path(row['path']).stem for row in rows if row['category'] == 'ORDERED_EXPANSION_OR_BATCH_CANDIDATE'}
    result = {key: [] for key in sorted(wanted)}
    for directory in sorted((root / 'data/batches').iterdir()):
        if not directory.is_dir() or not directory.name.startswith(('p2', 'p25', 'done')):
            continue
        for path in sorted(directory.rglob('*.json')):
            try:
                record = json.loads(path.read_text())
                batch_id = record.get('batch_id')
                if batch_id not in wanted:
                    continue
                values = record.get('result') or {}
                if not isinstance(values, dict):
                    continue
                keys = ('p1_verdict', 'p2_verdict', 'p25_verdict', 'dynamic_state',
                        'transport_state', 'temperature_K', 'p2_input_relaxed_sha256',
                        'input_structure_sha256', 'relaxed_structure_sha256')
                result[batch_id].append({'path': str(path.relative_to(root)),
                    'fields': {key: values[key] for key in keys if key in values},
                    'link_scope': 'BATCH_ID_ONLY_STRUCTURE_AND_CONDITIONS_NOT_VERIFIED'})
            except (OSError, ValueError, TypeError):
                continue
    return result
