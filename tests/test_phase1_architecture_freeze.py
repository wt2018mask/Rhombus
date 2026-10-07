import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "data/development/rhombus_v2_architecture_freeze_v1.json"


def _load():
    return json.loads(FREEZE.read_text(encoding="utf-8"))


def test_phase1_architecture_freeze_is_explicit_and_conservative():
    doc = _load()
    assert doc["schema_version"] == "rhombus-v2-architecture-freeze-v1"
    assert doc["status"] == "FROZEN"
    assert doc["architecture"]["canonical_package"] == "rhombus"
    assert doc["architecture"]["legacy_package"] == "rudeus"
    assert doc["legacy_boundary"]["b6_b8"] == "DEFERRED_LEGACY_PATH"
    assert (
        doc["legacy_boundary"]["future_sealed_qualification_cohort"]
        == "DO_NOT_CONSUME_BEFORE_V2_QUALIFICATION_PROTOCOL_FREEZE"
    )
    assert doc["integration_targets"]["mcp"]["target"] is True
    assert doc["integration_targets"]["chatgpt_codex_plugin"]["target"] is True


def test_public_tool_catalog_uses_semantic_names_and_unique_contracts():
    doc = _load()
    contract = doc["public_tool_contract"]
    tools = contract["tool_catalog"]
    names = [tool["name"] for tool in tools]

    assert len(names) == len(set(names))
    assert set(contract["default_core_tools"]).issubset(names)
    assert "classify_transport_regime" in names
    assert "resolve_claims" in names
    assert "build_evidence_manifest" in names

    forbidden = re.compile(r"^(p\d(?:_?\d+)?|x|n|s)$", re.IGNORECASE)
    for tool in tools:
        assert re.fullmatch(r"[a-z][a-z0-9_]*", tool["name"])
        assert forbidden.fullmatch(tool["name"]) is None
        assert tool["required_inputs"]
        assert tool["side_effect_class"]
        assert tool["cost_class"]
        assert tool["implementation_status"]


def test_public_result_envelope_preserves_scientific_semantics():
    doc = _load()
    required = set(doc["public_tool_contract"]["required_result_fields"])
    assert {
        "operational_status",
        "scientific_verdict",
        "applicability",
        "uncertainty",
        "limitations",
        "evidence_ids",
        "artifact_ids",
        "protocol_id",
        "provenance",
    }.issubset(required)
    assert "PASS" in doc["public_tool_contract"]["allowed_scientific_verdict"]
    assert "ERROR" in doc["public_tool_contract"]["allowed_operational_status"]
    assert "FAR_OOD" in doc["public_tool_contract"]["allowed_domain_status"]


def test_phase1_freeze_does_not_claim_phase2_implementation():
    doc = _load()
    boundary = doc["phase2_boundary"]
    assert "public executable rhombus.tools exports" in boundary["not_implemented_by_this_freeze"]
    assert boundary["next_phase"] == "R2_PHASE2_EVIDENCE_LEDGER_COMPATIBILITY"
    assert boundary["next_action"] == "implement_v2_evidence_schemas_and_legacy_adapters"
