"""P2 CUDA/MACE slowdown diagnostics (DIAGNOSTIC-ONLY, no science).

Motivation: a 68-atom candidate shows normal CUDA/MACE step timing for the
first few hundred steps and then appears to stall for minutes with apparent
GPU inactivity (unproven). This module distinguishes:

1. MACE force-evaluation slowdown (CUDA-synchronized timing),
2. MD/integration overhead (wall step time minus force time),
3. async-timing artifacts (explicit timing semantics on every number),
4. GPU throttling/loss (NVML or nvidia-smi telemetry, bounded),
5. state-dependent MACE behavior (windowed force times over an evolving
   trajectory vs. a force-only loop on a fixed structure).

Scope: harness + probes only. No protocol/threshold/evidence/schema/
sharding/checkpoint/resume/git changes. No production writes (outputs go to
dedicated audit dirs or stdout). No daemons, services, databases, queues.
All functions are safe to import and run on CPU-only machines without CUDA,
MACE, pynvml, or nvidia-smi; unavailable backends yield explicit nulls or
error fields instead of failures.

Timing-semantics labels (every reported duration carries one):
- "cuda_event_s": torch.cuda.Event elapsed (synchronized GPU work).
- "cuda_synchronized_wall_s": perf_counter around torch.cuda.synchronize()
  (completed-work wall time; NOT claimed equal to GPU execution time).
- "cpu_wall_s": perf_counter with no CUDA (CPU wall clock only; never
  claimed equivalent to GPU execution time).
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

DIAGNOSTIC_VERSION = "1"
FORCE_DIAG_OUT_DIR = Path("data/batches/audit/p2_force_diagnostic")
STATE_DIAG_OUT_DIR = Path("data/batches/audit/p2_state_diagnostic")
FORBIDDEN_OUT_DIR = Path("data/batches/p2")


def ensure_force_diag_out_dir(out_dir: Union[str, Path]) -> Path:
    """Resolve output dir; refuse anything inside production data/batches/p2."""
    from rudeus.mlip.stall_diagnostic import ensure_diag_out_dir

    return ensure_diag_out_dir(out_dir)


def _refuses_production_dir(out_dir: Union[str, Path]) -> None:
    resolved = Path(out_dir).resolve()
    forbidden = FORBIDDEN_OUT_DIR.resolve()
    if resolved == forbidden or forbidden in resolved.parents:
        raise ValueError(
            f"refusing diagnostic output inside production dir: {out_dir}")


# ---------------------------------------------------------------------------
# 1. CUDA-accurate force timing (diagnostic only; never used by production).
# ---------------------------------------------------------------------------
def timing_semantics(device: str) -> str:
    """Label the timing method for a device without touching CUDA state."""
    try:
        import torch

        if device.startswith("cuda") and torch.cuda.is_available():
            try:
                torch.cuda.Event(enable_timing=True)
                return "cuda_event_s"
            except Exception:
                return "cuda_synchronized_wall_s"
    except Exception:
        pass
    return "cpu_wall_s"


def cuda_synchronize() -> None:
    """Best-effort device synchronize; no-op (never raises) without CUDA."""
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.synchronize()
    except Exception:
        pass


def timed_call(fn: Callable[[], Any], device: str) -> tuple:
    """Time one callable with the best available CUDA-accurate mechanism.

    Returns (result, dt_seconds, semantics). Prefers torch.cuda.Events;
    falls back to synchronize()+perf_counter; on CPU-only boxes uses plain
    perf_counter labeled "cpu_wall_s". Never raises for missing CUDA: the
    fallback path is the normal CPU-box behavior.
    """
    use_cuda = device.startswith("cuda")
    if use_cuda:
        try:
            import torch

            if torch.cuda.is_available():
                try:
                    start = torch.cuda.Event(enable_timing=True)
                    end = torch.cuda.Event(enable_timing=True)
                    torch.cuda.synchronize()
                    start.record()
                    result = fn()
                    end.record()
                    torch.cuda.synchronize()
                    return result, start.elapsed_time(end) / 1000.0, \
                        "cuda_event_s"
                except Exception:
                    pass
                t0 = time.perf_counter()
                result = fn()
                torch.cuda.synchronize()
                return result, time.perf_counter() - t0, \
                    "cuda_synchronized_wall_s"
        except Exception:
            pass
    t0 = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - t0, "cpu_wall_s"


class EventTimingCalculator:
    """Factory for a delegating ASE calculator with CUDA-event force timing.

    Same delegation pattern as stall_diagnostic.TimingCalculator (a REAL
    Calculator subclass so ASE dispatches through it), but each evaluation
    is timed with torch.cuda.Events when available. Diagnostic only: the
    production path never constructs this (see tests).
    """

    def __new__(cls, inner: Any, record: Dict[str, Any], device: str = "cpu"):
        from ase.calculators.calculator import Calculator

        class _Timed(Calculator):
            def __init__(self):
                object.__setattr__(self, "_inner", inner)
                object.__setattr__(self, "_record", record)
                object.__setattr__(self, "_device", str(device))
                Calculator.__init__(self)
                try:
                    self.implemented_properties = list(
                        inner.implemented_properties)
                except Exception:
                    self.implemented_properties = [
                        "energy", "free_energy", "forces",
                        "stress", "stresses"]

            def __getattr__(self, name: str) -> Any:
                try:
                    _inner = object.__getattribute__(self, "_inner")
                except AttributeError:
                    raise AttributeError(name)
                return getattr(_inner, name)

            def calculate(self, atoms=None, properties=None,
                          system_changes=None):
                _dev = object.__getattribute__(self, "_device")
                _inner = object.__getattribute__(self, "_inner")
                _rec = object.__getattribute__(self, "_record")

                def _eval():
                    _inner.calculate(atoms, properties, system_changes)
                    return _inner.results

                if _dev.startswith("cuda"):
                    cuda_synchronize()
                _, dt, semantics = timed_call(_eval, _dev)
                self.results = _inner.results
                _rec.setdefault("force_times_s", []).append(dt)
                _rec.setdefault("force_timing_semantics", semantics)

        return _Timed()


# ---------------------------------------------------------------------------
# 6. Per-window statistics (pure; no CUDA/MACE needed).
# ---------------------------------------------------------------------------
def _quantile_sorted(vals: List[float], q: float) -> Optional[float]:
    if not vals:
        return None
    if len(vals) == 1:
        return float(vals[0])
    pos = q * (len(vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return float(vals[lo] * (1.0 - frac) + vals[hi] * frac)


def summarize_values(vals: List[float]) -> Dict[str, Any]:
    """Overall summary: n, median, p90, p99, min, max (nulls when empty)."""
    s = sorted(float(v) for v in vals)
    if not s:
        return {"n": 0, "median": None, "p90": None, "p99": None,
                "min": None, "max": None}
    return {"n": len(s), "median": _quantile_sorted(s, 0.5),
            "p90": _quantile_sorted(s, 0.90), "p99": _quantile_sorted(s, 0.99),
            "min": float(s[0]), "max": float(s[-1])}


def windowed_summary(vals: List[float],
                     window: int = 100) -> Dict[str, Any]:
    """Split a series into consecutive windows; per-window + overall stats.

    Returns {"windows": [...], "overall": {...}, "first_window_median": ...,
    "middle_window_median": ..., "last_window_median": ...}. The three named
    medians make early-vs-late comparison trivial without re-slicing.
    """
    window = max(1, int(window))
    windows = []
    for i in range(0, len(vals), window):
        chunk = vals[i:i + window]
        windows.append({"window_index": len(windows),
                        "start": i, "end": i + len(chunk),
                        "n": len(chunk), **summarize_values(chunk)})
    overall = summarize_values(vals)
    medians = [w["median"] for w in windows]
    mid = medians[len(medians) // 2] if medians else None
    return {"windows": windows, "overall": overall,
            "first_window_median": medians[0] if medians else None,
            "middle_window_median": mid,
            "last_window_median": medians[-1] if medians else None}


# ---------------------------------------------------------------------------
# 4. GPU telemetry (diagnostic only; bounded; never blocks the MD loop).
# ---------------------------------------------------------------------------
TELEMETRY_FIELDS = ("timestamp", "gpu_index", "utilization_pct", "power_W",
                    "temperature_C", "sm_clock_MHz", "mem_clock_MHz",
                    "mem_used_MiB", "source", "error")


def _telemetry_error(reason: str) -> Dict[str, Any]:
    out = {k: None for k in TELEMETRY_FIELDS}
    out["source"] = "unavailable"
    out["error"] = str(reason)[:300]
    return out


def sample_gpu_telemetry(gpu_index: int = 0,
                         timeout_s: float = 5.0) -> Dict[str, Any]:
    """One bounded GPU sample; never raises (failures -> error field).

    Prefers NVML (pynvml) when importable; otherwise a single lightweight
    `nvidia-smi` subprocess call with a timeout. No daemon, no persistence.
    """
    ts = time.time()
    try:
        import pynvml  # type: ignore

        try:
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(int(gpu_index))
            util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
            power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
            temp = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU)
            try:
                sm = pynvml.nvmlDeviceGetClockInfo(
                    handle, pynvml.NVML_CLOCK_SM)
                mem_clk = pynvml.nvmlDeviceGetClockInfo(
                    handle, pynvml.NVML_CLOCK_MEM)
            except Exception:
                sm, mem_clk = None, None
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle).used / (1 << 20)
            return {"timestamp": ts, "gpu_index": int(gpu_index),
                    "utilization_pct": float(util), "power_W": float(power),
                    "temperature_C": float(temp),
                    "sm_clock_MHz": None if sm is None else float(sm),
                    "mem_clock_MHz": None if mem_clk is None else float(
                        mem_clk),
                    "mem_used_MiB": float(mem), "source": "nvml",
                    "error": None}
        except Exception as exc:
            return _telemetry_error(f"nvml: {type(exc).__name__}: {exc}")
    except Exception:
        pass
    try:
        proc = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=utilization.gpu,power.draw,temperature.gpu,"
             "clocks.sm,clocks.mem,memory.used",
             "--format=csv,noheader,nounits", f"--id={int(gpu_index)}"],
            capture_output=True, text=True, timeout=float(timeout_s))
        if proc.returncode != 0:
            return _telemetry_error(
                f"nvidia-smi rc={proc.returncode}: "
                f"{(proc.stderr or '').strip()[:200]}")
        parts = [p.strip() for p in (proc.stdout or "").strip().split(",")]
        if len(parts) != 6:
            return _telemetry_error(
                f"nvidia-smi: unexpected field count {len(parts)}")

        def _num(s: str) -> Optional[float]:
            try:
                return float(s)
            except Exception:
                return None

        return {"timestamp": ts, "gpu_index": int(gpu_index),
                "utilization_pct": _num(parts[0]), "power_W": _num(parts[1]),
                "temperature_C": _num(parts[2]),
                "sm_clock_MHz": _num(parts[3]),
                "mem_clock_MHz": _num(parts[4]),
                "mem_used_MiB": _num(parts[5]), "source": "nvidia-smi",
                "error": None}
    except FileNotFoundError:
        return _telemetry_error("nvidia-smi not found; no NVML")
    except subprocess.TimeoutExpired:
        return _telemetry_error(f"nvidia-smi timed out after {timeout_s}s")
    except Exception as exc:
        return _telemetry_error(f"{type(exc).__name__}: {exc}")


def summarize_telemetry(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Descriptive means over successful samples; count of failures."""
    ok = [s for s in samples if not s.get("error")]
    out: Dict[str, Any] = {"n_samples": len(samples),
                           "n_ok": len(ok),
                           "n_failed": len(samples) - len(ok)}
    for key in ("utilization_pct", "power_W", "temperature_C",
                "sm_clock_MHz", "mem_clock_MHz", "mem_used_MiB"):
        vals = [s[key] for s in ok
                if isinstance(s.get(key), (int, float))]
        out[f"mean_{key}"] = (float(sum(vals) / len(vals)) if vals else None)
    return out


# ---------------------------------------------------------------------------
# 2. Force-only MACE benchmark (bounded; no MD; no production writes).
# ---------------------------------------------------------------------------
def run_force_benchmark(*, candidate: Dict[str, Any], calc: Any,
                        device: str = "cpu",
                        n_warmup: int = 10, n_evals: int = 300,
                        window: int = 100,
                        cache_buster_eps_A: float = 1e-6,
                        telemetry_every: int = 50,
                        checkpoint_id: str = "",
                        checkpoint_sha256: str = "",
                        out_dir: Union[str, Path] = FORCE_DIAG_OUT_DIR,
                        worker_info: Optional[Dict[str, Any]] = None,
                        stream=None) -> Dict[str, Any]:
    """Repeated force evaluations on the FIXED candidate structure.

    Same pinned checkpoint (verified by the caller exactly as production),
    same CUDA device, no MD integration. Compares early vs late evaluations
    via per-window medians. Bounded: exactly n_warmup + n_evals evaluations,
    then exits. Writes one atomic diagnostic record (never production).
    """
    import sys
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    from rudeus.mlip.sharding import structure_dict_sha256, write_json_atomic
    from rudeus.mlip.validation import collect_backend_versions

    _refuses_production_dir(out_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    batch_id = candidate["batch_id"]
    stream = stream if stream is not None else sys.stdout
    n_warmup, n_evals = max(0, int(n_warmup)), max(1, int(n_evals))

    structure = Structure.from_dict(candidate["structure_dict"])
    atoms = AseAtomsAdaptor.get_atoms(structure)
    atoms.calc = calc
    natoms = len(atoms)
    semantics = timing_semantics(device)
    print(f"[p2forcediag] start batch={batch_id} natoms={natoms} "
          f"device={device} timing={semantics} warmup={n_warmup} "
          f"evals={n_evals}", flush=True, file=stream)

    # Warmup (counts reported; excluded from statistics).
    for k in range(n_warmup):
        atoms.positions[k % natoms, 0] += cache_buster_eps_A
        atoms.get_forces()
    cuda_synchronize()

    force_times: List[float] = []
    wall_times: List[float] = []
    telemetry: List[Dict[str, Any]] = []
    progress_every = max(1, min(int(n_evals), 50))
    for k in range(n_evals):
        atoms.positions[(n_warmup + k) % natoms, 0] += cache_buster_eps_A
        wall_t0 = time.perf_counter()

        def _eval():
            return atoms.get_forces()

        forces, dt, sem = timed_call(_eval, device)
        wall_times.append(time.perf_counter() - wall_t0)
        force_times.append(dt)
        semantics = sem  # actual mechanism used (may differ from probe)
        if telemetry_every and (k % max(1, int(telemetry_every)) == 0):
            telemetry.append(sample_gpu_telemetry())
        if (k + 1) % progress_every == 0 or (k + 1) == n_evals:
            print(f"[p2forcediag] eval={k + 1}/{n_evals} "
                  f"force_s={dt:.4f} ({sem})", flush=True, file=stream)
    try:
        max_force = float(abs(forces).max())  # noqa: F821 (loop-bound)
    except Exception:
        max_force = None

    force_windows = windowed_summary(force_times, window)
    payload = {
        "diagnostic": "p2-force-benchmark",
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "batch_id": batch_id,
        "child_material_id": candidate.get("child_material_id"),
        "parent_id": candidate.get("parent_id"),
        "input_structure_sha256": structure_dict_sha256(
            candidate["structure_dict"]),
        "natoms": natoms,
        "device": device,
        "checkpoint_id": checkpoint_id,
        "checkpoint_sha256": checkpoint_sha256,
        "force_timing_semantics": semantics,
        "timing_note": ("cpu_wall_s is CPU wall-clock time only and is "
                        "NOT equivalent to GPU execution time; "
                        "cuda_event_s measures synchronized GPU work."),
        "n_warmup": n_warmup,
        "n_evals": n_evals,
        "cache_buster_eps_A": cache_buster_eps_A,
        "force_times_s": force_times,
        "wall_times_s": wall_times,
        "force_summary": summarize_values(force_times),
        "force_windows": force_windows,
        "first_window_median_s": force_windows["first_window_median"],
        "middle_window_median_s": force_windows["middle_window_median"],
        "last_window_median_s": force_windows["last_window_median"],
        "wall_summary": summarize_values(wall_times),
        "max_abs_force_eV_A": max_force,
        "telemetry": telemetry,
        "telemetry_summary": summarize_telemetry(telemetry),
        "versions": collect_backend_versions(),
        "worker": worker_info or {},
    }
    target = out_path / f"{batch_id}.forcediag.json"
    write_json_atomic(target, payload)
    payload = dict(payload)
    payload["record_file"] = str(target)
    return payload


# ---------------------------------------------------------------------------
# 3. State-dependent force benchmark via the existing P2 trajectory path.
# ---------------------------------------------------------------------------
def run_state_diagnostic(*, candidate: Dict[str, Any], calc: Any,
                         protocol: Dict[str, Any], seed: int,
                         device: str = "cpu",
                         checkpoint_id: str = "",
                         checkpoint_sha256: str = "",
                         out_dir: Union[str, Path] = STATE_DIAG_OUT_DIR,
                         max_steps: int = 600, heartbeat_steps: int = 100,
                         window: int = 100,
                         worker_info: Optional[Dict[str, Any]] = None,
                         device_info: Optional[Dict[str, Any]] = None,
                         stream=None) -> Dict[str, Any]:
    """Bounded run_nvt on the evolving trajectory with CUDA-synced force
    timing per evaluation + wall step times + heartbeat telemetry.

    Small-hook design: the ONLY instrumentation is the existing
    (step, phase) step_hook plus a delegating calculator wrapper, so the
    production trajectory is unaltered (same seeds, thermostat, sampling,
    abort logic). Windowed synchronized-force medians then answer whether
    force evaluation slows only after the MD state changes. Bounded by
    max_steps; never writes production results or verdicts.
    """
    import sys
    from rudeus.mlip.p2 import protocol_config_hash, run_nvt
    from rudeus.mlip.sharding import structure_dict_sha256, write_json_atomic
    from rudeus.mlip.stall_diagnostic import classify_termination
    from rudeus.mlip.validation import collect_backend_versions

    _refuses_production_dir(out_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    batch_id = candidate["batch_id"]
    stream = stream if stream is not None else sys.stdout

    force_record: Dict[str, Any] = {}
    timing_calc = EventTimingCalculator(calc, force_record, device)
    force_times: List[float] = force_record.setdefault("force_times_s", [])

    equil_exec = min(int(protocol["equil_steps"]), int(max_steps))
    prod_exec = int(max_steps) - equil_exec
    exec_protocol = dict(protocol)
    exec_protocol["equil_steps"] = equil_exec
    exec_protocol["production_steps"] = prod_exec

    # Per-step wall times + heartbeat telemetry via the existing hook slot.
    steps: List[Dict[str, Any]] = []
    heartbeats: List[Dict[str, Any]] = []
    telemetry: List[Dict[str, Any]] = []
    hook_state = {"last_t": None, "t0": time.perf_counter(), "calls": 0,
                  "prev_n": 0}

    def _hook(step: int, phase: str) -> None:
        now = time.perf_counter()
        dt = None if hook_state["last_t"] is None else now - hook_state[
            "last_t"]
        hook_state["last_t"] = now
        hook_state["calls"] += 1
        if dt is not None:
            # Attribute this interval's force cost exactly (count + sum
            # snapshot, same pattern as ProductionProfiler).
            n_now = len(force_times)
            prev_n = hook_state["prev_n"]
            interval_force = float(sum(force_times[prev_n:n_now]))
            hook_state["prev_n"] = n_now
            steps.append({"step": step, "phase": phase, "wall_dt_s": dt,
                          "force_s": interval_force,
                          "n_force": n_now - prev_n})
            if step % max(1, int(heartbeat_steps)) == 0:
                tel = sample_gpu_telemetry()
                telemetry.append(tel)
                entry = {"step": step, "phase": phase,
                         "elapsed_s": now - hook_state["t0"],
                         "wall_dt_s": dt,
                         "interval_force_s": interval_force,
                         "telemetry": tel}
                heartbeats.append(entry)
                print(f"[p2statediag] step={step}/{max_steps} "
                      f"phase={phase} wall_dt_s={dt:.4f} "
                      f"force_s={interval_force:.4f} "
                      f"gpu_util={tel.get('utilization_pct')}",
                      flush=True, file=stream)

    # (hook_state dict above carries all mutable hook state.)
    print(f"[p2statediag] start batch={batch_id} max_steps={max_steps} "
          f"(equil_exec={equil_exec} prod_exec={prod_exec}) "
          f"device={device} heartbeat={heartbeat_steps}",
          flush=True, file=stream)

    outcome = "EXCEPTION"
    record: Dict[str, Any] = {}
    try:
        record = run_nvt(candidate["structure_dict"], timing_calc,
                         exec_protocol, seed, batch_id=batch_id,
                         step_hook=_hook)
        outcome = classify_termination(record.get("termination_note"),
                                       record.get("completed", False))
    except Exception as exc:
        record = {"frames": [], "species": [],
                  "completed": False,
                  "termination_note": f"exception: {type(exc).__name__}: "
                                      f"{exc}"}
        raise
    finally:
        semantics = force_record.get("force_timing_semantics",
                                     timing_semantics(device))
        step_force = [s["force_s"] for s in steps]
        step_wall = [s["wall_dt_s"] for s in steps]
        overhead = [w - f for w, f in zip(step_wall, step_force)]
        force_windows = windowed_summary(step_force, window)
        payload = {
            "diagnostic": "p2-state-benchmark",
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "batch_id": batch_id,
            "child_material_id": candidate.get("child_material_id"),
            "parent_id": candidate.get("parent_id"),
            "input_structure_sha256": structure_dict_sha256(
                candidate["structure_dict"]),
            "protocol_hash": protocol_config_hash(protocol),
            "seed": seed,
            "natoms": len(record.get("species", [])),
            "device": device,
            "checkpoint_id": checkpoint_id,
            "checkpoint_sha256": checkpoint_sha256,
            "force_timing_semantics": semantics,
            "timing_note": ("cpu_wall_s is CPU wall-clock time only and is "
                            "NOT equivalent to GPU execution time; "
                            "cuda_event_s measures synchronized GPU work."),
            "executed": {"equil_steps": equil_exec,
                         "production_steps": prod_exec},
            "heartbeat_interval_steps": heartbeat_steps,
            "window_steps": max(1, int(window)),
            "n_force_evals": len(force_times),
            "force_summary": summarize_values(step_force),
            "force_windows": force_windows,
            "first_window_median_s": force_windows["first_window_median"],
            "middle_window_median_s": force_windows["middle_window_median"],
            "last_window_median_s": force_windows["last_window_median"],
            "wall_summary": summarize_values(step_wall),
            "overhead_summary": summarize_values(overhead),
            "heartbeats": heartbeats,
            "telemetry": telemetry,
            "telemetry_summary": summarize_telemetry(telemetry),
            "termination": {
                "completed": bool(record.get("completed", False)),
                "note": record.get("termination_note")},
            "outcome": outcome,
            "device_info": device_info or {},
            "versions": collect_backend_versions(),
            "worker": worker_info or {},
        }
        target = out_path / f"{batch_id}.statediag.json"
        write_json_atomic(target, payload)
        payload = dict(payload)
        payload["record_file"] = str(target)
    return payload
