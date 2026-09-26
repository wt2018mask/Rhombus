"""P2.5 transport-evidence tests (CPU-only synthetics, no MLIP, no GPU).

Covers, with small in-memory trajectories written through the real
artifact path (build_traj_payload -> write_traj_artifact -> bound P2
result JSON):

  A. artifact integrity (valid/tampered/missing/malformed/production-only)
  B. PBC (unwrap recovery, wrapped-direct F3 failure mode, P2.5 unwraps)
  C. F3 integration (Brownian DIFFUSIVE, caged NONDIFFUSIVE, N=1
     INDETERMINATE, thin hopping INDETERMINATE, gate mirrors locked,
     no state overreach)
  D. block bootstrap (block method, determinism, insufficient blocks,
     nonzero uncertainty, no iid resampling)
  E. resume (fresh/skip-valid/malformed-recompute/ERROR-retry)
  F. atomic output (valid JSON read-back, tmp masquerade, no clobber)
  G. git preparation (exact staging, foreign-staged abort, no main push)

F3 thresholds and core estimators are NEVER retuned here; tests assert
the provisional gates only through the existing F3 entry points.
"""

import inspect
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from rudeus.filters.f3_diffusive import validate_diffusive_regime
from rudeus.mlip.gitpush import (
    GitSafetyError,
    p25_worker_branch,
    persist_p25_results,
    push_branch,
    validate_p25_result_file,
)
from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, protocol_config_hash
from rudeus.mlip.p2_traj import build_traj_payload, write_traj_artifact
from rudeus.mlip.p25 import (
    P25_ALPHA2_MAX_PROVISIONAL,
    P25_DEFAULTS,
    P25_SLOPE_MAX_PROVISIONAL,
    P25_SLOPE_MIN_PROVISIONAL,
    P25Error,
    analyze_p25,
    block_bootstrap_uncertainty,
    load_verified_artifact,
    p25_config_hash,
    run_p25_batches,
)
from rudeus.mlip.sharding import structure_dict_sha256


# --------------------------------------------------------------------------
# synthetic trajectory builders (unwrapped, Angstrom, 10 fs/frame)
# --------------------------------------------------------------------------

def _brownian(n_frames, n_li, seed, sigma=0.12):
    rng = np.random.default_rng(seed)
    traj = np.zeros((n_frames, n_li, 3))
    traj[1:] = np.cumsum(rng.normal(0, sigma, size=(n_frames - 1, n_li, 3)),
                         axis=0)
    return traj


def _caged(n_frames, n_li, seed, k=0.3, sigma=0.05):
    rng = np.random.default_rng(seed)
    traj = np.zeros((n_frames, n_li, 3))
    for t in range(1, n_frames):
        traj[t] = traj[t - 1] - k * traj[t - 1] \
            + rng.normal(0, sigma, size=(n_li, 3))
    return traj


def _hopping(n_frames, n_li, seed, spacing=2.8, mean_wait=60.0):
    rng = np.random.default_rng(seed)
    site = np.zeros((n_li, 3))
    traj = np.zeros((n_frames, n_li, 3))
    countdown = rng.exponential(mean_wait, size=n_li)
    nbrs = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0],
                     [0, -1, 0], [0, 0, 1], [0, 0, -1]]) * spacing
    for t in range(n_frames):
        countdown -= 1.0
        jumpers = countdown <= 0
        if jumpers.any():
            pick = rng.integers(0, 6, size=int(jumpers.sum()))
            site[jumpers] += nbrs[pick]
            cd = rng.exponential(mean_wait, size=int(jumpers.sum()))
            countdown[jumpers] = cd
        if t == 0:
            traj[t] = site + rng.normal(0, 0.12, size=(n_li, 3))
        else:
            traj[t] = traj[t - 1] + 0.5 * (site - traj[t - 1]) \
                + rng.normal(0, 0.12, size=(n_li, 3))
    return traj


def _record_from_traj(traj, species, box=10.0, equil_steps=200,
                      interval=10, seed=7):
    """Wrap an unwrapped mobile trajectory in a P2-like sampled record.

    Frames are stored WRAPPED (production sampler contract); P2.5 must
    unwrap them itself.
    """
    n_frames = traj.shape[0]
    cell = np.eye(3) * box
    wrapped = np.mod(traj, box)
    frames = []
    for k, pos in enumerate(wrapped):
        frames.append({"phase": "production", "positions": pos,
                       "md_step": equil_steps + (k + 1) * interval,
                       "temperature_K": 550.0, "energy_ev": -50.0,
                       "volume_A3": box ** 3, "pressure_GPa": 0.1,
                       "max_force_ev_A": 0.05, "finite": True,
                       "step_jump_A": 0.01})
    return {"species": list(species), "cell": cell, "frames": frames,
            "completed": True, "termination_note": None,
            "timestep_fs": 1.0, "sample_interval_steps": interval,
            "equil_steps": equil_steps,
            "production_steps": n_frames * interval,
            "thermostat": "langevin", "friction_fs_inv": 0.02, "seed": seed}


def _job(batch_id="aa00"):
    from pymatgen.core import Lattice, Structure
    proto = dict(P2_PROTOCOL_DEFAULTS)
    s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    return {"batch_id": batch_id, "child_material_id": "g1-test",
            "parent_id": "obelix:test",
            "relaxed_structure_dict": s,
            "relaxed_structure_sha256": structure_dict_sha256(s),
            "p1_checkpoint": None, "p1_worker": None,
            "p2_protocol": proto,
            "p2_config_hash": protocol_config_hash(proto),
            "seed": 11}


def _write_bound_p2(tmp_path, batch_id, traj, species, box=10.0,
                    p2_verdict="PASS", dynamic_state="PASS",
                    temperature_K=550.0, with_binding=True):
    """Persist artifact + bound P2 result JSON; return (p2_path, sha)."""
    record = _record_from_traj(traj, species, box=box)
    job = _job(batch_id)
    payload = build_traj_payload(record, job)
    traj_path = tmp_path / f"{batch_id}.npz"
    sha = write_traj_artifact(traj_path, payload)
    result = {"candidate_material_id": "g1-test", "batch_id": batch_id,
              "parent_id": "obelix:test",
              "p2_input_relaxed_sha256": job["relaxed_structure_sha256"],
              "p2_config_hash": job["p2_config_hash"],
              "p2_protocol_version": "p2-adaptive-v1-provisional",
              "seed": 11, "temperature_K": temperature_K,
              "dynamic_state": dynamic_state, "p2_verdict": p2_verdict,
              "provenance": {
                  "calc": {"checkpoint_name": "medium-mpa-0"},
                  "trajectory_sha256": sha},
              "evidence_events": []}
    if with_binding:
        result["trajectory_artifact"] = {
            "path": str(traj_path), "sha256": sha,
            "format_version": "p2-traj-v1",
            "n_production_frames": payload["n_production_frames"]}
    p2_path = tmp_path / f"{batch_id}.p2.json"
    p2_path.write_text(json.dumps({"batch_id": batch_id, "job": job,
                                   "result": result}), encoding="utf-8")
    return p2_path, sha


def _config(**over):
    cfg = dict(P25_DEFAULTS)
    cfg.update(n_bootstrap=50)  # test speed; production default is 200
    cfg.update(over)
    return cfg


def _run_batch_files(tmp_path, specs):
    """Specs: list of (batch_id, traj, species). Returns (p2_dir, cfg)."""
    p2_dir = tmp_path / "p2in"
    p2_dir.mkdir(parents=True, exist_ok=True)
    for batch_id, traj, species in specs:
        p2_path, _ = _write_bound_p2(tmp_path, batch_id, traj, species)
        p2_path.rename(p2_dir / f"{batch_id}.json")
    return p2_dir, _config()


# --------------------------------------------------------------------------
# A. artifact integrity
# --------------------------------------------------------------------------

def test_a_valid_artifact_loads_and_verifies(tmp_path):
    traj = _brownian(120, 4, seed=11)
    p2_path, sha = _write_bound_p2(tmp_path, "aa00", traj, ["Li"] * 4)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    artifact, binding = load_verified_artifact(payload)
    assert binding["sha256"] == sha
    assert artifact["n_production_frames"] == 120
    assert artifact["species"] == ["Li"] * 4
    assert artifact["positions"].shape == (120, 4, 3)


def test_a_tampered_artifact_fails_closed(tmp_path):
    traj = _brownian(120, 4, seed=11)
    p2_path, sha = _write_bound_p2(tmp_path, "bb01", traj, ["Li"] * 4)
    (tmp_path / "bb01.npz").write_bytes(b"corrupted-bytes")
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    with pytest.raises(P25Error, match="verification failed"):
        load_verified_artifact(payload)
    with pytest.raises(P25Error, match="verification failed"):
        analyze_p25(payload, _config())


def test_a_missing_artifact_path_fails_closed(tmp_path):
    traj = _brownian(120, 4, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "cc02", traj, ["Li"] * 4)
    (tmp_path / "cc02.npz").unlink()
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    with pytest.raises(P25Error, match="verification failed"):
        load_verified_artifact(payload)


def test_a_malformed_npz_fails_closed(tmp_path):
    bad = tmp_path / "dd03.npz"
    bad.write_bytes(b"not a numpy archive")
    payload = {"batch_id": "dd03",
               "result": {"trajectory_artifact": {
                   "path": str(bad), "sha256": "0" * 64,
                   "format_version": "p2-traj-v1"}}}
    with pytest.raises(P25Error, match="verification failed"):
        load_verified_artifact(payload)


def test_a_legacy_p2_without_binding_is_rejected(tmp_path):
    traj = _brownian(120, 4, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "ee04", traj, ["Li"] * 4,
                                 with_binding=False)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    with pytest.raises(P25Error, match="no trajectory_artifact binding"):
        load_verified_artifact(payload)


def test_a_production_only_frames_reach_analysis(tmp_path):
    # Equilibration-like prefix must not leak: artifact holds production
    # frames only, and the P2.5 frame count matches them exactly.
    traj = _brownian(90, 2, seed=11)
    record = _record_from_traj(traj, ["Li", "Li"])
    record["frames"] = ([{"phase": "equil",
                          "positions": np.zeros((2, 3)),
                          "md_step": 10}] + record["frames"])
    job = _job("ff05")
    payload = build_traj_payload(record, job)
    assert payload["n_production_frames"] == 90
    traj_path = tmp_path / "ff05.npz"
    sha = write_traj_artifact(traj_path, payload)
    p2 = {"batch_id": "ff05",
          "result": {"p2_verdict": "PASS", "dynamic_state": "PASS",
                     "temperature_K": 550.0, "seed": 11,
                     "p2_config_hash": job["p2_config_hash"],
                     "provenance": {"calc": {}},
                     "trajectory_artifact": {
                         "path": str(traj_path), "sha256": sha,
                         "format_version": "p2-traj-v1",
                         "n_production_frames": 90}}}
    res = analyze_p25(p2, _config())
    assert res["transport"]["n_frames"] == 90


# --------------------------------------------------------------------------
# B. PBC
# --------------------------------------------------------------------------

def test_b_unwrap_recovers_periodic_truth():
    rng = np.random.default_rng(99)
    box = 12.0
    cell = np.eye(3) * box
    true = np.zeros((400, 4, 3))
    true[1:] = np.cumsum(rng.normal(0, 0.5, size=(399, 4, 3)), axis=0)
    wrapped = np.mod(true, box)
    assert (np.abs(np.diff(wrapped, axis=0)).max(axis=(1, 2)) > box / 2).any()
    from rudeus.mlip.p2 import unwrap_trajectory
    rec = unwrap_trajectory(wrapped, cell)
    np.testing.assert_allclose(rec, true, atol=1e-9)


def test_b_wrapped_direct_to_f3_is_known_failure_mode():
    rng = np.random.default_rng(99)
    box = 12.0
    true = np.zeros((400, 4, 3))
    true[1:] = np.cumsum(rng.normal(0, 0.5, size=(399, 4, 3)), axis=0)
    wrapped = np.mod(true, box)
    species = ["Li"] * 4
    bad = validate_diffusive_regime(wrapped, species)
    good = validate_diffusive_regime(true, species)
    assert good.transport_state.value == "DIFFUSIVE"
    assert bad.transport_state.value != "DIFFUSIVE"  # false negative
    assert bad.log_slope < 0.4


def test_b_p25_always_unwraps_before_f3(tmp_path):
    rng = np.random.default_rng(99)
    box = 12.0
    true = np.zeros((400, 4, 3))
    true[1:] = np.cumsum(rng.normal(0, 0.5, size=(399, 4, 3)), axis=0)
    # Store the TRUE trajectory through the wrapped artifact path.
    p2_path, _ = _write_bound_p2(tmp_path, "pb01", true, ["Li"] * 4,
                                 box=box)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    res = analyze_p25(payload, _config())
    assert res["diagnostics"]["unwrapped"] is True
    assert res["transport_state"] == "DIFFUSIVE"
    assert res["point_transport_state"] == "DIFFUSIVE"


# --------------------------------------------------------------------------
# C. F3 integration
# --------------------------------------------------------------------------

def test_c_f3_gate_mirrors_locked_to_f3_defaults():
    sig = inspect.signature(validate_diffusive_regime)
    assert sig.parameters["min_slope_provisional"].default == \
        P25_SLOPE_MIN_PROVISIONAL == 0.75
    assert sig.parameters["max_slope_provisional"].default == \
        P25_SLOPE_MAX_PROVISIONAL == 1.30
    assert sig.parameters["max_alpha2_provisional"].default == \
        P25_ALPHA2_MAX_PROVISIONAL == 0.35


def test_c_brownian_is_provisionally_diffusive(tmp_path):
    traj = _brownian(400, 8, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "br01", traj, ["Li"] * 8)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    res = analyze_p25(payload, _config())
    assert res["transport_state"] == "DIFFUSIVE"
    assert res["point_transport_state"] == "DIFFUSIVE"
    assert res["transport_claim_status"] == "provisional"
    assert res["target_species"] == "Li"
    assert res["temperature_K"] == 550.0
    assert res["transport"]["n_mobile_ions"] == 8
    assert res["transport"]["uncertainty"]["status"] == "sufficient"
    assert res["evidence_events"][0]["level"] == "P2.5"


def test_c_caged_is_nondiffusive(tmp_path):
    traj = _caged(400, 8, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "cg01", traj, ["Li"] * 8)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    res = analyze_p25(payload, _config())
    assert res["transport_state"] == "NONDIFFUSIVE"
    assert res["point_transport_state"] == "NONDIFFUSIVE"


def test_c_single_ion_never_diffusive(tmp_path):
    traj = _brownian(400, 1, seed=22)  # point estimate would be DIFFUSIVE
    p2_path, _ = _write_bound_p2(tmp_path, "c101", traj, ["Li"])
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    res = analyze_p25(payload, _config())
    assert res["point_transport_state"] == "DIFFUSIVE"
    assert res["transport_state"] == "INDETERMINATE"
    assert any("insufficient_mobile_ions" in r
               for r in res["diagnostics"]["reasons"])


def test_c_thin_hopping_evidence_is_indeterminate(tmp_path):
    # Short hopping trajectory: tail alpha2 gate holds the point claim.
    traj = _hopping(100, 8, seed=22)
    p2_path, _ = _write_bound_p2(tmp_path, "c102", traj, ["Li"] * 8)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    res = analyze_p25(payload, _config())
    assert res["transport_state"] == "INDETERMINATE"
    assert res["transport_state"] != "DIFFUSIVE"


def test_c_no_state_overreach(tmp_path):
    traj = _brownian(400, 8, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "c103", traj, ["Li"] * 8)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    res = analyze_p25(payload, _config())
    blob = json.dumps(res).lower()
    assert "dynamic_state" not in res
    assert "existence_state" not in res
    assert "conductivity" not in blob
    assert "sigma_ne" not in blob
    assert "d_self" not in blob
    assert res["transport_claim_status"] == "provisional"


def test_c_zero_mobile_ions_is_indeterminate(tmp_path):
    traj = _brownian(200, 2, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "c104", traj, ["O", "O"])
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    res = analyze_p25(payload, _config())
    assert res["transport_state"] == "INDETERMINATE"
    assert res["point_transport_state"] == "INDETERMINATE"
    assert res["transport"]["n_mobile_ions"] == 0
    assert any("no_target_ions_found" in r for r in res["diagnostics"]["reasons"])


def test_c_two_frame_trajectory_is_indeterminate(tmp_path):
    traj = _brownian(2, 4, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "c104b", traj, ["Li"] * 4)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    res = analyze_p25(payload, _config())
    assert res["transport_state"] == "INDETERMINATE"
    assert res["point_transport_state"] == "INDETERMINATE"
    assert res["transport"]["log_slope"] is None
    assert any("insufficient_lag_points" in r for r in res["diagnostics"]["reasons"])


def test_c_missing_temperature_fails_closed(tmp_path):
    traj = _brownian(200, 4, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "c105", traj, ["Li"] * 4)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    del payload["result"]["temperature_K"]
    with pytest.raises(P25Error, match="temperature"):
        analyze_p25(payload, _config())


# --------------------------------------------------------------------------
# D. block bootstrap
# --------------------------------------------------------------------------

def test_d_bootstrap_is_block_based_and_nonzero(tmp_path):
    traj = _brownian(400, 8, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "c106", traj, ["Li"] * 8)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    res = analyze_p25(payload, _config())
    unc = res["transport"]["uncertainty"]
    assert unc["method"] == "block_bootstrap_origins"
    assert unc["status"] == "sufficient"
    assert unc["n_blocks"] >= 4
    slo, shi = unc["log_slope_ci"]
    assert shi - slo > 0.05  # not artificially narrow (iid gave ~0.01)
    alo, ahi = unc["tail_alpha2_ci"]
    assert ahi - alo > 1e-6
    assert not (alo == 0.0 and ahi == 0.0)
    assert "iid" not in json.dumps(unc).lower()


def test_d_bootstrap_is_deterministic(tmp_path):
    traj = _brownian(300, 8, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "c107", traj, ["Li"] * 8)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    r1 = analyze_p25(payload, _config())["transport"]["uncertainty"]
    r2 = analyze_p25(payload, _config())["transport"]["uncertainty"]
    assert r1["log_slope_ci"] == r2["log_slope_ci"]
    assert r1["tail_alpha2_ci"] == r2["tail_alpha2_ci"]


def test_d_insufficient_blocks_is_explicit(tmp_path):
    # 60 production frames -> 30 origins -> 1 block < min_blocks=4.
    traj = _brownian(60, 8, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "c108", traj, ["Li"] * 8)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    res = analyze_p25(payload, _config())
    unc = res["transport"]["uncertainty"]
    assert unc["status"] == "insufficient"
    assert unc.get("log_slope_ci") is None
    # No decisive transport claim may stand without uncertainty.
    if res["point_transport_state"] in ("DIFFUSIVE", "NONDIFFUSIVE"):
        assert res["transport_state"] == "INDETERMINATE"
        assert any("insufficient_uncertainty_blocks" in r
                   for r in res["diagnostics"]["reasons"])


def test_d_direct_bootstrap_helper_reports_blocks():
    traj = _brownian(400, 8, seed=11)
    out = block_bootstrap_uncertainty(traj, (0.3, 0.9), block_origins=20,
                                      n_bootstrap=30, ci_level=0.68, seed=7)
    assert out["status"] == "sufficient"
    assert out["n_blocks"] == 10
    assert out["block_length_origins"] == 20
    assert out["log_slope_ci"][0] < out["log_slope_ci"][1]
    assert out["tail_alpha2_ci"][0] < out["tail_alpha2_ci"][1]
    assert not (
        out["tail_alpha2_ci"][0] == 0.0
        and out["tail_alpha2_ci"][1] == 0.0
    )
    tiny = block_bootstrap_uncertainty(traj[:40], (0.3, 0.9),
                                       block_origins=20, n_bootstrap=30,
                                       ci_level=0.68, seed=7)
    assert tiny["status"] == "insufficient"


# --------------------------------------------------------------------------
# E. resume
# --------------------------------------------------------------------------

def test_e_fresh_run_processes_and_rerun_skips(tmp_path, monkeypatch):
    import rudeus.mlip.p25 as p25mod
    p2_dir, cfg = _run_batch_files(
        tmp_path, [("c201", _brownian(300, 8, seed=11), ["Li"] * 8)])
    out = tmp_path / "p25"
    calls = []
    real = p25mod.analyze_p25

    def counting(payload, config, worker_info=None, p2_result_path=""):
        calls.append(payload["batch_id"])
        return real(payload, config, worker_info, p2_result_path)

    monkeypatch.setattr(p25mod, "analyze_p25", counting)
    first = run_p25_batches(p2_dir, out, 0, 1, cfg, {"session": "t"})
    assert first["processed"] == 1 and first["wrote"] == ["c201"]
    assert calls == ["c201"]
    second = run_p25_batches(p2_dir, out, 0, 1, cfg, {"session": "t"})
    assert second["processed"] == 0 and second["skipped_done"] == 1
    assert second["wrote"] == [] and calls == ["c201"]  # no recompute


def test_e_malformed_done_is_recomputed_not_trusted(tmp_path):
    p2_dir, cfg = _run_batch_files(
        tmp_path, [("c202", _brownian(300, 8, seed=11), ["Li"] * 8)])
    out = tmp_path / "p25"
    run_p25_batches(p2_dir, out, 0, 1, cfg, {"session": "t"})
    (out / "c202.json").write_text("not json{{{", encoding="utf-8")
    again = run_p25_batches(p2_dir, out, 0, 1, cfg, {"session": "t"})
    assert again["stale_recomputed"] == 1 and again["wrote"] == ["c202"]
    payload = json.loads((out / "c202.json").read_text(encoding="utf-8"))
    assert payload["result"]["transport_state"] in (
        "DIFFUSIVE", "NONDIFFUSIVE", "INDETERMINATE")


def test_e_error_retry_semantics(tmp_path):
    p2_dir, cfg = _run_batch_files(
        tmp_path, [("c203", _brownian(300, 8, seed=11), ["Li"] * 8)])
    out = tmp_path / "p25"
    run_p25_batches(p2_dir, out, 0, 1, cfg, {"session": "t"})
    # Corrupt the artifact AFTER a valid result, then force recompute with
    # a changed config: analysis now fails -> ERROR record (fail closed).
    (tmp_path / "c203.npz").write_bytes(b"corrupted")
    cfg2 = _config(n_bootstrap=51)
    stale = run_p25_batches(p2_dir, out, 0, 1, cfg2, {"session": "t"})
    assert stale["stale_recomputed"] == 1
    payload = json.loads((out / "c203.json").read_text(encoding="utf-8"))
    assert payload["result"]["p25_verdict"] == "ERROR"
    assert payload["result"]["transport_state"] == "NOT_RUN"
    # ERROR without retry flag: skipped, not recomputed.
    skip = run_p25_batches(p2_dir, out, 0, 1, cfg2, {"session": "t"})
    assert skip["skipped_done"] == 1 and skip["processed"] == 0
    # ERROR with retry flag: recomputed (still ERROR: artifact still bad).
    retry = run_p25_batches(p2_dir, out, 0, 1, cfg2, {"session": "t"},
                            retry_errors=True)
    assert retry["retried_errors"] == 1 and retry["wrote"] == ["c203"]


def test_e_ineligible_p2_is_skipped_not_errored(tmp_path):
    p2_dir = tmp_path / "p2in"
    p2_dir.mkdir()
    # P2 FAIL verdict: transport analysis would be meaningless.
    traj = _brownian(200, 4, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "c204", traj, ["Li"] * 4,
                                 p2_verdict="FAIL", dynamic_state="FAIL")
    p2_path.rename(p2_dir / "c204.json")
    # Legacy P2 without artifact binding.
    legacy = {"batch_id": "c205",
              "result": {"p2_verdict": "PASS", "dynamic_state": "PASS",
                         "temperature_K": 550.0, "seed": 1,
                         "provenance": {}}}
    (p2_dir / "c205.json").write_text(json.dumps(legacy), encoding="utf-8")
    out = tmp_path / "p25"
    summary = run_p25_batches(p2_dir, out, 0, 1, _config(),
                              {"session": "t"})
    assert summary["skipped_ineligible"] == 2
    assert summary["processed"] == 0 and summary["errored"] == 0
    assert list(out.glob("*.json")) == []


# --------------------------------------------------------------------------
# F. atomic output
# --------------------------------------------------------------------------

def test_f_valid_json_read_back_and_no_tmp_masquerade(tmp_path):
    p2_dir, cfg = _run_batch_files(
        tmp_path, [("c206", _brownian(300, 8, seed=11), ["Li"] * 8)])
    out = tmp_path / "p25"
    summary = run_p25_batches(p2_dir, out, 0, 1, cfg, {"session": "t"})
    assert summary["wrote"] == ["c206"]
    assert list(out.glob("*.tmp")) == []
    payload = json.loads((out / "c206.json").read_text(encoding="utf-8"))
    assert payload["batch_id"] == "c206"
    assert payload["result"]["transport_state"] in (
        "DIFFUSIVE", "NONDIFFUSIVE", "INDETERMINATE")
    # A crashed worker's leftover temp file must not count as done.
    (out / "zz99.json.tmp").write_text('{"batch_id": "zz99", "half": ',
                                       encoding="utf-8")
    assert (out / "zz99.json").exists() is False


def test_f_valid_prior_survives_failed_recompute(tmp_path, monkeypatch):
    import rudeus.mlip.p25 as p25mod
    p2_dir, cfg = _run_batch_files(
        tmp_path, [("c207", _brownian(300, 8, seed=11), ["Li"] * 8)])
    out = tmp_path / "p25"
    run_p25_batches(p2_dir, out, 0, 1, cfg, {"session": "t"})
    before = (out / "c207.json").read_text(encoding="utf-8")

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated analyzer failure")

    monkeypatch.setattr(p25mod, "analyze_p25", _boom)
    # Prior is valid for the same input+config: resume skips BEFORE any
    # analysis, so the boom never fires and the file is untouched.
    summary = run_p25_batches(p2_dir, out, 0, 1, cfg, {"session": "t"})
    assert summary["skipped_done"] == 1
    assert (out / "c207.json").read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------
# G. git preparation
# --------------------------------------------------------------------------

def _init_repo(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    assert _git(repo, "init").returncode == 0
    assert _git(repo, "config", "user.email", "p25-test@local").returncode == 0
    assert _git(repo, "config", "user.name", "p25-test").returncode == 0
    assert _git(repo, "config", "commit.gpgsign", "false").returncode == 0
    (repo / "README.md").write_text("test repo", encoding="utf-8")
    assert _git(repo, "add", "--", "README.md").returncode == 0
    assert _git(repo, "commit", "-m", "init").returncode == 0
    return repo


def _git(repo, *args):
    return subprocess.run(["git", "-c", "commit.gpgsign=false", *args],
                          cwd=str(repo), capture_output=True, text=True)


def _staged(repo) -> list:
    r = _git(repo, "diff", "--cached", "--name-only")
    assert r.returncode == 0
    return sorted(l for l in r.stdout.splitlines() if l.strip())


def test_g_only_intended_p25_files_staged(tmp_path):
    import shutil
    if shutil.which("git") is None:
        pytest.skip("git binary not available")
    repo = _init_repo(tmp_path / "repo")
    p2_dir, cfg = _run_batch_files(tmp_path / "work",
                                   [("c208", _brownian(300, 8, seed=11),
                                     ["Li"] * 8)])
    out = tmp_path / "work" / "p25"
    run_p25_batches(p2_dir, out, 0, 1, cfg, {"session": "t"})
    p25dir = repo / "data" / "batches" / "p25"
    p25dir.mkdir(parents=True, exist_ok=True)
    (p25dir / "c208.json").write_text(
        (out / "c208.json").read_text(encoding="utf-8"), encoding="utf-8")
    (repo / "notes.txt").write_text("user scratch", encoding="utf-8")
    info = persist_p25_results(repo, p25dir, ["c208"],
                               "p25 test-worker shard 0/1: 1 processed")
    assert info["files"] == ["data/batches/p25/c208.json"]
    show = _git(repo, "show", "--name-only", "--format=", info["commit"])
    assert sorted(show.stdout.split()) == info["files"]
    assert _staged(repo) == []
    assert (repo / "notes.txt").read_text(encoding="utf-8") == "user scratch"


def test_g_staged_foreign_file_aborts_without_touching_index(tmp_path):
    import shutil
    if shutil.which("git") is None:
        pytest.skip("git binary not available")
    repo = _init_repo(tmp_path / "repo")
    p2_dir, cfg = _run_batch_files(tmp_path / "work",
                                   [("c209", _brownian(300, 8, seed=11),
                                     ["Li"] * 8)])
    out = tmp_path / "work" / "p25"
    run_p25_batches(p2_dir, out, 0, 1, cfg, {"session": "t"})
    p25dir = repo / "data" / "batches" / "p25"
    p25dir.mkdir(parents=True, exist_ok=True)
    (p25dir / "c209.json").write_text(
        (out / "c209.json").read_text(encoding="utf-8"), encoding="utf-8")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "user-plan.md").write_text("user work in progress",
                                       encoding="utf-8")
    assert _git(repo, "add", "--", "user-plan.md").returncode == 0
    with pytest.raises(GitSafetyError, match="unrelated files already staged"):
        persist_p25_results(repo, p25dir, ["c209"], "worker commit")
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head
    assert _staged(repo) == ["user-plan.md"]


def test_g_branch_naming_and_main_push_refusal():
    assert p25_worker_branch("kaggle-gpu-1", 3, 44) == \
        "worker/p25/kaggle-gpu-1-s3-of44"
    from rudeus.mlip.run_p25 import resolve_push_branch
    assert resolve_push_branch("auto", "w", 0, 2) == "worker/p25/w-s0-of2"
    with pytest.raises(GitSafetyError, match="main/master"):
        push_branch(".", "main")
    with pytest.raises(GitSafetyError, match="main/master"):
        push_branch(".", "master")


def test_g_malformed_result_refuses_to_stage(tmp_path):
    import shutil
    if shutil.which("git") is None:
        pytest.skip("git binary not available")
    repo = _init_repo(tmp_path / "repo")
    p25dir = repo / "data" / "batches" / "p25"
    p25dir.mkdir(parents=True, exist_ok=True)
    (p25dir / "bad01.json").write_text("corrupt{{{", encoding="utf-8")
    with pytest.raises(GitSafetyError):
        persist_p25_results(repo, p25dir, ["bad01"], "msg")
    assert _staged(repo) == []


# ---------------------------------------------------------------------------
# P2.5 v2 symmetric sufficiency regression
# ---------------------------------------------------------------------------

def test_v2_short_caged_negative_becomes_indeterminate(tmp_path):
    """A short trajectory cannot support a definitive negative claim."""
    # 60 frames -> fewer than min_blocks=4 with block_origins=20.
    traj = _caged(60, 8, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "v201", traj, ["Li"] * 8)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))
    res = analyze_p25(payload, _config())
    assert res["point_transport_state"] == "NONDIFFUSIVE"
    assert res["transport_state"] == "INDETERMINATE"
    assert res["transport"]["uncertainty"]["status"] == "insufficient"
    assert any(
        "insufficient_uncertainty_blocks" in reason
        for reason in res["diagnostics"]["reasons"]
    )


def test_v2_non_diffusive_requires_ci_to_exclude_diffusive_gate(monkeypatch, tmp_path):
    """A NONDIFFUSIVE point estimate is not enough when its CI overlaps."""
    traj = _caged(300, 8, seed=11)
    p2_path, _ = _write_bound_p2(tmp_path, "v202", traj, ["Li"] * 8)
    payload = json.loads(p2_path.read_text(encoding="utf-8"))

    def fake_uncertainty(*args, **kwargs):
        return {
            "method": "block_bootstrap_origins",
            "block_length_origins": 20,
            "n_bootstrap": 200,
            "ci_level": 0.68,
            "status": "sufficient",
            "reason": None,
            "n_blocks": 7,
            "log_slope_ci": [0.35, 1.19],
            "tail_alpha2_ci": [0.24, 0.46],
            "log_slope_bootstrap_mean": 0.7,
            "tail_alpha2_bootstrap_mean": 0.35,
        }

    monkeypatch.setattr(
        "rudeus.mlip.p25.block_bootstrap_uncertainty",
        fake_uncertainty,
    )
    res = analyze_p25(payload, _config())
    assert res["point_transport_state"] == "NONDIFFUSIVE"
    assert res["transport_state"] == "INDETERMINATE"
    assert any(
        "uncertainty_overlaps_diffusive_gate" in reason
        for reason in res["diagnostics"]["reasons"]
    )
