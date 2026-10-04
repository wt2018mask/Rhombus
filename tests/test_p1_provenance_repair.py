"""Tests for audited P1 provenance repair."""

import json

import pytest

from rudeus.mlip.repair_p1_provenance import (
    REPAIR_ID,
    repair_done_input_hashes,
)
from rudeus.mlip.sharding import make_batch_file


def _setup_pair(tmp_path):
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
    path = make_batch_file(pending, "obelix:test", 0, 42, "cfg", "ckpt", structure)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["result"] = {
        "p1_verdict": "KEEP_FOR_P2",
        "input_structure_sha256": "runtime-dependent-wrong-hash",
        "relaxed_energy_ev": -1.23,
    }
    done.mkdir()
    (done / path.name).write_text(json.dumps(payload), encoding="utf-8")
    return pending, done, path.name


def test_repair_changes_only_input_hash_and_records_old_value(tmp_path):
    pending, done, name = _setup_pair(tmp_path)
    before = json.loads((done / name).read_text(encoding="utf-8"))
    frozen = before["structure_sha256"]
    energy = before["result"]["relaxed_energy_ev"]

    report = repair_done_input_hashes(pending, done)
    after = json.loads((done / name).read_text(encoding="utf-8"))

    assert report["n_repaired"] == 1
    assert after["result"]["input_structure_sha256"] == frozen
    assert after["result"]["relaxed_energy_ev"] == energy
    repair = after["provenance_repairs"][-1]
    assert repair["repair_id"] == REPAIR_ID
    assert repair["old_value"] == "runtime-dependent-wrong-hash"
    assert repair["new_value"] == frozen


def test_repair_refuses_done_structure_tamper(tmp_path):
    pending, done, name = _setup_pair(tmp_path)
    payload = json.loads((done / name).read_text(encoding="utf-8"))
    payload["structure_dict"]["sites"][0]["abc"][0] = 0.125
    (done / name).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="done structure hash mismatch"):
        repair_done_input_hashes(pending, done)
