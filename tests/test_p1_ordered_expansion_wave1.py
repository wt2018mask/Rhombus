"""CPU-only admission tests for ordered-expansion P1 wave1."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rudeus.mlip.priority import load_execution_priority_audit


ROOT = Path(__file__).resolve().parents[1]
PENDING = ROOT / "data" / "batches" / "pending_ordered_expansion_wave1_v1"
AUDIT = ROOT / "data" / "batches" / "audit" / "g_ordered_expansion_wave1_v1.json"


def test_ordered_expansion_wave1_manifest_matches_pending_cohort():
    report = json.loads(AUDIT.read_text(encoding="utf-8"))
    order = load_execution_priority_audit(AUDIT, PENDING)

    assert len(order) == 36
    assert order == report["wave1"]["batch_ids"]
    assert len(order) == len(set(order))
    assert report["wave1"]["cohort_identity_sha256"] == (
        "2229256d68c46da4ae2082158e8714a66bf8d2d8662cb53673863756eb74e78c"
    )


def test_ordered_expansion_wave1_rejects_pending_structure_tamper(tmp_path):
    pending = tmp_path / "pending"
    shutil.copytree(PENDING, pending)

    target = next(iter(sorted(pending.glob("*.json"))))
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["structure_dict"]["sites"][0]["abc"][0] += 0.001
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="pending structure_sha256 mismatch"):
        load_execution_priority_audit(AUDIT, pending)


def test_ordered_expansion_wave1_rejects_manifest_binding_tamper(tmp_path):
    report = json.loads(AUDIT.read_text(encoding="utf-8"))
    report["wave1"]["bindings"][0]["structure_sha256"] = "0" * 64
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="does not exactly match pending cohort"):
        load_execution_priority_audit(audit, PENDING)
