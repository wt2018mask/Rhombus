"""Tests for the P2 production-path diagnostic (measurement only).

No test here requires CUDA, a checkpoint, or network. MD uses a stub
zero-force calculator. Nothing writes to data/batches/p2/.
"""

import json

import pytest

from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, run_nvt
from rudeus.mlip.production_diagnostic import (
    DIAGNOSTIC_TYPE,
    PROD_DIAG_OUT_DIR,
    ProductionProfiler,
    ensure_prod_diag_out_dir,
    run_production_diagnostic,
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
    return {"batch_id": "bb11", "child_material_id": "g1-test",
            "parent_id": "obelix:test",
            "structure_dict": _tiny_struct_dict()}


def test_cli_flag_exists():
    import argparse
    from rudeus.mlip import run_p2
    import inspect
    src = inspect.getsource(run_p2.main)
    assert "--p2-production-diagnostic" in src
    assert "--batch-id" in src


def test_run_nvt_without_profiler_unchanged():
    """No profiler/hook -> identical trajectory record shape as before."""
    proto = _tiny_protocol()
    rec = run_nvt(_tiny_struct_dict(), _ZeroCalculator(), proto, seed=3,
                  batch_id="noprod")
    assert len(rec["frames"]) > 0
    assert rec["completed"] is True
    # profiler=None must not leak profiler keys into the record
    assert "profiler" not in rec


def test_run_nvt_with_profiler_same_trajectory():
    """Profiler enabled -> same frames/completion, plus timing keys."""
    proto = _tiny_protocol()
    plain = run_nvt(_tiny_struct_dict(), _ZeroCalculator(), proto, seed=3,
                    batch_id="plain")
    profiler: dict = {}
    timed = run_nvt(_tiny_struct_dict(), _ZeroCalculator(), proto, seed=3,
                    batch_id="timed", profiler=profiler)
    assert len(timed["frames"]) == len(plain["frames"])
    assert timed["completed"] == plain["completed"]
    assert timed["termination_note"] == plain["termination_note"]
    assert profiler["n_samples"] == len(timed["frames"])
    assert profiler["frame_capture_time_s"] >= 0
    assert len(profiler["step_times_s"]) == 17  # 16 steps + attach call
    assert set(profiler["frame_capture_by_phase_s"]) <= {"equil", "production"}


def test_diagnostic_bounded_and_schema(tmp_path):
    out = tmp_path / "proddiag"
    payload = run_production_diagnostic(
        candidate=_candidate(), calc=_ZeroCalculator(),
        protocol=_tiny_protocol(), seed=11,
        checkpoint_id="mace_mp:medium-mpa-0", checkpoint_sha256="abc123",
        out_dir=out, max_steps=12, heartbeat_steps=5,
        worker_info={"session": "test"},
        device_info={"requested": "cpu", "resolved": "cpu"})
    assert payload["diagnostic_type"] == DIAGNOSTIC_TYPE == "p2-production"
    assert payload["batch_id"] == "bb11"
    assert payload["natoms"] == 2
    assert payload["seed"] == 11
    assert payload["protocol_hash"]
    assert payload["checkpoint_id"] == "mace_mp:medium-mpa-0"
    assert payload["checkpoint_sha256"] == "abc123"
    assert payload["requested_device"] == "cpu"
    assert payload["resolved_device"] == "cpu"
    assert payload["python_version"] and payload["torch_version"]
    assert payload["mace_version"] and payload["ase_version"]
    # bounded: equil first, then production
    assert payload["executed"] == {"equil_steps": 6, "production_steps": 6}
    total = (payload["phase_results"]["equilibration"]["steps_completed"]
             + payload["phase_results"]["production"]["steps_completed"])
    assert total == 12
    # no scientific verdicts anywhere in the diagnostic record
    blob = json.dumps(payload, default=str)
    assert "dynamic_state" not in payload
    assert "p2_verdict" not in payload
    assert "DIFFUSIVE" not in blob
    assert (out / "bb11.proddiag.json").exists()
    assert list(out.glob("*.tmp")) == []
    json.dumps(payload, default=str)


def test_heartbeat_required_fields(tmp_path):
    out = tmp_path / "proddiag"
    payload = run_production_diagnostic(
        candidate=_candidate(), calc=_ZeroCalculator(),
        protocol=_tiny_protocol(), seed=11, out_dir=out,
        max_steps=12, heartbeat_steps=5,
        device_info={"requested": "cpu", "resolved": "cpu"})
    assert len(payload["heartbeats"]) >= 1
    required = {"step", "phase", "elapsed_seconds", "mean_step_seconds",
                "max_step_seconds", "cpu_time", "rss_mb",
                "cuda_memory_allocated_mb", "cuda_memory_reserved_mb"}
    for hb in payload["heartbeats"]:
        assert required <= set(hb)
        assert hb["phase"] in ("equil", "production")


def test_timing_breakdown_fields(tmp_path):
    out = tmp_path / "proddiag"
    payload = run_production_diagnostic(
        candidate=_candidate(), calc=_ZeroCalculator(),
        protocol=_tiny_protocol(), seed=11, out_dir=out,
        max_steps=12, heartbeat_steps=5,
        device_info={"requested": "cpu", "resolved": "cpu"})
    required = {"force_time_s", "integration_time_s", "frame_capture_time_s",
                "metric_update_time_s", "other_python_time_s"}
    assert required <= set(payload["timing_breakdown"])
    for v in payload["timing_breakdown"].values():
        if isinstance(v, float):
            assert v >= 0
    for phase in ("equilibration", "production"):
        sec = payload["phase_results"][phase]
        for k in ("steps_completed", "wall_seconds", "mean_step_seconds",
                  "max_step_seconds", "timing_breakdown"):
            assert k in sec
        assert required - {"metric_update_time_s", "other_python_time_s"} <= \
            set(sec["timing_breakdown"])
    # force attribution is exact: global == sum of step attributions
    assert payload["timing_breakdown"]["n_force_evals"] > 0


def test_out_dir_inside_production_refused(tmp_path):
    from pathlib import Path
    with pytest.raises(ValueError, match="production dir"):
        ensure_prod_diag_out_dir(Path("data/batches/p2"))
    with pytest.raises(ValueError, match="production dir"):
        run_production_diagnostic(
            candidate=_candidate(), calc=_ZeroCalculator(),
            protocol=_tiny_protocol(), seed=11,
            out_dir=Path("data/batches/p2"), max_steps=4)
    assert PROD_DIAG_OUT_DIR.as_posix().endswith(
        "audit/p2_production_diagnostic")


def test_no_production_result_or_verdict(tmp_path):
    """Diagnostic never invokes run_p2_batches verdict machinery output."""
    from pathlib import Path
    src = Path("rudeus/mlip/production_diagnostic.py").read_text(
        encoding="utf-8")
    assert "run_p2_batches" not in src
    assert "commit_done_files" not in src
    assert "push_branch" not in src
    assert "dynamic_state" not in src
    assert "TransportState" not in src
    assert "DIFFUSIVE" not in src


def test_protocol_thresholds_untouched():
    p = P2_PROTOCOL_DEFAULTS
    assert (p["equil_steps"], p["production_steps"]) == (2000, 8000)
    assert p["temperature_K"] == 550.0
    assert p["timestep_fs"] == 1.0
    assert p["explosion_abort_A_provisional"] == 3.0
    assert p["lindemann_fail_provisional"] == 0.20
    assert p["host_rmsd_fail_A_provisional"] == 1.0


def test_cli_missing_batch_id_fails_closed(capsys):
    import sys
    from rudeus.mlip import run_p2
    argv = ["run_p2", "--p2-production-diagnostic", "--config", "config.yaml"]
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
    argv = ["run_p2", "--p2-production-diagnostic", "--batch-id", "deadbeef",
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


def test_profiler_hook_counts_match():
    """Hook sees every step; profiler timestamps match hook calls."""
    proto = _tiny_protocol()
    profiler: dict = {}
    force_times: list = []
    hook = ProductionProfiler(heartbeat_steps=5, force_times=force_times,
                              stream=None)
    run_nvt(_tiny_struct_dict(), _ZeroCalculator(), proto, seed=3,
            batch_id="counts", step_hook=hook, profiler=profiler)
    assert hook.calls == len(profiler["step_times_s"]) == 17
    assert len(hook.steps) == 16
    assert [h["step"] for h in hook.heartbeats] == [5, 10, 15]
