"""Synthetic architecture tests: no cross-family scientific validation claimed."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from rhombus.domain.context import (
    CapabilityDeclaration, ResearchContext, assess_declared_capability,
)
from rhombus.evidence.identity import SourceBinding
from rhombus.tools.evidence_query import ReadOnlyEvidenceTools, list_tool_specs
from rhombus.tools.evidence_manifest import ReadOnlyEvidenceManifestTools
from rhombus.tools.task_proposal import DenyByDefaultTaskPlanner


def context(**changes):
    return replace(ResearchContext(
        domain_id="solid_ionic_conductors", family_id="O_ONLY",
        candidate_id="fixture:oxide", observable_id="total_ionic_conductivity",
        unit="S/cm", composition_id="fixture:nominal-oxide",
        measurement_temperature_K=298.15,
    ), **changes)


def declaration(**changes):
    return replace(CapabilityDeclaration(
        capability="quantify_ionic_transport", domain_id="solid_ionic_conductors",
        family_id="O_ONLY", observable_id="total_ionic_conductivity", unit="S/cm",
        model_id="fixture:oxide-only-model", protocol_id="fixture:protocol-v1",
    ), **changes)


def test_second_family_represented_without_oxide_claim_transfer(tmp_path):
    oxide = context()
    sulfide = context(family_id="S_ONLY", candidate_id="fixture:sulfide",
                      composition_id="fixture:Li6PS5Cl", processing_state_id="fixture:batch")
    source = SourceBinding(source_type="SYNTHETIC_FIXTURE", source_id="fixture:source")
    records = [assess_declared_capability(c, declaration(), source_bindings=(source,))
               for c in (oxide, sulfide)]
    assert records[0].scientific_verdict.value == "UNKNOWN"
    assert records[0].payload["routing_decision"] == "ABSTAIN"
    assert records[1].scientific_verdict.value == "NOT_APPLICABLE"
    assert records[1].payload["mismatched_fields"] == ["family_id"]
    assert all(r.applicability.domain_status.value == "UNQUALIFIED" for r in records)
    path = tmp_path / "snapshot.jsonl"
    path.write_text("".join(json.dumps(r.to_dict()) + "\n" for r in records))
    before = path.read_bytes()
    query = ReadOnlyEvidenceTools(path)
    manifest = ReadOnlyEvidenceManifestTools(path)
    for record in records:
        result = query.call_tool("get_candidate_evidence", {"candidate_id": record.candidate_id})
        assert result["claim_authorized"] is False
        assert result["scientific_verdict"] == "UNKNOWN"
        delivered = result["evidence_records"][0]
        assert delivered["research_context"] == record.payload["research_context"]
        assert delivered["evidence_id"] == record.evidence_id
        assert delivered["source_bindings"][0]["source_type"] == "SYNTHETIC_FIXTURE"
        index = manifest.call_tool("build_evidence_manifest", {"candidate_id": record.candidate_id})
        assert index["evidence_ids"] == [record.evidence_id]
        assert index["claim_authorized"] is False
        proposal = DenyByDefaultTaskPlanner().call_tool("plan_scientific_task", {
            "candidate_id": record.candidate_id,
            "capability": "quantify_ionic_transport",
            "evidence_manifest_id": index["manifest_id"],
            "requested_backend": "LOCAL_CPU", "max_walltime_seconds": 60,
            "max_cpu_cores": 1, "max_memory_mib": 256,
        })
        assert proposal["dispatch_status"] == "NOT_SUBMITTED"
        assert proposal["execution_authorized"] is False
        assert proposal["evidence_manifest_id_verified"] is False
    assert path.read_bytes() == before
    assert len(list_tool_specs()) == 6


@pytest.mark.parametrize("field,value", [
    ("domain_id", "another_science"), ("family_id", "halide"),
    ("observable_id", "bulk_ionic_conductivity"), ("unit", "mS/cm"),
])
def test_unsupported_domain_family_quantity_or_units_rejected(field, value):
    r = assess_declared_capability(context(**{field: value}), declaration())
    assert r.scientific_verdict.value == "NOT_APPLICABLE"
    assert r.payload["mismatched_fields"] == [field]
    assert r.payload["execution_authorized"] is False
    assert r.payload["prediction"] is None


def test_second_family_declaration_alone_still_abstains():
    r = assess_declared_capability(context(family_id="S_ONLY"), declaration(family_id="S_ONLY"))
    assert r.scientific_verdict.value == "UNKNOWN"
    assert r.payload["routing_decision"] == "ABSTAIN"
    assert not r.payload["execution_authorized"]
    assert r.source_bindings == ()
    assert r.uncertainty.status == "UNKNOWN"


@pytest.mark.parametrize("temperature", [True, False, 0, -1, float("nan"), float("inf"), "298.15"])
def test_invalid_temperature_not_coerced(temperature):
    with pytest.raises(ValueError):
        context(measurement_temperature_K=temperature)


@pytest.mark.parametrize("changes", [
    {"domain_id": ""}, {"family_id": True}, {"candidate_id": " "},
    {"unit": "x" * 257}, {"composition_id": []}, {"schema_version": "v999"},
])
def test_invalid_context_rejected(changes):
    with pytest.raises(ValueError):
        context(**changes)


def test_undeclared_schema_unknown_fields_and_authority_rejected():
    row = context().to_dict()
    assert ResearchContext.from_mapping(row) == context()
    for bad in (row | {"execute": True}, {k: v for k, v in row.items() if k != "schema_version"},
                row | {"claim_authorized": True}, row | {"candidate_id": None}):
        with pytest.raises(ValueError):
            ResearchContext.from_mapping(bad)
    with pytest.raises(ValueError):
        assess_declared_capability(context(), declaration(), source_bindings=({"source_id": "fake"},))


def test_hash_valid_but_candidate_misbound_context_fails_query_and_manifest(tmp_path):
    row = assess_declared_capability(context(), declaration()).to_dict()
    row["payload"]["research_context"]["candidate_id"] = "another-candidate"
    body = {k: v for k, v in row.items() if k != "evidence_id"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    row["evidence_id"] = "evidence:sha256:" + hashlib.sha256(raw.encode()).hexdigest()
    path = tmp_path / "misbound.jsonl"
    path.write_text(json.dumps(row) + "\n")
    for gateway, tool in ((ReadOnlyEvidenceTools(path), "get_candidate_evidence"),
                          (ReadOnlyEvidenceManifestTools(path), "build_evidence_manifest")):
        with pytest.raises(ValueError, match="candidate mismatch"):
            gateway.call_tool(tool, {"candidate_id": row["candidate_id"]})


def test_family_is_metadata_not_inferred_composition_or_phase():
    c = context(family_id="S_ONLY", composition_id="fixture:oxide", structure_artifact_id=None)
    assert c.family_id == "S_ONLY"  # Contradiction is not silently 'corrected'.
    r = assess_declared_capability(c, declaration(family_id="S_ONLY"))
    assert r.scientific_verdict.value == "UNKNOWN"
    assert "FAMILY_LABEL_DOES_NOT_CERTIFY_COMPOSITION_STRUCTURE_OR_PHASE" in r.limitations


def test_retained_real_transport_receipt_does_not_promote_synthetic_evidence():
    from rhombus.tools.evidence_query import _verify_evidence_row
    root = Path(__file__).resolve().parents[1]
    report = json.loads((root / "data/development/0199.json").read_text())
    assert report["call_count"] == 6 and report["tool_count"] == 6 and report["session_closed"]
    assert report["autonomous_AI_selection_accuracy"] is None
    assert report["actual_model_token_usage"] is None
    assert not report["scientific_generalization_verified"] and not report["scientific_GO"]
    assert not report["production_enabled"] and not report["TEST121_accessed"]
    assert set(report["code_sha256"]) == {"rhombus/domain/context.py",
        "rhombus/tools/evidence_query.py", "scripts/tools/verify_domain_context.py"}
    for path, digest in report["code_sha256"].items():
        assert hashlib.sha256((root / path).read_bytes()).hexdigest() == digest
    for i, row in enumerate(report["evidence_records"], 1):
        _verify_evidence_row(row, lineno=i)
        assert row["source_bindings"][0]["source_type"] == "SYNTHETIC_FIXTURE"
        assert row["scientific_verdict"] in ("UNKNOWN", "NOT_APPLICABLE")
    for call in report["calls"]:
        result = call["response"]["structuredContent"]
        assert not result["claim_authorized"]
        if call["tool"] == "plan_scientific_task":
            assert not result["execution_authorized"] and result["dispatch_status"] == "NOT_SUBMITTED"
