"""Actual SDK subprocess transport over synthetic second-family evidence."""
import json
from pathlib import Path
import sys

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rhombus.domain.context import (
    CapabilityDeclaration, ResearchContext, assess_declared_capability,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_second_family_context_survives_real_stdio_without_authorization(tmp_path):
    context = ResearchContext("solid_ionic_conductors", "S_ONLY", "fixture:sulfide",
                              "total_ionic_conductivity", "S/cm")
    declaration = CapabilityDeclaration("quantify_ionic_transport", "solid_ionic_conductors",
                                       "O_ONLY", "total_ionic_conductivity", "S/cm",
                                       "fixture:oxide-model", "fixture:v1")
    record = assess_declared_capability(context, declaration)
    path = tmp_path / "synthetic.jsonl"
    path.write_text(json.dumps(record.to_dict()) + "\n")
    before = path.read_bytes()
    params = StdioServerParameters(
        command=sys.executable, cwd=Path(__file__).resolve().parents[1],
        args=["-m", "rhombus.tools.mcp_server", "--evidence-jsonl", str(path)],
    )
    async with stdio_client(params) as streams:
        async with ClientSession(*streams, read_timeout_seconds=20) as client:
            await client.initialize()
            assert len((await client.list_tools()).tools) == 6
            response = await client.call_tool("get_candidate_evidence", {"candidate_id": context.candidate_id})
            result = response.model_dump(mode="json", by_alias=True)["structuredContent"]
            assert result["claim_authorized"] is False
            delivered = result["evidence_records"][0]
            assert delivered["research_context"] == context.to_dict()
            assert delivered["scientific_verdict"] == "NOT_APPLICABLE"
            assert delivered["evidence_id"] == record.evidence_id
    assert path.read_bytes() == before
