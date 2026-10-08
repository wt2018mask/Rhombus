"""Official MCP v2 in-memory tool discovery and fail-closed integration."""
from __future__ import annotations

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


def make_record(candidate: str):
    return EvidenceRecord.create(
        candidate_id=candidate,
        evidence_kind="synthetic-structure",
        capability="validate_candidate_structure",
        operational_status=OperationalStatus.SUCCEEDED,
        scientific_verdict=ScientificVerdict.PASS,
        applicability=Applicability(
            claim_kind="structure", domain_status=DomainStatus.UNQUALIFIED,
        ),
        uncertainty=Uncertainty(status="UNKNOWN", reason="unqualified"),
        limitations=("SYNTHETIC_TEST_ONLY",),
        artifact_ids=("artifact:sha256:" + "1" * 64,),
        protocol_id="synthetic-protocol-v1",
        provenance={"synthetic": True},
        payload={"bounded": True},
    )


def write_snapshot(tmp_path, *rows):
    path = tmp_path / "evidence.jsonl"
    path.write_text(
        "".join(json.dumps(r.to_dict(), sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )
    return path


@pytest.mark.anyio
async def test_mcp_discovery_exposes_only_readonly_evidence(tmp_path):
    server = create_mcp_server(write_snapshot(tmp_path, make_record("a")))
    async with Client(server, raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        assert [t.name for t in tools] == ["get_candidate_evidence"]
        schema = tools[0].input_schema
        assert set(schema["properties"]) == {"candidate_id", "max_records"}
        assert schema["required"] == ["candidate_id"]
        assert schema["properties"]["max_records"]["minimum"] == 1
        assert schema["properties"]["max_records"]["maximum"] == 25
        assert tools[0].annotations.read_only_hint is True


@pytest.mark.anyio
async def test_mcp_call_preserves_unqualified_scientific_outcome(tmp_path):
    path = write_snapshot(tmp_path, make_record("a"), make_record("b"))
    original = path.read_bytes()
    async with Client(create_mcp_server(path), raise_exceptions=True) as client:
        result = await client.call_tool("get_candidate_evidence", {"candidate_id": "a"})
        assert result.is_error is not True
        payload = result.structured_content
        assert payload["operational_status"] == "SUCCEEDED"
        assert payload["scientific_verdict"] == "UNKNOWN"
        assert payload["domain_status"] == "UNQUALIFIED"
        assert payload["claim_authorized"] is False
        assert payload["evidence_count"] == 1
        assert payload["evidence_records"][0]["scientific_verdict"] == "PASS"
        missing = await client.call_tool("get_candidate_evidence", {"candidate_id": "missing"})
        assert missing.structured_content["evidence_count"] == 0
        assert missing.structured_content["claim_authorized"] is False
    assert path.read_bytes() == original


@pytest.mark.anyio
async def test_mcp_rejects_invalid_args_and_tampered_evidence(tmp_path):
    path = write_snapshot(tmp_path, make_record("a"))
    async with Client(create_mcp_server(path), raise_exceptions=True) as client:
        invalid = await client.call_tool(
            "get_candidate_evidence", {"candidate_id": "a", "max_records": 1000}
        )
        assert invalid.is_error is True
        row = make_record("a").to_dict()
        row["scientific_verdict"] = "FAIL"
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        corrupted = await client.call_tool(
            "get_candidate_evidence", {"candidate_id": "a"}
        )
        assert corrupted.is_error is True
