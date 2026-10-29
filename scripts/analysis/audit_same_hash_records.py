"""Audit stored P1/P2 structures by verified hashes without model inference."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from pymatgen.core import Structure
from rhombus.transport.cohort_audit import assess, geometric_percolation_radius
from rhombus.transport.cohort_evidence import _digest_structure

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/benchmarks/v3_static/same_hash_all_records_v1.json'


def collect():
    p1, p2 = defaultdict(list), defaultdict(list)
    for directory in sorted((ROOT / 'data/batches').glob('done*')):
        for path in sorted(directory.rglob('*.json')):
            try:
                d = json.loads(path.read_text()); r = d.get('result') or {}
                if not r.get('relaxed_structure_dict') or not d.get('structure_dict'):
                    continue
                raw = _digest_structure(d['structure_dict']); relaxed = _digest_structure(r['relaxed_structure_dict'])
                if raw == r.get('input_structure_sha256') and relaxed == r.get('relaxed_structure_sha256'):
                    p1[relaxed].append((path, d))
            except (ValueError, KeyError, TypeError, OSError):
                continue
    for directory in sorted((ROOT / 'data/batches').glob('p2*')):
        if directory.name.startswith('p25'):
            continue
        for path in sorted(directory.rglob('*.json')):
            try:
                d = json.loads(path.read_text()); r = d.get('result') or {}; key = r.get('p2_input_relaxed_sha256')
                if key in p1:
                    p2[key].append((path, d))
            except (ValueError, TypeError, OSError):
                continue
    return p1, p2


def main():
    p1, p2 = collect(); rows = []
    for h in sorted(p2):
        path, d = p1[h][0]; r = d['result']
        row = {'p1_path': str(path.relative_to(ROOT)), 'batch_id': d.get('batch_id'),
               'relaxed_sha256': h, 'p2_records': []}
        for p, record in p2[h]:
            v = record['result']
            row['p2_records'].append({'path': str(p.relative_to(ROOT)), 'batch_id': record.get('batch_id'),
                'temperature_K': v.get('temperature_K'), 'p2_verdict': v.get('p2_verdict'),
                'termination': v.get('termination'), 'production_steps_completed': v.get('production_steps_completed'),
                'mobile_ion_metrics': v.get('mobile_ion_metrics')})
        try:
            inp = Structure.from_dict(d['structure_dict']); rel = Structure.from_dict(r['relaxed_structure_dict'])
            def screen(s, digest):
                return assess({'path': row['p1_path'], 'category': 'ORDERED_EXPANSION_OR_BATCH_CANDIDATE',
                               'structure_sha256': digest, 'structure': s, 'defect': {}})
            row.update(formula=rel.composition.reduced_formula, unrelaxed=screen(inp, _digest_structure(d['structure_dict'])), relaxed=screen(rel, h),
                       geometric=geometric_percolation_radius(rel), p1_hull_ev_atom=r.get('e_hull_ev_per_atom'),
                       p1_volume_change_fraction=r.get('volume_change_fraction'), status='COMPUTED_UNQUALIFIED')
        except Exception as e:
            row.update(status='FAILED', error=repr(e))
        rows.append(row)
        out = {'schema': 'same-hash-all-records-v1', 'source_commit': '3516cb69fbac1ef0f612e8e3f97954ddf9e230e1',
               'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'rows': rows,
               'p1_unique_hashes': len(p1), 'matching_p1_p2_hashes': len(p2), 'qualification': 'ABSTAIN',
               'scope': 'MATCHED_STRUCTURE_HASH_NOT_CONVERGENCE_OR_SCIENTIFIC_VALIDATION'}
        OUT.write_text(json.dumps(out, indent=2, sort_keys=True, allow_nan=False) + '\n')
        print(len(rows), '/', len(p2), row['batch_id'], row['status'], flush=True)


if __name__ == '__main__':
    main()
