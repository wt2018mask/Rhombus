"""Summarize exact-structure observations, keeping path-linked P2.5 separate."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'data/benchmarks/v3_static'


def main():
    paths = [BASE / 'same_hash_all_records_v1.json', BASE / 'same_hash_relaxed_only_v1.json']
    rows = [row for p in paths for row in json.loads(p.read_text())['rows']]
    refs = defaultdict(list)
    for folder in sorted((ROOT / 'data/batches').glob('p25*')):
        for path in sorted(folder.rglob('*.json')):
            try:
                data = json.loads(path.read_text()); value = data.get('result') or {}
                source = (value.get('provenance') or {}).get('p2_result_path')
                if not source: continue
                refs[source.replace('\\', '/')].append({'path': str(path.relative_to(ROOT)),
                    'p25_verdict': value.get('p25_verdict'), 'transport_state': value.get('transport_state'),
                    'temperature_K': value.get('temperature_K'), 'link_scope': 'PROVENANCE_PATH_NOT_CONTENT_HASH'})
            except (ValueError, TypeError, OSError): continue
    for row in rows:
        row['p25_records'] = [r for p2 in row['p2_records'] for r in refs.get(p2['path'], [])]
    eligible = []
    for row in rows:
        outcomes = {p['p2_verdict'] for p in row['p2_records']}
        if row['status'] == 'COMPUTED_UNQUALIFIED' and outcomes in ({'PASS'}, {'FAIL'}):
            eligible.append((row, int('PASS' in outcomes)))
    correlations = {}
    for name, values in [('channel', [r['relaxed']['host_channel_barrier_3d_ev'] for r, _ in eligible]),
                         ('radius', [r['geometric']['radius_A'] for r, _ in eligible])]:
        if len(set(values)) > 1 and len({v for _, v in eligible}) > 1:
            s = spearmanr(values, [v for _, v in eligible])
            correlations[name] = {'rho': float(s.statistic), 'p_value': float(s.pvalue), 'n': len(eligible)}
    out = {'schema': 'same-hash-full-comparison-v1', 'rows': rows,
           'input_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
           'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'p2_record_counts': dict(Counter(str(p['p2_verdict']) for r in rows for p in r['p2_records'])),
           'p2_completion_counts': dict(Counter(str((p['termination'] or {}).get('completed')) for r in rows for p in r['p2_records'])),
           'exploratory_spearman_p2_pass_vs_fail': correlations, 'qualification': 'ABSTAIN'}
    (BASE / 'same_hash_full_comparison_v1.json').write_text(json.dumps(out, indent=2, sort_keys=True, allow_nan=False) + '\n')


if __name__ == '__main__': main()
