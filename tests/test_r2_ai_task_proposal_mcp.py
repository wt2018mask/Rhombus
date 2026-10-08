"""Official MCP tool discovery and proposal-only scientific task contract."""
import pytest
from mcp import Client

from rhombus.tools.mcp_server import create_mcp_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_plan_never_approves_or_dispatches(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("")
    async with Client(create_mcp_server(path), raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        assert [tool.name for tool in tools] == [
            "get_candidate_evidence", "get_domain_assessment",
            "validate_candidate_structure", "build_evidence_manifest",
            "plan_scientific_task",
        ]
        assert all(tool.annotations.read_only_hint is True for tool in tools)
        assert "approve_scientific_task" not in [tool.name for tool in tools]
        assert "execute_scientific_task" not in [tool.name for tool in tools]
        reply = await client.call_tool("plan_scientific_task", {
            "candidate_id": "a",
            "capability": "relax_structure",
            "evidence_manifest_id": "manifest:sha256:" + "a" * 64,
            "requested_backend": "KAGGLE_CPU",
            "max_walltime_seconds": 3600,
            "max_cpu_cores": 2,
            "max_memory_mib": 4096,
        })
        assert reply.is_error is not True
        assert reply.structured_content["execution_authorized"] is False
        assert reply.structured_content["dispatch_status"] == "NOT_SUBMITTED"
        assert reply.structured_content["scientific_verdict"] == "UNKNOWN"
        err = await client.call_tool("plan_scientific_task", {
            "candidate_id": "a",
            "capability": "relax_structure",
            "evidence_manifest_id": "manifest:sha256:" + "a" * 64,
            "requested_backend": "KAGGLE_CPU",
            "max_walltime_seconds": 999999,
            "max_cpu_cores": 2,
            "max_memory_mib": 4096,
        })
        assert err.is_error is True
