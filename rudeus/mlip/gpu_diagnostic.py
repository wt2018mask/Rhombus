"""GPU execution-path diagnostic for P2 MACE runs (Task 5.2A).

Answers one question with evidence instead of dashboard readings: is MACE
actually executing force evaluation on the pinned CUDA device, or is
substantial work silently falling back to CPU?

Scope: harness + probes only. No science changes, no campaign execution,
no manifest/commit/push behavior, no threshold or protocol changes. All
functions are safe to import on CPU-only machines; CUDA-specific sections
report unavailability instead of failing.
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

DIAGNOSTIC_VERSION = "5.2A.1"


def resolve_device(requested: str) -> str:
    """Map a CLI device request to a concrete device string.

    Never silently converts an explicit ``cuda`` request to ``cpu``;
    unknown values fail fast instead of reaching MACE.
    """
    if requested == "auto":
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"
    if requested in ("cpu", "cuda"):
        return requested
    raise ValueError(
        f"unknown device {requested!r}; expected one of auto|cpu|cuda")


def check_cuequivariance() -> Dict[str, Any]:
    """Determine what missing cuequivariance actually means (no speculation).

    Inspects the installed mace package: whether the optional import
    exists, and whether MACECalculator enables it by default.
    """
    installed = importlib.util.find_spec("cuequivariance") is not None
    default_enabled: Optional[bool] = None
    raises_only_if_enabled: Optional[bool] = None
    try:
        import inspect
        from mace.calculators import mace as mace_mod
        sig = inspect.signature(mace_mod.MACECalculator.__init__)
        default_enabled = bool(sig.parameters["enable_cueq"].default)
        src = inspect.getsource(mace_mod.MACECalculator.__init__)
        raises_only_if_enabled = (
            "if enable_cueq and not CUEQQ_AVAILABLE" in src
            and "raise ImportError" in src)
    except Exception:
        pass
    return {
        "installed": installed,
        "mace_default_enable_cueq": default_enabled,
        "mace_raises_only_if_enabled": raises_only_if_enabled,
        "conclusion": (
            "optional-acceleration-only"
            if installed is False and default_enabled is False
            else "needs-human-review"),
    }


def probe_calculator(calc: Any) -> Dict[str, Any]:
    """Record where the model actually lives (not just what was requested)."""
    info: Dict[str, Any] = {"param_devices": [], "dtype": None,
                            "n_params": 0, "param_bytes": 0}
    try:
        models = getattr(calc, "models", [calc])
        devices = set()
        n_params = 0
        n_bytes = 0
        dtype = None
        for m in models:
            for p in m.parameters():
                devices.add(str(p.device))
                n_params += int(p.numel())
                n_bytes += int(p.numel() * p.element_size())
                if dtype is None:
                    dtype = str(p.dtype)
        info["param_devices"] = sorted(devices)
        info["dtype"] = dtype
        info["n_params"] = n_params
        info["param_bytes"] = n_bytes
    except Exception as exc:
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def cuda_memory_snapshot(device: str = "cuda") -> Dict[str, Any]:
    """Current CUDA allocator readings; explicit nulls when unavailable."""
    snap: Dict[str, Any] = {"allocated_bytes": None,
                            "reserved_bytes": None,
                            "device_count": 0, "device_name": None}
    try:
        import torch
        if not torch.cuda.is_available():
            return snap
        snap["device_count"] = int(torch.cuda.device_count())
        try:
            snap["device_name"] = str(torch.cuda.get_device_name(0))
        except Exception:
            snap["device_name"] = "UNKNOWN"
        if device.startswith("cuda"):
            snap["allocated_bytes"] = int(torch.cuda.memory_allocated(device))
            snap["reserved_bytes"] = int(torch.cuda.memory_reserved(device))
    except Exception:
        pass
    return snap


def benchmark_forces(atoms: Any, calc: Any, device: str,
                     n_warmup: int = 2, n_timed: int = 5,
                     cache_buster_eps_A: float = 1e-6) -> Dict[str, Any]:
    """Time repeated force evaluations with CUDA sync so timings are real.

    ASE caches calculator results for unmoved atoms, so every call
    deterministically nudges one atom by ``cache_buster_eps_A`` first;
    without this, repeat calls are cache hits (~0 ms) and timings lie.
    The nudge is far below any physical scale and is reported explicitly.
    """
    import time as _time

    use_cuda = device.startswith("cuda")
    if use_cuda:
        import torch
    atoms.calc = calc
    mem_before = cuda_memory_snapshot(device)
    natoms = len(atoms)

    def _timed_call(k: int):
        atoms.positions[k % natoms, 0] += cache_buster_eps_A
        t0 = _time.perf_counter()
        forces = atoms.get_forces()
        if use_cuda:
            torch.cuda.synchronize()
        return _time.perf_counter() - t0, forces

    for k in range(n_warmup):
        _timed_call(k)
    if use_cuda:
        torch.cuda.synchronize()
    times: List[float] = []
    maxforces: List[float] = []
    for k in range(n_warmup, n_warmup + n_timed):
        dt, forces = _timed_call(k)
        times.append(dt)
        maxforces.append(float(abs(forces).max()))
    mem_after = cuda_memory_snapshot(device)
    peak = None
    if use_cuda:
        try:
            peak = int(torch.cuda.max_memory_allocated(device))
        except Exception:
            pass
    return {"n_warmup": n_warmup, "n_timed": n_timed,
            "cache_buster_eps_A": cache_buster_eps_A,
            "per_call_s": times,
            "mean_s": sum(times) / len(times),
            "median_s": sorted(times)[len(times) // 2],
            "max_abs_force_eV_A": maxforces,
            "mem_before": mem_before, "mem_after": mem_after,
            "peak_allocated_bytes": peak}


def resolve_diagnostic_candidate(p1_done_dir: Union[str, Path],
                                 batch_id: str) -> Dict[str, Any]:
    """Load one P1 done record as diagnostic input; fail clearly if unusable.

    Refuses non-KEEP records and records without a relaxed structure instead
    of silently substituting another candidate.
    """
    path = Path(p1_done_dir) / f"{batch_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"diagnostic candidate {batch_id!r} not found at {path}; "
            "refusing to substitute another candidate")
    payload = json.loads(path.read_text(encoding="utf-8"))
    res = payload.get("result") or {}
    if (res.get("p1_verdict") != "KEEP_FOR_P2"
            or not res.get("relaxed_structure_dict")):
        raise ValueError(
            f"diagnostic candidate {batch_id!r} is not KEEP_FOR_P2 with a "
            "relaxed structure; refusing to substitute another candidate")
    return {"batch_id": batch_id,
            "child_material_id": payload.get("child_material_id"),
            "parent_id": payload.get("parent_id"),
            "structure_dict": res["relaxed_structure_dict"],
            "relaxed_structure_sha256": res.get("relaxed_structure_sha256"),
            "source": f"p1-done:{batch_id}"}


def mini_md(structure_dict: Dict[str, Any], calc: Any,
            protocol: Dict[str, Any], seed: int,
            batch_id: Optional[str] = None) -> Dict[str, Any]:
    """Tiny ASE/Langevin trajectory through the exact production run_nvt path.

    The caller supplies a miniature protocol (e.g. prod 10-20 steps); the MD
    construction (thermostat, seeds, seeds handling) is production code, so
    this exercises the real orchestration, not a copy of it.
    """
    from rudeus.mlip.p2 import run_nvt
    return run_nvt(structure_dict, calc, protocol, seed, batch_id=batch_id)


def compare_cpu_cuda(cpu_forces: List[float], cuda_forces: List[float],
                     cpu_times: List[float], cuda_times: List[float],
                     n_atoms: int) -> Dict[str, Any]:
    """Gross execution-path comparison (descriptive only, no tolerance gate)."""
    import statistics
    diffs = [abs(a - b) for a, b in zip(cpu_forces, cuda_forces)]
    return {
        "n_compared": len(diffs),
        "max_abs_force_difference_eV_A": max(diffs) if diffs else None,
        "cpu_mean_s": statistics.mean(cpu_times) if cpu_times else None,
        "cuda_mean_s": statistics.mean(cuda_times) if cuda_times else None,
        "cuda_median_s": (sorted(cuda_times)[len(cuda_times) // 2]
                          if cuda_times else None),
        "note": ("descriptive only; small systems may legitimately show "
                 "poor GPU utilization when CPU/ASE overhead dominates"),
    }


def run_diagnostic(candidate: Dict[str, Any], calc: Any,
                   calc_info: Dict[str, Any], protocol: Dict[str, Any],
                   seed: int, worker_info: Optional[Dict[str, Any]] = None,
                   n_warmup: int = 2, n_timed: int = 5,
                   mini_steps: int = 12,
                   compare_with: Optional[Callable] = None) -> Dict[str, Any]:
    """Execute the full diagnostic for one candidate; return a JSON report.

    Never writes production outputs, never touches manifests, never commits.
    `compare_with` optionally maps device->calculator for a CPU/CUDA pair.
    """
    from pymatgen.io.ase import AseAtomsAdaptor
    from pymatgen.core import Structure

    structure = Structure.from_dict(candidate["structure_dict"])
    atoms = AseAtomsAdaptor.get_atoms(structure)
    device = str(calc_info.get("device", "cpu"))
    report: Dict[str, Any] = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "batch_id": candidate["batch_id"],
        "child_material_id": candidate.get("child_material_id"),
        "natoms": len(structure),
        "requested_device": device,
        "calculator_probe": probe_calculator(calc),
        "cuequivariance": check_cuequivariance(),
        "worker": worker_info or {},
    }
    report["forces"] = benchmark_forces(atoms, calc, device,
                                        n_warmup=n_warmup, n_timed=n_timed)
    mini_proto = dict(protocol)
    # Small equilibration mirrors production staging (which uses 2000) so
    # startup transients do not dominate the miniature trajectory.
    mini_proto.update({"equil_steps": 10, "production_steps": mini_steps,
                       "sample_interval_steps": max(1, mini_steps // 2)})
    t0 = time.perf_counter()
    record = mini_md(candidate["structure_dict"], calc, mini_proto, seed,
                     batch_id=candidate["batch_id"])
    report["mini_md"] = {
        "steps": mini_steps, "wall_s": time.perf_counter() - t0,
        "completed": record.get("completed"),
        "termination_note": record.get("termination_note"),
        "n_frames": len(record.get("frames", [])),
    }
    if compare_with is not None:
        other = compare_with("cpu" if device.startswith("cuda") else "cuda")
        if other is not None:
            other_calc, other_device = other
            atoms2 = AseAtomsAdaptor.get_atoms(structure)
            other_bench = benchmark_forces(atoms2, other_calc, other_device,
                                           n_warmup=n_warmup, n_timed=n_timed)
            report["comparison"] = compare_cpu_cuda(
                report["forces"]["max_abs_force_eV_A"],
                other_bench["max_abs_force_eV_A"],
                report["forces"]["per_call_s"],
                other_bench["per_call_s"], len(structure))
            report["comparison"]["other_device"] = other_device
        else:
            report["comparison"] = {"status": "unavailable-on-this-machine"}
    return report
