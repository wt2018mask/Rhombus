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


def minimum_host_host_distance(structure):
    """Minimum MIC distance between distinct non-Li sites, not periodic self-images."""
    indices = [i for i, site in enumerate(structure) if site.specie.symbol != 'Li']
    if len(indices) < 2:
        return None
    distances = structure.distance_matrix[np.ix_(indices, indices)].copy()
    np.fill_diagonal(distances, np.inf)
    return float(distances.min())


def host_steric_diagnostics(structure, *, warning_distance_A=1.8):
    """Owner-specified distance warning and radius-ratio heuristic, not an MD gate."""
    indices = [i for i, site in enumerate(structure) if site.specie.symbol != 'Li']
    if len(indices) < 2:
        return {'host_min_distance_A': None, 'host_min_radius_ratio': None,
                'host_steric_collision_warning': None}
    distances = structure.distance_matrix[np.ix_(indices, indices)].copy()
    radii = np.asarray(host_radii(structure), float)
    np.fill_diagonal(distances, np.inf)
    minimum = float(distances.min())
    return {'host_min_distance_A': minimum,
            'host_min_radius_ratio': float((distances / (radii[:, None] + radii[None, :])).min()),
            'host_steric_collision_warning': minimum < warning_distance_A,
            'warning_threshold_A': warning_distance_A,
            'scope': 'OWNER_THRESHOLD_HEURISTIC_NOT_VALIDATED_MD_GATE_NO_SELF_IMAGES'}


def accessible_basin_fraction(structure, host, field, graph, *, li_occupancy_A=1.4,
                              li_clearance_A=1.95, host_clearance_A=1.5, basin_separation_A=1.95):
    """Voxel-minimum diagnostic; not a crystallographic vacancy concentration."""
    from scipy.ndimage import minimum_filter
    mobile = [s.frac_coords for s in structure if s.specie.symbol == 'Li']
    hosts = [s.frac_coords for s in structure if s.specie.symbol != 'Li']
    if not mobile or not hosts:
        raise ValueError('Li and host sites required')
    values = np.asarray(field, float)
    indices = np.argwhere(values == minimum_filter(values, size=3, mode='wrap'))
    indices = sorted(indices.tolist(), key=lambda idx: (float(values[tuple(idx)]), tuple(idx)))
    threshold = graph['minimum_energy_eV'] + graph['barriers_eV']['3D']
    occupied_energy_median = (float(np.median(host(structure.lattice.get_cartesian_coords(mobile))[0]))
                              if host is not None else None)
    selected = []; occupied = 0; vacant = 0; ambiguous = 0
    for index in indices:
        point = np.asarray(index) / np.asarray(values.shape)
        if selected and structure.lattice.get_all_distances([point], selected).min() < basin_separation_A:
            continue
        selected.append(point)
        li = float(structure.lattice.get_all_distances([point], mobile).min())
        host_distance = float(structure.lattice.get_all_distances([point], hosts).min())
        if li <= li_occupancy_A:
            occupied += 1
        elif li >= li_clearance_A and host_distance >= host_clearance_A and values[tuple(index)] <= threshold:
            vacant += 1
        else:
            ambiguous += 1
    return {'x_vac_basin': vacant / (len(mobile) + vacant), 'occupied_basins': occupied,
            'unoccupied_accessible_basins': vacant, 'other_basins': ambiguous,
            'energy_threshold_eV': float(threshold), 'occupied_site_energy_median_eV': occupied_energy_median,
            'grid_shape': list(values.shape),
            'parameters_A': {'li_occupancy': li_occupancy_A, 'li_clearance': li_clearance_A,
                             'host_clearance': host_clearance_A, 'basin_separation': basin_separation_A},
            'scope': 'GRID_THRESHOLD_HEURISTIC_NOT_VACANCY_CONCENTRATION', 'qualification': 'ABSTAIN'}


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
        result.update(host_steric_diagnostics(s))
        host = build_charge_scaled_evaluator(s)
        field = host.grid(.35, min_dimension=12, max_dimension=28)
        graph = percolation_thresholds(field)
        channel = graph['barriers_eV']['3D']
        result['basin_diagnostic'] = accessible_basin_fraction(s, host, field, graph)
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
