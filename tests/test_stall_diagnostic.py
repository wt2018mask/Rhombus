"""Tests for the P2 stall diagnostic (Task: observe step ~1000 stall).

No test here requires CUDA, a checkpoint, or network. MD uses a stub
zero-force calculator. Nothing writes to data/batches/p2/.
"""

import json

import pytest

from rudeus.mlip.p2 import DiagnosticStall, P2_PROTOCOL_DEFAULTS, run_nvt
from rudeus.mlip.stall_diagnostic import (
    STALL_OUT_DIR,
    HeartbeatRecorder,
    TimingCalculator,
    check_stall,
    classify_termination,
    ensure_diag_out_dir,
    run_stall_diagnostic,
    summarize_frames,
)
from tests.test_gpu_diagnostic import _ZeroCalculator


def _tiny_struct_dict():
    from pymatgen.core import Lattice, Structure
    return Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                     [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]).as_dict()


def _tiny_protocol(**over):
    p = dict(P2_PROTOCOL_DEFAULTS)
    p.update(equil_steps=6, production_steps=10, sample_interval_steps=2)
    p.update(over)
    return p


def _candidate():
    return {"batch_id": "aa00", "child_material_id": "g1-test",
            "parent_id": "obelix:test",
            "structure_dict": _tiny_struct_dict()}


def test_heartbeat_interval_phase_and_metadata():
    """Hook fires every step with correct phase labels and timing fields."""
    rec = HeartbeatRecorder(heartbeat_steps=5, stall_timeout_s=300.0,
                            stream=None)
    proto = _tiny_protocol()
    run_nvt(_tiny_struct_dict(), _ZeroCalculator(), proto, seed=3,
            batch_id="hb", step_hook=rec)
    assert rec.calls == 17  # 16 MD steps + 1 ASE attach-time call
    assert [h["step"] for h in rec.heartbeats] == [5, 10, 15]
    assert [h["phase"] for h in rec.heartbeats] == (
        ["equil", "production", "production"])  # equil is only 6 steps here
    summary = rec.finalize()
    assert summary["n_hook_calls"] == 17
    assert summary["step_dt_s"]["n"] == 16  # first call has no delta
    assert summary["step_dt_s"]["mean"] >= 0
    assert summary["stall"] is None


def test_run_nvt_without_hook_unchanged():
    """No hook -> identical trajectory record shape as before."""
    proto = _tiny_protocol()
    rec = run_nvt(_tiny_struct_dict(), _ZeroCalculator(), proto, seed=3,
                  batch_id="hb")
    assert len(rec["frames"]) > 0
    assert rec["completed"] is True


def test_check_stall_pure():
    assert check_stall(None, 300.0) is False
    assert check_stall(0.5, 300.0) is False
    assert check_stall(301.0, 300.0) is True


def test_stall_exception_becomes_termination_note():
    """A hook-raised DiagnosticStall ends the run with a loud note, no crash."""
    def hook(step, phase):
        if step >= 4:
            raise DiagnosticStall("synthetic slow step in test")

    proto = _tiny_protocol()
    rec = run_nvt(_tiny_struct_dict(), _ZeroCalculator(), proto, seed=3,
                  batch_id="stalltest", step_hook=hook)
    assert rec["completed"] is False
    assert "diagnostic-stall-suspected" in rec["termination_note"]
    assert classify_termination(rec["termination_note"],
                                rec["completed"]) == "STALL_SUSPECTED"


def test_classify_termination_branches():
    assert classify_termination(None, True) == "COMPLETED"
    assert classify_termination("", True) == "COMPLETED"
    assert classify_termination("diagnostic-stall-suspected: x", False) == \
        "STALL_SUSPECTED"
    assert classify_termination("explosive-step", False) == \
        "EXPLOSIVE_TERMINATION"
    assert classify_termination("non-finite-data", False) == "NUMERICAL_FAILURE"
    assert classify_termination("sampling-error: X", False) == \
        "NUMERICAL_FAILURE"
    assert classify_termination(None, False) == "NUMERICAL_FAILURE"


def _frame(phase="production", finite=True, temp=550.0, fmax=0.05):
    return {"phase": phase, "positions": [[0.0, 0.0, 0.0]],
            "temperature_K": temp, "energy_ev": -1.0, "volume_A3": 64.0,
            "pressure_GPa": 0.0, "max_force_ev_A": fmax, "finite": finite,
            "step_jump_A": 0.01}


def test_summarize_frames_and_numerical_paths():
    good = [_frame() for _ in range(10)]
    s = summarize_frames(good)
    assert s["n_frames"] == 10 and s["n_finite_frames"] == 10
    assert s["n_nonfinite_frames"] == 0
    assert s["last_temperature_K"] == 550.0
    mixed = [_frame()] * 3 + [_frame(finite=False)] * 2
    s2 = summarize_frames(mixed)
    assert s2["n_nonfinite_frames"] == 2
    assert s2["last_temperature_K"] == 550.0  # last *finite* frame reported


def test_run_stall_diagnostic_record_schema(tmp_path):
    """Full bounded run on stub calc: schema, no verdicts, atomic write."""
    out = tmp_path / "diag"
    payload = run_stall_diagnostic(
        candidate=_candidate(), calc=_ZeroCalculator(),
        protocol=_tiny_protocol(), seed=11, out_dir=out,
        max_steps=12, heartbeat_steps=5, stall_timeout_s=300.0,
        worker_info={"session": "test"},
        device_info={"requested": "cpu", "resolved": "cpu"})
    assert payload["diagnostic"] == "p2-stall"
    assert payload["batch_id"] == "aa00"
    assert payload["seed"] == 11
    assert payload["outcome"] == "COMPLETED"
    assert "dynamic_state" not in payload
    assert "p2_verdict" not in payload
    assert payload["executed"] == {"equil_steps": 6, "production_steps": 6}
    assert payload["protocol_hash"]
    assert payload["input_structure_sha256"]
    assert payload["timing"]["n_heartbeats"] >= 1
    assert payload["frames_summary"]["n_frames"] > 0
    assert (out / "aa00.stall.json").exists()  # atomic record written
    assert list(out.glob("*.tmp")) == []
    json.dumps(payload, default=str)  # JSON-serializable


def test_run_stall_diagnostic_bounded_prefix(tmp_path):
    """max_steps < equil budget runs equil-only prefix deterministically."""
    out = tmp_path / "diag"
    payload = run_stall_diagnostic(
        candidate=_candidate(), calc=_ZeroCalculator(),
        protocol=_tiny_protocol(), seed=11, out_dir=out,
        max_steps=4, heartbeat_steps=2, stall_timeout_s=300.0)
    assert payload["executed"] == {"equil_steps": 4, "production_steps": 0}
    assert payload["outcome"] == "COMPLETED"


def test_out_dir_inside_production_refused(tmp_path):
    """Diagnostic records can never land in data/batches/p2/."""
    # NOTE: the guard compares against the real production dir, so this
    # test uses the repo-relative path (mkdir exist_ok: no writes made).
    from pathlib import Path
    with pytest.raises(ValueError, match="production dir"):
        ensure_diag_out_dir(Path("data/batches/p2"))
    with pytest.raises(ValueError, match="production dir"):
        run_stall_diagnostic(
            candidate=_candidate(), calc=_ZeroCalculator(),
            protocol=_tiny_protocol(), seed=11,
            out_dir=Path("data/batches/p2"),
            max_steps=4)
    assert STALL_OUT_DIR.as_posix().endswith("audit/p2_stall_diagnostic")


def test_no_gitpush_or_transport_in_module():
    """Diagnostic layer never commits, never classifies transport."""
    from pathlib import Path
    src = Path("rudeus/mlip/stall_diagnostic.py").read_text(encoding="utf-8")
    assert "gitpush" not in src
    assert "commit_done_files" not in src
    assert "push_branch" not in src
    assert "load_authorization_manifest" not in src
    assert "TransportState" not in src
    assert "DIFFUSIVE" not in src
    assert "dynamic_state" not in src


def test_cli_missing_batch_id_fails_closed(capsys):
    import sys
    from rudeus.mlip import run_p2
    argv = ["run_p2", "--p2-stall-diagnostic", "--config", "config.yaml"]
    old = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(SystemExit) as e:
            run_p2.main()
        assert e.value.code == 2
        assert "--batch-id" in capsys.readouterr().out
    finally:
        sys.argv = old


def test_cli_unknown_batch_id_fails_closed(capsys, tmp_path):
    import sys
    from rudeus.mlip import run_p2
    argv = ["run_p2", "--p2-stall-diagnostic", "--batch-id", "deadbeef",
            "--p1-done", str(tmp_path), "--config", "config.yaml"]
    old = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(SystemExit) as e:
            run_p2.main()
        assert e.value.code == 2
        assert "STOP" in capsys.readouterr().out
    finally:
        sys.argv = old


def test_max_steps_bounds_execution_not_just_record(tmp_path):
    """Regression: max_steps must bound the executed trajectory (equil first).

    Previously the bounded values were recorded while run_nvt silently ran
    the full production protocol.
    """
    out = tmp_path / "diag"
    payload = run_stall_diagnostic(
        candidate=_candidate(), calc=_ZeroCalculator(),
        protocol=_tiny_protocol(), seed=11, out_dir=out,
        max_steps=8, heartbeat_steps=1000, stall_timeout_s=300.0)
    assert payload["executed"] == {"equil_steps": 6, "production_steps": 2}
    # 8 MD steps + 1 attach-time hook call at most
    assert payload["timing"]["n_hook_calls"] <= 9
    assert payload["frames_summary"]["n_frames"] <= 8 + 1
    # identity still refers to the FULL production protocol
    from rudeus.mlip.p2 import protocol_config_hash
    assert payload["protocol_hash"] == protocol_config_hash(_tiny_protocol())


def test_cuda_sync_guarded_on_cpu_only_box():
    """use_cuda_sync=True must not crash where CUDA is absent (sync guarded)."""
    from pymatgen.core import Lattice, Structure
    from pymatgen.io.ase import AseAtomsAdaptor
    s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    atoms = AseAtomsAdaptor.get_atoms(s)
    rec: dict = {}
    calc = TimingCalculator(_ZeroCalculator(), rec, use_cuda_sync=True)
    atoms.calc = calc
    forces = atoms.get_forces()
    assert len(rec["force_times_s"]) == 1
    assert float(abs(forces).max()) == 0.0
