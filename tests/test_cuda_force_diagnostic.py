"""Tests for the P2 CUDA/MACE slowdown diagnostics (diagnostic-only).

No test here requires CUDA, a checkpoint, Kaggle credentials, network, or a
live GitHub remote. MD/force loops use a stub zero-force calculator. Nothing
writes to data/batches/p2/.
"""

import json

import pytest

from rudeus.mlip.cuda_force_diagnostic import (
    FORCE_DIAG_OUT_DIR,
    STATE_DIAG_OUT_DIR,
    EventTimingCalculator,
    cuda_synchronize,
    run_force_benchmark,
    run_state_diagnostic,
    sample_gpu_telemetry,
    summarize_telemetry,
    summarize_values,
    timed_call,
    timing_semantics,
    windowed_summary,
)
from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS
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


def _candidate(batch_id="cc22"):
    return {"batch_id": batch_id, "child_material_id": "g1-test",
            "parent_id": "obelix:test",
            "structure_dict": _tiny_struct_dict()}


# --- 1. CUDA timing helper behavior where CUDA is unavailable ---
def test_timing_semantics_cpu_without_cuda():
    import torch
    if torch.cuda.is_available():
        pytest.skip("meant for CUDA-absent machines")
    assert timing_semantics("cpu") == "cpu_wall_s"
    # cuda requested but unavailable: must degrade, never raise
    assert timing_semantics("cuda") == "cpu_wall_s"


def test_timed_call_cpu_wall_semantics():
    import torch
    if torch.cuda.is_available():
        pytest.skip("meant for CUDA-absent machines")
    result, dt, semantics = timed_call(lambda: 42, "cpu")
    assert result == 42
    assert dt >= 0
    assert semantics == "cpu_wall_s"


def test_cuda_synchronize_never_raises_without_cuda():
    cuda_synchronize()  # must not raise on a CPU-only box


def test_event_timing_calculator_records_wall_time_cpu():
    from pymatgen.core import Lattice, Structure
    from pymatgen.io.ase import AseAtomsAdaptor
    s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    atoms = AseAtomsAdaptor.get_atoms(s)
    rec: dict = {}
    calc = EventTimingCalculator(_ZeroCalculator(), rec, "cpu")
    atoms.calc = calc
    forces = atoms.get_forces()
    assert len(rec["force_times_s"]) == 1
    assert rec["force_times_s"][0] >= 0
    assert rec["force_timing_semantics"] == "cpu_wall_s"
    assert float(abs(forces).max()) == 0.0


# --- 6. window aggregation ---
def test_summarize_values_known():
    s = summarize_values([1.0, 2.0, 3.0, 4.0])
    assert s["n"] == 4
    assert s["median"] == pytest.approx(2.5)
    assert s["min"] == pytest.approx(1.0) and s["max"] == pytest.approx(4.0)
    assert s["p90"] == pytest.approx(3.7)
    empty = summarize_values([])
    assert empty == {"n": 0, "median": None, "p90": None, "p99": None,
                     "min": None, "max": None}


def test_windowed_summary_early_middle_late():
    vals = [float(i) for i in range(250)]  # increasing: late slower
    w = windowed_summary(vals, window=100)
    assert len(w["windows"]) == 3
    assert [x["n"] for x in w["windows"]] == [100, 100, 50]
    assert w["first_window_median"] == pytest.approx(49.5)
    assert w["middle_window_median"] == pytest.approx(149.5)
    assert w["last_window_median"] == pytest.approx(224.5)
    assert w["overall"]["n"] == 250
    assert w["overall"]["median"] == pytest.approx(124.5)
    for win in w["windows"]:
        for k in ("median", "p90", "p99", "min", "max"):
            assert win[k] is not None


# --- 4. telemetry failure does not crash ---
def test_telemetry_failure_never_crashes(monkeypatch):
    import rudeus.mlip.cuda_force_diagnostic as m
    import subprocess
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(
                            FileNotFoundError("no nvidia-smi")))
    sample = m.sample_gpu_telemetry()
    assert sample["error"] is not None
    assert sample["source"] == "unavailable"


def test_telemetry_sample_schema_on_this_box():
    sample = sample_gpu_telemetry()
    for k in ("timestamp", "gpu_index", "utilization_pct", "power_W",
              "temperature_C", "sm_clock_MHz", "mem_clock_MHz",
              "mem_used_MiB", "source", "error"):
        assert k in sample
    summary = summarize_telemetry([sample])
    assert summary["n_samples"] == 1
    assert summary["n_ok"] + summary["n_failed"] == 1


# --- 2. force-only benchmark: schema, bounded termination ---
def test_force_benchmark_schema_and_bounded(tmp_path):
    out = tmp_path / "forcediag"
    payload = run_force_benchmark(
        candidate=_candidate(), calc=_ZeroCalculator(), device="cpu",
        n_warmup=2, n_evals=12, window=5, telemetry_every=0,
        checkpoint_id="mace_mp:medium-mpa-0", checkpoint_sha256="abc",
        out_dir=out, worker_info={"session": "test"})
    assert payload["diagnostic"] == "p2-force-benchmark"
    assert payload["batch_id"] == "cc22"
    assert payload["n_warmup"] == 2 and payload["n_evals"] == 12
    assert len(payload["force_times_s"]) == 12  # bounded: exactly n_evals
    assert len(payload["wall_times_s"]) == 12
    for k in ("median", "p90", "p99", "min", "max"):
        assert payload["force_summary"][k] is not None
    assert payload["first_window_median_s"] is not None
    assert payload["middle_window_median_s"] is not None
    assert payload["last_window_median_s"] is not None
    assert len(payload["force_windows"]["windows"]) == 3  # 12 in windows of 5
    assert payload["force_timing_semantics"] == "cpu_wall_s"
    assert "NOT equivalent" in payload["timing_note"]
    assert payload["checkpoint_id"] == "mace_mp:medium-mpa-0"
    blob = json.dumps(payload, default=str)
    assert "dynamic_state" not in payload and "p2_verdict" not in blob
    assert "DIFFUSIVE" not in blob
    assert (out / "cc22.forcediag.json").exists()
    assert list(out.glob("*.tmp")) == []


def test_force_benchmark_refuses_production_dir():
    from pathlib import Path
    with pytest.raises(ValueError, match="production dir"):
        run_force_benchmark(
            candidate=_candidate(), calc=_ZeroCalculator(), device="cpu",
            n_warmup=0, n_evals=1, out_dir=Path("data/batches/p2"))
    assert FORCE_DIAG_OUT_DIR.as_posix().endswith("audit/p2_force_diagnostic")


# --- 3. state-dependent diagnostic: bounded, windowed, no verdicts ---
def test_state_diagnostic_bounded_and_schema(tmp_path):
    out = tmp_path / "statediag"
    payload = run_state_diagnostic(
        candidate=_candidate(), calc=_ZeroCalculator(),
        protocol=_tiny_protocol(), seed=11, device="cpu",
        checkpoint_id="mace_mp:medium-mpa-0", checkpoint_sha256="abc",
        out_dir=out, max_steps=12, heartbeat_steps=5, window=5,
        worker_info={"session": "test"},
        device_info={"requested": "cpu", "resolved": "cpu"})
    assert payload["diagnostic"] == "p2-state-benchmark"
    assert payload["executed"] == {"equil_steps": 6, "production_steps": 6}
    assert payload["outcome"] == "COMPLETED"
    assert payload["n_force_evals"] > 0
    # Each MD step needs >=1 force eval (dynamics); samples add a bounded
    # few more via energy/force/stress getters. Generous but finite bound.
    assert 12 < payload["n_force_evals"] <= 12 * 10
    assert payload["first_window_median_s"] is not None
    assert payload["last_window_median_s"] is not None
    assert len(payload["heartbeats"]) >= 1
    assert "dynamic_state" not in payload
    assert "p2_verdict" not in payload
    assert "DIFFUSIVE" not in json.dumps(payload, default=str)
    assert (out / "cc22.statediag.json").exists()
    assert list(out.glob("*.tmp")) == []


def test_state_diagnostic_refuses_production_dir():
    from pathlib import Path
    with pytest.raises(ValueError, match="production dir"):
        run_state_diagnostic(
            candidate=_candidate(), calc=_ZeroCalculator(),
            protocol=_tiny_protocol(), seed=11,
            out_dir=Path("data/batches/p2"), max_steps=4)
    assert STATE_DIAG_OUT_DIR.as_posix().endswith("audit/p2_state_diagnostic")


# --- production behavior unchanged ---
def test_production_path_has_no_cuda_sync_or_telemetry():
    from pathlib import Path
    for name in ("rudeus/mlip/p2.py", "rudeus/mlip/calibration.py"):
        src = Path(name).read_text(encoding="utf-8")
        assert "cuda.synchronize" not in src, name
        assert "cuda.Event" not in src, name
        assert "sample_gpu_telemetry" not in src, name
        assert "nvidia-smi" not in src, name
        assert "pynvml" not in src, name
        assert "cuda_force_diagnostic" not in src, name


def test_production_protocol_defaults_untouched():
    p = P2_PROTOCOL_DEFAULTS
    assert (p["equil_steps"], p["production_steps"]) == (2000, 8000)
    assert p["temperature_K"] == 550.0
    assert p["timestep_fs"] == 1.0
    assert p["sample_interval_steps"] == 10


def test_cli_flags_exist_and_fail_closed(capsys, tmp_path):
    import sys
    from rudeus.mlip import run_p2
    import inspect
    src = inspect.getsource(run_p2.main)
    assert "--p2-force-benchmark" in src
    assert "--p2-state-diagnostic" in src
    for flag in ("--p2-force-benchmark", "--p2-state-diagnostic"):
        argv = ["run_p2", flag, "--config", "config.yaml"]
        old = sys.argv
        sys.argv = argv
        try:
            with pytest.raises(SystemExit) as e:
                run_p2.main()
            assert e.value.code == 2
            assert "--batch-id" in capsys.readouterr().out
        finally:
            sys.argv = old
    argv = ["run_p2", "--p2-force-benchmark", "--batch-id", "deadbeef",
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
