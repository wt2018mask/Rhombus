"""Tests for the P2 stall-profile diagnostic (measurement only).

No test here requires CUDA, a checkpoint, Kaggle credentials, network, or a
live GitHub remote. MD uses stub calculators. Nothing writes to
data/batches/p2/ (the module writes no files at all).
"""

import io
import json

import pytest

from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS
from rudeus.mlip.stall_profile_diagnostic import (
    DEFAULT_CHECKPOINT_EVERY,
    DEFAULT_PROD_STEPS,
    TABLE_COLUMNS,
    _force_timing_semantics,
    _select_timing_calc,
    build_checkpoint_rows,
    format_checkpoint_table,
    run_stall_profile_diagnostic,
)
from tests.test_gpu_diagnostic import _ZeroCalculator


def _tiny_struct_dict():
    from pymatgen.core import Lattice, Structure
    return Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                     [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]).as_dict()


def _tiny_protocol(**over):
    p = dict(P2_PROTOCOL_DEFAULTS)
    p.update(equil_steps=20, production_steps=8000, sample_interval_steps=2)
    p.update(over)
    return p


def _candidate(batch_id="dd33"):
    return {"batch_id": batch_id, "child_material_id": "g1-test",
            "parent_id": "obelix:test",
            "structure_dict": _tiny_struct_dict()}


def _run(buf=None, **over):
    kw = {"candidate": _candidate(), "calc": _ZeroCalculator(),
          "protocol": _tiny_protocol(), "seed": 7,
          "checkpoint_id": "medium-mpa-0", "checkpoint_sha256": "abc123",
          "prod_steps": 10, "checkpoint_every": 2,
          "device": "cpu", "dtype": "float32",
          "stream": buf if buf is not None else io.StringIO()}
    kw.update(over)
    return run_stall_profile_diagnostic(**kw)


class _NaNCalculator(_ZeroCalculator):
    """Zero forces for a while, then NaN: deterministic numerical abort."""

    def __init__(self, clean_evals=25, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clean_evals = int(clean_evals)

    def calculate(self, atoms=None, properties=None,
                  system_changes=None):
        from ase.calculators.calculator import Calculator
        import numpy as np
        Calculator.calculate(self, atoms, properties, system_changes)
        n = len(atoms)
        if self.n_calculations >= self.clean_evals:
            self.results = {"energy": 0.0, "free_energy": 0.0,
                            "forces": np.full((n, 3), np.nan)}
        else:
            self.results = {"energy": 0.0, "free_energy": 0.0,
                            "forces": np.zeros((n, 3))}
        self.n_calculations += 1


# --- CLI argument handling -------------------------------------------------

def test_cli_flag_exists():
    import inspect
    from rudeus.mlip import run_p2
    src = inspect.getsource(run_p2.main)
    assert "--p2-stall-profile" in src
    assert "--batch-id" in src


def test_cli_missing_batch_id_fails_closed(capsys):
    import sys
    from rudeus.mlip import run_p2
    argv = ["run_p2", "--p2-stall-profile", "--config", "config.yaml"]
    old = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(SystemExit) as e:
            run_p2.main()
        assert e.value.code == 2
        assert "--batch-id" in capsys.readouterr().out
    finally:
        sys.argv = old


def _write_p1_done(tmp_path, batch_id):
    from rudeus.mlip.sharding import structure_dict_sha256
    struct = _tiny_struct_dict()
    rec = {"batch_id": batch_id, "child_material_id": "g1-test",
           "parent_id": "obelix:test",
           "result": {"p1_verdict": "KEEP_FOR_P2",
                      "relaxed_structure_dict": struct,
                      "relaxed_structure_sha256":
                          structure_dict_sha256(struct)}}
    (tmp_path / f"{batch_id}.json").write_text(json.dumps(rec),
                                               encoding="utf-8")


def test_cli_unknown_batch_id_fails_closed(capsys, tmp_path):
    import sys
    from rudeus.mlip import run_p2
    argv = ["run_p2", "--p2-stall-profile", "--batch-id", "deadbeef",
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


def test_cli_cuda_requested_without_cuda_fails_closed(capsys, tmp_path):
    import sys
    import torch
    if torch.cuda.is_available():
        pytest.skip("meant for CUDA-absent machines")
    from rudeus.mlip import run_p2
    _write_p1_done(tmp_path, "ee44")
    argv = ["run_p2", "--p2-stall-profile", "--batch-id", "ee44",
            "--p1-done", str(tmp_path), "--config", "config.yaml",
            "--device", "cuda"]
    old = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(SystemExit) as e:
            run_p2.main()
        assert e.value.code == 2
        assert "no CUDA device" in capsys.readouterr().out
    finally:
        sys.argv = old


# --- Requested limits respected --------------------------------------------

def test_default_1000_step_limit_respected():
    assert DEFAULT_PROD_STEPS == 1000
    assert DEFAULT_CHECKPOINT_EVERY == 100
    buf = io.StringIO()
    out = _run(buf, prod_steps=1000, checkpoint_every=100)
    assert out["executed"] == {"equil_steps": 20, "production_steps": 1000}
    assert [r["step"] for r in out["checkpoints"]] == \
        [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    assert out["outcome"] == "COMPLETED"
    assert out["last_production_step"] == 1000


def test_full_equil_plus_1000_shape():
    """Exact diagnostic shape: 2000 equil + 1000 production, one trajectory."""
    buf = io.StringIO()
    out = _run(buf, protocol=_tiny_protocol(equil_steps=2000),
               prod_steps=1000, checkpoint_every=100)
    assert out["executed"] == {"equil_steps": 2000,
                               "production_steps": 1000}
    assert len(out["checkpoints"]) == 10
    assert out["checkpoints"][-1]["step"] == 1000
    assert out["last_production_step"] == 1000


def test_custom_bounds_respected():
    buf = io.StringIO()
    out = _run(buf, prod_steps=10, checkpoint_every=2)
    assert [r["step"] for r in out["checkpoints"]] == [2, 4, 6, 8, 10]
    assert out["last_production_step"] == 10


# --- Output fields ----------------------------------------------------------

def test_output_contains_required_fields(capsys):
    buf = io.StringIO()
    out = _run(buf)
    header_required = {"diagnostic", "batch_id", "natoms", "seed",
                       "checkpoint_id", "device", "dtype",
                       "force_timing_semantics", "executed", "checkpoints",
                       "termination", "outcome", "versions",
                       "interval_comparison"}
    assert header_required <= set(out)
    assert out["diagnostic"] == "p2-stall-profile"
    assert out["natoms"] == 2 and out["seed"] == 7
    assert out["versions"]["torch_version"]
    row_required = set(TABLE_COLUMNS)
    assert row_required == {"step", "elapsed_s", "interval_s_per_step",
                            "force_s", "force_evals", "T_K", "max_force",
                            "energy_eV", "min_dist_A", "max_disp_A"}
    for r in out["checkpoints"]:
        assert row_required <= set(r)
        assert r["elapsed_s"] is not None
        assert r["interval_s_per_step"] is not None
        assert r["force_s"] is not None and r["force_s"] >= 0
        assert r["force_evals"] is not None and r["force_evals"] > 0
        assert r["T_K"] is not None and r["min_dist_A"] is not None
    text = buf.getvalue()
    for col in TABLE_COLUMNS:
        assert col in text
    assert "01: " not in text  # sanity: table is the printed format
    assert "force_timing=" in text and "outcome=COMPLETED" in text


def test_payload_carries_no_verdict_language():
    out = _run()
    blob = json.dumps(out, default=str)
    assert "dynamic_state" not in out and "p2_verdict" not in out
    assert "TransportState" not in blob and "DIFFUSIVE" not in blob
    assert "transport_state" not in blob


def test_table_format_pure():
    rows = [{"step": 100, "elapsed_s": 12.345, "interval_s_per_step": 0.1234,
             "force_s": 0.1111, "force_evals": 320, "T_K": 550.2,
             "max_force": 0.5, "energy_eV": -100.123, "min_dist_A": 1.234,
             "max_disp_A": None}]
    text = format_checkpoint_table(rows)
    lines = text.splitlines()
    assert lines[0] == " | ".join(TABLE_COLUMNS)
    assert "n/a" in lines[1]  # missing displacement renders explicitly
    assert lines[1].startswith("100 | ")
    assert format_checkpoint_table([]) == " | ".join(TABLE_COLUMNS)


def test_build_checkpoint_rows_empty_record():
    rows = build_checkpoint_rows({"frames": []}, 100, 1000)
    assert rows == []


# --- No production writes ----------------------------------------------------

def test_writes_no_files(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _run()
    assert list(tmp_path.iterdir()) == []


def test_no_production_machinery_in_source():
    from pathlib import Path
    src = Path("rudeus/mlip/stall_profile_diagnostic.py").read_text(
        encoding="utf-8")
    for token in ("run_p2_batches", "commit_done_files", "push_branch",
                  "build_p2_result", "evaluate_p2", "dynamic_state",
                  "TransportState", "DIFFUSIVE", "write_json_atomic",
                  "data/batches/p2"):
        assert token not in src, token


# --- CUDA timing path honesty -------------------------------------------------

def test_select_timing_calc_matches_device():
    """Device-matched wrapper by behavior: one eval records timing."""
    from pymatgen.core import Lattice, Structure
    from pymatgen.io.ase import AseAtomsAdaptor
    from rudeus.mlip.stall_diagnostic import TimingCalculator

    atoms = AseAtomsAdaptor.get_atoms(
        Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]))
    rec: dict = {}
    cuda_wrapped = _select_timing_calc(_ZeroCalculator(), rec, "cuda")
    atoms.calc = cuda_wrapped
    atoms.get_forces()
    assert len(rec["force_times_s"]) == 1  # cuda path delegates + records
    rec2: dict = {}
    cpu_wrapped = _select_timing_calc(_ZeroCalculator(), rec2, "cpu")
    assert isinstance(cpu_wrapped, TimingCalculator)


def test_cuda_path_never_claims_sync_without_cuda():
    import torch
    if torch.cuda.is_available():
        pytest.skip("meant for CUDA-absent machines")
    buf = io.StringIO()
    out = _run(buf, device="cuda")
    # Requested CUDA but none present: honest CPU-wall label, never a
    # synchronized-GPU claim from asynchronous timestamps.
    assert out["force_timing_semantics"] == "cpu_wall_s"
    assert out["cuda_available"] is False
    assert "cuda_event_s" not in out["force_timing_semantics"]
    assert len(out["checkpoints"]) == 5


def test_semantics_helper_labels():
    assert _force_timing_semantics({"force_timing_semantics": "cuda_event_s"},
                                   "cuda") == "cuda_event_s"
    assert _force_timing_semantics({"force_times_s": [0.1]}, "cpu") == \
        "cpu_wall_s"
    assert _force_timing_semantics({}, "cuda") == "not-measured"


def test_sync_mechanism_present_in_source():
    from pathlib import Path
    src = Path("rudeus/mlip/stall_profile_diagnostic.py").read_text(
        encoding="utf-8")
    assert "EventTimingCalculator" in src  # cuda-event + synchronize path


# --- Early termination ---------------------------------------------------------

def test_numerical_abort_prints_partial_and_continues():
    buf = io.StringIO()
    out = _run(buf, calc=_NaNCalculator(clean_evals=25))
    assert out["outcome"] == "NUMERICAL_FAILURE"
    assert "non-finite" in (out["termination"]["note"] or "")
    assert len(out["checkpoints"]) < 5  # aborted before the full 10 steps
    assert out["last_production_step"] < 10
    text = buf.getvalue()
    assert " | ".join(TABLE_COLUMNS) in text  # table still printed
    assert "NUMERICAL_FAILURE" in text


def test_hard_exception_prints_then_raises(monkeypatch):
    import rudeus.mlip.p2 as p2mod

    def _boom(*args, **kwargs):
        raise RuntimeError("synthetic infrastructure boom")

    monkeypatch.setattr(p2mod, "run_nvt", _boom)
    buf = io.StringIO()
    with pytest.raises(RuntimeError, match="synthetic infrastructure boom"):
        _run(buf)
    text = buf.getvalue()
    assert "EXCEPTION" in text  # measurements printed before propagating
    assert "last_production_step=0" in text


# --- Production science untouched ----------------------------------------------

def test_production_protocol_defaults_untouched():
    p = P2_PROTOCOL_DEFAULTS
    assert (p["equil_steps"], p["production_steps"]) == (2000, 8000)
    assert p["temperature_K"] == 550.0
    assert p["timestep_fs"] == 1.0
    assert p["thermostat"] == "langevin"
    assert p["friction_fs_inv_provisional"] == 0.02
    assert p["explosion_abort_A_provisional"] == 3.0
    assert p["lindemann_fail_provisional"] == 0.20
    assert p["host_rmsd_fail_A_provisional"] == 1.0
    assert list(p["production_tier_schedule_provisional"]) == [1000, 3000, 8000]
