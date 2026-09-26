"""Tests for exact P2 authorization freezing and admission."""

import json

import pytest

from rudeus.mlip.freeze_p2_authorization import build_p2_authorization
from rudeus.mlip.p2 import load_authorization_manifest


def _write_p1(path, batch_id, verdict="KEEP_FOR_P2", p0="PLAUSIBLE", sha="a" * 64):
    payload = {
        "batch_id": batch_id,
        "parent_id": "obelix:test",
        "child_material_id": "g1-test",
        "generation_operator": "displace",
        "parent_chemical_family": "oxide",
        "p0_state": p0,
        "result": {
            "p1_verdict": verdict,
            "relaxed_structure_sha256": sha,
            "relaxed_structure_dict": {"sites": [{"label": "Li"}]},
        },
    }
    (path / f"{batch_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_freeze_and_load_exact_p2_authorization(tmp_path):
    done = tmp_path / "done"
    done.mkdir()
    _write_p1(done, "a1", sha="1" * 64)
    _write_p1(done, "b1", sha="2" * 64)
    _write_p1(done, "c1", verdict="FAIL_CONVERGENCE", sha="3" * 64)

    report = build_p2_authorization(done)
    assert report["expected_authorized"] == 2
    assert report["scientific_verdict_changed"] is False

    manifest = tmp_path / "auth.json"
    manifest.write_text(json.dumps(report), encoding="utf-8")
    assert load_authorization_manifest(manifest, done) == {"a1", "b1"}


def test_exact_p2_authorization_rejects_relaxed_sha_tamper(tmp_path):
    done = tmp_path / "done"
    done.mkdir()
    _write_p1(done, "a1", sha="1" * 64)

    report = build_p2_authorization(done)
    report["candidates"][0]["relaxed_structure_sha256"] = "9" * 64
    manifest = tmp_path / "auth.json"
    manifest.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="does not exactly match"):
        load_authorization_manifest(manifest, done)
