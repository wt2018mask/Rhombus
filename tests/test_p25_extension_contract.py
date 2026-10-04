"""Lightweight contracts for the canonical P2.5 evidence transition.

No MLIP/GPU work occurs here.  These tests lock the scientific state
transition, exact protocol, one-shot rule, source provenance binding, and
ID-independent admission semantics.
"""

import json

from rudeus.mlip.p2 import (
    P2_PROTOCOL_DEFAULTS,
    p2_job_seed,
    run_nvt_adaptive,
)
from rudeus.mlip.p25_extension import (
    ADMISSION_POLICY,
    CANONICAL_BASE_SEED,
    EXTENSION_POLICY,
    EXTENSION_PROTOCOL_VERSION,
    TRANSITION_VERSION,
    build_extension_manifest,
    build_extension_protocol,
    extension_protocol_hash,
    load_extension_manifest,
    write_extension_manifest,
)
from rudeus.schema import DynamicState
from rudeus.mlip.sharding import assign_shard
from rudeus.mlip import p25_transition_environment as envmod


def _write_sources(
    root,
    bid,
    *,
    transport_state="INDETERMINATE",
    n_mobile=4,
    min_mobile=2,
    uncertainty_status="insufficient",
    reasons=None,
    point_state="NONDIFFUSIVE",
    source_p2_protocol="p2-adaptive-v2-fixcom-constraint-provisional",
):
    p1d, p2d, p25d = [root / x for x in ("p1", "p2", "p25")]
    for d in (p1d, p2d, p25d):
        d.mkdir(exist_ok=True)

    relaxed = ("r" + bid)[:1] * 64
    traj = ("t" + bid)[:1] * 64
    checkpoint = "c" * 64
    seed = p2_job_seed(CANONICAL_BASE_SEED, bid)

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
            "p2_protocol_version": source_p2_protocol,
            "seed": seed,
            "trajectory_artifact": {"sha256": traj},
            "provenance": {"calc": {"sha256": checkpoint, "dtype": "float32"}},
        },
    }), encoding="utf-8")

    (p25d / f"{bid}.json").write_text(json.dumps({
        "batch_id": bid,
        "result": {
            "transport_state": transport_state,
            "point_transport_state": point_state,
            "sufficiency": {
                "n_mobile_ions": n_mobile,
                "min_mobile_ions": min_mobile,
            },
            "transport": {
                "uncertainty": {"status": uncertainty_status},
            },
            "diagnostics": {"reasons": reasons or []},
            "provenance": {
                "trajectory_artifact_sha256": traj,
                "p25_config_hash": "p25hash",
                "p25_version": "p25-f3-v2-symmetric-sufficiency-provisional",
                "p2_protocol_version": source_p2_protocol,
            },
        },
    }), encoding="utf-8")
    return p1d, p2d, p25d


def test_canonical_protocol_is_fixed_and_not_runtime_tunable():
    p = build_extension_protocol()
    assert p["p2_protocol_version"] == EXTENSION_PROTOCOL_VERSION
    assert p["trajectory_policy"] == EXTENSION_POLICY
    assert p["temperature_K"] == 550
    assert p["timestep_fs"] == 1.0
    assert p["equil_steps"] == 2000
    assert p["production_tier_schedule_provisional"] == [1000, 3000, 8000]
    assert p["production_steps"] == 8000
    assert p["sample_interval_steps"] == 10
    assert p["thermostat"] == "langevin"
    assert p["friction_fs_inv_provisional"] == 0.02
    assert p["fix_center_of_mass"] is True
    assert p["base_seed"] == 550
    assert p["force_full_production_for_transport"] is True
    assert extension_protocol_hash()


def test_canonical_transition_ignores_early_pass_but_stops_fail(monkeypatch):
    import rudeus.mlip.p2 as p2mod

    protocol = build_extension_protocol()
    calls = []

    def fake_segments(*args, prod_segments, segment_callback, **kwargs):
        total = 0
        snap = None
        for delta in prod_segments:
            total += delta
            snap = {
                "species": ["Li", "O"],
                "cell": [[4, 0, 0], [0, 4, 0], [0, 0, 4]],
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
        return snap

    monkeypatch.setattr(p2mod, "_run_nvt_segments", fake_segments)

    def always_pass(record, protocol):
        return DynamicState.PASS, {
            "n_production_frames": 100,
            "n_usable_frames": 100,
        }, []

    out = run_nvt_adaptive(
        {}, None, protocol, 7, "x", evaluate_fn=always_pass
    )
    assert calls == [(1000, False), (3000, False), (8000, True)]
    assert out["production_steps"] == 8000

    calls.clear()

    def fail_at_3000(record, protocol):
        state = (
            DynamicState.FAIL
            if record["production_steps"] >= 3000
            else DynamicState.PASS
        )
        return state, {
            "n_production_frames": 100,
            "n_usable_frames": 100,
        }, []

    out = run_nvt_adaptive(
        {}, None, protocol, 7, "x", evaluate_fn=fail_at_3000
    )
    assert calls == [(1000, False), (3000, True)]
    assert out["production_steps"] == 3000


def test_admission_is_id_independent_for_same_scientific_state(tmp_path):
    dirs = None
    for bid in ("03bc47ef27166988", "f0db485b49bce2f3"):
        dirs = _write_sources(
            tmp_path,
            bid,
            reasons=[
                "insufficient_uncertainty_blocks: too few origin blocks"
            ],
        )
    p1d, p2d, p25d = dirs
    manifest = build_extension_manifest(p1d, p2d, p25d)
    assert manifest["transition_version"] == TRANSITION_VERSION
    assert manifest["admission_policy"] == ADMISSION_POLICY
    assert manifest["n_authorized"] == 2
    assert {r["batch_id"] for r in manifest["candidates"]} == {
        "03bc47ef27166988",
        "f0db485b49bce2f3",
    }
    assert {
        r["admission_basis"] for r in manifest["candidates"]
    } == {"trajectory_statistical_sufficiency"}


def test_nonextendable_mobile_count_and_prior_extension_are_rejected(tmp_path):
    p1d, p2d, p25d = _write_sources(
        tmp_path,
        "245ce322c5ff3994",
        n_mobile=1,
        min_mobile=2,
    )
    _write_sources(
        tmp_path,
        "518ff3ccd9252e6f",
        source_p2_protocol=EXTENSION_PROTOCOL_VERSION,
    )
    manifest = build_extension_manifest(p1d, p2d, p25d)
    assert manifest["n_authorized"] == 0
    assert manifest["candidates"] == []


def test_manifest_binds_sources_protocol_seed_and_checkpoint(tmp_path):
    bid = "5369d16d453bfc74"
    p1d, p2d, p25d = _write_sources(
        tmp_path,
        bid,
        uncertainty_status="sufficient",
        reasons=[
            "uncertainty_overlaps_diffusive_gate: CI does not exclude gate"
        ],
    )

    manifest = build_extension_manifest(p1d, p2d, p25d)
    assert manifest["n_authorized"] == 1
    row = manifest["candidates"][0]
    assert row["source_p2_seed"] == p2_job_seed(CANONICAL_BASE_SEED, bid)
    assert row["source_p2_checkpoint_sha256"] == "c" * 64
    assert row["source_p2_calc_dtype"] == "float32"
    assert row["transition_protocol_hash"] == extension_protocol_hash()
    assert row["admission_basis"] == "uncertainty_gate_ambiguity"
    assert manifest["one_shot"] is True

    path = tmp_path / "auth.json"
    write_extension_manifest(p1d, p2d, p25d, path)
    assert load_extension_manifest(path, p1d, p2d, p25d) == {bid}

    # Any upstream provenance mutation invalidates the frozen transition.
    p25_path = p25d / f"{bid}.json"
    p25 = json.loads(p25_path.read_text(encoding="utf-8"))
    p25["result"]["provenance"]["p25_config_hash"] = "changed"
    p25_path.write_text(json.dumps(p25), encoding="utf-8")

    try:
        load_extension_manifest(path, p1d, p2d, p25d)
    except ValueError:
        pass
    else:
        raise AssertionError("mutated source must invalidate authorization")


def test_noncanonical_source_seed_fails_closed(tmp_path):
    bid = "71137be4704df025"
    p1d, p2d, p25d = _write_sources(tmp_path, bid)
    p2_path = p2d / f"{bid}.json"
    p2 = json.loads(p2_path.read_text(encoding="utf-8"))
    p2["result"]["seed"] += 1
    p2_path.write_text(json.dumps(p2), encoding="utf-8")

    try:
        build_extension_manifest(p1d, p2d, p25d)
    except ValueError as exc:
        assert "canonical batch-derived seed" in str(exc)
    else:
        raise AssertionError("noncanonical source seed must fail closed")


def test_two_shard_partition_is_disjoint_and_complete():
    ids = [
        "03bc47ef27166988",
        "245ce322c5ff3994",
        "518ff3ccd9252e6f",
        "5369d16d453bfc74",
        "71137be4704df025",
        "9437c63d0446ae9d",
        "9f7812a466402dd8",
        "a08649ae5622454d",
        "f0db485b49bce2f3",
    ]
    s0 = {bid for bid in ids if assign_shard(bid, 0, 2)}
    s1 = {bid for bid in ids if assign_shard(bid, 1, 2)}
    assert s0.isdisjoint(s1)
    assert s0 | s1 == set(ids)
    assert s0
    assert s1


def test_transition_environment_contract_fails_closed_on_drift(tmp_path, monkeypatch):
    frozen = {
        "environment_contract_version": envmod.ENV_CONTRACT_VERSION,
        "python": "3.12.13",
        "platform": "record-only",
        "torch": "2.10.0+cu128",
        "cuda_runtime": "12.8",
        "numpy": "2.0.2",
        "ase": "3.29.0",
        "mace": "0.3.16",
        "pymatgen": "2026.9.24",
        "pymatgen_core": "2026.9.23",
        "cudnn": 91002,
        "gpu_model": "Tesla T4",
    }
    path = tmp_path / "env.json"
    path.write_text(json.dumps(frozen), encoding="utf-8")

    monkeypatch.setattr(
        envmod,
        "collect_transition_environment",
        lambda: dict(frozen),
    )
    assert envmod.validate_transition_environment(path)["torch"] == "2.10.0+cu128"

    drifted = dict(frozen)
    drifted["torch"] = "2.11.0+cu128"
    monkeypatch.setattr(
        envmod,
        "collect_transition_environment",
        lambda: drifted,
    )
    try:
        envmod.validate_transition_environment(path)
    except RuntimeError as exc:
        assert "environment mismatch" in str(exc)
        assert "torch" in str(exc)
    else:
        raise AssertionError("runtime environment drift must fail closed")
