import hashlib
import json
import pytest
from rhombus.automation.campaign_worker_v3 import canonical
from rhombus.mcp.catalog_v3 import build_portfolio_catalog, create_server
from rhombus.transport.cohort_audit import retrospective_joint_profiles


def test_joint_ranks_keep_absent_basins_at_zero():
    rows = [{'relaxed_sha256': 'a', 'basin': {'x_vac_basin': 0.}, 'channel_ev': .5, 'radius_A': .4},
            {'relaxed_sha256': 'b', 'basin': {'x_vac_basin': .2}, 'channel_ev': .6, 'radius_A': .5}]
    result = retrospective_joint_profiles(rows)
    assert result[0]['score'] == 0 and result[0]['basin_state'] == 'NO_ACCESSIBLE_VACANCY_BASIN'
    assert result[1]['score'] > 0 and 'NOT_VALIDATED' in result[1]['scope']
    assert retrospective_joint_profiles(rows) == result


@pytest.fixture
def anyio_backend(): return 'asyncio'


@pytest.mark.anyio
async def test_mcp_opinion_is_host_pinned_and_read_only(tmp_path):
    from mcp import Client
    evidence = tmp_path / 'evidence.jsonl'; evidence.write_text('')
    catalog = tmp_path / 'catalog.json'; catalog.write_bytes(canonical(build_portfolio_catalog([])))
    audit = tmp_path / 'audit.json'; key = 'a' * 64
    audit.write_text(json.dumps({'qualification': 'ABSTAIN', 'rows': [{'relaxed_sha256': key, 'formula': 'Li2S'}]}))
    catalog_hash = hashlib.sha256(catalog.read_bytes()).hexdigest()
    audit_hash = hashlib.sha256(audit.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='mismatch'):
        create_server(evidence, portfolio_path=catalog, expected_sha256=catalog_hash, audit_path=audit, expected_audit_sha256='0'*64)
    server = create_server(evidence, portfolio_path=catalog, expected_sha256=catalog_hash, audit_path=audit, expected_audit_sha256=audit_hash)
    async with Client(server, raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        tool = next(t for t in tools if t.name == 'synthesize_scientific_opinion_v3')
        assert tool.annotations.read_only_hint
        result = await client.call_tool(tool.name, {'relaxed_sha256': key})
        assert result.structured_content['qualification'] == 'ABSTAIN'
        assert result.structured_content['opinion']['section_1_structure_and_provenance']['formula'] == 'Li2S'
        assert (await client.call_tool(tool.name, {'relaxed_sha256': key, 'path': 'x'})).is_error
