"""Verify the existing MCP tools serve actual 0196 diagnostics conservatively."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import tempfile
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rhombus.tools.evidence_query import _verify_evidence_row

ROOT = Path(__file__).resolve().parents[2]
RESULT = 'data/development/process_choice_stability_0196_result_v1.json'
RESULT_SHA256 = 'ed1d3a3691d40aa8c8a25c073e701558152a39546bd8c93060838d07c0f04f7d'
PROTOCOL_SHA256 = '256d176c2e9f294fa99a144c89cc6e68be149be89f2ee5fcd14cc5220e72dcd2'


async def verify_computed_evidence():
    raw = (ROOT / RESULT).read_bytes()
    if hashlib.sha256(raw).hexdigest() != RESULT_SHA256:
        raise ValueError('scientific result artifact drift')
    result = json.loads(raw)
    assert result['protocol_sha256'] == PROTOCOL_SHA256
    protocol_path = ROOT / result['protocol_path']
    if hashlib.sha256(protocol_path.read_bytes()).hexdigest() != PROTOCOL_SHA256:
        raise ValueError('scientific protocol drift')
    code = ROOT / 'rhombus/qualification/process_choice_stability.py'
    if hashlib.sha256(code.read_bytes()).hexdigest() != result['computation_code_sha256']:
        raise ValueError('scientific computation code drift')
    records = result['evidence_records']
    for i, row in enumerate(records, 1):
        _verify_evidence_row(row, lineno=i)
    observations = []
    with tempfile.TemporaryDirectory(prefix='rhombus-computed-evidence-') as directory:
        snapshot = Path(directory) / 'evidence.jsonl'
        snapshot.write_text(''.join(json.dumps(row) + '\n' for row in records))
        original = snapshot.read_bytes()
        params = StdioServerParameters(command=sys.executable, cwd=ROOT,
            args=['-m', 'rhombus.tools.mcp_server', '--evidence-jsonl', str(snapshot)],
            env={'PYTHONDONTWRITEBYTECODE': '1'})
        with (Path(directory) / 'stderr.log').open('w') as err:
            async with stdio_client(params, errlog=err) as streams:
                async with ClientSession(*streams, read_timeout_seconds=20) as client:
                    initialization = await client.initialize()
                    tools = (await client.list_tools()).tools
                    assert len(tools) == 6
                    for row in records:
                        for name in ('get_candidate_evidence', 'build_evidence_manifest'):
                            started = time.perf_counter()
                            reply = await client.call_tool(name, {'candidate_id': row['candidate_id']})
                            seconds = time.perf_counter() - started
                            assert not reply.is_error
                            payload = reply.structured_content
                            assert payload['scientific_verdict'] == 'UNKNOWN' and not payload['claim_authorized']
                            if name == 'get_candidate_evidence':
                                delivered = payload['evidence_records'][0]
                                assert delivered['evidence_id'] == row['evidence_id']
                                assert delivered['evidence_kind'] == 'COMPUTED_PROCESS_SELECTION_SENSITIVITY'
                                assert delivered['scientific_verdict'] == 'INDETERMINATE'
                                assert delivered['applicability']['domain_status'] == 'UNQUALIFIED'
                                assert delivered['uncertainty'] == row['uncertainty']
                                assert delivered['source_bindings'] == row['source_bindings']
                                assert not delivered['uncertainty']['metrics']['independent_validation']
                            else:
                                assert payload['evidence_ids'] == [row['evidence_id']]
                            observations.append({'tool': name, 'candidate_id': row['candidate_id'],
                                'invocation_seconds': seconds,
                                'normalized_response_bytes': len(reply.model_dump_json(by_alias=True).encode()),
                                'response': reply.model_dump(mode='json', by_alias=True)})
        assert snapshot.read_bytes() == original
    return {'schema_version': 'rhombus-computed-evidence-mcp-integration-v1',
        'science_artifact': RESULT, 'science_artifact_sha256': RESULT_SHA256,
        'science_protocol_sha256': PROTOCOL_SHA256, 'evidence_ids': [r['evidence_id'] for r in records],
        'client': 'official MCP SDK stdio subprocess', 'mcp_version': importlib.metadata.version('mcp'),
        'protocol_version': initialization.protocol_version, 'tool_count': len(tools),
        'calls': observations, 'session_closed': True, 'server_changed': False,
        'scientific_result': result['findings'], 'scientific_GO': False, 'production_enabled': False,
        'new_original_bytes': 0, 'TEST121_accessed': False, 'compute_dispatch_from_MCP': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('prior observations are immutable; choose new output')
    result = asyncio.run(verify_computed_evidence())
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'tool_count': result['tool_count'], 'calls': len(result['calls']),
                      'session_closed': result['session_closed'], 'scientific_GO': False}))


if __name__ == '__main__':
    main()
