"""P2 trajectory artifact tests (persistence only, no science).

Covers the P2 -> P2.5 handoff increment using small synthetic in-memory
records only — never MACE, never GPU, never the 44-candidate campaign:

  A. artifact contents (positions, species, cell, steps, sampling +
     identity metadata, format version)
  B. production slicing (equilibration excluded, exact frame indices)
  C. deterministic serialization (same logical artifact -> same SHA256)
  D. artifact verification (correct passes; modified/missing fail)
  E. P2 result binding (trajectory_artifact block == provenance hash ==
     verifiable file; no transport_state; legacy path unbound)
  F. failure semantics (fail closed; no partial final artifact; valid
     pre-existing artifact never clobbered by a failed rewrite)
  G. git persistence (bound result + verified artifact commit together;
     legacy/ERROR results commit JSON-only)

P2 science (thresholds, gates, tiers) is NOT exercised beyond reusing
build_p2_result; existing P2 tests lock those semantics.
"""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from rudeus.mlip.p2 import (
    P2_PROTOCOL_DEFAULTS,
    build_p2_result,
    protocol_config_hash,
    run_p2_batches,
)
from rudeus.mlip.p2_traj import (
    P2_TRAJ_FORMAT_VERSION,
    TrajectoryArtifactError,
    build_traj_payload,
    canonical_traj_bytes,
    load_traj_artifact,
    traj_sha256,
    verify_traj_artifact,
    write_traj_artifact,
)

CALC_INFO = {"checkpoint_name": "mace_mp:medium-mpa-0",
             "url": "pinned", "sha256": "pinned-sha",
             "device": "cpu", "dtype": "float32"}


def _protocol(**over):
    p = dict(P2_PROTOCOL_DEFAULTS)
    p.update(over)
    return p


def _mixed_record(n_equili=20, n_prod=10, n_host=4, n_li=2, box=6.0,
                  equil_steps=200, interval=10, seed=7, with_md_step=True):
    """Synthetic sampled record with equil + production frames on cadence.

    md_step follows the sampler contract: total MD steps completed at
    sampling (multiples of `interval`; equil samples at interval..equil,
    production samples at equil+interval..).
    """
    rng = np.random.default_rng(3)
    species = ["O"] * n_host + ["Li"] * n_li
    cell = np.eye(3) * box
    base = rng.uniform(0, box, size=(len(species), 3))
    frames = []
    for k in range(1, n_equili + 1):
        p = base + rng.normal(0, 0.02, size=base.shape)
        frames.append({"phase": "equil", "positions": p,
                       "md_step": k * interval,
                       "temperature_K": 550.0, "energy_ev": -50.0,
                       "volume_A3": box ** 3, "pressure_GPa": 0.1,
                       "max_force_ev_A": 0.05, "finite": True,
                       "step_jump_A": 0.01})
    for k in range(1, n_prod + 1):
        p = base + rng.normal(0, 0.05, size=base.shape)
        frames.append({"phase": "production", "positions": p,
                       "md_step": equil_steps + k * interval,
                       "temperature_K": 550.0, "energy_ev": -50.0,
                       "volume_A3": box ** 3, "pressure_GPa": 0.1,
                       "max_force_ev_A": 0.05, "finite": True,
                       "step_jump_A": 0.01})
    if not with_md_step:
        for f in frames:
            del f["md_step"]
    return {"species": species, "cell": cell, "frames": frames,
            "completed": True, "termination_note": None,
            "timestep_fs": 1.0, "sample_interval_steps": interval,
            "equil_steps": equil_steps,
            "production_steps": n_prod * interval,
            "thermostat": "langevin", "friction_fs_inv": 0.02, "seed": seed}


def _job(batch_id="aa00", proto=None):
    from rudeus.mlip.sharding import structure_dict_sha256
    from pymatgen.core import Lattice, Structure
    s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    proto = proto if proto is not None else _protocol()
    return {"batch_id": batch_id, "child_material_id": "g1-test",
            "parent_id": "obelix:test",
            "relaxed_structure_dict": s,
            "relaxed_structure_sha256": structure_dict_sha256(s),
            "p1_checkpoint": None, "p1_worker": None,
            "p2_protocol": proto,
            "p2_config_hash": protocol_config_hash(proto),
            "seed": 11}


# --------------------------------------------------------------------------
# A. artifact contents
# --------------------------------------------------------------------------

def test_a_payload_carries_self_describing_contents():
    record = _mixed_record()
    job = _job()
    payload = build_traj_payload(record, job)
    assert payload["format_version"] == P2_TRAJ_FORMAT_VERSION
    assert payload["batch_id"] == "aa00"
    assert payload["species"] == ["O"] * 4 + ["Li"] * 2  # exact ASE order
    assert payload["cell"].shape == (3, 3)
    assert payload["cell_mode"] == "fixed"
    assert payload["positions"].shape == (10, 6, 3)  # prod frames only
    assert payload["positions"].dtype == np.float64
    assert list(payload["frame_steps"]) == [10 * k for k in range(1, 11)]
    assert payload["timestep_fs"] == 1.0
    assert payload["sample_interval_steps"] == 10
    assert payload["equil_steps"] == 200
    assert payload["production_steps_completed"] == 100
    assert payload["seed"] == 7
    assert payload["p2_config_hash"] == job["p2_config_hash"]
    assert payload["p2_protocol_version"] == "p2-adaptive-v1-provisional"
    assert payload["n_production_frames"] == 10
    assert payload["n_atoms"] == 6


# --------------------------------------------------------------------------
# B. production slicing
# --------------------------------------------------------------------------

def test_b_only_production_frames_persisted_with_exact_indices():
    record = _mixed_record(n_equili=20, n_prod=10)
    payload = build_traj_payload(record, _job())
    # Equilibration positions must not leak into the artifact: every
    # persisted frame must equal its production source frame exactly.
    prod_src = [f["positions"] for f in record["frames"]
                if f.get("phase") == "production"]
    assert len(prod_src) == 10
    for got, want in zip(payload["positions"], prod_src):
        np.testing.assert_array_equal(got, want)
    # Indices are production-relative 1-based MD steps on cadence.
    steps = payload["frame_steps"]
    assert int(steps[0]) == 10  # first production sample, not equil
    assert int(steps[-1]) == 100  # last production step executed
    assert bool((np.diff(steps) == 10).all())
    # Wrapped (not unwrapped): values stay inside the simulation box.
    assert bool((payload["positions"] >= 0).all())
    assert bool((payload["positions"] < 6.0).all())


def test_b_missing_md_step_fails_closed():
    record = _mixed_record(with_md_step=False)
    with pytest.raises(TrajectoryArtifactError, match="md_step"):
        build_traj_payload(record, _job())


def test_b_empty_production_slice_is_truthful_not_fabricated(tmp_path):
    record = _mixed_record(n_equili=5, n_prod=0)
    payload = build_traj_payload(record, _job())
    assert payload["n_production_frames"] == 0
    assert payload["positions"].shape == (0, 6, 3)
    sha = write_traj_artifact(tmp_path / "empty.npz", payload)
    back = verify_traj_artifact(tmp_path / "empty.npz", sha)
    assert back["n_production_frames"] == 0


# --------------------------------------------------------------------------
# C. deterministic serialization
# --------------------------------------------------------------------------

def test_c_same_logical_artifact_same_sha_across_writes(tmp_path):
    record = _mixed_record()
    job = _job()
    p1 = build_traj_payload(record, job)
    p2 = build_traj_payload(record, job)
    assert canonical_traj_bytes(p1) == canonical_traj_bytes(p2)
    assert traj_sha256(p1) == traj_sha256(p2)
    a = tmp_path / "run-a"
    b = tmp_path / "run-b"
    a.mkdir()
    b.mkdir()
    sha1 = write_traj_artifact(a / "aa00.npz", p1)
    sha2 = write_traj_artifact(b / "aa00.npz", p2)
    assert sha1 == sha2  # temp filenames/dirs do not enter the hash
    assert len(sha1) == 64


def test_c_hash_is_stable_under_layout_normalization():
    # Value-preserving container differences (memory layout, list vs
    # array steps) must not change the hash. Lossy conversions (e.g.
    # float64 -> float32) correctly DO change it and are not tested here.
    record = _mixed_record()
    payload = build_traj_payload(record, _job())
    clone = dict(payload)
    clone["positions"] = np.array(payload["positions"], dtype=np.float64,
                                  order="F")
    clone["cell"] = np.array(payload["cell"], dtype=np.float64, order="F")
    clone["frame_steps"] = [int(v) for v in payload["frame_steps"]]
    assert traj_sha256(clone) == traj_sha256(payload)


# --------------------------------------------------------------------------
# D. verification
# --------------------------------------------------------------------------

def test_d_verify_accepts_correct_rejects_tampered_and_missing(tmp_path):
    payload = build_traj_payload(_mixed_record(), _job())
    target = tmp_path / "aa00.npz"
    sha = write_traj_artifact(target, payload)
    back = verify_traj_artifact(target, sha)
    np.testing.assert_array_equal(back["positions"], payload["positions"])
    assert back["species"] == payload["species"]
    np.testing.assert_array_equal(back["cell"], payload["cell"])
    np.testing.assert_array_equal(back["frame_steps"],
                                  payload["frame_steps"])

    # Tampered bytes (positions perturbed, valid NPZ): hash must mismatch.
    tampered = dict(payload)
    tampered["positions"] = payload["positions"].copy()
    tampered["positions"][0, 0, 0] += 1.0
    write_traj_artifact(target, tampered)
    with pytest.raises(TrajectoryArtifactError, match="mismatch"):
        verify_traj_artifact(target, sha)

    # Missing file fails closed.
    with pytest.raises(TrajectoryArtifactError, match="missing"):
        verify_traj_artifact(tmp_path / "absent.npz", sha)

    # Garbage file fails closed.
    bad = tmp_path / "bad.npz"
    bad.write_bytes(b"not a numpy archive")
    with pytest.raises(TrajectoryArtifactError):
        verify_traj_artifact(bad, sha)


def test_d_load_rejects_wrong_format_version(tmp_path):
    payload = build_traj_payload(_mixed_record(), _job())
    target = tmp_path / "aa00.npz"
    write_traj_artifact(target, payload)
    with np.load(str(target), allow_pickle=False) as z:
        members = {k: z[k] for k in z.files}
    members["meta_json"] = np.array(
        json.dumps({"format_version": "p2-traj-v99"}))
    np.savez_compressed(str(target), **members)
    with pytest.raises(TrajectoryArtifactError, match="format_version"):
        load_traj_artifact(target)


# --------------------------------------------------------------------------
# E. P2 result binding (+ legacy path preserved)
# --------------------------------------------------------------------------

def test_e_bound_result_points_at_verifiable_artifact(tmp_path):
    record = _mixed_record()
    job = _job()
    traj_dir = tmp_path / "p2_traj"
    result = build_p2_result(job, record, CALC_INFO, {"session": "test"},
                             traj_artifact_dir=traj_dir)
    block = result["trajectory_artifact"]
    assert block["path"].endswith("aa00.npz")
    assert block["format_version"] == P2_TRAJ_FORMAT_VERSION
    assert block["n_production_frames"] == 10
    assert len(block["sha256"]) == 64
    # One hash everywhere: block == provenance == evidence event.
    assert result["provenance"]["trajectory_sha256"] == block["sha256"]
    assert result["evidence_events"][0]["artifact_hash"] == block["sha256"]
    # The referenced file verifies against the recorded hash. The
    # recorded path is worker-CWD-relative, so resolve it from the CWD.
    resolved = Path(os.path.abspath(block["path"]))
    assert resolved == Path(os.path.abspath(traj_dir / "aa00.npz"))
    payload = verify_traj_artifact(resolved, block["sha256"])
    assert payload["n_production_frames"] == 10
    assert payload["species"] == ["O"] * 4 + ["Li"] * 2
    # Science contract untouched: dynamic state only, never transport.
    assert result["dynamic_state"] in ("PASS", "FAIL", "INDETERMINATE")
    assert "transport_state" not in result
    assert "transport" not in json.dumps(result).lower()


def test_e_recorded_path_is_repo_relative_not_machine_specific(tmp_path,
                                                               monkeypatch):
    record = _mixed_record()
    job = _job()
    monkeypatch.chdir(tmp_path)  # worker repo-root convention
    result = build_p2_result(job, record, CALC_INFO, {},
                             traj_artifact_dir="data/batches/p2_traj")
    assert result["trajectory_artifact"]["path"] == \
        "data/batches/p2_traj/aa00.npz"
    assert (tmp_path / "data" / "batches" / "p2_traj" / "aa00.npz").is_file()


def test_e_legacy_path_stays_unbound_and_compatible():
    record = _mixed_record()
    result = build_p2_result(_job(), record, CALC_INFO, {"session": "test"})
    assert "trajectory_artifact" not in result
    assert result["provenance"]["trajectory_sha256"]  # legacy dangling hash
    assert "transport_state" not in result


def test_e_binding_failure_fails_closed_without_result(tmp_path):
    record = _mixed_record(with_md_step=False)  # unpersistable frames
    with pytest.raises(TrajectoryArtifactError):
        build_p2_result(_job(), record, CALC_INFO, {},
                        traj_artifact_dir=tmp_path / "p2_traj")
    assert list((tmp_path / "p2_traj").glob("*.npz")) == []


# --------------------------------------------------------------------------
# F. atomicity
# --------------------------------------------------------------------------

def test_f_no_tmp_leftovers_and_no_partial_final_artifact(tmp_path):
    payload = build_traj_payload(_mixed_record(), _job())
    target = tmp_path / "aa00.npz"
    write_traj_artifact(target, payload)
    assert list(tmp_path.glob("*.tmp*")) == []
    assert list(tmp_path.glob("*.npz")) == [target]


def test_f_failed_rewrite_never_clobbers_valid_artifact(tmp_path,
                                                        monkeypatch):
    import rudeus.mlip.p2_traj as traj_mod
    payload = build_traj_payload(_mixed_record(), _job())
    target = tmp_path / "aa00.npz"
    good_sha = write_traj_artifact(target, payload)
    good_bytes = target.read_bytes()

    def _boom(*args, **kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(traj_mod.np, "savez_compressed", _boom)
    with pytest.raises(TrajectoryArtifactError):
        write_traj_artifact(target, payload)
    # Valid artifact intact, verifiable, no temp debris.
    assert target.read_bytes() == good_bytes
    verify_traj_artifact(target, good_sha)
    assert list(tmp_path.glob("*.tmp*")) == []


# --------------------------------------------------------------------------
# G. end-to-end binding through run_p2_batches + git persistence
# --------------------------------------------------------------------------

def test_g_batches_write_bound_results_with_artifacts(tmp_path):
    from rudeus.mlip.sharding import structure_dict_sha256
    from pymatgen.core import Lattice, Structure
    p1done = tmp_path / "p1done"
    p1done.mkdir()
    s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    (p1done / "aa00.json").write_text(json.dumps(
        {"batch_id": "aa00", "child_material_id": "g1-test",
         "parent_id": "obelix:test",
         "result": {"p1_verdict": "KEEP_FOR_P2",
                    "relaxed_structure_dict": s,
                    "relaxed_structure_sha256": structure_dict_sha256(s)}}),
        encoding="utf-8")
    p2out = tmp_path / "p2"
    traj_dir = tmp_path / "p2_traj"

    def md_runner(job):
        return build_p2_result(job, _mixed_record(), CALC_INFO,
                               {"session": "test"},
                               traj_artifact_dir=traj_dir)

    summary = run_p2_batches(p1done, p2out, 0, 1, md_runner, _protocol(),
                             {"session": "test"})
    assert summary["processed"] == 1 and summary["wrote"] == ["aa00"]
    payload = json.loads((p2out / "aa00.json").read_text(encoding="utf-8"))
    block = payload["result"]["trajectory_artifact"]
    assert (traj_dir / "aa00.npz").is_file()
    verify_traj_artifact(traj_dir / "aa00.npz", block["sha256"])
    assert list(p2out.glob("*.tmp")) == []
    assert list(traj_dir.glob("*.tmp*")) == []


def test_g_persist_commits_bound_result_plus_verified_artifact(tmp_path,
                                                               monkeypatch):
    import subprocess
    from rudeus.mlip.gitpush import GitSafetyError, persist_p2_results

    def _git(repo, *args):
        return subprocess.run(["git", "-c", "commit.gpgsign=false", *args],
                              cwd=str(repo), capture_output=True, text=True)

    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init").returncode == 0
    assert _git(repo, "config", "user.email", "t@local").returncode == 0
    assert _git(repo, "config", "user.name", "t").returncode == 0
    assert _git(repo, "config", "commit.gpgsign", "false").returncode == 0
    (repo / "README.md").write_text("test repo", encoding="utf-8")
    assert _git(repo, "add", "--", "README.md").returncode == 0
    assert _git(repo, "commit", "-m", "init").returncode == 0

    # Bound result + artifact in the worker repo layout: chdir into the
    # fake repo so the recorded path is repo-relative (worker convention).
    monkeypatch.chdir(repo)
    record, job = _mixed_record(), _job()
    p2dir = Path("data") / "batches" / "p2"
    tdir = Path("data") / "batches" / "p2_traj"
    p2dir.mkdir(parents=True)
    result = build_p2_result(job, record, CALC_INFO, {"session": "t"},
                             traj_artifact_dir=tdir)
    (p2dir / "aa00.json").write_text(
        json.dumps({"batch_id": "aa00", "job": job, "result": result,
                    "worker": {}}), encoding="utf-8")

    info = persist_p2_results(repo, p2dir, ["aa00"], "p2 with traj",
                              traj_dir=tdir)
    assert info["files"] == ["data/batches/p2/aa00.json",
                             "data/batches/p2_traj/aa00.npz"]
    show = _git(repo, "show", "--name-only", "--format=", info["commit"])
    assert sorted(show.stdout.split()) == info["files"]

    # Corrupted artifact aborts with nothing staged (fail closed).
    (tdir / "aa00.npz").write_bytes(b"corrupted")
    (repo / "scratch.txt").write_text("user file", encoding="utf-8")
    with pytest.raises(GitSafetyError):
        persist_p2_results(repo, p2dir, ["aa00"], "must abort",
                           traj_dir=tdir)
    staged = _git(repo, "diff", "--cached", "--name-only")
    assert staged.stdout.strip() == ""


def test_g_persist_without_traj_dir_keeps_legacy_behavior(tmp_path):
    import subprocess
    from rudeus.mlip.gitpush import persist_p2_results

    def _git(repo, *args):
        return subprocess.run(["git", "-c", "commit.gpgsign=false", *args],
                              cwd=str(repo), capture_output=True, text=True)

    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init").returncode == 0
    assert _git(repo, "config", "user.email", "t@local").returncode == 0
    assert _git(repo, "config", "user.name", "t").returncode == 0
    assert _git(repo, "config", "commit.gpgsign", "false").returncode == 0
    (repo / "README.md").write_text("test repo", encoding="utf-8")
    assert _git(repo, "add", "--", "README.md").returncode == 0
    assert _git(repo, "commit", "-m", "init").returncode == 0

    p2dir = repo / "data" / "batches" / "p2"
    p2dir.mkdir(parents=True)
    result = build_p2_result(_job(), _mixed_record(), CALC_INFO, {})
    (p2dir / "aa00.json").write_text(
        json.dumps({"batch_id": "aa00", "result": result}), encoding="utf-8")
    info = persist_p2_results(repo, p2dir, ["aa00"], "legacy json only")
    assert info["files"] == ["data/batches/p2/aa00.json"]


# --------------------------------------------------------------------------
# H. live sampler contract (synthetic CPU MD, zero calculator, no GPU)
# --------------------------------------------------------------------------

def test_h_live_sampled_record_persists_with_exact_indices(tmp_path):
    """End-to-end through the real sampler: md_step cadence recorded by
    sample() slices to exact production indices in the artifact."""
    from ase.calculators.calculator import Calculator

    from rudeus.mlip.p2 import run_nvt_adaptive

    class ZeroCalc(Calculator):
        implemented_properties = ["energy", "energies", "forces",
                                  "free_energy"]

        def calculate(self, atoms=None, properties=None,
                      system_changes=None):
            super().calculate(atoms, properties, system_changes)
            n = len(atoms)
            self.results = {"energy": 0.0, "free_energy": 0.0,
                            "energies": np.zeros(n),
                            "forces": np.zeros((n, 3))}

    from pymatgen.core import Lattice, Structure
    proto = _protocol(equil_steps=20, production_steps=30,
                      production_tier_schedule_provisional=[30])
    struct = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                       [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    record = run_nvt_adaptive(struct, ZeroCalc(), proto, seed=7,
                              batch_id="live-test")
    prod_steps = [f["md_step"] for f in record["frames"]
                  if f.get("phase") == "production"]
    assert prod_steps == [30, 40, 50]  # equil=20, interval=10 cadence

    job = _job(batch_id="live-test", proto=proto)
    payload = build_traj_payload(record, job)
    assert list(payload["frame_steps"]) == [10, 20, 30]
    assert payload["species"] == ["Li", "Cl"]  # ASE order preserved
    target = tmp_path / "live-test.npz"
    sha = write_traj_artifact(target, payload)
    verify_traj_artifact(target, sha)
    assert list(tmp_path.glob("*.tmp*")) == []
