"""P2 stall diagnostic: bounded, instrumented single-candidate MD runs.

Answers "what happened around step N" without touching science: heartbeat
logs, per-step timing, force-call timing (delegating wrapper), CUDA
telemetry, stall detection, and numerical triage. Writes ONLY to a dedicated
audit directory (never data/batches/p2/), never commits, never ranks,
never sets P2 verdicts or transport states.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import time

from ase.calculators.calculator import Calculator

DIAGNOSTIC_VERSION = "1"
STALL_OUT_DIR = Path("data/batches/audit/p2_stall_diagnostic")
FORBIDDEN_OUT_DIR = Path("data/batches/p2")


def ensure_diag_out_dir(out_dir: Union[str, Path]) -> Path:
    """Resolve output dir; refuse anything inside production data/batches/p2."""
    resolved = Path(out_dir).resolve()
    forbidden = FORBIDDEN_OUT_DIR.resolve()
    if resolved == forbidden or forbidden in resolved.parents:
        raise ValueError(
            f"refusing diagnostic output inside production dir: {out_dir}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def check_stall(last_step_dt_s: Optional[float], threshold_s: float) -> bool:
    """Pure stall predicate: a single step slower than threshold."""
    return last_step_dt_s is not None and last_step_dt_s > threshold_s


class HeartbeatRecorder:
    """Per-step timing + heartbeat state for one bounded run (no MD here)."""

    def __init__(self, heartbeat_steps: int, stall_timeout_s: float,
                 stream=None):
        self.heartbeat_steps = max(1, int(heartbeat_steps))
        self.stall_timeout_s = float(stall_timeout_s)
        self.stream = stream
        self.calls = 0
        self.last_t: Optional[float] = None
        self.step_dts: List[float] = []
        self.heartbeats: List[Dict[str, Any]] = []
        self.stall: Optional[Dict[str, Any]] = None

    def __call__(self, step: int, phase: str) -> None:
        from rudeus.mlip.p2 import DiagnosticStall

        now = time.perf_counter()
        dt = None if self.last_t is None else now - self.last_t
        self.last_t = now
        self.calls += 1
        if dt is not None:
            self.step_dts.append(dt)
        if check_stall(dt, self.stall_timeout_s):
            self.stall = {"step": step, "phase": phase,
                          "step_dt_s": dt,
                          "threshold_s": self.stall_timeout_s}
            raise DiagnosticStall(
                f"step {step} ({phase}) took {dt:.1f}s "
                f"> {self.stall_timeout_s:.0f}s threshold")
        if step % self.heartbeat_steps == 0:
            entry = {"step": step, "phase": phase,
                     "step_dt_s": dt, "wall_elapsed_s": None}
            self.heartbeats.append(entry)
            if self.stream is not None:
                print(f"[p2diag] step={step} phase={phase} "
                      f"step_dt_s={dt if dt is None else round(dt, 3)}",
                      flush=True, file=self.stream)

    def finalize(self) -> Dict[str, Any]:
        dts = self.step_dts
        return {"n_hook_calls": self.calls,
                "n_heartbeats": len(self.heartbeats),
                "step_dt_s": {"n": len(dts),
                              "mean": float(sum(dts) / len(dts)) if dts else None,
                              "max": float(max(dts)) if dts else None},
                "stall": self.stall}


class TimingCalculator(Calculator):
    """Delegating ASE calculator wrapper recording force-eval wall time.

    A REAL Calculator subclass (not a duck-typed wrapper): ASE dispatches
    atoms.get_forces() through base-class methods into self.calculate(),
    so only a true subclass override observes every evaluation. Delegates
    every calculate() call to the inner (production) calculator unchanged;
    records per-call wall time with optional CUDA synchronization around
    timing boundaries so GPU timings measure completed work.
    """

    def __init__(self, inner: Any, record: Dict[str, Any],
                 use_cuda_sync: bool):
        # Set _inner FIRST: base Calculator.__init__ performs attribute
        # lookups (e.g. self._deprecated) that must resolve exactly as they
        # would on the inner calculator itself.
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_record", record)
        object.__setattr__(self, "_use_cuda_sync", use_cuda_sync)
        Calculator.__init__(self)
        try:
            self.implemented_properties = list(
                inner.implemented_properties)
        except Exception:
            self.implemented_properties = [
                "energy", "free_energy", "forces", "stress", "stresses"]

    def __getattr__(self, name: str) -> Any:
        # Delegate everything not found normally (including dunder/class
        # sentinels like _deprecated) to the inner calculator, so behavior
        # matches direct use. Guarded against unset _inner (recursion).
        try:
            inner = object.__getattribute__(self, "_inner")
        except AttributeError:
            raise AttributeError(name)
        return getattr(inner, name)

    def calculate(self, atoms=None, properties=None, system_changes=None):
        import time as _time
        if self._use_cuda_sync:
            try:
                import torch
                torch.cuda.synchronize()
            except Exception:
                pass
        t0 = _time.perf_counter()
        self._inner.calculate(atoms, properties, system_changes)
        if self._use_cuda_sync:
            try:
                import torch
                torch.cuda.synchronize()
            except Exception:
                pass
        dt = _time.perf_counter() - t0
        self.results = self._inner.results
        self._record.setdefault("force_times_s", []).append(dt)
        return self.results


def classify_termination(termination_note: Optional[str],
                         completed: bool) -> str:
    """Map trajectory termination to a diagnostic-only outcome (pure).

    Never produces P2 verdicts or transport claims; INDETERMINATE-style
    uncertainty stays an outcome label, not a scientific state.
    """
    note = termination_note or ""
    if "diagnostic-stall" in note:
        return "STALL_SUSPECTED"
    if "explosive-step" in note:
        return "EXPLOSIVE_TERMINATION"
    if "non-finite" in note or "sampling-error" in note:
        return "NUMERICAL_FAILURE"
    if completed:
        return "COMPLETED"
    return "NUMERICAL_FAILURE"


def summarize_frames(frames: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Descriptive frame statistics (no verdicts)."""
    n_total = len(frames)
    finite = [f for f in frames if f.get("finite", False)]
    phases: Dict[str, int] = {}
    for f in frames:
        phases[str(f.get("phase"))] = phases.get(str(f.get("phase")), 0) + 1
    out: Dict[str, Any] = {
        "n_frames": n_total,
        "n_finite_frames": len(finite),
        "n_nonfinite_frames": n_total - len(finite),
        "phases": phases,
        "last_temperature_K": None,
        "last_max_force_eV_A": None,
        "last_min_distance_A": None,
    }
    if finite:
        last = finite[-1]
        out["last_temperature_K"] = last.get("temperature_K")
        out["last_max_force_eV_A"] = last.get("max_force_eV_A")
    return out


def run_stall_diagnostic(*, candidate: Dict[str, Any], calc: Any,
                         protocol: Dict[str, Any], seed: int,
                         out_dir: Union[str, Path] = STALL_OUT_DIR,
                         max_steps: int = 1200, heartbeat_steps: int = 100,
                         stall_timeout_s: float = 300.0,
                         worker_info: Optional[Dict[str, Any]] = None,
                         device_info: Optional[Dict[str, Any]] = None,
                         stream=None) -> Dict[str, Any]:
    """Bounded instrumented run for one candidate; atomic diagnostic record.

    Executes at most max_steps (equil first, then production) with the SAME
    seed stream as production, so the trajectory is a deterministic prefix
    of the production trajectory. Never writes production results.
    """
    import sys
    from rudeus.mlip.p2 import (
        protocol_config_hash,
        run_nvt,
    )
    from rudeus.mlip.sharding import structure_dict_sha256, write_json_atomic
    from rudeus.mlip.validation import collect_backend_versions

    out_dir = ensure_diag_out_dir(out_dir)
    batch_id = candidate["batch_id"]
    stream = stream if stream is not None else sys.stdout
    timings: Dict[str, Any] = {}
    resolved = str((device_info or {}).get("resolved", ""))
    use_cuda = resolved.startswith("cuda") or bool(
        (device_info or {}).get("cuda_available", False))
    timing_calc = TimingCalculator(calc, timings, use_cuda_sync=use_cuda)

    equil_exec = min(int(protocol["equil_steps"]), int(max_steps))
    prod_exec = int(max_steps) - equil_exec
    # Bounded execution: run_nvt reads step counts from the protocol mapping,
    # so pass an execution-scoped copy. Identity (hash/seed) always refers
    # to the FULL production protocol: same seed stream => the bounded run
    # is a deterministic prefix of the production trajectory.
    exec_protocol = dict(protocol)
    exec_protocol["equil_steps"] = equil_exec
    exec_protocol["production_steps"] = prod_exec
    heartbeat = HeartbeatRecorder(heartbeat_steps, stall_timeout_s,
                                  stream=stream)
    print(f"[p2diag] start batch={batch_id} max_steps={max_steps} "
          f"(equil_exec={equil_exec} prod_exec={prod_exec}) "
          f"heartbeat={heartbeat_steps} stall_timeout_s={stall_timeout_s}",
          flush=True, file=stream)

    outcome = "EXCEPTION"
    record: Dict[str, Any] = {}
    try:
        record = run_nvt(candidate["structure_dict"], timing_calc,
                         exec_protocol, seed, batch_id=batch_id,
                         step_hook=heartbeat)
        hb = heartbeat.finalize()
        outcome = classify_termination(record.get("termination_note"),
                                       record.get("completed", False))
    except KeyboardInterrupt:
        outcome = "CANCELLED"
        record = {"frames": [], "completed": False,
                  "termination_note": "keyboard-interrupt",
                  "cancelled": True}
        raise
    except Exception as exc:
        outcome = "EXCEPTION"
        record = {"frames": [], "completed": False,
                  "termination_note": f"exception: {type(exc).__name__}: {exc}"}
        raise
    finally:
        payload = {
            "diagnostic": "p2-stall",
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "batch_id": batch_id,
            "child_material_id": candidate.get("child_material_id"),
            "parent_id": candidate.get("parent_id"),
            "input_structure_sha256": structure_dict_sha256(
                candidate["structure_dict"]),
            "protocol_hash": protocol_config_hash(protocol),
            "seed": seed,
            "executed": {"equil_steps": equil_exec,
                         "production_steps": prod_exec},
            "heartbeat_interval_steps": heartbeat_steps,
            "stall_timeout_s": stall_timeout_s,
            "termination": {"completed": bool(record.get("completed", False)),
                            "note": record.get("termination_note")},
            "outcome": outcome,
            "timing": heartbeat.finalize(),
            "force_timing_s": timings.get("force_times_s", []),
            "frames_summary": summarize_frames(record.get("frames", [])),
            "device": device_info or {},
            "versions": collect_backend_versions(),
            "worker": worker_info or {},
        }
        target = out_dir / f"{batch_id}.stall.json"
        write_json_atomic(target, payload)
        payload = dict(payload)
        payload["record_file"] = str(target)
    return payload
