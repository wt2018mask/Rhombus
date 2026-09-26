"""Lightweight contract tests for P2.5 transport-evidence extension."""

import json

from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, run_nvt_adaptive
from rudeus.mlip.p25_extension import (
    build_extension_manifest,
    load_extension_manifest,
    write_extension_manifest,
)
from rudeus.mlip.run_p25_extension import (
    EXTENSION_POLICY,
    EXTENSION_PROTOCOL_VERSION,
    build_extension_protocol,
)
from rudeus.schema import DynamicState


def test_extension_protocol_is_fixed_and_separate():
    cfg = {"p2": dict(P2_PROTOCOL_DEFAULTS)}
    p = build_extension_protocol(cfg)
    assert p["p2_protocol_version"] == EXTENSION_PROTOCOL_VERSION
    assert p["trajectory_policy"] == EXTENSION_POLICY
    assert p["production_tier_schedule_provisional"] == [1000, 3000, 8000]
    assert p["production_steps"] == 8000
    assert p["force_full_production_for_transport"] is True
    assert p["fix_center_of_mass"] is True


def test_extension_ignores_early_pass_but_stops_fail(monkeypatch):
    import rudeus.mlip.p2 as p2mod

    protocol = dict(P2_PROTOCOL_DEFAULTS)
    protocol.update({
        "production_tier_schedule_provisional": [1000, 3000, 8000],
        "production_steps": 8000,
        "force_full_production_for_transport": True,
    })

    calls = []
    def fake_segments(*args, prod_segments, segment_callback, **kwargs):
        total = 0
        for delta in prod_segments:
            total += delta
            snap = {
                "species": ["Li", "O"],
                "cell": [[4,0,0],[0,4,0],[0,0,4]],
                "frames": [],
                "completed": True,
                "termination_note": None,
                "timestep_fs": 1.0,
                "sample_interval_steps": 10,
                "equil_steps": 2000,
                "production_steps": total,
            }
            stop = segment_callback(total, snap, False)
            calls.append((total, stop))
            if stop:
                break
        snap["production_steps"] = total
        return snap

    monkeypatch.setattr(p2mod, "_run_nvt_segments", fake_segments)

    def always_pass(record, protocol):
        return DynamicState.PASS, {"n_production_frames": 100, "n_usable_frames": 100}, []

    out = run_nvt_adaptive({}, None, protocol, 7, "x", evaluate_fn=always_pass)
    assert calls == [(1000, False), (3000, False), (8000, True)]
    assert out["production_steps"] == 8000

    calls.clear()
    def fail_at_3000(record, protocol):
        state = DynamicState.FAIL if record["production_steps"] >= 3000 else DynamicState.PASS
        return state, {"n_production_frames": 100, "n_usable_frames": 100}, []

    out = run_nvt_adaptive({}, None, protocol, 7, "x", evaluate_fn=fail_at_3000)
    assert calls == [(1000, False), (3000, True)]
    assert out["production_steps"] == 3000


def test_extension_manifest_exact_binds_sources(tmp_path):
    p1d, p2d, p25d = [tmp_path / x for x in ("p1", "p2", "p25")]
    for d in (p1d, p2d, p25d):
        d.mkdir()
    bid = "abc123"
    relaxed = "r" * 64
    traj = "t" * 64

    (p1d / f"{bid}.json").write_text(json.dumps({
        "batch_id": bid,
        "result": {
            "p1_verdict": "KEEP_FOR_P2",
            "relaxed_structure_sha256": relaxed,
        },
    }), encoding="utf-8")
    (p2d / f"{bid}.json").write_text(json.dumps({
        "batch_id": bid,
        "result": {
            "p2_verdict": "PASS",
            "p2_input_relaxed_sha256": relaxed,
            "p2_config_hash": "p2hash",
            "trajectory_artifact": {"sha256": traj},
        },
    }), encoding="utf-8")
    (p25d / f"{bid}.json").write_text(json.dumps({
        "batch_id": bid,
        "result": {
            "transport_state": "INDETERMINATE",
            "provenance": {
                "trajectory_artifact_sha256": traj,
                "p25_config_hash": "p25hash",
            },
        },
    }), encoding="utf-8")

    manifest = build_extension_manifest(p1d, p2d, p25d)
    assert manifest["n_authorized"] == 1
    assert manifest["candidates"][0]["batch_id"] == bid

    path = tmp_path / "auth.json"
    write_extension_manifest(p1d, p2d, p25d, path)
    assert load_extension_manifest(path, p1d, p2d, p25d) == {bid}

    # Any source mutation invalidates the frozen authorization.
    p25 = json.loads((p25d / f"{bid}.json").read_text(encoding="utf-8"))
    p25["result"]["provenance"]["p25_config_hash"] = "changed"
    (p25d / f"{bid}.json").write_text(json.dumps(p25), encoding="utf-8")
    try:
        load_extension_manifest(path, p1d, p2d, p25d)
    except ValueError:
        pass
    else:
        raise AssertionError("mutated source must invalidate authorization")
