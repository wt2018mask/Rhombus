"""CPU-only tests for frozen P1 execution-priority admission.

These tests deliberately avoid importing or initializing MACE/Torch calculators.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rudeus.mlip.priority import load_execution_priority_audit


ROOT = Path(__file__).resolve().parents[1]
PENDING = ROOT / "data" / "batches" / "pending_topcond20_ordered"
AUDIT = ROOT / "data" / "batches" / "audit" / "p1_topcond20_ordered_priority.json"


def test_frozen_ordered_v2_priority_matches_pending_cohort():
    order = load_execution_priority_audit(AUDIT, PENDING)

    assert len(order) == 13
    assert order[0] == "4e66d5af3e72b3e2"
    assert order[-1] == "3ef1d26bb53596de"
    assert len(order) == len(set(order))


def test_priority_rejects_pending_structure_tamper(tmp_path):
    pending = tmp_path / "pending"
    shutil.copytree(PENDING, pending)

    target = pending / "4e66d5af3e72b3e2.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["structure_dict"]["sites"][0]["abc"][0] += 0.001
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="pending structure_sha256 mismatch"):
        load_execution_priority_audit(AUDIT, pending)


def test_priority_rejects_policy_tamper(tmp_path):
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    audit["policy_id"] = "forged-policy"
    path = tmp_path / "priority.json"
    path.write_text(json.dumps(audit), encoding="utf-8")

    with pytest.raises(ValueError, match="policy_id mismatch"):
        load_execution_priority_audit(path, PENDING)
