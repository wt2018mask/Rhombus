"""Tests for P2 550 K NVT stability (replay harness + units, no MACE/CUDA)."""

import json

import numpy as np
import pytest

from rudeus.mlip.p2 import (
    P2_PROTOCOL_DEFAULTS,
    evaluate_p2,
    min_image_distances,
    p2_job_seed,
    partition_host_mobile,
    protocol_config_hash,
    run_p2_batches,
    unwrap_trajectory,
)
from rudeus.schema import DynamicState


def _protocol(**over):
    p = dict(P2_PROTOCOL_DEFAULTS)
    p.update(over)
    return p


def _base_cell(n_host=16, n_li=4, box=10.0):
    rng = np.random.default_rng(0)
    host = rng.uniform(0, box, size=(n_host, 3))
    li = rng.uniform(0, box, size=(n_li, 3))
    pos = np.vstack([host, li])
    species = ["O"] * n_host + ["Li"] * n_li
    return pos, species, np.eye(3) * box


def _record(pos0, species, cell, n_frames=120, host_sig=0.05, li_sig=0.1,
            drift=None, nan_at=None, contract=None):
    """Synthetic sampled record. drift: per-frame expansion factor slope."""
    rng = np.random.default_rng(1)
    frames = []
    n = len(species)
    host_idx = [i for i, s in enumerate(species) if s != "Li"]
    for t in range(n_frames):
        p = pos0.copy()
        p[host_idx] += rng.normal(0, host_sig, size=(len(host_idx), 3))
        li_idx = [i for i, s in enumerate(species) if s == "Li"]
        if li_idx:
            p[li_idx] += rng.normal(0, li_sig, size=(len(li_idx), 3))
        if contract is not None:
            p = pos0.mean(axis=0) + (p - pos0.mean(axis=0)) * (1 - contract * t)
        if drift is not None:
            p = p * (1 + drift * t)
        if nan_at is not None and t == nan_at:
            p[0, 0] = np.nan
        frames.append({"phase": "production", "positions": p,
                       "temperature_K": 550.0 + rng.normal(0, 12.0),
                       "energy_ev": -100.0 + rng.normal(0, 0.01),
                       "volume_A3": 1000.0,
                       "pressure_GPa": 0.1,
                       "max_force_ev_A": 0.05,
                       "finite": bool(np.all(np.isfinite(p)))})
    return {"species": species, "cell": cell, "frames": frames,
            "completed": True, "termination_note": None,
            "timestep_fs": 1.0, "sample_interval_steps": 10,
            "equil_steps": 200, "production_steps": 800,
            "thermostat": "langevin", "friction_fs_inv": 0.02, "seed": 7}


def test_protocol_hash_deterministic():
    a = protocol_config_hash(_protocol())
    assert protocol_config_hash(_protocol()) == a
    assert protocol_config_hash(_protocol(temperature_K=600.0)) != a
    assert p2_job_seed(550, "ab12cd34") == p2_job_seed(550, "ab12cd34")
    assert p2_job_seed(550, "ab12cd34") != p2_job_seed(550, "ab12cd35")


def test_partition_host_mobile_and_absent():
    part = partition_host_mobile(["O", "O", "Li", "Li"])
    assert part["n_host"] == 2 and part["n_mobile"] == 2
    assert part["mobile_species_absent"] is False
    bare = partition_host_mobile(["O", "Si"])
    assert bare["n_mobile"] == 0 and bare["mobile_species_absent"] is True


def test_unwrap_continuous_across_boundary():
    rng = np.random.default_rng(2)
    cell = np.eye(3) * 10.0
    steps = rng.normal(0, 0.3, size=(50, 3, 3))
    wrapped = np.mod(5.0 + np.cumsum(steps, axis=0), 10.0)
    unw = unwrap_trajectory(wrapped, cell)
    jumps = np.abs(np.diff(unw, axis=0)).max()
    assert jumps < 2.0  # no 10A PBC jumps remain


def test_stable_replay_passes():
    pos0, species, cell = _base_cell()
    state, metrics, reasons = evaluate_p2(
        _record(pos0, species, cell), _protocol())
    assert state == DynamicState.PASS, reasons
    assert metrics["n_production_frames"] == 120
    assert metrics["temp_mean_K"] == pytest.approx(550.0, abs=30.0)


def test_collapse_replay_fails():
    pos0, species, cell = _base_cell()
    state, metrics, reasons = evaluate_p2(
        _record(pos0, species, cell, contract=0.004), _protocol())
    assert state == DynamicState.FAIL, reasons
    assert any("volume drift" in r or "RMSD" in r or "overlap" in r
               or "coordination" in r for r in reasons)


def test_short_trajectory_indeterminate():
    pos0, species, cell = _base_cell()
    state, _, reasons = evaluate_p2(
        _record(pos0, species, cell, n_frames=5), _protocol())
    assert state == DynamicState.INDETERMINATE
    assert any("insufficient" in r for r in reasons)


def test_li_motion_with_collapse_is_fail_not_transport():
    pos0, species, cell = _base_cell(n_host=16, n_li=8)
    rec = _record(pos0, species, cell, li_sig=2.5, contract=0.004)
    state, metrics, _ = evaluate_p2(rec, _protocol())
    assert state == DynamicState.FAIL
    assert metrics["mobile_max_displacement_A"] > 1.0  # Li moved a lot...
    flat = json.dumps({"state": state.value, "metrics": metrics}).lower()
    assert "diffus" not in flat and "transport" not in flat  # ...still no claim


def test_nan_frame_is_fail():
    pos0, species, cell = _base_cell()
    state, _, reasons = evaluate_p2(
        _record(pos0, species, cell, nan_at=60), _protocol())
    assert state == DynamicState.FAIL
    assert any("numerical" in r for r in reasons)


def test_explosive_termination_is_fail_with_metrics():
    """Aborted-for-explosion runs are FAIL (explicit evidence), metrics kept."""
    pos0, species, cell = _base_cell()
    rec = _record(pos0, species, cell, n_frames=60)
    rec["completed"] = False
    rec["termination_note"] = "explosive-step"
    state, metrics, reasons = evaluate_p2(rec, _protocol())
    assert state == DynamicState.FAIL
    assert any("explosive" in r for r in reasons)
    assert metrics["n_production_frames"] == 60  # evidence preserved


def test_no_li_material_stays_transport_neutral():
    rng = np.random.default_rng(3)
    grid = np.array([[i, j, k] for i in (2.0, 6.0) for j in (2.0, 6.0)
                     for k in (2.0, 4.0, 8.0)])  # 12 sites, ~2.8A apart
    pos0 = grid + rng.normal(0, 0.05, size=grid.shape)
    species = ["O"] * 12
    state, metrics, _ = evaluate_p2(
        _record(pos0, species, cell=np.eye(3) * 10.0), _protocol())
    assert state == DynamicState.PASS
    assert metrics["mobile_species_absent"] is True
    assert metrics["mobile_ms_final_A2"] is None


def test_mic_step_jump_ignores_boundary_crossing():
    """A cell-length wrapped jump is ~0 under MIC, genuine motion is kept."""
    from rudeus.mlip.p2 import mic_step_jump

    cell = np.eye(3) * 8.0
    prev = np.array([[7.9, 4.0, 4.0], [1.0, 1.0, 1.0]])
    crossed = np.array([[0.1, 4.0, 4.0], [1.0, 1.0, 1.0]])  # wrapped +x face
    assert mic_step_jump(prev, crossed, cell) == pytest.approx(0.2)
    moved = np.array([[7.9, 4.0, 4.0], [2.5, 1.0, 1.0]])
    assert mic_step_jump(prev, moved, cell) == pytest.approx(1.5)


def test_p2_source_has_no_transport_machinery():
    from pathlib import Path
    for name in ("rudeus/mlip/p2.py", "rudeus/mlip/run_p2.py"):
        src = Path(name).read_text(encoding="utf-8")
        assert "TransportState" not in src, name
        assert "validate_diffusive" not in src, name
        assert "is_diffusive" not in src, name


def _p1_done_record(tmp_path, batch_id, struct_dict, verdict="KEEP_FOR_P2"):
    from rudeus.mlip.sharding import structure_dict_sha256
    rec = {"batch_id": batch_id,
           "child_material_id": "g1-test",
           "parent_id": "obelix:test",
           "result": {"p1_verdict": verdict,
                      "relaxed_structure_dict": struct_dict,
                      "relaxed_structure_sha256":
                          structure_dict_sha256(struct_dict)}}
    (tmp_path / f"{batch_id}.json").write_text(json.dumps(rec),
                                               encoding="utf-8")


def test_p2_resume_retry_and_ineligible(tmp_path):
    from pymatgen.core import Lattice, Structure
    from rudeus.mlip.sharding import structure_dict_sha256

    p1done, p2out = tmp_path / "p1done", tmp_path / "p2"
    p1done.mkdir()
    a = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    b = Structure(Lattice.cubic(5.0), ["Li", "O"],
                  [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    _p1_done_record(p1done, "aa00", a)
    _p1_done_record(p1done, "bb01", b, verdict="FAIL_CONVERGENCE")

    calls = []

    def stub(job):
        calls.append(job["batch_id"])
        return {"p2_verdict": "PASS",
                "dynamic_state": "PASS",
                "p2_input_relaxed_sha256": job["relaxed_structure_sha256"],
                "p2_config_hash": job["p2_config_hash"]}

    proto = _protocol()
    s = run_p2_batches(p1done, p2out, 0, 1, stub, proto)
    assert calls == ["aa00"]  # ineligible P1 record never attempted
    assert s["processed"] == 1 and s["skipped_ineligible"] == 1

    again = run_p2_batches(p1done, p2out, 0, 1, stub, proto)
    assert again["skipped_done"] == 1 and again["processed"] == 0
    assert calls == ["aa00"]  # idempotent rerun

    # tampered output (wrong input hash) is recomputed, never trusted
    tampered = json.loads((p2out / "aa00.json").read_text(encoding="utf-8"))
    tampered["result"]["p2_input_relaxed_sha256"] = "0" * 64
    (p2out / "aa00.json").write_text(json.dumps(tampered), encoding="utf-8")
    fix = run_p2_batches(p1done, p2out, 0, 1, stub, proto)
    assert fix["stale_recomputed"] == 1 and calls == ["aa00", "aa00"]
    restored = json.loads((p2out / "aa00.json").read_text(encoding="utf-8"))
    assert restored["result"]["p2_input_relaxed_sha256"] == \
        structure_dict_sha256(a)

    # ERROR records skip by default, recompute only with the flag
    err = json.loads((p2out / "aa00.json").read_text(encoding="utf-8"))
    err["result"] = {"p2_verdict": "ERROR", "dynamic_state": "NOT_RUN",
                     "error_type": "X", "error_message": "y",
                     "p2_input_relaxed_sha256": structure_dict_sha256(a),
                     "p2_config_hash": protocol_config_hash(proto)}
    (p2out / "aa00.json").write_text(json.dumps(err), encoding="utf-8")
    assert run_p2_batches(p1done, p2out, 0, 1, stub, proto)["skipped_done"] == 1
    assert calls == ["aa00", "aa00"]
    assert run_p2_batches(p1done, p2out, 0, 1, stub, proto,
                          retry_errors=True)["retried_errors"] == 1
    assert calls == ["aa00", "aa00", "aa00"]

    # tampered output (wrong config hash) is recomputed, never trusted
    tampered = json.loads((p2out / "aa00.json").read_text(encoding="utf-8"))
    tampered["result"]["p2_config_hash"] = "0" * 16
    (p2out / "aa00.json").write_text(json.dumps(tampered), encoding="utf-8")
    fix = run_p2_batches(p1done, p2out, 0, 1, stub, proto)
    assert fix["stale_recomputed"] == 1 and calls == ["aa00"] * 4
    restored = json.loads((p2out / "aa00.json").read_text(encoding="utf-8"))
    assert restored["result"]["p2_config_hash"] == protocol_config_hash(proto)



def _dense_grid(n_per_dim=3, spacing=2.8, n_li=4):
    """Dense crystal-like fixture (mean NN ~ spacing) for gate-boundary tests.

    Li placed at body-center interstitial offsets (never overlapping framework).
    """
    grid = np.array([[[i, j, k] for k in range(n_per_dim)]
                     for j in range(n_per_dim)
                     for i in range(n_per_dim)],
                    dtype=float).reshape(-1, 3) * spacing
    off = (np.array([[i, j, k] for i in range(n_per_dim)
                     for j in range(n_per_dim)
                     for k in range(n_per_dim)],
                    dtype=float).reshape(-1, 3) + 0.5) * spacing
    box = n_per_dim * spacing
    li = np.mod(off[:n_li], box)
    pos = np.vstack([grid, li])
    species = ["O"] * len(grid) + ["Li"] * n_li
    return pos, species, np.eye(3) * n_per_dim * spacing


def test_uncorroborated_lindemann_is_indeterminate_not_fail():
    """Task 3: Lindemann excursion with healthy mind/coord/RMS/thermal is
    conflicting evidence -> INDETERMINATE (marginal), never PASS, never FAIL."""
    pos0, species, cell = _dense_grid()
    rec = _record(pos0, species, cell, n_frames=120, host_sig=0.24, li_sig=0.1)
    state, metrics, reasons = evaluate_p2(rec, _protocol())
    assert 0.20 < metrics["lindemann_provisional"] < 0.30, metrics
    assert metrics["host_rmsd_final_A"] < 0.7
    assert metrics["min_distance_traj_A"] > 1.2
    assert state == DynamicState.INDETERMINATE
    assert any("marginal-lindemann-uncorroborated" in r for r in reasons)


def test_corroborated_lindemann_is_fail():
    """Same excursion + collapsed min-distance -> FAIL with corroboration note."""
    pos0, species, cell = _dense_grid()
    rec = _record(pos0, species, cell, n_frames=120, host_sig=0.24, li_sig=0.1)
    for f in rec["frames"]:
        f["positions"][:2] = f["positions"][0]  # force one overlapping pair
    state, metrics, reasons = evaluate_p2(rec, _protocol())
    assert metrics["lindemann_provisional"] > 0.20
    assert state == DynamicState.FAIL
    assert any("corroborating evidence" in r for r in reasons)


def test_volume_drift_alone_never_fails():
    """Task 3 Step 8: NVT volume drift is diagnostic-only, not a FAIL gate."""
    pos0, species, cell = _dense_grid()
    rec = _record(pos0, species, cell, n_frames=120)
    for t, f in enumerate(rec["frames"]):
        f["volume_A3"] = 1000.0 * (1 + 0.5 * t / len(rec["frames"]))
    state, metrics, _ = evaluate_p2(rec, _protocol())
    assert metrics["volume_drift_fraction"] == pytest.approx(0.5 * 119 / 120)
    assert state == DynamicState.PASS  # drift recorded, never gated


def test_too_few_mobile_ions_is_indeterminate():
    """b0e223dc analogue: 2 Li with otherwise healthy trajectory -> INDETERMINATE."""
    pos0, species, cell = _dense_grid(n_li=2)
    state, _, reasons = evaluate_p2(
        _record(pos0, species, cell, n_frames=120), _protocol())
    assert state == DynamicState.INDETERMINATE
    assert any("mobile ions" in r for r in reasons)
