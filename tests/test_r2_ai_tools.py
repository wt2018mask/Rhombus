"""Fail-closed, CPU-free AI function-call evidence gateway contracts."""
import copy
import json

import pytest

from rhombus.evidence import (
    Applicability, DomainStatus, EvidenceRecord, OperationalStatus,
    ScientificVerdict, Uncertainty,
)
from rhombus.tools import ReadOnlyEvidenceTools, list_tool_specs


def record(candidate: str, *, kind: str, verdict=ScientificVerdict.UNKNOWN):
    return EvidenceRecord.create(
        candidate_id=candidate,
        evidence_kind=kind,
        capability="validate_candidate_structure",
        operational_status=OperationalStatus.SUCCEEDED,
        scientific_verdict=verdict,
        applicability=Applicability(
            claim_kind="structure",
            domain_status=DomainStatus.UNQUALIFIED,
        ),
        uncertainty=Uncertainty(status="UNKNOWN", reason="not qualified"),
        limitations=("NO_CLAIM_AUTHORIZATION",),
        artifact_ids=("artifact:sha256:" + "1" * 64,),
        protocol_id="test-protocol-v1",
        provenance={"input": "unit-test", "immutable": True},
        payload={"structure_found": True},
    )


def snapshot(tmp_path, *records):
    path = tmp_path / "evidence.jsonl"
    path.write_text(
        "".join(json.dumps(r.to_dict(), sort_keys=True) + "\n" for r in records),
        encoding="utf-8",
    )
    return path


def test_ai_catalog_small_pure_and_model_schema_strict():
    first = list_tool_specs()
    assert len(first) == 1
    schema = first[0]["function"]
    assert schema["name"] == "get_candidate_evidence"
    assert schema["parameters"]["additionalProperties"] is False
    assert "evidence_jsonl" not in schema["parameters"]["properties"]
    first[0]["function"]["name"] = "unsafe"
    assert list_tool_specs()[0]["function"]["name"] == "get_candidate_evidence"


def test_readonly_evidence_preserves_record_verdict_and_never_promotes_claim(tmp_path):
    a = record("candidate-1", kind="geometry", verdict=ScientificVerdict.PASS)
    b = record("candidate-1", kind="transport")
    c = record("candidate-2", kind="geometry")
    path = snapshot(tmp_path, a, b, c)
    original_bytes = path.read_bytes()
    gateway = ReadOnlyEvidenceTools(path)
    answer = gateway.call_tool("get_candidate_evidence", {"candidate_id": "candidate-1"})
    assert answer["operational_status"] == "SUCCEEDED"
    assert answer["scientific_verdict"] == "UNKNOWN"
    assert answer["domain_status"] == "UNQUALIFIED"
    assert answer["claim_authorized"] is False
    assert answer["evidence_count"] == 2
    assert {r["scientific_verdict"] for r in answer["evidence_records"]} == {"PASS", "UNKNOWN"}
    assert {r["evidence_id"] for r in answer["evidence_records"]} == {a.evidence_id, b.evidence_id}
    assert all(r["protocol_id"] == "test-protocol-v1" for r in answer["evidence_records"])
    assert path.read_bytes() == original_bytes


def test_missing_candidate_is_unknown_and_not_pass(tmp_path):
    gateway = ReadOnlyEvidenceTools(snapshot(tmp_path, record("present", kind="structure")))
    result = gateway.call_tool("get_candidate_evidence", {"candidate_id": "absent"})
    assert result["evidence_records"] == []
    assert result["scientific_verdict"] == "UNKNOWN"
    assert result["claim_authorized"] is False
    assert result["operational_status"] == "SUCCEEDED"


def test_return_bounds_and_argument_guard(tmp_path):
    rows = [record("target", kind=f"test-{i}") for i in range(4)]
    gateway = ReadOnlyEvidenceTools(snapshot(tmp_path, *rows))
    result = gateway.call_tool("get_candidate_evidence", {"candidate_id": "target", "max_records": 2})
    assert result["evidence_count"] == 4
    assert result["returned_count"] == 2
    assert result["truncated"] is True
    for args in (
        {"candidate_id": "target", "max_records": True},
        {"candidate_id": "target", "max_records": 0},
        {"candidate_id": "target", "max_records": 26},
        {"candidate_id": "target", "path": "/etc/passwd"},
        {"candidate_id": "  "},
        {"max_records": 1},
    ):
        with pytest.raises(ValueError):
            gateway.call_tool("get_candidate_evidence", args)
    with pytest.raises(ValueError):
        gateway.call_tool("relax_structure", {"candidate_id": "target"})


def test_tampered_sha_or_verdict_fail_closed_even_for_other_candidate(tmp_path):
    original = record("other", kind="structure").to_dict()
    for field, value in (
        ("scientific_verdict", "PASS"),
        ("evidence_id", "evidence:sha256:" + "0" * 64),
    ):
        corrupt = copy.deepcopy(original)
        corrupt[field] = value
        path = tmp_path / f"{field}.jsonl"
        path.write_text(json.dumps(corrupt) + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="hash mismatch"):
            ReadOnlyEvidenceTools(path).call_tool(
                "get_candidate_evidence", {"candidate_id": "different"}
            )


def test_missing_corrupt_duplicate_and_oversize_file_fail_closed(tmp_path):
    path = tmp_path / "missing.jsonl"
    with pytest.raises(FileNotFoundError):
        ReadOnlyEvidenceTools(path).call_tool("get_candidate_evidence", {"candidate_id": "x"})
    path.write_text("{bad-json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid evidence JSONL"):
        ReadOnlyEvidenceTools(path).call_tool("get_candidate_evidence", {"candidate_id": "x"})
    a = record("x", kind="test")
    snapshot(tmp_path, a, a)
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        ReadOnlyEvidenceTools(tmp_path / "evidence.jsonl").call_tool(
            "get_candidate_evidence", {"candidate_id": "x"}
        )
    path.write_bytes(b" " * (1024 * 1024 + 1) + b"\n")
    with pytest.raises(ValueError, match="exceeds size budget"):
        ReadOnlyEvidenceTools(path).call_tool("get_candidate_evidence", {"candidate_id": "x"})
