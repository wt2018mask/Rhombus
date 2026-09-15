"""P2 stall-profile diagnostic: 1000 production steps, checkpoints every 100.

Diagnostic-only companion for a suspected production stall on one candidate.
Runs the exact production-path MD construction (same Langevin NVT setup,
thermostat, friction, seeds, sampling cadence, explosive abort as the
campaign uses) for the full 2000-step equilibration plus 1000 production
steps as ONE continuous trajectory, and prints a checkpoint table at
production steps 100, 200, ..., 1000 with wall timing, synchronized
force-evaluation timing, and physical state. The table distinguishes:

  A. stable timing + stable physical metrics (ordinary steady-state run),
  B. timing explosion without physical instability (force-evaluation
     slowdown on an intact trajectory),
  C. physical instability preceding timing explosion (metrics degrade
     first, then steps get slow).

Measurement only: no thresholds, no protocol changes, no P2 classification,
no verdicts, no transport claims, no production writes (no files at all --
stdout plus the returned payload), no commits, no pushes. Nothing here
writes any production result directory or any P2 production JSON. The
trajectory is
a deterministic prefix of the production trajectory (same seed stream), but
nothing here writes any production result directory or any P2 production
JSON.
"""

from __future__ import annotations

import sys
import time
from typing import Any, Callable, Dict, List, Optional

DIAGNOSTIC_TYPE = "p2-stall-profile"
DIAGNOSTIC_VERSION = "1"
DEFAULT_PROD_STEPS = 1000
DEFAULT_CHECKPOINT_EVERY = 100

TABLE_COLUMNS = ("step", "elapsed_s", "interval_s_per_step", "force_s",
                 "force_evals", "T_K", "max_force", "energy_eV",
                 "min_dist_A", "max_disp_A")


def _select_timing_calc(calc: Any, force_record: Dict[str, Any],
                        device: str):
    """Force-timing wrapper matching the device (diagnostic only).

    CUDA resolves to the event-based wrapper (torch.cuda.Events with
    synchronize() around timing boundaries, so reported force times measure
    completed GPU work, never queued-but-unfinished launches). Anywhere else
    resolves to the plain wall-clock wrapper with synchronization disabled.
    The production path never constructs either (see tests).
    """
    if str(device).startswith("cuda"):
        from rudeus.mlip.cuda_force_diagnostic import EventTimingCalculator
        return EventTimingCalculator(calc, force_record, str(device))
    from rudeus.mlip.stall_diagnostic import TimingCalculator
    return TimingCalculator(calc, force_record, use_cuda_sync=False)


def _force_timing_semantics(force_record: Dict[str, Any],
                            device: str) -> str:
    """Explicit timing label; never silently claims synchronized timing."""
    recorded = force_record.get("force_timing_semantics")
    if isinstance(recorded, str) and recorded:
        return recorded
    if not force_record.get("force_times_s"):
        return "not-measured"
    return "cpu_wall_s"


def format_checkpoint_table(rows: List[Dict[str, Any]]) -> str:
    """Render the compact checkpoint table (pure; no CUDA/MACE needed)."""
    lines = [" | ".join(TABLE_COLUMNS)]
    for r in rows:
        cells = []
        for col in TABLE_COLUMNS:
            v = r.get(col)
            if v is None:
                cells.append("n/a")
            elif col in ("step", "force_evals"):
                cells.append(str(int(v)))
            elif col in ("elapsed_s",):
                cells.append(f"{float(v):.2f}")
            elif col in ("interval_s_per_step", "force_s"):
                cells.append(f"{float(v):.4f}")
            elif col == "T_K":
                cells.append(f"{float(v):.1f}")
            elif col == "energy_eV":
                cells.append(f"{float(v):.3f}")
            else:
                cells.append(f"{float(v):.4f}")
        lines.append(" | ".join(cells))
    return "\n".join(lines)


def build_checkpoint_rows(record: Dict[str, Any],
                          checkpoint_every: int,
                          prod_steps: int) -> List[Dict[str, Any]]:
    """Checkpoint rows from a sampled trajectory record (pure).

    Each checkpoint carries the last sampled production frame at or before
    the checkpoint step (exact on the production cadence), plus timing
    aggregates attached later by the runner. Physical metrics come from the
    recorded frames only, so building rows never perturbs MD timing.
    """
    from rudeus.mlip.p2 import min_image_distances, unwrap_trajectory

    every = max(1, int(checkpoint_every))
    frames = record.get("frames", []) or []
    prod_frames = [f for f in frames if f.get("phase") == "production"]
    interval = int(record.get("sample_interval_steps", 10) or 10)
    cell = record.get("cell")
    try:
        import numpy as np

        has_np = cell is not None
    except Exception:
        np = None  # type: ignore
        has_np = False
    unwrapped = None
    if has_np and prod_frames:
        try:
            import numpy as _np

            pos = _np.array([f["positions"] for f in prod_frames])
            unwrapped = unwrap_trajectory(pos, _np.asarray(cell, float))
        except Exception:
            unwrapped = None
    rows: List[Dict[str, Any]] = []
    targets = list(range(every, int(prod_steps) + 1, every))
    for target in targets:
        # Last production frame with implied step <= target. Implied prod
        # step of 0-based frame j is (j + 1) * interval.
        jmax = (target + interval - 1) // interval - 1
        if jmax >= len(prod_frames):
            jmax = len(prod_frames) - 1
        if jmax < 0:
            continue
        f = prod_frames[jmax]
        actual_step = (jmax + 1) * interval
        min_dist = None
        if has_np:
            try:
                import numpy as _np2

                dm = min_image_distances(
                    _np2.asarray(f["positions"], dtype=float),
                    _np2.asarray(cell, dtype=float))
                n = dm.shape[0]
                if n > 1:
                    iu = _np2.triu_indices(n, k=1)
                    vals = dm[iu]
                    vals = vals[_np2.isfinite(vals)]
                    if len(vals):
                        min_dist = float(vals.min())
            except Exception:
                min_dist = None
        max_disp = None
        if unwrapped is not None:
            try:
                import numpy as _np3

                d = unwrapped[jmax] - unwrapped[0]
                max_disp = float(_np3.sqrt((d ** 2).sum(axis=1)).max())
            except Exception:
                max_disp = None
        rows.append({
            "step": int(actual_step),
            "checkpoint_step": int(target),
            "elapsed_s": None,
            "interval_s_per_step": None,
            "force_s": None,
            "force_evals": None,
            "T_K": f.get("temperature_K"),
            "max_force": f.get("max_force_ev_A"),
            "energy_eV": f.get("energy_ev"),
            "min_dist_A": min_dist,
            "max_disp_A": max_disp,
        })
    return rows


def _attach_timing(rows: List[Dict[str, Any]],
                   step_entries: List[Dict[str, Any]],
                   equil_steps: int, t0: float) -> None:
    """Fill elapsed/interval/force columns from per-step hook entries.

    step_entries carry MD-step ("md_step") wall deltas plus exact force
    attribution for that step's interval. Checkpoint c aggregates MD steps
    (equil + prev_c, equil + c]; missing entries (early abort) fall back to
    whatever executed, and checkpoints with no data stay absent upstream.
    """
    by_step = {e["md_step"]: e for e in step_entries}
    prev = 0
    for r in rows:
        c = int(r["checkpoint_step"])
        lo, hi = int(equil_steps) + prev, int(equil_steps) + c
        got = [by_step[s] for s in range(lo + 1, hi + 1) if s in by_step]
        if not got:
            continue
        wall = float(sum(e["dt_s"] for e in got))
        r["elapsed_s"] = float(got[-1]["elapsed_s"])
        r["interval_s_per_step"] = wall / max(1, c - prev)
        r["force_s"] = float(sum(e["force_s"] for e in got))
        r["force_evals"] = int(sum(e["n_force"] for e in got))
        prev = c
    _ = t0  # elapsed basis is entry-relative; kept for signature clarity


def run_stall_profile_diagnostic(
        *, candidate: Dict[str, Any], calc: Any,
        protocol: Dict[str, Any], seed: int,
        checkpoint_id: str = "", checkpoint_sha256: str = "",
        prod_steps: int = DEFAULT_PROD_STEPS,
        checkpoint_every: int = DEFAULT_CHECKPOINT_EVERY,
        device: str = "cpu", dtype: str = "float32",
        worker_info: Optional[Dict[str, Any]] = None,
        device_info: Optional[Dict[str, Any]] = None,
        stream=None) -> Dict[str, Any]:
    """Run the 2000-step equil + 1000-step production profile, print table.

    Uses the exact production run_nvt construction on an execution-scoped
    protocol copy (equil/protocol seeds/thermostat/sampling/abort
    untouched); identity (hash/seed/checkpoint) always refers to the FULL
    production protocol. Prints the checkpoint table to stdout and returns
    the payload. Writes no files. May end early on the existing P2
    explosive guard or a hard exception; either way the reached step and
    available measurements are printed.
    """
    from rudeus.mlip.p2 import protocol_config_hash, run_nvt
    from rudeus.mlip.sharding import structure_dict_sha256
    from rudeus.mlip.stall_diagnostic import classify_termination
    from rudeus.mlip.validation import collect_backend_versions

    batch_id = candidate["batch_id"]
    stream = stream if stream is not None else sys.stdout
    equil_exec = int(protocol["equil_steps"])
    prod_exec = max(1, int(prod_steps))
    every = max(1, int(checkpoint_every))
    exec_protocol = dict(protocol)
    exec_protocol["equil_steps"] = equil_exec
    exec_protocol["production_steps"] = prod_exec

    force_record: Dict[str, Any] = {}
    timing_calc = _select_timing_calc(calc, force_record, device)
    force_times: List[float] = force_record.setdefault("force_times_s", [])

    t0 = time.perf_counter()
    step_entries: List[Dict[str, Any]] = []
    hook_state = {"last_t": None, "prev_n": 0, "last_md_step": 0}

    def _hook(md_step: int, phase: str) -> None:
        # md_step is the observer-call ordinal: ASE fires attached observers
        # once at attach time plus once per MD step (pre-existing semantics,
        # same +1 the production engine accounts for), so the physical MD
        # step is md_step - 1. Normalize here so checkpoint aggregation uses
        # true step boundaries.
        phys_step = int(md_step) - 1
        now = time.perf_counter()
        dt = None if hook_state["last_t"] is None else now - hook_state[
            "last_t"]
        hook_state["last_t"] = now
        hook_state["last_md_step"] = phys_step
        if dt is None:
            return  # attach-time call carries no step delta
        n_now = len(force_times)
        prev_n = hook_state["prev_n"]
        hook_state["prev_n"] = n_now
        step_entries.append({
            "md_step": phys_step, "phase": str(phase),
            "dt_s": float(dt), "elapsed_s": float(now - t0),
            "force_s": float(sum(force_times[prev_n:n_now])),
            "n_force": int(n_now - prev_n),
        })

    try:
        import torch as _torch

        cuda_available = bool(_torch.cuda.is_available())
    except Exception:
        cuda_available = False
    semantics_note = (
        "cuda_event_s measures synchronized GPU work; "
        "cuda_synchronized_wall_s is perf_counter around "
        "torch.cuda.synchronize() (completed-work wall time); "
        "cpu_wall_s is CPU wall-clock only and is NOT equivalent to "
        "GPU execution time.")
    print(f"[p2stallprofile] start batch={batch_id} "
          f"equil={equil_exec} prod={prod_exec} every={every} "
          f"device={device} cuda_available={cuda_available}",
          flush=True, file=stream)

    outcome = "EXCEPTION"
    exception: Optional[str] = None
    record: Dict[str, Any] = {}
    raise_after_print: Optional[BaseException] = None
    try:
        record = run_nvt(candidate["structure_dict"], timing_calc,
                         exec_protocol, seed, batch_id=batch_id,
                         step_hook=_hook)
        outcome = classify_termination(record.get("termination_note"),
                                       record.get("completed", False))
    except KeyboardInterrupt as exc:
        outcome = "CANCELLED"
        exception = "KeyboardInterrupt"
        record = {"frames": [], "species": [],
                  "completed": False,
                  "termination_note": "keyboard-interrupt"}
        raise_after_print = exc
    except Exception as exc:
        outcome = "EXCEPTION"
        exception = f"{type(exc).__name__}: {exc}"
        record = {"frames": [], "species": [],
                  "completed": False,
                  "termination_note": f"exception: {exception}"}
        raise_after_print = exc

    rows = build_checkpoint_rows(record, every, prod_exec)
    _attach_timing(rows, step_entries, equil_exec, t0)
    semantics = _force_timing_semantics(force_record, device)
    versions = collect_backend_versions()
    try:
        from rudeus.mlip.gpu_diagnostic import probe_calculator

        calc_probe = probe_calculator(timing_calc)
    except Exception:
        calc_probe = {"error": "probe-unavailable"}
    natoms = len(record.get("species") or [])
    if not natoms:
        try:
            natoms = len((candidate.get("structure_dict") or {}).get(
                "sites", []))
        except Exception:
            natoms = 0
    last_md = int(hook_state["last_md_step"])
    last_prod = max(0, last_md - equil_exec)
    payload: Dict[str, Any] = {
        "diagnostic": DIAGNOSTIC_TYPE,
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "batch_id": batch_id,
        "child_material_id": candidate.get("child_material_id"),
        "parent_id": candidate.get("parent_id"),
        "input_structure_sha256": structure_dict_sha256(
            candidate["structure_dict"]),
        "protocol_hash": protocol_config_hash(protocol),
        "seed": seed,
        "natoms": natoms,
        "device": device,
        "requested_device": (device_info or {}).get("requested"),
        "cuda_available": cuda_available,
        "dtype": dtype,
        "checkpoint_id": checkpoint_id,
        "checkpoint_sha256": checkpoint_sha256,
        "calculator_probe": calc_probe,
        "force_timing_semantics": semantics,
        "timing_note": semantics_note,
        "executed": {"equil_steps": equil_exec,
                     "production_steps": prod_exec},
        "checkpoint_every_steps": every,
        "n_force_evals": len(force_times),
        "checkpoints": rows,
        "interval_comparison": _interval_comparison(rows),
        "termination": {"completed": bool(record.get("completed", False)),
                        "note": record.get("termination_note")},
        "outcome": outcome,
        "exception": exception,
        "last_md_step": last_md,
        "last_production_step": last_prod,
        "versions": versions,
        "worker": worker_info or {},
    }
    print(f"[p2stallprofile] header batch={batch_id} natoms={natoms} "
          f"seed={seed} device={device} dtype={dtype} "
          f"checkpoint={checkpoint_id} "
          f"torch={versions.get('torch_version')} "
          f"mace={versions.get('mace_version')} "
          f"force_timing={semantics}",
          flush=True, file=stream)
    print(format_checkpoint_table(rows), flush=True, file=stream)
    print(f"[p2stallprofile] end batch={batch_id} outcome={outcome} "
          f"last_production_step={last_prod}/{prod_exec} "
          f"termination={record.get('termination_note')} "
          f"n_checkpoints={len(rows)}",
          flush=True, file=stream)
    if raise_after_print is not None:
        raise raise_after_print
    return payload


def _interval_comparison(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Descriptive early-vs-late interval contrast (no gates, no verdicts).

    Compares mean interval s/step and mean force s/eval between the first
    and second halves of the checkpoint series so a late timing explosion
    (case B) or a stable run (case A) reads off directly; physical columns
    in the table itself carry the instability evidence (case C).
    """
    timed = [r for r in rows if r.get("interval_s_per_step") is not None]
    if len(timed) < 2:
        return {"status": "insufficient-checkpoints", "n_timed": len(timed)}
    half = max(1, len(timed) // 2)
    early, late = timed[:half], timed[half:]

    def _mean(vals: List[float]) -> Optional[float]:
        vals = [float(v) for v in vals if v is not None]
        return float(sum(vals) / len(vals)) if vals else None

    e_step = _mean([r["interval_s_per_step"] for r in early])
    l_step = _mean([r["interval_s_per_step"] for r in late])
    e_force = _mean([r["force_s"] / r["force_evals"] for r in early
                     if r.get("force_evals")])
    l_force = _mean([r["force_s"] / r["force_evals"] for r in late
                     if r.get("force_evals")])
    out: Dict[str, Any] = {
        "status": "ok",
        "n_timed": len(timed),
        "early_steps": [r["step"] for r in early],
        "late_steps": [r["step"] for r in late],
        "early_mean_s_per_step": e_step,
        "late_mean_s_per_step": l_step,
        "early_mean_force_s_per_eval": e_force,
        "late_mean_force_s_per_eval": l_force,
    }
    out["late_early_step_ratio"] = (
        None if not e_step else float(l_step / e_step))
    out["late_early_force_ratio"] = (
        None if not e_force or not l_force
        else float(l_force / e_force))
    return out
