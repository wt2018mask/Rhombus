from __future__ import annotations

import json
from pathlib import Path

from rhombus.evidence import DomainStatus, ScientificVerdict


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "data/development/rhombus_v2_evidence_ledger_freeze_v1.json"


def test_phase2_evidence_ledger_freeze_contract() -> None:
    row = json.loads(FREEZE.read_text(encoding="utf-8"))

    assert row["status"] == "FROZEN"
    contract = row["contract"]
    assert contract["evidence_schema_version"] == "rhombus-evidence-record-v1"
    assert contract["claim_schema_version"] == "rhombus-claim-record-v1"
    assert contract["missing_evidence_never_pass"] is True
    assert contract["operational_scientific_separation"] is True
    assert contract["claim_specific_applicability_required_for_pass"] is True

    assert "UNQUALIFIED" == DomainStatus.UNQUALIFIED.value
    assert "PASS" == ScientificVerdict.PASS.value

    supported = row["legacy_compatibility"]["supported"]
    assert {item["legacy_stage"] for item in supported} == {"P1", "P2", "P2.5"}
    assert len(supported) == 4
    assert row["identity_resolution"]["model_identity"] == (
        "exact checkpoint SHA-256 only"
    )
    assert row["qualification_boundary"]["sealed_future_cohort_consumed"] is False
    assert row["closure"]["phase2_complete"] is True
    assert row["closure"]["next_phase"] == "R2_PHASE3_DOMAIN_MAP_C0_C4"


def test_phase2_freeze_does_not_open_public_tool_surface() -> None:
    row = json.loads(FREEZE.read_text(encoding="utf-8"))
    public = row["public_api_boundary"]

    assert public["rhombus_tools_exports"] == "still gated"
    assert public["mcp_server"] == "not implemented"
    assert public["chatgpt_codex_plugin"] == "not implemented"
