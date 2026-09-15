"""Worker robustness for expected explosive P2 terminations (Tests A-F).

A candidate whose MD aborts with an explosive/numerical termination is a
normal scientific P2 FAIL (termination_reason = EXPLOSIVE_TERMINATION,
dynamic_state = FAIL), not a worker crash. These tests lock the existing
production chain:

  run_nvt structured record -> build_p2_result (FAIL) -> run_p2_batches
  atomic write -> continue shard -> resume skip

No test here requires CUDA, Kaggle credentials, or a live GitHub remote.
Nothing writes to data/batches/p2/.
"""

import json

import numpy as np

from rudeus.mlip.p2 import (
    P2_PROTOCOL_DEFAULTS,
    build_p2_result,
    run_p2_batches,
)
from rudeus.schema import DynamicState

CALC_INFO = {"checkpoint_name": "mace_mp:medium-mpa-0",
             "url": "pinned", "sha256": "pinned-sha",
             "device": "cpu", "dtype": "float32"}


def _protocol(**over):
    p = dict(P2_PROTOCOL_DEFAULTS)
    p.update(over)
    return p


def _base_cell(n_host=16, n_li=4, box=10.0):
    rng = np.random.default_rng(0)
    host = rng.uniform(0, box, size=(n_host, 3))
    li = rng.uniform(0, box, size=(n_li, 3))
    return np.vstack([host, li]), ["O"] * n_host + ["Li"] * n_li, \
        np.eye(3) * box


def _explosive_record(n_prod_frames=40):
    """Partial trajectory aborted mid-equilibration/production (structured).

    Mirrors what run_nvt returns on an explosive abort: completed=False,
    termination_note="explosive-step", and only the frames sampled so far.
    """
    pos0, species, cell = _base_cell()
    rng = np.random.default_rng(1)
    frames = []
    for _ in range(n_prod_frames):
        p = pos0 + rng.normal(0, 0.05, size=pos0.shape)
        frames.append({"phase": "production", "positions": p,
                       "temperature_K": 550.0, "energy_ev": -100.0,
                       "volume_A3": 1000.0, "pressure_GPa": 0.1,
                       "max_force_ev_A": 0.05, "finite": True,
                       "step_jump_A": 0.01})
    return {"species": species, "cell": cell, "frames": frames,
            "completed": False, "termination_note": "explosive-step",
            "wall_clock_s": 7.2,
            "timestep_fs": 1.0, "sample_interval_steps": 10,
            "equil_steps": 2000, "production_steps": 8000,
            "thermostat": "langevin", "friction_fs_inv": 0.02, "seed": 11}


def _stable_record(n_frames=120):
    pos0, species, cell = _base_cell()
    rng = np.random.default_rng(1)
    frames = []
    for _ in range(n_frames):
        p = pos0.copy()
        p += rng.normal(0, 0.05, size=p.shape)
        frames.append({"phase": "production", "positions": p,
                       "temperature_K": 550.0 + rng.normal(0, 12.0),
                       "energy_ev": -100.0 + rng.normal(0, 0.01),
                       "volume_A3": 1000.0, "pressure_GPa": 0.1,
                       "max_force_ev_A": 0.05, "finite": True,
                       "step_jump_A": 0.01})
    return {"species": species, "cell": cell, "frames": frames,
            "completed": True, "termination_note": None,
            "wall_clock_s": 3.1,
            "timestep_fs": 1.0, "sample_interval_steps": 10,
            "equil_steps": 200, "production_steps": 800,
            "thermostat": "langevin", "friction_fs_inv": 0.02, "seed": 7}


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
            "p2_protocol": proto, "p2_config_hash": "cfghash",
            "seed": 11}


def _p1_done_record(p1done_dir, batch_id):
    from rudeus.mlip.sharding import structure_dict_sha256
    from pymatgen.core import Lattice, Structure
    s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    rec = {"batch_id": batch_id, "child_material_id": "g1-test",
           "parent_id": "obelix:test",
           "result": {"p1_verdict": "KEEP_FOR_P2",
                      "relaxed_structure_dict": s,
                      "relaxed_structure_sha256":
                          structure_dict_sha256(s)}}
    (p1done_dir / f"{batch_id}.json").write_text(json.dumps(rec),
                                                 encoding="utf-8")


def _read_result(p2out, batch_id):
    return json.loads((p2out / f"{batch_id}.json").read_text(encoding="utf-8"))


# --- Test A: explosive termination becomes FAIL, reason preserved ---
def test_a_explosive_termination_becomes_fail():
    result = build_p2_result(_job(), _explosive_record(), CALC_INFO,
                             {"session": "test"})
    assert result["dynamic_state"] == DynamicState.FAIL.value
    assert result["p2_verdict"] == DynamicState.FAIL.value
    assert result["termination"] == {"completed": False,
                                     "note": "explosive-step"}
    assert result["sampling_metrics"]["completed"] is False
    assert result["sampling_metrics"]["termination_note"] == "explosive-step"
    assert any("explosive" in r for r in result["reasons"])
    assert result["error_info"] is None


# --- Test B: explosive result written atomically ---
def test_b_explosive_result_written_atomically(tmp_path):
    p1done, p2out = tmp_path / "p1done", tmp_path / "p2"
    p1done.mkdir()

    def md_runner(job):
        assert job["batch_id"] == "aa00"
        return build_p2_result(job, _explosive_record(), CALC_INFO,
                               {"session": "test"})

    _p1_done_record(p1done, "aa00")
    summary = run_p2_batches(p1done, p2out, 0, 1, md_runner, _protocol())
    assert summary["processed"] == 1 and summary["errored"] == 0
    payload = _read_result(p2out, "aa00")
    assert payload["result"]["dynamic_state"] == "FAIL"
    assert payload["result"]["termination"]["note"] == "explosive-step"
    assert payload["result"]["termination"]["completed"] is False
    assert payload["batch_id"] == "aa00"
    assert list(p2out.glob("*.tmp")) == []  # no partial final JSON


# --- Test C: worker continues after explosive candidate ---
def test_c_worker_continues_after_explosive(tmp_path):
    p1done, p2out = tmp_path / "p1done", tmp_path / "p2"
    p1done.mkdir()

    def md_runner(job):
        if job["batch_id"] == "aa00":
            return build_p2_result(job, _explosive_record(), CALC_INFO, {})
        return build_p2_result(job, _stable_record(), CALC_INFO, {})

    _p1_done_record(p1done, "aa00")
    _p1_done_record(p1done, "bb01")
    summary = run_p2_batches(p1done, p2out, 0, 1, md_runner, _protocol())
    assert summary["processed"] == 2 and summary["errored"] == 0
    first = _read_result(p2out, "aa00")["result"]
    second = _read_result(p2out, "bb01")["result"]
    assert first["dynamic_state"] == "FAIL"
    assert first["termination"]["note"] == "explosive-step"
    assert second["dynamic_state"] == "PASS"  # shard was not aborted


# --- Test D: resume skips a recorded explosive FAIL ---
def test_d_resume_skips_explosive_fail(tmp_path):
    p1done, p2out = tmp_path / "p1done", tmp_path / "p2"
    p1done.mkdir()
    calls = []

    def md_runner(job):
        calls.append(job["batch_id"])
        return build_p2_result(job, _explosive_record(), CALC_INFO, {})

    _p1_done_record(p1done, "aa00")
    first = run_p2_batches(p1done, p2out, 0, 1, md_runner, _protocol())
    assert first["processed"] == 1 and calls == ["aa00"]
    before = (p2out / "aa00.json").read_text(encoding="utf-8")
    second = run_p2_batches(p1done, p2out, 0, 1, md_runner, _protocol())
    assert second["skipped_done"] == 1 and second["processed"] == 0
    assert calls == ["aa00"]  # not recomputed; no --retry-errors needed
    assert (p2out / "aa00.json").read_text(encoding="utf-8") == before


# --- Test E: unexpected exception remains ERROR (retry semantics intact) ---
def test_e_unexpected_exception_remains_error(tmp_path):
    p1done, p2out = tmp_path / "p1done", tmp_path / "p2"
    p1done.mkdir()
    calls = []

    def md_runner(job):
        calls.append(job["batch_id"])
        raise RuntimeError("synthetic infrastructure boom")

    _p1_done_record(p1done, "aa00")
    summary = run_p2_batches(p1done, p2out, 0, 1, md_runner, _protocol())
    assert summary["errored"] == 1 and summary["processed"] == 0
    result = _read_result(p2out, "aa00")["result"]
    assert result["p2_verdict"] == "ERROR"  # NOT scientific FAIL
    assert result["dynamic_state"] == DynamicState.NOT_RUN.value
    assert result["error_type"] == "RuntimeError"
    # ERROR skips by default, recomputes only with the retry flag.
    again = run_p2_batches(p1done, p2out, 0, 1, md_runner, _protocol())
    assert again["skipped_done"] == 1 and calls == ["aa00"]
    retried = run_p2_batches(p1done, p2out, 0, 1, md_runner, _protocol(),
                             retry_errors=True)
    assert retried["retried_errors"] == 1 and calls == ["aa00", "aa00"]


# --- Test F: no transport inference from an explosive P2 result ---
def test_f_no_transport_inference_from_explosive():
    result = build_p2_result(_job(), _explosive_record(), CALC_INFO, {})
    assert "transport_state" not in result
    blob = json.dumps(result).lower()
    assert "diffus" not in blob and "transport" not in blob
