"""Real SDK stdio lifecycle on immutable historical evidence; no scientific dispatch."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import warnings

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rhombus.tools.evidence_query import _verify_evidence_row, list_tool_specs

ROOT = Path(__file__).resolve().parents[2]
HISTORY = 'data/development/adaptive_evidence_replay_0195_v1.json'
HISTORY_SHA256 = '5605d2f604fc2a44c0409d0f8b1dd4bdff7ad1f600f439fddd7c7ccdcc10e73c'
MODEL = 'data/benchmarks/known_material/model_domains/medium-mpa-0-domain-v1.json'
STRUCTURE_RECEIPT = 'data/benchmarks/known_material/receipts/artifacts/reference-structure-lialo2-gamma-cod-1008166-latest-freeze-v1.json'
EVALUATION_REQUESTS = [
    ('Retrieve existing O_ONLY candidate evidence.', 'retrieve_existing_evidence'),
    ('Explain why a candidate without retained evidence cannot qualify.', 'explain_missing_evidence'),
    ('Check model applicability without treating element coverage as qualification.', 'check_model_applicability'),
    ('Validate the retained LiAlO2 representation without claiming stability.', 'validate_retained_structure'),
    ('Construct a source-bound evidence manifest.', 'construct_manifest'),
    ('Propose a calculation under an explicit free CPU budget.', 'propose_bounded_calculation'),
    ('Retrieve the host snapshot status of that proposal.', 'retrieve_proposal_status'),
]
# Instrument the real child interpreter, not a replacement server or transport.
GUARD = '''import sys, os
sys.dont_write_bytecode = True
def guard(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.remove", "os.rename", "os.mkdir", "os.rmdir"}:
        raise PermissionError("MCP child attempted forbidden side effect")
    if event == "open" and not isinstance(args[0], int) and args[0] != "/dev/null":
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise PermissionError("MCP child attempted filesystem write")
sys.addaudithook(guard)
'''


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def prepare_inputs(directory):
    """Host-only export, with content IDs and historical receipt hashes verified."""
    raw = (ROOT / HISTORY).read_bytes()
    if sha(raw) != HISTORY_SHA256:
        raise ValueError('historical evidence artifact drift')
    rows = json.loads(raw)['evidence_records']
    source_receipts = {}
    ids = set()
    for index, row in enumerate(rows, 1):
        _verify_evidence_row(row, lineno=index)
        if row['evidence_id'] in ids:
            raise ValueError('duplicate historical evidence')
        ids.add(row['evidence_id'])
        provenance = row['provenance']
        path = provenance['receipt_path']
        if sha((ROOT / path).read_bytes()) != provenance['receipt_sha256']:
            raise ValueError('historical source receipt drift')
        if not row['source_bindings'] or not all(s['sha256'] for s in row['source_bindings']):
            raise ValueError('historical source identity missing')
        source_receipts[path] = provenance['receipt_sha256']
    snapshot = directory / 'historical.jsonl'
    snapshot.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))
    status = directory / 'status.jsonl'
    status.write_text('')  # No execution receipt invented for a new proposal.
    receipt = json.loads((ROOT / STRUCTURE_RECEIPT).read_text())
    structure_path = ROOT / receipt['retained_path']
    if sha(structure_path.read_bytes()) != receipt['artifact_sha256']:
        raise ValueError('retained structure source drift')
    from ase.io import read
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        atoms = read(structure_path)
    structure = {'lattice_vectors_angstrom': atoms.cell.array.tolist(),
                 'atomic_numbers': atoms.numbers.tolist(),
                 'fractional_coords': atoms.get_scaled_positions().tolist()}
    return snapshot, status, structure, {
        'historical_artifact': HISTORY, 'historical_sha256': HISTORY_SHA256,
        'snapshot_sha256': sha(snapshot.read_bytes()), 'evidence_ids': sorted(ids),
        'source_receipts': source_receipts, 'structure_receipt': STRUCTURE_RECEIPT,
        'structure_sha256': receipt['artifact_sha256'],
        'structure_candidate_id': receipt['material_key'],
        'structure_is_same_specimen_as_replay_candidate': False,
        'original_source_authentication': 'HISTORICAL_NOT_FRESH',
    }


async def verify_stdio():
    calls = []
    with tempfile.TemporaryDirectory(prefix='rhombus-real-mcp-') as tmp:
        directory = Path(tmp)
        snapshot, status, structure, provenance = prepare_inputs(directory)
        (directory / 'sitecustomize.py').write_text(GUARD)
        initial_bytes = snapshot.read_bytes()
        descriptor, stderr_name = tempfile.mkstemp(prefix='rhombus-mcp-stderr-', suffix='.log')
        os.close(descriptor)
        stderr_path = Path(stderr_name)
        params = StdioServerParameters(command=sys.executable, cwd=ROOT,
            args=['-m', 'rhombus.tools.mcp_server', '--evidence-jsonl', str(snapshot),
                  '--model-domain-snapshot', str(ROOT / MODEL), '--task-status-jsonl', str(status)],
            env={'PYTHONPATH': str(directory) + ':' + str(ROOT), 'PYTHONDONTWRITEBYTECODE': '1'})
        start = time.perf_counter()
        with stderr_path.open('w') as err:
            async with stdio_client(params, errlog=err) as streams:
                async with ClientSession(*streams, read_timeout_seconds=20) as client:
                    initialization = await client.initialize()
                    initialization_seconds = time.perf_counter() - start
                    tools = (await client.list_tools()).tools
                    catalog = {s['function']['name']: s['function']['parameters'] for s in list_tool_specs()}
                    assert [t.name for t in tools] == list(catalog)
                    assert all(t.input_schema == catalog[t.name] for t in tools)
                    assert all(t.annotations.read_only_hint and not t.annotations.open_world_hint for t in tools)

                    async def call(case, name, arguments, *, error=False):
                        before = time.perf_counter()
                        reply = await client.call_tool(name, arguments)
                        duration = time.perf_counter() - before
                        assert bool(reply.is_error) == error, (case, reply)
                        raw = reply.model_dump_json(by_alias=True).encode()
                        assert len(raw) <= 128 * 1024
                        payload = reply.structured_content
                        if not error:
                            assert payload['operational_status'] == 'SUCCEEDED'
                            assert payload['scientific_verdict'] == 'UNKNOWN'
                            assert payload['claim_authorized'] is False
                        input_raw = json.dumps(arguments).encode()
                        retained_arguments = arguments if len(input_raw) <= 8192 else {
                            'oversize_input_sha256': sha(input_raw), 'input_bytes': len(input_raw)}
                        calls.append({'case': case, 'tool': name, 'arguments': retained_arguments,
                            'is_error': bool(reply.is_error), 'invocation_seconds': duration,
                            'input_argument_bytes': len(input_raw),
                            'response_bytes': len(raw), 'estimated_output_tokens_bytes_div4': math.ceil(len(raw) / 4),
                            'response': reply.model_dump(mode='json', by_alias=True)})
                        return payload

                    candidate = '10.1039/c8ra01329b'
                    evidence_args = {'candidate_id': candidate}
                    evidence = await call('retrieve_existing_evidence', 'get_candidate_evidence', evidence_args)
                    assert evidence['evidence_count'] == 1
                    assert evidence['evidence_records'][0]['evidence_id'] in provenance['evidence_ids']
                    assert evidence['evidence_records'][0]['scientific_verdict'] == 'INDETERMINATE'
                    await call('explain_missing_evidence', 'get_candidate_evidence', {'candidate_id': 'unknown-candidate'})
                    domain_args = {'candidate_id': 'lialo2-gamma', 'model_id': 'medium-mpa-0',
                                   'claim_kind': 'finite_temperature_stability', 'atomic_numbers': sorted(set(structure['atomic_numbers']))}
                    domain = await call('check_model_applicability', 'get_domain_assessment', domain_args)
                    assert domain['domain_status'] == 'UNQUALIFIED'
                    structure_args = {'candidate_id': 'lialo2-gamma', 'structure': structure}
                    geom = await call('validate_retained_structure', 'validate_candidate_structure', structure_args)
                    assert geom['representation_status'] == 'VALID_REPRESENTATION'
                    manifest_args = {'candidate_id': candidate}
                    manifest = await call('construct_manifest', 'build_evidence_manifest', manifest_args)
                    assert manifest['evidence_ids'] == [evidence['evidence_records'][0]['evidence_id']]
                    proposal_args = {'candidate_id': candidate, 'capability': 'relax_structure',
                        'evidence_manifest_id': manifest['manifest_id'], 'requested_backend': 'LOCAL_CPU',
                        'max_walltime_seconds': 60, 'max_cpu_cores': 1, 'max_memory_mib': 512}
                    proposal = await call('propose_bounded_calculation', 'plan_scientific_task', proposal_args)
                    assert proposal['dispatch_status'] == 'NOT_SUBMITTED' and not proposal['execution_authorized']
                    assert not proposal['evidence_manifest_id_verified']
                    status_args = {'proposal_id': proposal['proposal_id']}
                    task_status = await call('retrieve_proposal_status', 'get_task_status', status_args)
                    assert task_status['task_state'] == 'UNKNOWN'
                    assert task_status['status_freshness'] == 'HOST_SNAPSHOT_ONLY_NOT_LIVE'
                    valid = {'get_candidate_evidence': evidence_args, 'get_domain_assessment': domain_args,
                             'validate_candidate_structure': structure_args, 'build_evidence_manifest': manifest_args,
                             'plan_scientific_task': proposal_args, 'get_task_status': status_args}
                    expected = [evidence, domain, geom, manifest, proposal, task_status]
                    for (name, arguments), previous in zip(valid.items(), expected):
                        assert await call('repeat_identity_' + name, name, arguments) == previous
                        await call('missing_input_' + name, name, {}, error=True)
                        key = next(iter(arguments))
                        await call('wrong_type_' + name, name, {**arguments, key: False}, error=True)
                        await call('forbidden_extra_' + name, name,
                                   {**arguments, 'command': 'DO_NOT_EXECUTE'}, error=True)
                    for value in (True, '1'):
                        await call('reject_coercion_' + str(value), 'get_candidate_evidence',
                                   {**evidence_args, 'max_records': value}, error=True)
                    await call('unavailable_tool', 'execute_scientific_task', {}, error=True)
                    await call('unbounded_input', 'validate_candidate_structure',
                               {**structure_args, 'padding': 'x' * 131073}, error=True)
                    await call('forged_manifest_still_untrusted', 'plan_scientific_task',
                               {**proposal_args, 'evidence_manifest_id': 'manifest:sha256:' + 'f' * 64})
                    # Host evidence corruption is a negative test only, never a real scientific observation.
                    damaged = json.loads(initial_bytes.splitlines()[0])
                    damaged['scientific_verdict'] = 'PASS'
                    snapshot.write_text(json.dumps(damaged) + '\n')
                    await call('corrupted_historical_snapshot', 'get_candidate_evidence', evidence_args, error=True)
                    snapshot.write_bytes(initial_bytes)
                    await call('host_snapshot_restored', 'get_candidate_evidence', evidence_args)
        assert snapshot.read_bytes() == initial_bytes and status.read_bytes() == b''
        assert 'MCP child attempted' not in stderr_path.read_text()
        closed_seconds = time.perf_counter() - start
    return {'schema_version': 'rhombus-real-mcp-stdio-e2e-v1',
        'implementation_sha256': {path: sha((ROOT / path).read_bytes()) for path in (
            'rhombus/tools/mcp_server.py', 'scripts/tools/verify_mcp_stdio.py')},
        'client': 'mcp.ClientSession + mcp.client.stdio.stdio_client',
        'mcp_sdk_version': importlib.metadata.version('mcp'), 'python_version': sys.version.split()[0],
        'initialization': initialization.model_dump(mode='json', by_alias=True),
        'initialization_seconds': initialization_seconds, 'session_closed': True,
        'total_lifecycle_seconds': closed_seconds, 'catalog': [t.model_dump(mode='json', by_alias=True) for t in tools],
        'provenance': provenance, 'calls': calls,
        'metrics': {'calls': len(calls), 'valid_calls': sum(not c['is_error'] for c in calls),
                    'expected_error_calls': sum(c['is_error'] for c in calls),
                    'maximum_response_bytes': max(c['response_bytes'] for c in calls),
                    'minimum_invocation_seconds': min(c['invocation_seconds'] for c in calls),
                    'maximum_invocation_seconds': max(c['invocation_seconds'] for c in calls)},
        'performance_limits': 'Single sequential local session, warm calls after startup; no savings claim. response_bytes measures SDK-normalized CallToolResult JSON UTF-8, excluding JSON-RPC framing. Bytes/4 is a heuristic, not tokenizer measurement.',
        'catalog_bytes': len(json.dumps([t.model_dump(mode='json', by_alias=True) for t in tools]).encode()),
        'agent_selection_accuracy': None, 'model_driven_client': 'NOT_RUN',
        'fixed_research_requests': [{'request': prompt, 'observed_call_case': case}
                                    for prompt, case in EVALUATION_REQUESTS],
        'guards': {'child_network_and_process_dispatch': 'DENIED_BY_PYTHON_AUDIT_HOOK',
                   'child_filesystem_writes': 'DENIED_BY_PYTHON_AUDIT_HOOK', 'host_snapshot_restored': True},
        'scientific_GO': False, 'production_enabled': False, 'TEST121_accessed': False,
        'new_authenticated_scientific_facts': 0, 'checkpoint_0196_consumed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; preserve prior observations')
    report = asyncio.run(verify_stdio())
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['metrics']))


if __name__ == '__main__':
    main()
