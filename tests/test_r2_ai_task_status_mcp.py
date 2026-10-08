"""Official MCP client access to host-selected status without side effects."""
import hashlib
import json

import pytest
from mcp import Client

from rhombus.tools.mcp_server import create_mcp_server
from rhombus.tools.task_status import STATUS_SCHEMA


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_task_status_is_readonly_and_host_bound(tmp_path):
    proposal_id = "task-proposal:sha256:" + "a" * 64
    record = {
        "schema_version": STATUS_SCHEMA,
        "proposal_id": proposal_id,
        "task_state": "RUNNING",
        "backend_identity": "KAGGLE_CPU",
        "observed_at_utc": "2026-10-08T01:00:00Z",
        "provider_run_id": "37713197144",
    }
    record["record_id"] = "task-status:sha256:" + hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    status = tmp_path / "status.jsonl"
    status.write_text(json.dumps(record) + "\n")
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text("")
    async with Client(create_mcp_server(evidence, task_status_jsonl=status), raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        assert [t.name for t in tools] == [
            "get_candidate_evidence", "get_domain_assessment",
            "validate_candidate_structure", "build_evidence_manifest",
            "plan_scientific_task", "get_task_status",
        ]
        assert all(t.annotations.read_only_hint is True for t in tools)
        result = await client.call_tool("get_task_status", {"proposal_id": proposal_id})
        assert result.is_error is not True
        assert result.structured_content["task_state"] == "RUNNING"
        assert result.structured_content["claim_authorized"] is False
        assert result.structured_content["status_freshness"] == "HOST_SNAPSHOT_ONLY_NOT_LIVE"
        forged = await client.call_tool("get_task_status", {"proposal_id": proposal_id, "path":"/etc/passwd"})
        assert forged.is_error is True


@pytest.mark.anyio
async def test_mcp_task_status_missing_host_file_is_error(tmp_path):
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text("")
    async with Client(create_mcp_server(evidence), raise_exceptions=True) as client:
        result = await client.call_tool("get_task_status", {
            "proposal_id": "task-proposal:sha256:" + "a" * 64
        })
        assert result.is_error is True
