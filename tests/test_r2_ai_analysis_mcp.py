"""Real official MCP v2 client tests for the additional read-only tools."""
from pathlib import Path

import pytest
from mcp import Client

from rhombus.tools.mcp_server import create_mcp_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "data/benchmarks/known_material/model_domains/medium-mpa-0-domain-v1.json"


def structure():
    return {
        "lattice_vectors_angstrom": [[4.0, 0, 0], [0, 4.0, 0], [0, 0, 4.0]],
        "atomic_numbers": [3, 8],
        "fractional_coords": [[0, 0, 0], [0.5, 0.5, 0.5]],
    }


@pytest.mark.anyio
async def test_mcp_catalog_is_exact_read_only_allowlist(tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    server = create_mcp_server(empty, model_domain_snapshot=MODEL)
    async with Client(server, raise_exceptions=True) as client:
        items = (await client.list_tools()).tools
        assert [x.name for x in items] == [
            "get_candidate_evidence", "get_domain_assessment",
            "validate_candidate_structure", "build_evidence_manifest", "plan_scientific_task",
        ]
        assert all(x.annotations.read_only_hint is True for x in items)
        assert all(x.annotations.open_world_hint is False for x in items)
        assert not any("token" in str(x.input_schema).lower() for x in items)
        assert not any("snapshot" in str(x.input_schema).lower() for x in items)


@pytest.mark.anyio
async def test_mcp_domain_and_structure_do_not_authorize_science(tmp_path):
    evidence = tmp_path / "empty.jsonl"
    evidence.write_text("")
    async with Client(
        create_mcp_server(evidence, model_domain_snapshot=MODEL),
        raise_exceptions=True,
    ) as client:
        domain = await client.call_tool("get_domain_assessment", {
            "candidate_id": "candidate-a",
            "model_id": "medium-mpa-0",
            "claim_kind": "finite_temperature_stability",
            "atomic_numbers": [3, 84],
        })
        assert domain.is_error is not True
        assert domain.structured_content["domain_status"] == "FAR_OOD"
        assert domain.structured_content["scientific_verdict"] == "UNKNOWN"
        assert domain.structured_content["claim_authorized"] is False
        geom = await client.call_tool("validate_candidate_structure", {
            "candidate_id": "candidate-a", "structure": structure(),
        })
        assert geom.is_error is not True
        assert geom.structured_content["representation_status"] == "VALID_REPRESENTATION"
        assert geom.structured_content["scientific_verdict"] == "UNKNOWN"
        assert geom.structured_content["claim_authorized"] is False
        forged = await client.call_tool("validate_candidate_structure", {
            "candidate_id": "candidate-a", "structure": {**structure(), "command": "whoami"},
        })
        assert forged.is_error is True


@pytest.mark.anyio
async def test_unconfigured_domain_source_fails_closed(tmp_path):
    evidence = tmp_path / "empty.jsonl"
    evidence.write_text("")
    async with Client(create_mcp_server(evidence), raise_exceptions=True) as client:
        result = await client.call_tool("get_domain_assessment", {
            "candidate_id": "candidate-a",
            "model_id": "medium-mpa-0",
            "claim_kind": "finite_temperature_stability",
            "atomic_numbers": [3, 8],
        })
        assert result.is_error is True
