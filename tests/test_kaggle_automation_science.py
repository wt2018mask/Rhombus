"""Synthetic scientific bytes, genuine verifier and MCP transport; no MLIP run."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

from tests.test_kaggle_thermal_0201 import synthetic_remote
from rhombus.automation.controller import build_request
from rhombus.automation.ledger import canonical, digest
from rhombus.automation.verify import verify_results


def test_worker_rejects_mismatched_checkout_before_source_use(monkeypatch, tmp_path):
    from rhombus.automation import worker
    monkeypatch.setattr(worker.subprocess, 'check_output', lambda *args, **kwargs: 'b' * 40 + '\n')
    with pytest.raises(RuntimeError, match='Source commit mismatch'):
        worker.verify_checkout_revision(tmp_path, 'a' * 40)
    worker.verify_checkout_revision(tmp_path, 'b' * 40)


@pytest.fixture
def automatic_result(synthetic_remote):
    directory, old_request, manifest, observation, _ = synthetic_remote
    request = build_request()
    manifest.update(task_id=request['task_id'], request_sha256=digest(request),
        job_id='synthetic/NOT-A-KAGGLE-RUN/1', qualification='ABSTAIN', conductivity_S_cm=None,
        execution_origin={'mode': 'POLICY_AUTOMATION', 'provider_attestation': 'SYNTHETIC_NOT_KAGGLE'})
    run = manifest['runs'][0]
    run['binding'].update(task_id=request['task_id'], source_commit=request['task']['code_revision'])
    trace_path = directory / run['trace']['path']
    trace = json.loads(trace_path.read_bytes())
    trace['binding'] = run['binding']
    trace_path.unlink()
    raw = canonical(trace)
    checksum = hashlib.sha256(raw).hexdigest()
    (directory / (checksum + '.thermal.json')).write_bytes(raw)
    run['trace'] = {'path': checksum + '.thermal.json', 'sha256': checksum, 'size_bytes': len(raw)}
    manifest['files'] = {path.name: {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}
                         for path in directory.iterdir() if path.name != 'manifest.json'}
    (directory / 'manifest.json').write_bytes(canonical(manifest))
    state = {'task_id': request['task_id'], 'provider_run_id': manifest['job_id'], 'request_sha256': digest(request),
             'policy_sha256': 'a' * 64, 'provider_origin_binding': 'SYNTHETIC_NOT_KAGGLE'}
    retrieval = {'provider_run_id': manifest['job_id'],
                 'files': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in directory.iterdir()}}
    return directory, request, state, retrieval


def test_independent_science_and_existing_evidence_interface(automatic_result):
    from rhombus.tools import ReadOnlyEvidenceTools
    directory, request, state, retrieval = automatic_result
    report = verify_results(directory, request, state, retrieval)
    assert report['state'] == 'SCIENTIFICALLY_INDETERMINATE'
    assert report['numerical_verification']['runs'][0]['temp_mean_K'] == pytest.approx(571.)
    assert report['numerical_verification']['operational_status'] == 'PARTIAL'
    assert report['evidence_records'][0]['operational_status'] == 'ERROR'
    assert report['evidence_records'][0]['payload']['remote_workload_status'] == 'PARTIAL'
    assert report['conductivity_S_cm'] is None
    snapshot = directory.parent / 'evidence.jsonl'
    snapshot.write_bytes(b''.join(canonical(row) for row in report['evidence_records']))
    result = ReadOnlyEvidenceTools(snapshot).call_tool('get_candidate_evidence', {'candidate_id': 'lialo2-gamma'})
    assert result['claim_authorized'] is False
    assert result['evidence_records'][0]['scientific_verdict'] == 'INDETERMINATE'


@pytest.mark.parametrize('attack', ['missing', 'corrupt', 'wrong_job', 'partial_download', 'false_summary', 'fake_conductivity'])
def test_bad_results_are_not_registered(automatic_result, attack):
    directory, request, state, retrieval = automatic_result
    if attack in ('missing', 'partial_download'):
        path = next(directory.glob('*.npz'))
        if attack == 'missing':
            path.unlink()
        else:
            path.write_bytes(path.read_bytes()[:100])
    elif attack == 'corrupt':
        next(directory.glob('*.thermal.json')).write_text('{}')
    elif attack == 'wrong_job':
        state['provider_run_id'] = 'synthetic/WRONG/1'
    else:
        manifest = json.loads((directory / 'manifest.json').read_bytes())
        if attack == 'false_summary':
            manifest['runs'][0]['P2']['thermal_metrics']['temp_mean_K'] = 999
        else:
            manifest['conductivity_S_cm'] = 42
        (directory / 'manifest.json').write_bytes(canonical(manifest))
        retrieval['files']['manifest.json'] = hashlib.sha256((directory / 'manifest.json').read_bytes()).hexdigest()
    with pytest.raises((ValueError, RuntimeError)):
        verify_results(directory, request, state, retrieval)


def test_complete_manifest_cannot_hide_partial_verified_run(automatic_result, monkeypatch):
    import rhombus.atomistics.thermal_study as thermal_study
    directory, request, state, retrieval = automatic_result
    manifest = json.loads((directory / 'manifest.json').read_bytes())
    manifest['status'] = 'COMPLETE'
    (directory / 'manifest.json').write_bytes(canonical(manifest))
    retrieval['files']['manifest.json'] = hashlib.sha256((directory / 'manifest.json').read_bytes()).hexdigest()
    monkeypatch.setattr(thermal_study, 'verify_thermal_result_artifacts',
                        lambda *args, **kwargs: {'operational_status': 'COMPLETE',
                                                 'runs': [{'operational_status': 'PARTIAL'}]})
    with pytest.raises(RuntimeError, match='INCOMPLETE_RUN_IN_COMPLETE_WORKLOAD'):
        verify_results(directory, request, state, retrieval)


def test_verified_records_via_real_mcp_stdio(automatic_result):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    directory, request, state, retrieval = automatic_result
    report = verify_results(directory, request, state, retrieval)
    snapshot = directory.parent / 'evidence.jsonl'
    snapshot.write_bytes(b''.join(canonical(row) for row in report['evidence_records']))
    async def inspect():
        parameters = StdioServerParameters(command=sys.executable,
            args=['-m', 'rhombus.tools.mcp_server', '--evidence-jsonl', str(snapshot)],
            cwd=Path(__file__).resolve().parents[1])
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams) as client:
                await client.initialize()
                assert len((await client.list_tools()).tools) == 6
                result = await client.call_tool('get_candidate_evidence', {'candidate_id': 'lialo2-gamma'})
                value = result.model_dump(mode='json', by_alias=True)
                assert not value['isError']
                assert value['structuredContent']['evidence_records'][0]['evidence_id'] == report['evidence_records'][0]['evidence_id']
                assert value['structuredContent']['claim_authorized'] is False
    asyncio.run(inspect())
