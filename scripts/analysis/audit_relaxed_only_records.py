"""Assess hash-verified P2 inputs whose P1 input binding was not verified."""
import hashlib
import json
from pathlib import Path
from pymatgen.core import Structure
from rhombus.transport.cohort_audit import assess, geometric_percolation_radius
from rhombus.transport.cohort_evidence import _digest_structure
from scripts.analysis.audit_same_hash_records import collect, ROOT


def main():
    strict, _ = collect(); relaxed = {}; p2 = {}
    for folder in sorted((ROOT / 'data/batches').glob('done*')):
        for path in sorted(folder.rglob('*.json')):
            try:
                data = json.loads(path.read_text()); result = data.get('result') or {}; structure = result.get('relaxed_structure_dict')
                if structure and _digest_structure(structure) == result.get('relaxed_structure_sha256'):
                    relaxed.setdefault(result['relaxed_structure_sha256'], (path, data))
            except (ValueError, TypeError, OSError):
                continue
    for folder in sorted((ROOT / 'data/batches').glob('p2*')):
        if folder.name.startswith('p25'): continue
        for path in sorted(folder.rglob('*.json')):
            try:
                data = json.loads(path.read_text()); result = data.get('result') or {}; h = result.get('p2_input_relaxed_sha256')
                if h in relaxed and h not in strict:
                    p2.setdefault(h, []).append((path, data))
            except (ValueError, TypeError, OSError):
                continue
    rows = []
    for h in sorted(p2):
        path, data = relaxed[h]; result = data['result']; s = Structure.from_dict(result['relaxed_structure_dict'])
        row = {'batch_id': data.get('batch_id'), 'p1_path': str(path.relative_to(ROOT)), 'relaxed_sha256': h,
               'unrelaxed_status': 'INPUT_BINDING_NOT_VERIFIED', 'p2_records': []}
        for pp, record in p2[h]:
            v = record['result']; row['p2_records'].append({'path': str(pp.relative_to(ROOT)),
                'temperature_K': v.get('temperature_K'), 'p2_verdict': v.get('p2_verdict'),
                'termination': v.get('termination'), 'production_steps_completed': v.get('production_steps_completed'),
                'mobile_ion_metrics': v.get('mobile_ion_metrics')})
        try:
            row.update(formula=s.composition.reduced_formula,
                relaxed=assess({'path': row['p1_path'], 'category': 'ORDERED_EXPANSION_OR_BATCH_CANDIDATE',
                    'structure_sha256': h, 'structure': s, 'defect': {}}),
                geometric=geometric_percolation_radius(s), status='COMPUTED_UNQUALIFIED')
        except Exception as e:
            row.update(status='FAILED', error=repr(e))
        rows.append(row); print(len(rows), '/', len(p2), row['batch_id'], row['status'], flush=True)
    out = {'schema': 'same-hash-relaxed-only-v1', 'source_commit': '3516cb69fbac1ef0f612e8e3f97954ddf9e230e1',
           'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'rows': rows,
           'qualification': 'ABSTAIN'}
    (ROOT / 'data/benchmarks/v3_static/same_hash_relaxed_only_v1.json').write_text(json.dumps(out, indent=2, sort_keys=True, allow_nan=False) + '\n')


if __name__ == '__main__': main()
