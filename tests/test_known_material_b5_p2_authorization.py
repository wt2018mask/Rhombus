import json
from pathlib import Path

import pytest

from rudeus.mlip.p2 import load_authorization_manifest


MANIFEST = Path("data/benchmarks/known_material/b5_p2_authorization_v1.json")


def _write_p1_done(root: Path, manifest: dict):
    root.mkdir(parents=True, exist_ok=True)
    for row in manifest["candidates"]:
        payload = {
            "batch_id": row["batch_id"],
            "p0_state": "PLAUSIBLE",
            "result": {
                "p1_verdict": "KEEP_FOR_P2",
                "relaxed_structure_sha256": row["relaxed_structure_sha256"],
            },
        }
        (root / f"{row['batch_id']}.json").write_text(json.dumps(payload))


def test_canonical_p2_authorization_exactly_matches_retained_p1_survivors(tmp_path):
    manifest = json.loads(MANIFEST.read_text())
    done = tmp_path / "p1"
    _write_p1_done(done, manifest)
    allow = load_authorization_manifest(MANIFEST, p1_done_dir=done)
    assert allow == {row["batch_id"] for row in manifest["candidates"]}
    assert manifest["cohort_identity_sha256"] == (
        "28c92e91c9ea2428b99b4fcfde757be8d2f29dcbbb52643c1faf0de0f22ea714"
    )
    assert manifest["decision"]["held_out_execution_authorized"] is False


def test_p2_authorization_fails_closed_on_relaxed_structure_substitution(tmp_path):
    manifest = json.loads(MANIFEST.read_text())
    done = tmp_path / "p1"
    _write_p1_done(done, manifest)
    target = done / "4ab81ca72174667c.json"
    payload = json.loads(target.read_text())
    payload["result"]["relaxed_structure_sha256"] = "0" * 64
    target.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="does not exactly match"):
        load_authorization_manifest(MANIFEST, p1_done_dir=done)
