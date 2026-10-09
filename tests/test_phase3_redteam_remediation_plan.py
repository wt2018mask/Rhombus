"""Protect the Phase 3 adversarial remediation register from claim promotion.

Planning CI verifies fail-closed provenance and concrete adversarial work,
not that any security or science finding has actually been remediated.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "data/development/phase3_redteam_remediation_register_v1.json"
DOCS = ROOT / "docs/PHASE3_REDTEAM_REMEDIATION_PLAN_V1.md"
EXPECTED = {
    "RT-P0-01","RT-P0-02","RT-P0-03",
    "RT-P1-01","RT-P1-02","RT-P1-03","RT-P1-04","RT-P1-05",
    "RT-P2-01","RT-P2-02","RT-P2-03",
}

def _load():
    return json.loads(REGISTER.read_text(encoding="utf-8"))

def test_redteam_source_basis_and_historical_pr281_mismatch_explicit():
    data = _load()
    assert data["schema_version"] == "rhombus-phase3-adversarial-remediation-register-v1"
    assert data["report"]["historical_main_sha"] == "79a2a329e67927a370c8e44531f75d4dd4c1b340"
    assert data["report"]["historical_pr"] == 281
    assert data["reconciled_main"]["checkpoint_index"] == 117
    assert data["reconciled_main"]["pr_281_merged"] is True
    assert data["reconciled_main"]["github_synthetic_cross_job_status"] == "PASS_ONLY_SYNTHETIC"
    assert data["reconciled_main"]["effective_branch_protection_readable"] is False
    assert data["reconciled_main"]["branch_admin_verification"] == "PENDING"
    assert "historical" in DOCS.read_text(encoding="utf-8").lower()

def test_redteam_risk_registry_all_findings_have_adversarial_pass_gates():
    d = _load()
    by_id = {f["id"]: f for f in d["findings"]}
    assert set(by_id) == EXPECTED
    assert len(by_id) == len(d["findings"])
    assert sum(f["priority"] == "P0" for f in d["findings"]) == 3
    assert sum(f["priority"] == "P1" for f in d["findings"]) == 5
    assert sum(f["priority"] == "P2" for f in d["findings"]) == 3
    for f in d["findings"]:
        assert f["priority"] == f["id"][3:5]
        assert f["status"] not in {"PASS","RESOLVED","CLOSED"}
        assert f["gate"] == "FAIL_CLOSED_UNTIL_INDEPENDENT_EVIDENCE"
        assert all(isinstance(f[key], str) and len(f[key]) > 35
                   for key in ("claim","remediation","acceptance"))
        assert f["owner"]
    assert "COMPROMISED" not in {f["status"] for f in d["findings"]}

def test_scientific_and_compute_no_go_is_not_accidentally_lifted():
    d = _load()
    gate = d["release_gate"]
    assert gate["mode"] == "RESEARCH_PROTOTYPE_DIAGNOSTIC_ONLY"
    for key,value in gate.items():
        if key != "mode":
            assert value is False, key
    assert d["severity_order"] == ["P0","P1","P2"]
    ids = [x["id"] for x in d["milestones"]]
    assert ids == ["R0","R1","R2","R3","R4","R5"]
    assert all(m["targets"] and m["deliverable"] for m in d["milestones"])
    assert all(set(m["depends_on"]).issubset(set(ids[:i]))
               for i,m in enumerate(d["milestones"]))
    assert all("RT-P0-0"+str(i) in set(x for m in d["milestones"] for x in m["targets"])
               for i in (1,2,3))
    assert "R4" in d["milestones"][-1]["depends_on"]
    assert any("UNKNOWN" in x and "FAILED" in x for x in d["operating_rules"])

def test_roadmap_requires_external_steward_and_admin_no_hidden_secrets():
    data = _load()
    roles = {x["scope"] for x in data["operator_tasks"]}
    assert {"ADMIN","INDEPENDENT_STEWARD","RESEARCH_AUTHOR"} == roles
    content = DOCS.read_text(encoding="utf-8")
    for ref in EXPECTED:
        assert ref in content
    assert "403" in content
    assert "one-time" not in content or "replay" in content
    assert not any(x in json.dumps(data).lower() for x in ("github_pat_", "ghp_", "kaggle_api_token="))
