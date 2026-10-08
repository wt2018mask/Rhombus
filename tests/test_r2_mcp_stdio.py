"""Rhombus local MCP stdio protocol tests: modern, legacy, and fail closed."""
import io
import json
import subprocess
import sys

from rhombus.evidence import (
    Applicability, DomainStatus, EvidenceRecord,
    OperationalStatus, ScientificVerdict, Uncertainty,
)
from rhombus.tools.mcp_stdio import (
    EvidenceMcpServer, LEGACY, MODERN, serve_stdio,
)

META = {
    "io.modelcontextprotocol/protocolVersion": MODERN,
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
}


def snapshot(tmp_path):
    record = EvidenceRecord.create(
        candidate_id="candidate-42",
        evidence_kind="geometry",
        capability="validate_candidate_structure",
        operational_status=OperationalStatus.SUCCEEDED,
        scientific_verdict=ScientificVerdict.PASS,
        applicability=Applicability(
            claim_kind="structure", domain_status=DomainStatus.UNQUALIFIED
        ),
        uncertainty=Uncertainty(status="UNKNOWN", reason="unqualified"),
        limitations=("NOT_GENERALIZATION_AUTHORITY",),
        artifact_ids=("artifact:sha256:" + "a" * 64,),
        protocol_id="test-protocol",
        provenance={"test": True},
        payload={"valid": True},
    )
    path = tmp_path / "evidence.jsonl"
    path.write_text(json.dumps(record.to_dict()) + "\n", encoding="utf-8")
    return path, record


def send(server, method, params=None, req_id=1):
    return server.handle({
        "jsonrpc": "2.0", "id": req_id, "method": method,
        "params": {"_meta": META} if params is None else params,
    })


def test_modern_discover_list_call_and_claim_boundary(tmp_path):
    path, record = snapshot(tmp_path)
    server = EvidenceMcpServer(path)
    discover = send(server, "server/discover")["result"]
    assert discover["resultType"] == "complete"
    assert discover["supportedVersions"] == [MODERN, LEGACY]
    assert discover["capabilities"] == {"tools": {}}
    assert discover["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "rhombus-evidence"
    catalog = send(server, "tools/list")["result"]
    assert len(catalog["tools"]) == 1
    tool = catalog["tools"][0]
    assert tool["name"] == "get_candidate_evidence"
    assert tool["annotations"]["readOnlyHint"] is True
    assert tool["annotations"]["destructiveHint"] is False
    assert "evidence_jsonl" not in tool["inputSchema"]["properties"]
    answer = send(server, "tools/call", {
        "_meta": META, "name": "get_candidate_evidence",
        "arguments": {"candidate_id": "candidate-42"},
    })["result"]
    assert answer["resultType"] == "complete"
    assert answer["isError"] is False
    assert answer["structuredContent"]["evidence_records"][0]["evidence_id"] == record.evidence_id
    assert answer["structuredContent"]["claim_authorized"] is False
    assert answer["structuredContent"]["scientific_verdict"] == "UNKNOWN"
    assert json.loads(answer["content"][0]["text"]) == answer["structuredContent"]


def test_mcp_legacy_handshake_and_allowlist(tmp_path):
    path, record = snapshot(tmp_path)
    server = EvidenceMcpServer(path)
    assert send(server, "tools/list")["error"]["code"] == -32022
    hello = send(server, "initialize", {
        "protocolVersion": LEGACY,
        "clientInfo": {"name": "old-agent", "version": "1"},
        "capabilities": {},
    })
    assert hello["result"]["protocolVersion"] == LEGACY
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert len(send(server, "tools/list", {})["result"]["tools"]) == 1
    assert send(server, "ping", {})["result"] == {}
    assert send(server, "tools/call", {"name": "relax_structure", "arguments": {}})["error"]["code"] == -32602
    good = send(server, "tools/call", {
        "name": "get_candidate_evidence",
        "arguments": {"candidate_id": "candidate-42"},
    })["result"]
    assert good["structuredContent"]["evidence_records"][0]["evidence_id"] == record.evidence_id
    assert good["structuredContent"]["claim_authorized"] is False


def test_mcp_bad_source_and_model_path_injection_fail_closed(tmp_path):
    path, _ = snapshot(tmp_path)
    server = EvidenceMcpServer(path)
    path.write_text("{invalid}\n", encoding="utf-8")
    result = send(server, "tools/call", {
        "_meta": META, "name": "get_candidate_evidence",
        "arguments": {"candidate_id": "candidate-42"},
    })["result"]
    assert result["isError"] is True
    assert result["structuredContent"]["scientific_verdict"] == "UNKNOWN"
    assert result["structuredContent"]["claim_authorized"] is False
    assert "evidence.jsonl" not in result["content"][0]["text"]
    fail = send(server, "tools/call", {
        "_meta": META, "name": "get_candidate_evidence",
        "arguments": {"candidate_id": "candidate-42", "path": "/etc/passwd"},
    })["result"]
    assert fail["isError"] is True
    assert fail["structuredContent"]["claim_authorized"] is False
    absent = EvidenceMcpServer(tmp_path / "absent.jsonl")
    missing = send(absent, "tools/call", {
        "_meta": META, "name": "get_candidate_evidence",
        "arguments": {"candidate_id": "candidate-42"},
    })["result"]
    assert missing["isError"] is True


def test_stdio_subprocess_emits_protocol_lines_only(tmp_path):
    path, _ = snapshot(tmp_path)
    events = [
        {"jsonrpc": "2.0", "id": "discover", "method": "server/discover",
         "params": {"_meta": META}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": "list", "method": "tools/list",
         "params": {"_meta": META}},
        {"jsonrpc": "2.0", "id": "lookup", "method": "tools/call",
         "params": {"_meta": META, "name": "get_candidate_evidence",
                    "arguments": {"candidate_id": "candidate-42"}}},
    ]
    output = subprocess.run(
        [sys.executable, "-m", "rhombus.tools.mcp_stdio",
         "--evidence-jsonl", str(path)],
        input="".join(json.dumps(event) + "\n" for event in events),
        capture_output=True, text=True, check=True, timeout=15,
    )
    assert output.stderr == ""
    replies = [json.loads(line) for line in output.stdout.splitlines()]
    assert [item["id"] for item in replies] == ["discover", "list", "lookup"]
    assert all(item["jsonrpc"] == "2.0" for item in replies)
    assert replies[2]["result"]["structuredContent"]["claim_authorized"] is False


def test_stdio_rejects_corrupt_and_oversized_without_following_fragment(tmp_path):
    path, _ = snapshot(tmp_path)
    valid = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list",
                        "params": {"_meta": META}})
    inp = io.StringIO("{broken}\n" + valid + "\n")
    out = io.StringIO()
    serve_stdio(EvidenceMcpServer(path), input_stream=inp, output_stream=out)
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    assert rows[0]["error"]["code"] == -32700
    assert len(rows[1]["result"]["tools"]) == 1
    inp = io.StringIO("X" * (1024 * 1024 + 50) + "\n" + valid + "\n")
    out = io.StringIO()
    serve_stdio(EvidenceMcpServer(path), input_stream=inp, output_stream=out)
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    assert len(rows) == 1
    assert rows[0]["error"]["code"] == -32600
