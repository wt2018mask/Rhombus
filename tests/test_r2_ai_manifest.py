"""Bounded evidence manifest regression tests: no PASS inference or external calls."""
import copy
import hashlib
import json

import pytest

from rhombus.evidence import (
    Applicability, DomainStatus, EvidenceRecord, OperationalStatus,
    ScientificVerdict, Uncertainty,
)
from rhombus.tools.evidence_manifest import ReadOnlyEvidenceManifestTools, manifest_tool_spec


def record(candidate, kind, verdict=ScientificVerdict.UNKNOWN):
    return EvidenceRecord.create(
        candidate_id=candidate, evidence_kind=kind,
        capability="validate_candidate_structure",
        operational_status=OperationalStatus.SUCCEEDED,
        scientific_verdict=verdict,
        applicability=Applicability(claim_kind="structure", domain_status=DomainStatus.UNQUALIFIED),
        uncertainty=Uncertainty(status="UNKNOWN", reason="not qualified"),
        limitations=("TEST_RECORD_ONLY",),
        artifact_ids=("artifact:sha256:" + "1" * 64,),
        protocol_id="synthetic-manifest-test-v1",
        provenance={"synthetic": True},
        payload={"kind": kind},
    )


def snapshot(tmp_path, records):
    path = tmp_path / "evidence.jsonl"
    path.write_text("".join(json.dumps(r.to_dict(), sort_keys=True) + "\n" for r in records), encoding="utf-8")
    return path


def test_manifest_returns_complete_digest_with_bounded_visible_ids(tmp_path):
    records = [record("target", f"kind-{i}", verdict=ScientificVerdict.PASS) for i in range(4)]
    records.append(record("other", "unrelated"))
    path = snapshot(tmp_path, records)
    original = path.read_bytes()
    out = ReadOnlyEvidenceManifestTools(path).call_tool("build_evidence_manifest", {
        "candidate_id": "target", "max_evidence_ids": 2,
    })
    assert out["manifest_id"].startswith("manifest:sha256:")
    assert out["snapshot_sha256"] == hashlib.sha256(original).hexdigest()
    assert out["evidence_count"] == 4
    assert out["returned_count"] == 2
    assert out["truncated"] is True
    assert out["evidence_ids"] == sorted(r.evidence_id for r in records[:4])[:2]
    assert out["operational_status"] == "SUCCEEDED"
    assert out["scientific_verdict"] == "UNKNOWN"
    assert out["domain_status"] == "UNQUALIFIED"
    assert out["claim_authorized"] is False
    assert "MANIFEST_INDEX_NOT_A_SCIENTIFIC_VERDICT" in out["limitations"]
    assert path.read_bytes() == original
    all_ids = ReadOnlyEvidenceManifestTools(path).call_tool("build_evidence_manifest", {
        "candidate_id": "target", "max_evidence_ids": 25,
    })
    assert all_ids["manifest_id"] == out["manifest_id"]
    assert all_ids["truncated"] is False


def test_empty_or_corrupt_snapshot_never_implies_positive_claim(tmp_path):
    target = snapshot(tmp_path, [record("other", "geometry")])
    answer = ReadOnlyEvidenceManifestTools(target).call_tool("build_evidence_manifest", {
        "candidate_id": "missing"
    })
    assert answer["evidence_count"] == 0
    assert answer["evidence_ids"] == []
    assert answer["scientific_verdict"] == "UNKNOWN"
    assert answer["claim_authorized"] is False
    row = copy.deepcopy(record("other", "geometry").to_dict())
    row["scientific_verdict"] = "PASS"
    target.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        ReadOnlyEvidenceManifestTools(target).call_tool("build_evidence_manifest", {
            "candidate_id": "unrelated"
        })


def test_schema_permissions_and_malformed_inputs(tmp_path):
    path = snapshot(tmp_path, [record("a", "first")])
    fn = manifest_tool_spec()["function"]
    assert fn["name"] == "build_evidence_manifest"
    assert fn["parameters"]["additionalProperties"] is False
    assert "path" not in fn["parameters"]["properties"]
    for args in (
        {"candidate_id": "a", "max_evidence_ids": 0},
        {"candidate_id": "a", "max_evidence_ids": 26},
        {"candidate_id": "a", "max_evidence_ids": True},
        {"candidate_id": "a", "evidence_jsonl": "/etc/passwd"},
        {"candidate_id": ""},
        {},
    ):
        with pytest.raises(ValueError):
            ReadOnlyEvidenceManifestTools(path).call_tool("build_evidence_manifest", args)
    with pytest.raises(ValueError):
        ReadOnlyEvidenceManifestTools(path).call_tool("relax_structure", {"candidate_id": "a"})
    with pytest.raises(FileNotFoundError):
        ReadOnlyEvidenceManifestTools(tmp_path / "missing").call_tool(
            "build_evidence_manifest", {"candidate_id": "a"},
        )


def test_duplicate_corrupt_and_oversized_data_fail_closed(tmp_path):
    rec = record("a", "one")
    path = snapshot(tmp_path, [rec, rec])
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        ReadOnlyEvidenceManifestTools(path).call_tool("build_evidence_manifest", {"candidate_id": "a"})
    path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid evidence JSONL"):
        ReadOnlyEvidenceManifestTools(path).call_tool("build_evidence_manifest", {"candidate_id": "a"})
    path.write_bytes(b" " * (1024 * 1024 + 1) + b"\n")
    with pytest.raises(ValueError, match="exceeds size budget"):
        ReadOnlyEvidenceManifestTools(path).call_tool("build_evidence_manifest", {"candidate_id": "a"})
