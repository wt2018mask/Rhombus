"""Compare retained structures and dynamic lineage without equating their claims."""
import hashlib
import json
from pathlib import Path


def _digest_structure(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def compare_retained_records(root, audit):
    root = Path(root)
    receipts = {}
    for path in sorted((root / 'data/benchmarks/known_material/receipts/artifacts').glob('*.json')):
        data = json.loads(path.read_text())
        receipts[data.get('retained_path')] = data
    known, batches = [], []
    for row in audit['results']:
        source = row['path']
        receipt = receipts.get(source)
        if receipt:
            digest = hashlib.sha256((root / source).read_bytes()).hexdigest()
            known.append({'path': source, 'material_key': receipt.get('material_key'),
                'file_sha256': digest, 'receipt_sha256': receipt.get('artifact_sha256'),
                'receipt_matches': digest == receipt.get('artifact_sha256'),
                'host_channel_barrier_3d_ev': row.get('host_channel_barrier_3d_ev'),
                'scope': 'SOURCE_BYTES_ONLY_NO_DYNAMIC_CONCORDANCE'})
        if row['category'] != 'ORDERED_EXPANSION_OR_BATCH_CANDIDATE':
            continue
        batch_id = Path(source).stem
        related = audit['related_records'].get(batch_id, [])
        if not related:
            continue
        record = json.loads((root / source).read_text())
        raw_hash = _digest_structure(record['structure_dict'])
        p1 = record.get('result') or {}
        relaxed = p1.get('relaxed_structure_dict')
        relaxed_hash = _digest_structure(relaxed) if relaxed else None
        p2 = [entry for entry in related if entry['fields'].get('p2_input_relaxed_sha256')]
        batches.append({'batch_id': batch_id, 'static_input_hash': raw_hash,
            'p1_input_hash': p1.get('input_structure_sha256'),
            'p1_input_matches': raw_hash == p1.get('input_structure_sha256') if p1 else None,
            'p1_relaxed_hash': relaxed_hash,
            'p1_relaxed_hash_matches': relaxed_hash == p1.get('relaxed_structure_sha256') if relaxed else None,
            'static_equals_relaxed': raw_hash == relaxed_hash if relaxed else None,
            'p2': [{'path': e['path'], 'input_hash': e['fields']['p2_input_relaxed_sha256'],
                    'matches_p1_relaxed': relaxed_hash == e['fields']['p2_input_relaxed_sha256'] if relaxed else None,
                    'temperature_K': e['fields'].get('temperature_K'), 'verdict': e['fields'].get('p2_verdict')}
                   for e in p2],
            'channel_ev': row.get('host_channel_barrier_3d_ev'),
            'scope': 'LINEAGE_CHECK_NOT_EMPIRICAL_CONCORDANCE'})
    return {'known_material': known, 'batch_records': batches}
