"""Real stdio process and hostile protocol boundary regressions."""
import json
from pathlib import Path

import pytest
from mcp import Client

from rhombus.evidence import (
    Applicability, DomainStatus, EvidenceRecord, OperationalStatus,
    ScientificVerdict, Uncertainty,
)
from rhombus.tools.evidence_query import list_tool_specs
from rhombus.tools.mcp_server import create_mcp_server
from scripts.tools import verify_mcp_stdio as v


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_real_stdio_historical_evidence_lifecycle():
    report = await v.verify_stdio()
    assert report['session_closed']
    assert report['metrics']['calls'] == 38
    assert report['metrics']['valid_calls'] == 15
    assert report['metrics']['expected_error_calls'] == 23
    assert len(report['catalog']) == 6
    assert len(report['provenance']['evidence_ids']) == 3
    assert report['provenance']['historical_sha256'] == v.HISTORY_SHA256
    assert not report['scientific_GO'] and not report['checkpoint_0196_consumed']
    assert report['agent_selection_accuracy'] is None
    successes = [c for c in report['calls'] if not c['is_error']]
    assert {c['tool'] for c in successes} == {t['function']['name'] for t in list_tool_specs()}
    assert all(c['response_bytes'] <= 128 * 1024 for c in report['calls'])
    assert all(c['response']['structuredContent']['claim_authorized'] is False for c in successes)
    assert any(c['case'] == 'corrupted_historical_snapshot' and c['is_error'] for c in report['calls'])


def test_host_export_rejects_historical_drift(tmp_path, monkeypatch):
    monkeypatch.setattr(v, 'HISTORY_SHA256', '0' * 64)
    with pytest.raises(ValueError, match='artifact drift'):
        v.prepare_inputs(tmp_path)
    assert not (tmp_path / 'historical.jsonl').exists()


def test_host_exports_preserve_ids_and_bytes(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    a = v.prepare_inputs(first)
    b = v.prepare_inputs(second)
    assert a[0].read_bytes() == b[0].read_bytes()
    assert a[3] == b[3]
    assert a[3]['structure_candidate_id'] == 'lialo2-gamma'
    assert not a[3]['structure_is_same_specimen_as_replay_candidate']


@pytest.mark.anyio
async def test_schema_is_exact_and_oversized_response_is_not_delivered(tmp_path):
    # Synthetic negative fixture: hash-valid oversized metadata must not reach AI.
    row = EvidenceRecord.create(
        candidate_id='oversize-negative-control', evidence_kind='SYNTHETIC_NEGATIVE_TEST',
        capability='validate_candidate_structure', operational_status=OperationalStatus.SUCCEEDED,
        scientific_verdict=ScientificVerdict.UNKNOWN,
        applicability=Applicability('structure', DomainStatus.UNQUALIFIED),
        uncertainty=Uncertainty(reason='x' * 100000), limitations=('SYNTHETIC_TEST_ONLY',),
    )
    path = tmp_path / 'negative.jsonl'
    path.write_text(json.dumps(row.to_dict()) + '\n')
    async with Client(create_mcp_server(path), raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        assert all(t.input_schema['additionalProperties'] is False for t in tools)
        result = await client.call_tool('get_candidate_evidence', {'candidate_id': row.candidate_id})
        assert result.is_error and 'output budget' in result.content[0].text
        assert len(result.model_dump_json()) < 1024


@pytest.mark.anyio
async def test_nested_types_and_unsupported_values_fail_before_core(tmp_path):
    snapshot, _, structure, _ = v.prepare_inputs(tmp_path)
    async with Client(create_mcp_server(snapshot), raise_exceptions=True) as client:
        for numbers in ([True], ['3'], [0], [119], []):
            reply = await client.call_tool('get_domain_assessment', {
                'candidate_id': 'lialo2-gamma', 'model_id': 'medium-mpa-0',
                'claim_kind': 'finite_temperature_stability', 'atomic_numbers': numbers})
            assert reply.is_error
        reply = await client.call_tool('validate_candidate_structure', {
            'candidate_id': 'lialo2-gamma', 'structure': {**structure, 'path': '/private/DO_NOT_READ'}})
        assert reply.is_error and '/private/DO_NOT_READ' not in reply.content[0].text
        reply = await client.call_tool('plan_scientific_task', {
            'candidate_id': 'a', 'capability': 'execute_shell',
            'evidence_manifest_id': 'manifest:sha256:' + 'f' * 64,
            'requested_backend': 'PAID_CLOUD', 'max_walltime_seconds': 1,
            'max_cpu_cores': 1, 'max_memory_mib': 256})
        assert reply.is_error
