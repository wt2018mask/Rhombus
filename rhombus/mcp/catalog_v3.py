"""Host-pinned portfolio tools: no agent-controlled code, paths or dispatch."""
import hashlib
import json
from pathlib import Path
from typing import Any

from rhombus.automation.campaign_worker_v3 import canonical


def build_portfolio_catalog(candidates, dossiers=()):
    if len(candidates) > 32 or len(dossiers) > 32:
        raise ValueError('bounded portfolio required')
    ids = [c['candidate_id'] for c in candidates]
    if len(ids) != len(set(ids)) or any(d['candidate']['candidate_id'] not in ids for d in dossiers):
        raise ValueError('unique candidate identities required')
    if len({d['candidate']['candidate_id'] for d in dossiers}) != len(dossiers):
        raise ValueError('duplicate candidate dossiers')
    for dossier in dossiers:
        body = {k:v for k,v in dossier.items() if k != 'dossier_sha256'}
        raw = json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if hashlib.sha256(raw).hexdigest() != dossier['dossier_sha256']:
            raise ValueError('dossier content mismatch')
    content = {'schema_version': 'rhombus-portfolio-v3', 'candidates': candidates,
               'dossiers': {d['candidate']['candidate_id']: d for d in dossiers},
               'qualification': 'ABSTAIN', 'remote_execution_authorized': False}
    return dict(content, catalog_sha256=hashlib.sha256(canonical(content)).hexdigest())


def _summary(row):
    return {k: row.get(k) for k in ('candidate_id', 'domain', 'template_id', 'origin', 'selection_utility', 'qualification')}


def create_server(evidence_snapshot, *, portfolio_path, expected_sha256, github=None,
                  audit_path=None, expected_audit_sha256=None):
    """6+3 tools, or existing 8 automation tools +3 when host supplies github.

    Generate/evaluate tool names expose host-prepared proposals/dossiers only.
    Repeated unprivileged calls cannot start static, MLIP, MD or provider work.
    """
    from mcp.types import ToolAnnotations
    from rhombus.tools.mcp_server import create_mcp_server
    path = Path(portfolio_path)
    if path.is_symlink() or path.stat().st_size > 4*1024*1024:
        raise ValueError('unsafe portfolio snapshot')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('host-pinned catalog file mismatch')
    catalog = json.loads(raw)
    payload = {k: v for k, v in catalog.items() if k != 'catalog_sha256'}
    if hashlib.sha256(canonical(payload)).hexdigest() != catalog['catalog_sha256']:
        raise ValueError('catalog content digest mismatch')
    if catalog['qualification'] != 'ABSTAIN' or catalog['remote_execution_authorized'] is not False:
        raise ValueError('catalog cannot authorize execution')
    audit_rows = None
    if audit_path is not None:
        audit_file = Path(audit_path)
        if audit_file.is_symlink() or audit_file.stat().st_size > 4*1024*1024:
            raise ValueError('unsafe audit snapshot')
        audit_raw = audit_file.read_bytes()
        if not expected_audit_sha256 or hashlib.sha256(audit_raw).hexdigest() != expected_audit_sha256:
            raise ValueError('host-pinned audit file mismatch')
        audit = json.loads(audit_raw)
        if audit.get('qualification') != 'ABSTAIN' or not isinstance(audit.get('rows'), list) or len(audit['rows']) > 1000:
            raise ValueError('invalid audit snapshot')
        audit_rows = {}
        for row in audit['rows']:
            key = row.get('relaxed_sha256')
            if not isinstance(key, str) or len(key) != 64 or key in audit_rows:
                raise ValueError('invalid or duplicate audit structure hash')
            audit_rows[key] = row
    elif expected_audit_sha256 is not None:
        raise ValueError('audit snapshot path required')
    domain = {'type': 'string', 'enum': ['O_ONLY', 'S_ONLY', 'HALIDE']}
    specs = []
    for name in ('generate_candidates_v3', 'evaluate_funnel_v3', 'query_portfolio_catalog_v3'):
        if name == 'evaluate_funnel_v3':
            props = {'candidate_id': {'type': 'string', 'minLength': 1, 'maxLength': 256}}
            required = ['candidate_id']
        else:
            props = {'domain': domain, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 10}}
            required = []
        specs.append({'type': 'function', 'function': {'name': name, 'parameters': {
            'type': 'object', 'properties': props, 'required': required, 'additionalProperties': False}}})
    if audit_rows is not None:
        specs.append({'type': 'function', 'function': {'name': 'synthesize_scientific_opinion_v3', 'parameters': {
            'type': 'object', 'properties': {'relaxed_sha256': {'type': 'string', 'minLength': 64, 'maxLength': 64}},
            'required': ['relaxed_sha256'], 'additionalProperties': False}}})
    if github is None:
        server = create_mcp_server(Path(evidence_snapshot), additional_tool_specs=tuple(specs))
    else:
        from rhombus.automation.mcp_server import create_server as automation_server
        server = automation_server(evidence_snapshot, github)
        server.additional_tool_specs += tuple(specs)
    readonly = ToolAnnotations(read_only_hint=True, open_world_hint=False)

    def selected(domain, limit):
        return [_summary(c) for c in catalog['candidates'] if domain is None or c['domain'] == domain][:limit]

    @server.tool(name='generate_candidates_v3', annotations=readonly)
    def generate_candidates_v3(domain: str | None = None, limit: int = 3) -> dict[str, Any]:
        """Retrieve bounded proposals already generated by the trusted host."""
        return {'candidates': selected(domain, limit), 'catalog_sha256': catalog['catalog_sha256'],
                'mode': 'HOST_PREPARED_PROPOSALS_NO_COMPUTE', 'execution_authorized': False}

    @server.tool(name='evaluate_funnel_v3', annotations=readonly)
    def evaluate_funnel_v3(candidate_id: str) -> dict[str, Any]:
        """Retrieve a stored funnel evaluation; never execute caller code."""
        dossier = catalog['dossiers'].get(candidate_id)
        if dossier is None:
            return {'status': 'NOT_EVALUATED', 'scientific_GO': False, 'execution_authorized': False}
        return {'status': 'STORED_DIAGNOSTIC', 'dossier_sha256': dossier['dossier_sha256'],
                'decision': dossier['decision'], 'qualification': 'ABSTAIN', 'scientific_GO': False,
                'stages': [o['stage'] for o in dossier['observations']]}

    @server.tool(name='query_portfolio_catalog_v3', annotations=readonly)
    def query_portfolio_catalog_v3(domain: str | None = None, limit: int = 10) -> dict[str, Any]:
        """Query the host-bound catalog without executing or promoting science."""
        return {'candidates': selected(domain, limit), 'catalog_sha256': catalog['catalog_sha256'],
                'qualification': 'ABSTAIN'}

    if audit_rows is not None:
        @server.tool(name='synthesize_scientific_opinion_v3', annotations=readonly)
        def synthesize_scientific_opinion_v3(relaxed_sha256: str) -> dict[str, Any]:
            """Summarize one host-pinned audit record without dispatch or inference."""
            from rhombus.qualification.opinion_synthesizer import synthesize_scientific_opinion
            row = audit_rows.get(relaxed_sha256)
            if row is None:
                return {'status': 'NOT_FOUND', 'qualification': 'ABSTAIN', 'execution_authorized': False}
            return {'status': 'STORED_DIAGNOSTIC', 'audit_sha256': expected_audit_sha256,
                    'opinion': synthesize_scientific_opinion(row), 'qualification': 'ABSTAIN',
                    'execution_authorized': False}

    return server
