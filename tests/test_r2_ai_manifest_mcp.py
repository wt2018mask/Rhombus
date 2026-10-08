"""Official MCP client recognizes deterministic evidence manifest tool."""
import json

import pytest
from mcp import Client

from rhombus.evidence import (
    Applicability, DomainStatus, EvidenceRecord, OperationalStatus,
    ScientificVerdict, Uncertainty,
)
from rhombus.tools.mcp_server import create_mcp_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_manifest_allowlisted_and_readonly(tmp_path):
    record = EvidenceRecord.create(
        candidate_id="target", evidence_kind="synthetic-test",
        capability="validate_candidate_structure",
        operational_status=OperationalStatus.SUCCEEDED,
        scientific_verdict=ScientificVerdict.PASS,
        applicability=Applicability(claim_kind="structure", domain_status=DomainStatus.UNQUALIFIED),
        uncertainty=Uncertainty(status="UNKNOWN", reason="not qualified"),
        limitations=("TEST_ONLY",), protocol_id="test-protocol", provenance={"synthetic": True},
    )
    target = tmp_path / "evidence.jsonl"
    target.write_text(json.dumps(record.to_dict()) + "\n", encoding="utf-8")
    async with Client(create_mcp_server(target), raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        assert [t.name for t in tools] == [
            "get_candidate_evidence", "get_domain_assessment",
            "validate_candidate_structure", "build_evidence_manifest", "plan_scientific_task", "get_task_status",
        ]
        assert all(t.annotations.read_only_hint is True for t in tools)
        result = await client.call_tool("build_evidence_manifest", "plan_scientific_task", "get_task_status", {
            "candidate_id": "target", "max_evidence_ids": 10,
        })
        assert result.is_error is not True
        payload = result.structured_content
        assert payload["evidence_ids"] == [record.evidence_id]
        assert payload["scientific_verdict"] == "UNKNOWN"
        assert payload["claim_authorized"] is False
        assert payload["manifest_id"].startswith("manifest:sha256:")
        error = await client.call_tool("build_evidence_manifest", "plan_scientific_task", "get_task_status", {
            "candidate_id": "target", "max_evidence_ids": 100,
        })
        assert error.is_error is True
