"""Tests for audited P2 FixCom-v2 provenance metadata repair."""

import json
from pathlib import Path

import numpy as np
import yaml

from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, protocol_config_hash
from rudeus.mlip.p2_traj import write_traj_artifact, verify_traj_artifact
from rudeus.mlip.repair_p2_fixcom_provenance import (
    NEW_VERSION,
    OLD_VERSION,
    REPAIR_ID,
    repair_p2_fixcom_provenance,
)


def _setup(tmp_path):
    root = tmp_path
    p2dir = root / "p2"
    trajdir = root / "traj"
    p2dir.mkdir()
    trajdir.mkdir()

    new_protocol = dict(P2_PROTOCOL_DEFAULTS)
    new_protocol["p2_protocol_version"] = NEW_VERSION
    old_protocol = dict(new_protocol)
    old_protocol["p2_protocol_version"] = OLD_VERSION
    old_hash = protocol_config_hash(old_protocol)

    cfg = {"p2": dict(new_protocol)}
    config_path = root / "config.yaml"
    config_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    bid = "abc123"
    payload = {
        "format_version": "p2-traj-v1",
        "batch_id": bid,
        "species": ["Li"],
        "cell": np.eye(3),
        "cell_mode": "fixed",
        "positions": np.array([[[0.1, 0.2, 0.3]]], dtype=float),
        "frame_steps": np.array([10], dtype=np.int64),
        "n_production_frames": 1,
        "n_atoms": 1,
        "timestep_fs": 1.0,
        "sample_interval_steps": 10,
        "equil_steps": 2,
        "production_steps_completed": 10,
        "seed": 7,
        "p2_config_hash": old_hash,
        "p2_protocol_version": OLD_VERSION,
    }
    art_path = trajdir / f"{bid}.npz"
    old_art_sha = write_traj_artifact(art_path, payload)

    rec = {
        "batch_id": bid,
        "job": {
            "p2_protocol": old_protocol,
            "p2_config_hash": old_hash,
        },
        "result": {
            "p2_verdict": "PASS",
            "dynamic_state": "PASS",
            "p2_protocol": old_protocol,
            "p2_protocol_version": OLD_VERSION,
            "p2_config_hash": old_hash,
            "trajectory_artifact": {
                "path": "traj/abc123.npz",
                "sha256": old_art_sha,
                "format_version": "p2-traj-v1",
                "n_production_frames": 1,
            },
            "provenance": {"trajectory_sha256": old_art_sha},
            "evidence_events": [{
                "artifact_hash": old_art_sha,
                "conditions": {
                    "p2_protocol_version": OLD_VERSION,
                    "p2_config_hash": old_hash,
                },
            }],
        },
    }
    (p2dir / f"{bid}.json").write_text(json.dumps(rec), encoding="utf-8")
    return root, p2dir, config_path, bid, old_art_sha


def test_repair_updates_metadata_and_hash_bindings_only(tmp_path):
    root, p2dir, config_path, bid, old_art_sha = _setup(tmp_path)

    before = np.load(root / "traj" / f"{bid}.npz", allow_pickle=False)["positions"].copy()
    report = repair_p2_fixcom_provenance(p2dir, root, config_path)
    after_rec = json.loads((p2dir / f"{bid}.json").read_text(encoding="utf-8"))
    result = after_rec["result"]
    after = np.load(root / "traj" / f"{bid}.npz", allow_pickle=False)["positions"].copy()

    assert report["n_repaired"] == 1
    assert result["p2_verdict"] == "PASS"
    assert result["p2_protocol_version"] == NEW_VERSION
    assert result["p2_config_hash"] == report["new_p2_config_hash"]
    assert result["trajectory_artifact"]["sha256"] != old_art_sha
    assert np.array_equal(before, after)
    verify_traj_artifact(
        root / result["trajectory_artifact"]["path"],
        result["trajectory_artifact"]["sha256"],
    )
    repair = after_rec["provenance_repairs"][-1]
    assert repair["repair_id"] == REPAIR_ID
    assert repair["scientific_trajectory_changed"] is False
    assert repair["scientific_verdict_changed"] is False
