"""Tests for the P2 GPU execution-path diagnostic (Task 5.2A).

No test here requires CUDA: GPU-specific assertions skip unless
torch.cuda.is_available(). Nothing here runs the 44-candidate campaign,
writes production outputs, or touches manifests.
"""

import json

import pytest

from rudeus.mlip.gpu_diagnostic import (
    DIAGNOSTIC_VERSION,
    benchmark_forces,
    check_cuequivariance,
    cuda_memory_snapshot,
    resolve_device,
    resolve_diagnostic_candidate,
    run_diagnostic,
)


def test_resolve_device_never_silently_converts_cuda_to_cpu():
    import torch
    assert resolve_device("cpu") == "cpu"
    assert resolve_device("cuda") == "cuda"
    # "auto" follows actual CUDA availability on this machine.
    expected_auto = "cuda" if torch.cuda.is_available() else "cpu"
    assert resolve_device("auto") == expected_auto
    with pytest.raises(ValueError, match="unknown device"):
        resolve_device("tpu")


def test_check_cuequivariance_is_optional_acceleration():
    info = check_cuequivariance()
    assert info["installed"] is False  # not present in this env
    assert info["mace_default_enable_cueq"] is False
    assert info["mace_raises_only_if_enabled"] is True
    assert info["conclusion"] == "optional-acceleration-only"


def test_cuda_memory_snapshot_explicit_nulls_without_cuda():
    import torch
    if torch.cuda.is_available():
        pytest.skip("meant for CUDA-absent machines")
    snap = cuda_memory_snapshot("cuda")
    assert snap["allocated_bytes"] is None
    assert snap["reserved_bytes"] is None


def _write_done_record(directory, batch_id, verdict="KEEP_FOR_P2",
                       with_structure=True):
    from pathlib import Path
    rec = {"batch_id": batch_id,
           "child_material_id": "g1-test",
           "parent_id": "obelix:test",
           "result": {"p1_verdict": verdict}}
    if with_structure:
        from pymatgen.core import Lattice, Structure
        s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                      [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
        rec["result"]["relaxed_structure_dict"] = s.as_dict()
    p = Path(directory) / f"{batch_id}.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    return p


def test_resolve_diagnostic_candidate_missing_fails_clearly(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        resolve_diagnostic_candidate(tmp_path, "deadbeef")


def test_resolve_diagnostic_candidate_rejects_non_keep(tmp_path):
    _write_done_record(tmp_path, "aa00", verdict="FAIL_CONVERGENCE")
    with pytest.raises(ValueError, match="not KEEP_FOR_P2"):
        resolve_diagnostic_candidate(tmp_path, "aa00")


def test_resolve_diagnostic_candidate_ok(tmp_path):
    _write_done_record(tmp_path, "aa00")
    cand = resolve_diagnostic_candidate(tmp_path, "aa00")
    assert cand["batch_id"] == "aa00"
    assert cand["child_material_id"] == "g1-test"
    assert len(cand["structure_dict"]["sites"]) == 2


from ase.calculators.calculator import Calculator

class _ZeroCalculator(Calculator):
    """Stub ASE calculator: zero forces, no ML anywhere."""

    implemented_properties = ["energy", "free_energy", "forces"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.n_calculations = 0

    def calculate(self, atoms=None, properties=None,
                  system_changes=None):
        super().calculate(atoms, properties, system_changes)
        import numpy as np
        n = len(atoms)
        self.results = {"energy": 0.0, "free_energy": 0.0,
                        "forces": np.zeros((n, 3))}
        self.n_calculations += 1


def test_benchmark_forces_with_stub_calculator():
    from pymatgen.core import Lattice, Structure
    from pymatgen.io.ase import AseAtomsAdaptor
    s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    atoms = AseAtomsAdaptor.get_atoms(s)
    stub = _ZeroCalculator()
    out = benchmark_forces(atoms, stub, "cpu", n_warmup=1, n_timed=3)
    assert len(out["per_call_s"]) == 3
    assert out["mean_s"] >= 0
    assert out["max_abs_force_eV_A"] == [0.0, 0.0, 0.0]
    assert out["mem_before"]["allocated_bytes"] is None  # CPU: explicit nulls
    # every call must genuinely evaluate (ASE result caching defeated);
    # otherwise timings measure cache hits (~0 ms) and lie.
    assert stub.n_calculations == 1 + 3
    assert out["cache_buster_eps_A"] == 1e-06


def test_run_diagnostic_writes_nothing_and_preserves_verdict(tmp_path):
    from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS
    _write_done_record(tmp_path, "aa00")
    cand = resolve_diagnostic_candidate(tmp_path, "aa00")
    before = {p.name for p in tmp_path.iterdir()}
    res = run_diagnostic(
        cand, _ZeroCalculator(),
        {"device": "cpu", "checkpoint_sha256": "x"},
        dict(P2_PROTOCOL_DEFAULTS), seed=7, n_warmup=1, n_timed=2,
        mini_steps=4)
    assert res["batch_id"] == "aa00"
    assert res["requested_device"] == "cpu"
    assert res["mini_md"]["completed"] is True
    assert {p.name for p in tmp_path.iterdir()} == before  # no writes
    json.dumps(res)  # JSON-serializable report


def test_cli_gpu_diagnostic_requires_batch_id(capsys):
    import sys
    from rudeus.mlip import run_p2
    argv = ["run_p2", "--gpu-diagnostic", "--config", "config.yaml"]
    old = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(SystemExit) as e:
            run_p2.main()
        assert e.value.code == 2
        assert "--batch-id" in capsys.readouterr().out
    finally:
        sys.argv = old


def test_real_checkpoint_cpu_end_to_end():
    """Real pinned calculator on CPU: full diagnostic on a tiny SYNTHETIC
    cell (labeled non-evidence; skips if checkpoint absent locally)."""
    from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS
    from rudeus.mlip.relax import default_model_path, load_calculator
    import yaml
    if not default_model_path().exists():
        pytest.skip("pinned checkpoint not downloaded locally")
    from pymatgen.core import Lattice, Structure
    mcfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))["mlip"]
    calc = load_calculator(default_model_path(), device="cpu", dtype="float32")
    s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    cand = {"batch_id": "synthetic-cpu-e2e",
            "child_material_id": "SYNTHETIC-NOT-EVIDENCE",
            "structure_dict": s.as_dict()}
    res = run_diagnostic(
        cand, calc, {"device": "cpu",
                     "checkpoint_sha256": mcfg["checkpoint_sha256"]},
        dict(P2_PROTOCOL_DEFAULTS), seed=7,
        n_warmup=1, n_timed=2, mini_steps=6)
    assert res["requested_device"] == "cpu"
    assert res["calculator_probe"]["param_devices"] == ["cpu"]
    assert res["mini_md"]["completed"] is True
    assert len(res["forces"]["per_call_s"]) == 2
    assert all(v >= 0 for v in res["forces"]["per_call_s"])
    json.dumps(res)  # report must stay JSON-serializable
