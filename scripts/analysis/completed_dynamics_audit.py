"""Describe completed displacement separately from aborted trajectories."""
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from pymatgen.core import Structure
from scipy.stats import spearmanr
from rhombus.transport.cohort_audit import minimum_host_host_distance
from rhombus.transport.cohort_evidence import _digest_structure

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/benchmarks/v3_static/same_hash_full_comparison_v1.json'
DEST = ROOT / 'data/benchmarks/v3_static/completed_dynamics_audit_v1.json'


def main():
    source = json.loads(SOURCE.read_text()); observations = []; structures = []
    for row in source['rows']:
        p1 = json.loads((ROOT / row['p1_path']).read_text())['result']
        raw = p1['relaxed_structure_dict']
        if _digest_structure(raw) != row['relaxed_sha256']:
            raise ValueError('P1 relaxed structure hash mismatch')
        structure = Structure.from_dict(raw); distance = minimum_host_host_distance(structure)
        complete, crashes = [], []
        for p in row['p2_records']:
            term = p.get('termination') or {}; mobile = p.get('mobile_ion_metrics') or {}
            displacement = mobile.get('mobile_mean_displacement_A'); steps = p.get('production_steps_completed')
            if term.get('completed') is True and isinstance(steps, int) and steps > 0 and isinstance(displacement, (int, float)) and not isinstance(displacement, bool) and math.isfinite(displacement):
                complete.append((p, float(displacement)))
            elif term.get('completed') is False and term.get('note') == 'explosive-step':
                crashes.append(p)
        common = {'batch_id': row['batch_id'], 'formula': row['formula'], 'relaxed_sha256': row['relaxed_sha256'],
                  'x_vac': row['relaxed'].get('x_vac'), 'channel_ev': row['relaxed'].get('host_channel_barrier_3d_ev'),
                  'normalized_channel_ev': row['relaxed'].get('normalized_channel_ev'),
                  'radius_A': row['geometric'].get('radius_A'), 'host_host_distance_A': distance,
                  'p1_hull_ev_atom': p1.get('e_hull_ev_per_atom'), 'p1_volume_change_fraction': p1.get('volume_change_fraction')}
        structures.append({**common, 'completed_count': len(complete), 'explosive_count': len(crashes),
                           'subset': 'MIXED' if complete and crashes else 'COMPLETED' if complete else 'EXPLOSIVE' if crashes else 'OTHER'})
        for p, displacement in complete:
            p25 = []
            for link in row.get('p25_records', []):
                result = json.loads((ROOT / link['path']).read_text()).get('result') or {}
                pointer = (result.get('provenance') or {}).get('p2_result_path', '').replace('\\', '/')
                if pointer == p['path']:
                    p25.append(link)
            observations.append({**common, 'p2_path': p['path'], 'temperature_K': p.get('temperature_K'),
                'production_steps': p.get('production_steps_completed'), 'p2_verdict': p.get('p2_verdict'),
                'mean_li_displacement_A': displacement, 'p25_records': p25})
    single = {s['relaxed_sha256'] for s in structures if s['completed_count'] == 1 and not s['explosive_count']}
    sample = [r for r in observations if r['relaxed_sha256'] in single and r['temperature_K'] == 550]
    correlations = {}
    for key in ('channel_ev', 'radius_A', 'x_vac', 'host_host_distance_A'):
        pairs = [(r[key], r['mean_li_displacement_A']) for r in sample if r[key] is not None]
        if len(pairs) >= 3 and len({p[0] for p in pairs}) > 1 and len({p[1] for p in pairs}) > 1:
            z = spearmanr([p[0] for p in pairs], [p[1] for p in pairs])
            correlations[key] = {'n': len(pairs), 'rho': float(z.statistic), 'p_value': float(z.pvalue)}
        else:
            correlations[key] = {'n': len(pairs), 'rho': None, 'reason': 'INSUFFICIENT_VARIATION_OR_DATA'}
    out = {'schema': 'completed-dynamics-audit-v1', 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
           'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'structures': structures, 'completed_records': observations, 'single_record_550K_correlations': correlations,
           'subset_counts': dict(Counter(s['subset'] for s in structures)), 'qualification': 'ABSTAIN',
           'scope': 'DESCRIPTIVE_NOT_INDEPENDENT_VALIDATION_P25_PATH_LINKS_UNATTESTED'}
    out['exclusive_subset_medians'] = {}
    for subset in ('COMPLETED', 'EXPLOSIVE'):
        for key in ('host_host_distance_A', 'p1_hull_ev_atom', 'p1_volume_change_fraction'):
            values = [s[key] for s in structures if s['subset'] == subset and s[key] is not None and math.isfinite(s[key])]
            out['exclusive_subset_medians'][subset + ':' + key] = {
                'n': len(values), 'median': statistics.median(values) if values else None}
    DEST.write_text(json.dumps(out, sort_keys=True, indent=2, allow_nan=False) + '\n')
    print('structures', len(structures), 'completed records', len(observations), 'counts', out['subset_counts'])
    print('single-record correlations', correlations)


if __name__ == '__main__': main()
