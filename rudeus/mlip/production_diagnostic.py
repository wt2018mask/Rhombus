"""P2 production-path diagnostic: bounded, high-resolution MD-loop timing.

Motivation: the real P2 worker prints only a start line and then one line
per 1000 MD steps, so a slow (or slow-to-start) run looks identical to a
stalled one. Task 5.2B proved the bare MD loop executes; this module
measures the PRODUCTION loop -- the exact same run_nvt construction the
campaign uses (Langevin NVT, same thermostat/seeds/sampling/explosive
abort) -- with per-step timing, force-vs-integration-vs-capture separation,
and heartbeat telemetry, all bounded by max_steps.

Measurement only: no thresholds, no protocol changes, no verdicts, no
transport claims, no production writes. The post-MD scientific classifier
(build_p2_result) is timed opaquely (wall seconds only) so its cost is
known without recording any verdict-like content.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

DIAGNOSTIC_TYPE = "p2-production"
DIAGNOSTIC_VERSION = "1"
PROD_DIAG_OUT_DIR = Path("data/batches/audit/p2_production_diagnostic")
FORBIDDEN_OUT_DIR = Path("data/batches/p2")


def ensure_prod_diag_out_dir(out_dir: Union[str, Path]) -> Path:
    """Resolve output dir; refuse anything inside production data/batches/p2."""
    resolved = Path(out_dir).resolve()
    forbidden = FORBIDDEN_OUT_DIR.resolve()
    if resolved == forbidden or forbidden in resolved.parents:
        raise ValueError(
            f"refusing diagnostic output inside production dir: {out_dir}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _cpu_time_s() -> Optional[float]:
    try:
        return float(time.process_time())
    except Exception:
        return None


def _rss_mb() -> Optional[float]:
    try:
        import resource
        return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
    except Exception:
        return None


def _cuda_state() -> Dict[str, Any]:
    """Best-effort in-process CUDA snapshot; never required for correctness."""
    out: Dict[str, Any] = {"available": False, "device_name": None,
                           "allocated_mb": None, "reserved_mb": None}
    try:
        import torch
        if not torch.cuda.is_available():
            return out
        out["available"] = True
        try:
            out["device_name"] = torch.cuda.get_device_name(0)
        except Exception:
            pass
        try:
            out["allocated_mb"] = float(torch.cuda.memory_allocated()) / 1e6
            out["reserved_mb"] = float(torch.cuda.memory_reserved()) / 1e6
        except Exception:
            pass
    except Exception:
        pass
    return out


class ProductionProfiler:
    """Per-step hook: wall-time, force attribution, heartbeat telemetry.

    Force attribution is exact: the force-timing wrapper appends one entry
    per MACE evaluation to a shared list, and this hook snapshots the
    cumulative (count, sum) at every call, so each step interval owns
    exactly the force evaluations that happened inside it (dynamics +
    sample-triggered alike).

    Step numbering note: ASE invokes attached observers once at attach
    time, so hook call 1 carries no step delta and physical MD step j maps
    to hook call j+1. Timing aggregates are unaffected by this shift.
    """

    def __init__(self, heartbeat_steps: int,
                 force_times: List[float],
                 stream=None):
        self.heartbeat_steps = max(1, int(heartbeat_steps))
        self.force_times = force_times
        self.stream = stream
        self.t0 = time.perf_counter()
        self.cpu_t0 = _cpu_time_s()
        self.last_t: Optional[float] = None
        self.calls = 0
        self.prev_force_n = 0
        self.prev_force_sum = 0.0
        self.steps: List[Dict[str, Any]] = []
        self.heartbeats: List[Dict[str, Any]] = []
        self.hook_overhead_s = 0.0

    def __call__(self, step: int, phase: str) -> None:
        hook_t0 = time.perf_counter()
        now = time.perf_counter()
        dt = None if self.last_t is None else now - self.last_t
        self.last_t = now
        self.calls += 1
        force_n = len(self.force_times)
        force_sum = float(sum(self.force_times[self.prev_force_n:]))
        step_force = force_sum
        step_n_force = force_n - self.prev_force_n
        self.prev_force_n = force_n
        # NOTE: force_sum above is the incremental sum (slice from the
        # previous snapshot), i.e. this interval's force cost, not cumulative.
        if dt is not None:
            self.steps.append({"step": step, "phase": phase,
                               "dt_s": dt, "force_s": step_force,
                               "n_force": step_n_force})
            if step % self.heartbeat_steps == 0:
                recent = [s["dt_s"] for s in self.steps
                          if s["step"] > step - self.heartbeat_steps]
                cuda = _cuda_state()
                cpu_now = _cpu_time_s()
                entry = {
                    "step": step, "phase": phase,
                    "elapsed_seconds": now - self.t0,
                    "mean_step_seconds": (float(sum(recent) / len(recent))
                                          if recent else None),
                    "max_step_seconds": (float(max(recent))
                                         if recent else None),
                    "last_step_seconds": dt,
                    "cpu_time": (None if (cpu_now is None or self.cpu_t0 is None)
                                 else cpu_now - self.cpu_t0),
                    "rss_mb": _rss_mb(),
                    "cuda_memory_allocated_mb": cuda["allocated_mb"],
                    "cuda_memory_reserved_mb": cuda["reserved_mb"],
                }
                self.heartbeats.append(entry)
                if self.stream is not None:
                    print(f"[p2proddiag] step={step} phase={phase} "
                          f"dt_s={round(dt, 4)} "
                          f"force_s={round(step_force, 4)} "
                          f"elapsed_s={round(now - self.t0, 1)}",
                          flush=True, file=self.stream)
        self.hook_overhead_s += time.perf_counter() - hook_t0


def _phase_stats(steps: List[Dict[str, Any]],
                 phase: str) -> Dict[str, Any]:
    dts = [s["dt_s"] for s in steps if s["phase"] == phase]
    force = float(sum(s["force_s"] for s in steps if s["phase"] == phase))
    wall = float(sum(dts))
    return {"steps_completed": len(dts),
            "wall_seconds": wall,
            "mean_step_seconds": (float(wall / len(dts)) if dts else None),
            "max_step_seconds": (float(max(dts)) if dts else None),
            "force_time_s": force}


def run_production_diagnostic(
        *, candidate: Dict[str, Any], calc: Any,
        protocol: Dict[str, Any], seed: int,
        checkpoint_id: str = "", checkpoint_sha256: str = "",
        out_dir: Union[str, Path] = PROD_DIAG_OUT_DIR,
        max_steps: int = 200, heartbeat_steps: int = 50,
        worker_info: Optional[Dict[str, Any]] = None,
        device_info: Optional[Dict[str, Any]] = None,
        stream=None) -> Dict[str, Any]:
    """Bounded production-path run with loop-internal timing.

    Uses the exact production run_nvt code path (same thermostat, seeds,
    sampling interval, explosive abort) on an execution-scoped protocol
    copy limited to max_steps (equil first, then production). Identity
    (hash/seed/checkpoint) always refers to the FULL production protocol.
    Never writes production results; one atomic diagnostic record only.
    """
    import sys
    from rudeus.mlip.p2 import (
        protocol_config_hash,
        run_nvt,
    )
    from rudeus.mlip.sharding import structure_dict_sha256, write_json_atomic
    from rudeus.mlip.stall_diagnostic import TimingCalculator
    from rudeus.mlip.validation import collect_backend_versions

    out_dir = ensure_prod_diag_out_dir(out_dir)
    batch_id = candidate["batch_id"]
    stream = stream if stream is not None else sys.stdout
    resolved = str((device_info or {}).get("resolved", ""))
    use_cuda = resolved.startswith("cuda")

    force_record: Dict[str, Any] = {}
    timing_calc = TimingCalculator(calc, force_record,
                                   use_cuda_sync=use_cuda)
    force_times: List[float] = force_record.setdefault("force_times_s", [])

    equil_exec = min(int(protocol["equil_steps"]), int(max_steps))
    prod_exec = int(max_steps) - equil_exec
    exec_protocol = dict(protocol)
    exec_protocol["equil_steps"] = equil_exec
    exec_protocol["production_steps"] = prod_exec

    profiler: Dict[str, Any] = {"force_times_ref": force_times}
    hook = ProductionProfiler(heartbeat_steps, force_times, stream=stream)
    print(f"[p2proddiag] start batch={batch_id} max_steps={max_steps} "
          f"(equil_exec={equil_exec} prod_exec={prod_exec}) "
          f"heartbeat={heartbeat_steps}", flush=True, file=stream)

    outcome = "EXCEPTION"
    exception: Optional[str] = None
    record: Dict[str, Any] = {}
    try:
        record = run_nvt(candidate["structure_dict"], timing_calc,
                         exec_protocol, seed, batch_id=batch_id,
                         step_hook=hook, profiler=profiler)
        from rudeus.mlip.stall_diagnostic import classify_termination
        outcome = classify_termination(record.get("termination_note"),
                                       record.get("completed", False))
    except KeyboardInterrupt:
        outcome = "CANCELLED"
        exception = "KeyboardInterrupt"
        record = {"frames": [], "species": [], "completed": False,
                  "termination_note": "keyboard-interrupt"}
        raise
    except Exception as exc:
        outcome = "EXCEPTION"
        exception = f"{type(exc).__name__}: {exc}"
        record = {"frames": [], "species": [],
                  "completed": False,
                  "termination_note": f"exception: {exception}"}
        raise
    finally:
        steps = hook.steps
        wall_total = float(sum(s["dt_s"] for s in steps))
        force_total = float(sum(s["force_s"] for s in steps))
        sample_wall = float(profiler.get("frame_capture_time_s", 0.0))
        sample_force = float(profiler.get("sample_force_time_s", 0.0))
        metric_wall = float(profiler.get("metric_update_time_s", 0.0))
        # Non-overlapping partition: frame_capture here is pure
        # capture/convert/metric Python cost (MACE time inside samples
        # is attributed to force, where it belongs).
        frame_pure = max(0.0, sample_wall - sample_force)
        integration = max(0.0, wall_total - force_total - frame_pure)
        residual = max(0.0, wall_total - force_total - frame_pure
                       - integration - hook.hook_overhead_s)
        timing_breakdown = {
            "force_time_s": force_total,
            "integration_time_s": integration,
            "frame_capture_time_s": frame_pure,
            "metric_update_time_s": metric_wall,
            "other_python_time_s": hook.hook_overhead_s + residual,
            "n_force_evals": len(force_times),
            "n_samples": profiler.get("n_samples", 0),
        }
        equil_stats = _phase_stats(steps, "equil")
        prod_stats = _phase_stats(steps, "production")
        for stats, phase in ((equil_stats, "equil"),
                             (prod_stats, "production")):
            cap = float(profiler.get("frame_capture_by_phase_s", {}).get(
                phase, 0.0))
            sforce = float(profiler.get("sample_force_by_phase_s", {}).get(
                phase, 0.0))
            pure = max(0.0, cap - sforce)
            phase_force = stats.pop("force_time_s")
            stats["timing_breakdown"] = {
                "force_time_s": phase_force,
                "integration_time_s": max(
                    0.0, stats["wall_seconds"] - phase_force - pure),
                "frame_capture_time_s": pure,
                "metric_update_time_s": None,
                "other_python_time_s": None,
            }

        # Opaque post-MD production-segment probe: time the real
        # build_p2_result on the partial record; record wall seconds
        # ONLY -- never any verdict/state/metric content.
        postprocess: Dict[str, Any] = {"wall_s": None, "ok": False,
                                       "error": None}
        try:
            from rudeus.mlip.p2 import build_p2_result
            job = {"batch_id": batch_id,
                   "child_material_id": candidate.get("child_material_id"),
                   "parent_id": candidate.get("parent_id"),
                   "relaxed_structure_dict": candidate["structure_dict"],
                   "relaxed_structure_sha256": structure_dict_sha256(
                       candidate["structure_dict"]),
                   "p1_checkpoint": None,
                   "p2_protocol": protocol,
                   "p2_config_hash": protocol_config_hash(protocol),
                   "seed": seed}
            calc_info = {"checkpoint_name": checkpoint_id,
                         "url": "", "sha256": checkpoint_sha256,
                         "device": resolved,
                         "dtype": "float32"}
            _pp_t0 = time.perf_counter()
            build_p2_result(job, dict(record, frames=list(
                record.get("frames", []))), calc_info, worker_info or {})
            postprocess["wall_s"] = time.perf_counter() - _pp_t0
            postprocess["ok"] = True
        except Exception as exc:
            postprocess["error"] = type(exc).__name__

        versions = collect_backend_versions()
        payload = {
            "diagnostic_type": DIAGNOSTIC_TYPE,
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "batch_id": batch_id,
            "candidate_id": candidate.get("child_material_id"),
            "natoms": len(record.get("species", [])),
            "seed": seed,
            "protocol_hash": protocol_config_hash(protocol),
            "executed": {"equil_steps": equil_exec,
                         "production_steps": prod_exec},
            "checkpoint_id": checkpoint_id,
            "checkpoint_sha256": checkpoint_sha256,
            "requested_device": (device_info or {}).get("requested"),
            "resolved_device": resolved,
            "cuda": _cuda_state(),
            "python_version": versions.get("python_version"),
            "torch_version": versions.get("torch_version"),
            "mace_version": versions.get("mace_version"),
            "ase_version": versions.get("ase_version"),
            "phase_results": {"equilibration": equil_stats,
                              "production": prod_stats},
            "timing_breakdown": timing_breakdown,
            "heartbeats": hook.heartbeats,
            "termination": {"completed": bool(record.get("completed", False)),
                            "note": record.get("termination_note")},
            "termination_reason": outcome,
            "exception": exception,
            "postprocess": postprocess,
            "worker": worker_info or {},
        }
        target = out_dir / f"{batch_id}.proddiag.json"
        write_json_atomic(target, payload)
        payload = dict(payload)
        payload["record_file"] = str(target)
    return payload
