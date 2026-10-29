from scripts.analysis.audit_same_hash_records import collect
from rhombus.transport.cohort_evidence import _digest_structure
import json
from pathlib import Path


def test_inventory_requires_recomputed_relaxed_hash():
    p1, p2 = collect()
    assert p2
    for digest, records in p2.items():
        assert digest in p1
        for _, record in p1[digest]:
            assert _digest_structure(record['result']['relaxed_structure_dict']) == digest
        for _, record in records:
            assert record['result']['p2_input_relaxed_sha256'] == digest


def test_recorded_unrelaxed_hash_is_not_relaxed_hash():
    root = Path(__file__).resolve().parents[1]
    report = json.loads((root / 'data/benchmarks/v3_static/same_hash_all_records_v1.json').read_text())
    for row in report['rows']:
        data = json.loads((root / row['p1_path']).read_text())
        assert row['unrelaxed']['structure_sha256'] == _digest_structure(data['structure_dict'])
        assert row['relaxed']['structure_sha256'] == _digest_structure(data['result']['relaxed_structure_dict'])
