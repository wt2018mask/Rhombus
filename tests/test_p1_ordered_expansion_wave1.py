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


def test_run_batches_overwrites_runtime_input_hash_with_frozen_batch_hash(tmp_path):
    from rudeus.mlip.sharding import make_batch_file, run_batches

    pending = tmp_path / "pending"
    done = tmp_path / "done"
    structure = {
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "charge": 0,
        "lattice": {
            "matrix": [[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]],
            "pbc": [True, True, True],
            "a": 3.0, "b": 3.0, "c": 3.0,
            "alpha": 90.0, "beta": 90.0, "gamma": 90.0,
            "volume": 27.0,
        },
        "properties": {},
        "sites": [{
            "species": [{"element": "Li", "occu": 1}],
            "abc": [0.0, 0.0, 0.0],
            "properties": {},
            "label": "Li",
            "xyz": [0.0, 0.0, 0.0],
        }],
    }
    path = make_batch_file(
        pending, "obelix:test", 0, 42, "cfg", "ckpt", structure
    )
    frozen = json.loads(path.read_text(encoding="utf-8"))["structure_sha256"]

    def fake_relax(_):
        return {
            "p1_verdict": "KEEP_FOR_P2",
            "input_structure_sha256": "runtime-dependent-wrong-hash",
        }

    summary = run_batches(
        pending, done, 0, 1, fake_relax, {"device": "cpu"}
    )
    assert summary["processed"] == 1
    result = json.loads((done / path.name).read_text(encoding="utf-8"))["result"]
    assert result["input_structure_sha256"] == frozen
