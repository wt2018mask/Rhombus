import json
from pathlib import Path

from rhombus.transport.cohort_evidence import compare_retained_records


def test_known_cif_receipt_and_batch_lineage():
    root = Path(__file__).resolve().parents[1]
    audit = json.loads((root / 'data/benchmarks/v3_static/repository_cohort_audit_v2.json').read_text())
    result = compare_retained_records(root, audit)
    assert result['known_material']
    assert all(item['receipt_matches'] for item in result['known_material'])
    candidate = next(x for x in result['batch_records'] if x['batch_id'] == '01f918b78d8fdc12')
    assert candidate['p1_input_matches'] and candidate['p1_relaxed_hash_matches']
    assert candidate['static_equals_relaxed'] is False
    assert all(x['matches_p1_relaxed'] for x in candidate['p2'])
