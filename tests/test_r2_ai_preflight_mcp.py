"""Real MCP v2 Client sees opt-in preflights without enabling computation."""
import hashlib
import json
from pathlib import Path

import pytest
from mcp import Client

from rhombus.evidence import Applicability, DomainStatus, EvidenceRecord, OperationalStatus, ScientificVerdict
from rhombus.tools.mcp_server import create_mcp_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


def trusted_files(tmp_path):
    snapshot = Path(__file__).resolve().parents[1] / "data/benchmarks/known_material/model_domains/medium-mpa-0-domain-v1.json"
    sha = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    record = EvidenceRecord.create(
        candidate_id="candidate-1", evidence_kind="test-only",
        capability="validate_candidate_structure", operational_status=OperationalStatus.SUCCEEDED,
        scientific_verdict=ScientificVerdict.UNKNOWN,
        applicability=Applicability(claim_kind="structure", domain_status=DomainStatus.UNQUALIFIED),
    )
    jsonl = tmp_path / "trusted.jsonl"
    jsonl.write_text(json.dumps(record.to_dict()) + "\n", encoding="utf-8")
    return jsonl, snapshot, sha


@pytest.mark.anyio
async def test_opt_in_mcp_tools_and_fail_closed_outputs(tmp_path):
    evidence, snapshot, sha = trusted_files(tmp_path)
    server = create_mcp_server(
        evidence, enable_preflight_tools=True,
        model_domain_snapshot=snapshot, model_domain_snapshot_sha256=sha,
    )
    async with Client(server, raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        assert {t.name for t in tools} == {
            "get_candidate_evidence", "get_domain_assessment", "validate_candidate_structure"
        }
        assert all(t.annotations.read_only_hint is True for t in tools)
        domain = await client.call_tool("get_domain_assessment", {
            "candidate_id": "candidate-1",
            "atomic_numbers": [3, 84],
            "claim_kind": "finite_temperature_stability",
        })
        assert domain.is_error is not True
        assert domain.structured_content["domain_status"] == "FAR_OOD"
        assert domain.structured_content["claim_authorized"] is False
        assert domain.structured_content["scientific_verdict"] == "UNKNOWN"
        valid = await client.call_tool("validate_candidate_structure", {
            "candidate_id": "candidate-1",
            "atomic_numbers": [11, 17],
            "cell_lengths_angstrom": [4.0, 4.0, 4.0],
            "cell_angles_degrees": [90.0, 90.0, 90.0],
            "fractional_coordinates": [[0, 0, 0], [0.5, 0.5, 0.5]],
        })
        assert valid.is_error is not True
        assert valid.structured_content["representation_status"] == "WELL_FORMED_PERIODIC_STRUCTURE"
        assert valid.structured_content["claim_authorized"] is False
        assert "relax_structure" not in {t.name for t in tools}


@pytest.mark.anyio
async def test_mcp_preflight_opt_out_remains_one_tool(tmp_path):
    evidence, _, _ = trusted_files(tmp_path)
    async with Client(create_mcp_server(evidence), raise_exceptions=True) as client:
        assert [t.name for t in (await client.list_tools()).tools] == ["get_candidate_evidence"]


def test_opt_in_requires_trusted_host_snapshot(tmp_path):
    evidence, snapshot, sha = trusted_files(tmp_path)
    with pytest.raises(ValueError, match="host-pinned"):
        create_mcp_server(evidence, enable_preflight_tools=True)
    with pytest.raises(ValueError):
        create_mcp_server(
            evidence, enable_preflight_tools=True,
            model_domain_snapshot=snapshot, model_domain_snapshot_sha256="not-sha",
        )
