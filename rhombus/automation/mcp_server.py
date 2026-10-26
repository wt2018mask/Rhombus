"""Optional automation-enabled MCP host; six existing tools remain compatible."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from rhombus.automation.controller import build_request
from rhombus.automation.ledger import GitHub, GitLedger, canonical


def create_server(snapshot, github):
    from mcp.types import ToolAnnotations
    from rhombus.tools import ReadOnlyEvidenceTools
    from rhombus.tools.mcp_server import create_mcp_server
    snapshot = Path(snapshot)
    snapshot.write_bytes(b'')
    specs = tuple({'type': 'function', 'function': {'name': name, 'parameters': {
        'type': 'object', 'properties': {}, 'additionalProperties': False}}}
        for name in ('request_approved_thermal_study', 'get_automated_thermal_evidence'))
    server = create_mcp_server(snapshot, additional_tool_specs=specs)

    @server.tool(name='request_approved_thermal_study',
                 annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True))
    def request_approved_thermal_study() -> dict:
        """Wake trusted main-branch policy controller for its one frozen CPU task.

        No code, policy, model, resource or source arguments are accepted.
        This requests reconciliation, and does not grant execution permission.
        """
        github.call('POST', '/actions/workflows/kaggle-thermal-controller.yml/dispatches',
                    {'ref': 'main', 'inputs': {'operation': 'reconcile'}})
        return {'task_id': build_request()['task_id'], 'state': 'RECONCILIATION_REQUESTED',
                'authorization': 'TRUSTED_CONTROLLER_POLICY_REQUIRED', 'scientific_result': 'NOT_ASSERTED'}

    @server.tool(name='get_automated_thermal_evidence', annotations=ToolAnnotations(read_only_hint=True))
    def get_automated_thermal_evidence() -> dict:
        """Fetch authenticated durable controller state and independently checked records.

        Also refreshes the evidence snapshot used by the six compatible tools.
        Provider observation time remains explicit; this is not live Kaggle polling.
        """
        revision, state = GitLedger(github).read()
        if state is None:
            return {'task_id': build_request()['task_id'], 'state': 'NOT_SUBMITTED', 'evidence_records': []}
        records = state.get('evidence_records', [])
        temporary = snapshot.with_suffix('.pending')
        temporary.write_bytes(b''.join(canonical(row) for row in records))
        reader = ReadOnlyEvidenceTools(temporary)
        for row in records:
            reader.call_tool('get_candidate_evidence', {'candidate_id': row['candidate_id']})
        temporary.replace(snapshot)
        return {'task_id': state['task_id'], 'state': state['state'], 'ledger_commit': revision,
                'last_provider_observation': state.get('observed_at'),
                'provider_run_id': state['provider_run_id'], 'archive': state.get('archive'),
                'evidence_records': records, 'qualification': 'ABSTAIN', 'conductivity_S_cm': None}

    return server


def main():
    github = GitHub('wt2018mask/Rhombus', os.environ.get('GH_TOKEN'))
    with tempfile.TemporaryDirectory(prefix='rhombus-mcp-') as directory:
        create_server(Path(directory) / 'evidence.jsonl', github).run(transport='stdio')


if __name__ == '__main__':
    main()
