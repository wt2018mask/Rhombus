"""P2 550 K NVT finite-temperature stability + framework integrity screen.

Scientific responsibility: judge whether a P1-relaxed candidate remains
structurally and thermally stable over a finite-temperature trajectory with
enough evidence to continue to P2.5. P2 is a DYNAMIC stability screen, NOT a
transport classifier: it NEVER asserts DIFFUSIVE/NONDIFFUSIVE or any transport
state (P2.5 owns mobile-ion MSD + alpha2). Large Li displacement with a
collapsed framework is FAIL, never transport success.

All numeric gates below are PROVISIONAL (uncalibrated placeholders) unless
noted. No scores, no ranking. DynamicState only (NOT_RUN/FAIL/INDETERMINATE/
PASS); transport_state is never touched.

P2 trajectory policy (PROVISIONAL screening-efficiency policy, not a
transport-convergence claim): 2 ps equilibration, then adaptive cumulative
production tiers of 1 ps / 3 ps / 8 ps (1000 / 3000 / 8000 steps at 1 fs).
A tier yielding clear existing FAIL or PASS evidence stops the trajectory;
borderline/insufficient evidence extends it as one continuous trajectory
(no velocity/thermostat restart). P2.5/P3 remain responsible for transport.
Shorter P2 trajectories reduce unnecessary compute; they say nothing about
diffusion-coefficient convergence, whose uncertainty depends on simulation
time, cell size, and mobile-particle/jump-event counts.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from rudeus.filters.f3_diffusive import compute_msd_curve
from rudeus.mlip.p2_traj import (
    P2_TRAJ_FORMAT_VERSION,
    build_traj_payload,
    write_traj_artifact,
)
from rudeus.mlip.sharding import (
    assign_shard,
    structure_dict_sha256,
    write_json_atomic,
)
from rudeus.schema import DynamicState, EvidenceEvent

# ---------------------------------------------------------------------------
# Adaptive production policy (PROVISIONAL screening-efficiency choice).
# Cumulative production tiers in MD steps (1 fs timestep): 1 ps / 3 ps / 8 ps.
# A fully extended candidate therefore runs 2000 equil + 8000 production =
# 10,000 total MD steps, but the default path stops earlier whenever tier
# evidence already supports the existing PASS/FAIL semantics. This schedule
# is part of the hashed protocol: changing it changes protocol_config_hash.
# ---------------------------------------------------------------------------
P2_PROTOCOL_VERSION = "p2-adaptive-v1-provisional"
P2_TRAJECTORY_POLICY = "adaptive-1000-3000-8000-v1-provisional"
P2_PRODUCTION_TIERS_PROVISIONAL: Tuple[int, ...] = (1000, 3000, 8000)

# Early-stop reason vocabulary for adaptive provenance (observability only;
# never a scientific gate, never part of any threshold).
P2_EARLY_STOP_REASONS = (
    "clear_failure",
    "clear_pass",
    "insufficient_evidence",
    "numerical_failure",
    "explosive_termination",
    "completed_final_tier",
)

# ---------------------------------------------------------------------------
# Protocol: one clearly identifiable configuration structure (550 K NVT).
# Durations are step counts (timestep 1 fs). Defaults target GPU sessions;
# pilot/CI runs override equil/production steps via CLI (same code path).
# ---------------------------------------------------------------------------
P2_PROTOCOL_DEFAULTS: Dict[str, Any] = {
    "p2_protocol_version": P2_PROTOCOL_VERSION,
    "trajectory_policy": P2_TRAJECTORY_POLICY,
    "production_tier_schedule_provisional": list(P2_PRODUCTION_TIERS_PROVISIONAL),
    "temperature_K": 550.0,
    "timestep_fs": 1.0,
    "equil_steps": 2000,
    "production_steps": 8000,
    "sample_interval_steps": 10,
    "thermostat": "langevin",
    "friction_fs_inv_provisional": 0.02,
    "fix_center_of_mass": True,
    "mobile_species": "Li",
    "base_seed": 550,
    # Sampling-sufficiency gates (PROVISIONAL).
    "min_production_frames_provisional": 50,
    "min_mobile_ions_provisional": 4,
    # Structural/thermal FAIL gates (PROVISIONAL, gross-failure only).
    "host_rmsd_fail_A_provisional": 1.0,
    "lindemann_fail_provisional": 0.20,
    # Lindemann corroboration bars (Task 3 falsification, PROVISIONAL): a
    # Lindemann excursion FAILs only with >=1 corroborating flag, else the
    # conflicting evidence is held INDETERMINATE (never PASS). Bars sit where
    # control evidence never reaches but collapse evidence does.
    "lindemann_corr_rmsd_A_provisional": 0.7,
    "lindemann_corr_min_dist_A_provisional": 1.2,
    "lindemann_corr_coord_provisional": 1.0,
    "volume_drift_fail_fraction_provisional": 0.15,
    "min_distance_fail_A_provisional": 0.8,
    "coord_mean_change_fail_provisional": 2.0,
    "temp_mean_tol_K_provisional": 150.0,
    "temp_std_fail_K_provisional": 150.0,
    "energy_drift_fail_ev_per_ps_per_atom_provisional": 0.05,
    # Numerical abort: single-sample max displacement above this ends the run.
    "explosion_abort_A_provisional": 3.0,
}


# Production progress heartbeat cadence (observability only, PROVISIONAL
# display choice, not a scientific threshold; never part of the protocol hash).
P2_PROGRESS_HEARTBEAT_STEPS = 100


def _format_duration_s(seconds: float) -> str:
    """Compact duration for the progress heartbeat (observability only)."""
    s = max(0.0, float(seconds))
    if s < 60.0:
        return f"{s:.1f}s"
    if s < 3600.0:
        m = int(s // 60)
        return f"{m}m{int(s % 60):02d}s"
    h = int(s // 3600)
    return f"{h}h{int((s % 3600) // 60):02d}m{int(s % 60):02d}s"


def protocol_config_hash(protocol: Dict[str, Any]) -> str:
    """Deterministic hash of the physics-defining protocol (no wall-clock)."""
    payload = json.dumps(protocol, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def batch_seed(base_seed: int, batch_id: str) -> int:
    """Deterministic per-batch seed (recorded in every result)."""
    return (int(base_seed) + int(batch_id[:8], 16)) % (2 ** 32)


def effective_production_tiers(protocol: Dict[str, Any]) -> List[int]:
    """Cumulative production tiers (steps) actually executed for a protocol.

    The default is exactly [1000, 3000, 8000]. The final tier is always the
    configured ``production_steps`` limit, so small pilot/CI overrides (e.g.
    600 production steps) collapse to a single final evaluation on the same
    code path instead of triggering inapplicable tiers.
    """
    limit = int(protocol["production_steps"])
    sched = protocol.get("production_tier_schedule_provisional") or []
    tiers = sorted({int(t) for t in sched if int(t) > 0 and int(t) <= limit})
    if not tiers or tiers[-1] != limit:
        tiers = sorted(set(tiers + [limit]))
    return tiers


def tier_stop_decision(state: DynamicState, is_final_tier: bool) -> bool:
    """Whether a tier evaluation ends the adaptive trajectory.

    Existing semantics only: PASS or FAIL stops at any tier; INDETERMINATE
    (borderline / insufficient evidence, including uncorroborated marginal
    Lindemann) continues unless no tiers remain. No new score, no loosened
    gate: short trajectories extend rather than force a verdict.
    """
    if state in (DynamicState.PASS, DynamicState.FAIL):
        return True
    return bool(is_final_tier)


def evaluate_p2_tier(record: Dict[str, Any],
                     protocol: Dict[str, Any]) -> Tuple[DynamicState, Dict[str, Any], List[str]]:
    """Evaluate a non-final tier snapshot with the existing P2 machinery.

    A cleanly reached tier is tier-complete by construction, so the
    "terminated before configured end" insufficiency (which guards truncated
    fixed-length runs against forced PASS) does not apply to it. Aborted
    trajectories keep their true flags so explosive/numerical evidence still
    FAILs through the existing order of gates.
    """
    note = record.get("termination_note") or ""
    aborted = (not record.get("completed", True)) or bool(note)
    if aborted:
        return evaluate_p2(record, protocol)
    view = dict(record)
    view["completed"] = True
    view["termination_note"] = None
    return evaluate_p2(view, protocol)


def infer_early_stop_reason(state: DynamicState,
                            reasons: List[str],
                            record: Dict[str, Any],
                            adaptive: Optional[Dict[str, Any]] = None) -> str:
    """Map a stopped trajectory to the provenance stop-reason vocabulary."""
    if adaptive and adaptive.get("early_stop_reason"):
        return str(adaptive["early_stop_reason"])
    note = (record.get("termination_note") or "")
    if "explosive-step" in note or any("explosive" in r for r in (reasons or [])):
        return "explosive_termination"
    if any(str(r).startswith("numerical-failure") for r in (reasons or [])) \
            or "non-finite-data" in note or "sampling-error" in note:
        return "numerical_failure"
    if state == DynamicState.FAIL:
        return "clear_failure"
    if state == DynamicState.PASS:
        return "clear_pass"
    if not record.get("completed", False):
        return "insufficient_evidence"
    return "completed_final_tier"


# ---------------------------------------------------------------------------
# Host/mobile partition (explicit, deterministic; Li mobile when present).
# ---------------------------------------------------------------------------
def partition_host_mobile(species: Sequence[str],
                          mobile_species: str = "Li") -> Dict[str, Any]:
    """Split atom indices into host framework vs mobile ions.

    A material with no mobile-species atoms is NOT a failure: mobile stats
    are recorded as absent and P2 stays transport-neutral.
    """
    mobile_idx = [i for i, s in enumerate(species) if s == mobile_species]
    host_idx = [i for i in range(len(species)) if i not in set(mobile_idx)]
    return {"host_idx": host_idx, "mobile_idx": mobile_idx,
            "n_host": len(host_idx), "n_mobile": len(mobile_idx),
            "mobile_species": mobile_species,
            "mobile_species_absent": len(mobile_idx) == 0}


# ---------------------------------------------------------------------------
# Unwrapping (minimum-image accumulated deltas; NVT cell is fixed).
# ---------------------------------------------------------------------------
def unwrap_trajectory(wrapped: np.ndarray, cell: np.ndarray) -> np.ndarray:
    """Unwrap wrapped Cartesian positions via accumulated MIC deltas.

    Args:
        wrapped: (n_frames, n_atoms, 3) wrapped Cartesian coordinates.
        cell: (3, 3) lattice matrix (rows = lattice vectors).
    """
    inv = np.linalg.inv(np.asarray(cell, dtype=float))
    frac = np.einsum("fij,jk->fik", np.asarray(wrapped, dtype=float), inv)
    deltas = np.diff(frac, axis=0)
    deltas -= np.round(deltas)  # minimum image in fractional space
    unwrapped_frac = np.zeros_like(frac)
    unwrapped_frac[0] = frac[0]
    unwrapped_frac[1:] = frac[0] + np.cumsum(deltas, axis=0)
    return np.einsum("fij,jk->fik", unwrapped_frac, np.asarray(cell, dtype=float))


def mic_step_jump(prev: np.ndarray, pos: np.ndarray,
                  cell: np.ndarray) -> float:
    """Max per-atom displacement between samples under minimum image.

    Raw Cartesian differences see PBC wraps as cell-length jumps; the MIC
    correction distinguishes genuine explosions from boundary crossings.
    """
    inv = np.linalg.inv(np.asarray(cell, dtype=float))
    dfrac = (np.asarray(pos, dtype=float) - np.asarray(prev, dtype=float)) @ inv
    dfrac -= np.round(dfrac)
    dcart = dfrac @ np.asarray(cell, dtype=float)
    return float(np.sqrt((dcart ** 2).sum(axis=1)).max())


def explosion_diagnostic(
    *,
    phase: str,
    md_step: int,
    step_jump_A: float,
    threshold_A: float,
    temperature_K: Optional[float],
    energy_eV: Optional[float],
    max_force_eV_A: Optional[float],
    positions: Optional[np.ndarray],
    cell: Optional[np.ndarray],
    finite: bool,
    previous_positions: Optional[np.ndarray] = None,
    species: Optional[List[str]] = None,
    forces: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Build audit-only information for an existing explosion/non-finite abort.

    This helper does not decide whether a trajectory aborts and does not
    change any scientific threshold or verdict semantics.
    """
    min_dist_A: Optional[float] = None
    max_atom_displacement_A: Optional[float] = None
    max_atom_index: Optional[int] = None
    max_atom_species: Optional[str] = None
    max_atom_force_eV_A: Optional[float] = None
    if finite and positions is not None and cell is not None:
        try:
            d = min_image_distances(np.asarray(positions, dtype=float),
                                    np.asarray(cell, dtype=float))
            finite_d = d[np.isfinite(d) & (d > 0.0)]
            if finite_d.size:
                min_dist_A = float(finite_d.min())
        except Exception:
            min_dist_A = None
    if (finite and positions is not None and previous_positions is not None
            and cell is not None):
        try:
            inv = np.linalg.inv(np.asarray(cell, dtype=float))
            dfrac = (np.asarray(positions, dtype=float)
                     - np.asarray(previous_positions, dtype=float)) @ inv
            dfrac -= np.round(dfrac)
            dcart = dfrac @ np.asarray(cell, dtype=float)
            disp = np.sqrt((dcart ** 2).sum(axis=1))
            if disp.size and np.all(np.isfinite(disp)):
                idx = int(np.argmax(disp))
                max_atom_displacement_A = float(disp[idx])
                max_atom_index = idx
                if species is not None and idx < len(species):
                    max_atom_species = str(species[idx])
                if forces is not None:
                    fm = np.sqrt((np.asarray(forces, dtype=float) ** 2).sum(axis=1))
                    if fm.size and np.all(np.isfinite(fm)):
                        max_atom_force_eV_A = float(fm[idx])
        except Exception:
            pass
    return {
        "phase": str(phase),
        "md_step": int(md_step),
        "step_jump_A": float(step_jump_A),
        "threshold_A": float(threshold_A),
        "temperature_K": None if temperature_K is None else float(temperature_K),
        "energy_eV": None if energy_eV is None else float(energy_eV),
        "max_force_eV_A": (
            None if max_force_eV_A is None else float(max_force_eV_A)
        ),
        "max_atom_displacement_A": max_atom_displacement_A,
        "max_atom_index": max_atom_index,
        "max_atom_species": max_atom_species,
        "max_atom_force_eV_A": max_atom_force_eV_A,
        "min_distance_A": min_dist_A,
        "finite": bool(finite),
    }


def min_image_distances(pos: np.ndarray, cell: np.ndarray) -> np.ndarray:
    """Pairwise minimum-image distances for one frame (Cartesian input)."""
    inv = np.linalg.inv(np.asarray(cell, dtype=float))
    frac = np.einsum("ij,jk->ik", np.asarray(pos, dtype=float), inv)
    n = len(frac)
    out = np.full((n, n), np.inf)
    cell_arr = np.asarray(cell, dtype=float)
    for i in range(n):
        d = frac[i] - frac
        d -= np.round(d)
        cart = d @ cell_arr
        out[i] = np.sqrt((cart ** 2).sum(axis=1))
    return out


# ---------------------------------------------------------------------------
# MD runner (needs calculator; tested in pilot, not unit tests).
# ---------------------------------------------------------------------------
class DiagnosticStall(RuntimeError):
    """Raised by diagnostic step hooks to stop a bounded run.

    Caught inside run_nvt and recorded as a diagnostic termination note.
    Never raised unless a caller supplies step_hook; never a P2 verdict.
    """


def _run_nvt_segments(
    structure_dict: Dict[str, Any], calc,
    protocol: Dict[str, Any], seed: int,
    batch_id: Optional[str] = None,
    step_hook: Optional[Callable[[int, str], None]] = None,
    profiler: Optional[Dict[str, Any]] = None,
    equil_steps: Optional[int] = None,
    prod_segments: Optional[List[int]] = None,
    segment_callback: Optional[Callable[[int, Dict[str, Any], bool], bool]] = None,
) -> Dict[str, Any]:
    """Single continuous 550 K NVT (Langevin) trajectory engine.

    Runs ``equil_steps`` equilibration, then each production segment in order
    on the SAME dynamics object (no velocity/thermostat restart between
    segments). After each production segment, ``segment_callback`` (when
    given) observes ``(production_steps_completed, record_snapshot, aborted)``
    and returns True to stop the trajectory early. Observability (start line,
    ~100-step heartbeat) never affects numerics, sampling, or storage.

    Diagnostic opt-in: step_hook observes each MD step (raises
    DiagnosticStall to stop a bounded run); profiler, when provided,
    accumulates loop-internal timing without changing any numerical,
    sampling, or storage behavior. Both default to None, in which case
    execution is exactly the historical production path.
    """
    from ase.md.langevin import Langevin
    from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    structure = Structure.from_dict(structure_dict)
    species = [str(s.specie) for s in structure]
    atoms = AseAtomsAdaptor.get_atoms(structure)
    atoms.calc = calc
    dt = float(protocol["timestep_fs"])
    temp = float(protocol["temperature_K"])
    fric = float(protocol["friction_fs_inv_provisional"])
    equil = int(equil_steps) if equil_steps is not None else int(protocol["equil_steps"])
    segments = list(prod_segments) if prod_segments is not None \
        else [int(protocol["production_steps"])]
    interval = int(protocol["sample_interval_steps"])

    rng_init = np.random.default_rng(seed + 1)
    rng_dyn = np.random.default_rng(seed + 2)
    MaxwellBoltzmannDistribution(atoms, temperature_K=temp, rng=rng_init)
    dyn = Langevin(atoms, timestep=dt, temperature_K=temp, friction=fric,
                   fixcm=bool(protocol["fix_center_of_mass"]), rng=rng_dyn)

    frames: List[Dict[str, Any]] = []
    state = {"phase": "equil", "aborted": False, "abort_reason": None,
             "prev": None, "termination_diagnostic": None}

    def sample():
        # Profiler-only timing boundary around the existing body: accumulates
        # frame-capture wall time (all getters + conversions + bookkeeping)
        # and, separately, the mic_step_jump metric-update portion. No
        # behavioral change: every exit path of the original body is kept.
        _prof_t0 = time.perf_counter() if profiler is not None else 0.0
        # Force-attribution reference (diagnostic only): when the caller
        # times force evaluations into profiler["force_times_ref"] (a list
        # the wrapper appends per-call durations to), snapshot its length
        # so MACE time spent inside this sample can be separated from
        # pure capture/convert/metric cost. Pure reads when enabled.
        _force_ref = profiler.get("force_times_ref") if profiler is not None else None
        _force_n0 = len(_force_ref) if _force_ref is not None else 0
        try:
            pos = np.asarray(atoms.get_positions(), dtype=float)
            t = float(atoms.get_temperature())
            e = float(atoms.get_potential_energy())
            v = float(atoms.get_volume())
            f = np.asarray(atoms.get_forces(), dtype=float)
            fmax = float(np.sqrt((f ** 2).sum(axis=1)).max())
            try:
                stress = np.asarray(atoms.get_stress(), dtype=float)
                press = float(-stress[:3].mean() * 160.21766208)  # eV/A^3 -> GPa
            except Exception:
                press = None
        except Exception as exc:  # calculator failure mid-run
            state["aborted"] = True
            state["abort_reason"] = f"sampling-error: {type(exc).__name__}"
            dyn.abort = True
            if profiler is not None:
                _prof_dt = time.perf_counter() - _prof_t0
                profiler["frame_capture_time_s"] = profiler.get(
                    "frame_capture_time_s", 0.0) + _prof_dt
                _by_phase = profiler.setdefault(
                    "frame_capture_by_phase_s", {})
                _by_phase[state["phase"]] = _by_phase.get(
                    state["phase"], 0.0) + _prof_dt
                if _force_ref is not None:
                    _fs = float(sum(_force_ref[_force_n0:]))
                    profiler["sample_force_time_s"] = profiler.get(
                        "sample_force_time_s", 0.0) + _fs
                    _sf = profiler.setdefault("sample_force_by_phase_s", {})
                    _sf[state["phase"]] = _sf.get(state["phase"], 0.0) + _fs
                profiler["n_samples"] = profiler.get("n_samples", 0) + 1
            return
        finite = bool(np.all(np.isfinite(pos)) and np.isfinite(t)
                      and np.isfinite(e) and np.isfinite(fmax))
        step_jump = 0.0
        if state["prev"] is not None and finite:
            _metric_t0 = time.perf_counter() if profiler is not None else 0.0
            step_jump = mic_step_jump(state["prev"], pos,
                                      np.asarray(atoms.cell.array, dtype=float))
            if profiler is not None:
                profiler["metric_update_time_s"] = profiler.get(
                    "metric_update_time_s", 0.0) + (
                        time.perf_counter() - _metric_t0)
        previous_pos = state["prev"]
        state["prev"] = pos
        # md_step: total MD steps completed when this frame was sampled
        # (progress holds one initial observer call + one entry per MD
        # step, cf. the prod_completed accounting below). Recorded for the
        # P2 trajectory artifact so a future consumer can verify exact
        # production frame indices; never used by P2 science gates.
        frames.append({"phase": state["phase"], "positions": pos,
                       "md_step": max(0, int(progress["n"]) - 1),
                       "temperature_K": t, "energy_ev": e, "volume_A3": v,
                       "pressure_GPa": press, "max_force_ev_A": fmax,
                       "finite": finite, "step_jump_A": step_jump})
        if profiler is not None:
            _prof_dt = time.perf_counter() - _prof_t0
            profiler["frame_capture_time_s"] = profiler.get(
                "frame_capture_time_s", 0.0) + _prof_dt
            _by_phase = profiler.setdefault("frame_capture_by_phase_s", {})
            _by_phase[state["phase"]] = _by_phase.get(
                state["phase"], 0.0) + _prof_dt
            if _force_ref is not None:
                _fs = float(sum(_force_ref[_force_n0:]))
                profiler["sample_force_time_s"] = profiler.get(
                    "sample_force_time_s", 0.0) + _fs
                _sf = profiler.setdefault("sample_force_by_phase_s", {})
                _sf[state["phase"]] = _sf.get(state["phase"], 0.0) + _fs
            profiler["n_samples"] = profiler.get("n_samples", 0) + 1
        _explosion_threshold = float(protocol["explosion_abort_A_provisional"])
        if (not finite or step_jump > _explosion_threshold):
            state["aborted"] = state["aborted"] or True
            state["abort_reason"] = state["abort_reason"] or (
                "non-finite-data" if not finite else "explosive-step")
            if state["termination_diagnostic"] is None:
                state["termination_diagnostic"] = explosion_diagnostic(
                    phase=state["phase"],
                    md_step=max(0, int(progress["n"]) - 1),
                    step_jump_A=step_jump,
                    threshold_A=_explosion_threshold,
                    temperature_K=t,
                    energy_eV=e,
                    max_force_eV_A=fmax,
                    positions=pos,
                    cell=np.asarray(atoms.cell.array, dtype=float),
                    finite=finite,
                    previous_positions=previous_pos,
                    species=species,
                    forces=f,
                )
            dyn.abort = True

    total_steps = equil + sum(segments)
    print(f"[p2] start batch={batch_id} natoms={len(structure)} "
          f"equil={equil} prod={sum(segments)}", flush=True)
    progress = {"n": 0}
    # Heartbeat clock: monotonic elapsed only; read ONLY on heartbeat steps
    # so the per-step cost stays one increment + one modulo (no CUDA sync,
    # no scientific computation).
    _hb_t0 = time.monotonic()

    def count_step():
        # Observability only: one increment + modulo per MD step.
        # Profiler-only: record the step-boundary timestamp so per-step
        # wall time can be derived without touching loop behavior.
        if profiler is not None:
            profiler.setdefault("step_times_s", []).append(time.perf_counter())
        progress["n"] += 1
        if progress["n"] % P2_PROGRESS_HEARTBEAT_STEPS == 0:
            _elapsed = time.monotonic() - _hb_t0
            _rate = _elapsed / progress["n"] if progress["n"] else 0.0
            _remaining = total_steps - progress["n"]
            _msg = (f"[p2] progress batch={batch_id} "
                    f"step={progress['n']}/{total_steps} "
                    f"elapsed={_elapsed:.1f}s rate={_rate:.3f}s/step")
            if _elapsed > 0 and _rate > 0 and _remaining > 0:
                _msg += f" eta={_format_duration_s(_remaining * _rate)}"
            print(_msg, flush=True)
        if step_hook is not None:
            step_hook(progress["n"], state["phase"])

    def snapshot(production_completed: int) -> Dict[str, Any]:
        return {"species": species,
                "cell": np.asarray(atoms.cell.array, dtype=float),
                "frames": [dict(f, positions=np.asarray(f["positions"], dtype=float))
                           for f in frames],
                "wall_clock_s": 0.0,
                "completed": not state["aborted"],
                "termination_note": state["abort_reason"],
                "timestep_fs": dt, "sample_interval_steps": interval,
                "equil_steps": equil, "production_steps": production_completed,
                "thermostat": protocol["thermostat"],
                "friction_fs_inv": fric, "seed": seed,
                "termination_diagnostic": state["termination_diagnostic"]}

    dyn.attach(count_step, interval=1)
    dyn.attach(sample, interval=interval)
    t0 = time.time()
    prod_completed = 0
    stop_early = False
    try:
        state["phase"] = "equil"
        dyn.run(equil)
        state["phase"] = "production"
        state["prev"] = None
        for seg in segments:
            if state["aborted"]:
                break
            dyn.run(int(seg))
            # Truthful executed-step accounting: an abort mid-segment stops
            # dyn.run early, so completed steps come from the step counter,
            # not the segment endpoint. The counter holds one initial
            # attach-time observer call plus one entry per MD step
            # (pre-existing ASE semantics, cf. the +1 sampled frame).
            prod_completed = max(0, int(progress["n"]) - 1 - equil)
            if state["aborted"]:
                break
            if segment_callback is not None:
                if segment_callback(prod_completed, snapshot(prod_completed),
                                    bool(state["aborted"])):
                    stop_early = True
                    break
    except DiagnosticStall as e:
        # Diagnostic-only path: record loud stall, return partial record.
        state["aborted"] = True
        state["abort_reason"] = f"diagnostic-stall-suspected: {e}"
    # Exception-path accounting: a DiagnosticStall raised out of dyn.run
    # skips the per-segment update above, so reconcile once from the step
    # counter here (clean paths are already exact; max keeps them so).
    prod_completed = max(prod_completed, max(0, int(progress["n"]) - 1 - equil))
    wall_s = time.time() - t0
    record = snapshot(prod_completed if segments else 0)
    record["wall_clock_s"] = wall_s
    record["completed"] = (not state["aborted"]) or stop_early
    if stop_early and state["abort_reason"] is None:
        record["termination_note"] = None
    return record


def run_nvt(structure_dict: Dict[str, Any], calc,
            protocol: Dict[str, Any], seed: int,
            batch_id: Optional[str] = None,
            step_hook: Optional[Callable[[int, str], None]] = None,
            profiler: Optional[Dict[str, Any]] = None,
            ) -> Dict[str, Any]:
    """Run deterministic 550 K NVT (Langevin) MD; return the sampled record.

    Fixed-length entry point preserved for diagnostics, pilots, and existing
    tests: runs ``equil_steps`` + ``production_steps`` in one trajectory.
    Production P2 screening prefers :func:`run_nvt_adaptive`.
    """
    prod = int(protocol["production_steps"])
    record = _run_nvt_segments(
        structure_dict, calc, protocol, seed,
        batch_id=batch_id, step_hook=step_hook, profiler=profiler,
        equil_steps=int(protocol["equil_steps"]),
        prod_segments=[prod],
        segment_callback=None)
    # Legacy contract: the fixed-length record reports the configured
    # production length (provenance), even if an abort cut it short.
    record["production_steps"] = prod
    return record


def run_nvt_adaptive(
    structure_dict: Dict[str, Any], calc,
    protocol: Dict[str, Any], seed: int,
    batch_id: Optional[str] = None,
    step_hook: Optional[Callable[[int, str], None]] = None,
    profiler: Optional[Dict[str, Any]] = None,
    evaluate_fn: Optional[Callable[[Dict[str, Any], Dict[str, Any]],
                                   Tuple[DynamicState, Dict[str, Any], List[str]]]] = None,
) -> Dict[str, Any]:
    """Run the adaptive P2 trajectory: 2 ps equil, then cumulative tiers.

    Executes ``effective_production_tiers(protocol)`` (default 1000 / 3000 /
    8000 production steps) as ONE continuous trajectory: equilibration runs
    once, then production extends segment by segment with no velocity or
    thermostat restart. After each tier the existing P2 machinery
    (:func:`evaluate_p2_tier`, same thresholds) decides: PASS/FAIL stops and
    is final; INDETERMINATE continues unless no tiers remain.

    Returns the sampled record (same schema as :func:`run_nvt`, with
    ``production_steps`` set to the steps actually executed) plus an
    ``adaptive`` block: ``trajectory_policy``, ``tiers``, per-tier
    evaluations, ``production_steps_completed``, ``production_stage_reached``,
    ``production_stage_limit``, and ``early_stop_reason``.
    """
    evaluate = evaluate_fn or evaluate_p2_tier
    tiers = effective_production_tiers(protocol)
    limit = tiers[-1]
    equil = int(protocol["equil_steps"])
    deltas = [tiers[0]] + [b - a for a, b in zip(tiers, tiers[1:])]
    tier_traces: List[Dict[str, Any]] = []
    outcome: Dict[str, Any] = {}

    print(f"[p2] adaptive batch={batch_id} equil={equil} "
          f"tiers={','.join(str(t) for t in tiers)} "
          f"policy={protocol.get('trajectory_policy', P2_TRAJECTORY_POLICY)}",
          flush=True)

    def on_segment(prod_completed: int, snap: Dict[str, Any],
                   aborted: bool) -> bool:
        tier_index = tiers.index(prod_completed) + 1 if prod_completed in tiers \
            else len(tiers)
        is_final = prod_completed >= limit
        if aborted:
            state, metrics, reasons = evaluate_p2(snap, protocol)
        else:
            state, metrics, reasons = evaluate(snap, protocol)
        tier_traces.append({
            "tier_index": tier_index,
            "tier_production_steps": prod_completed,
            "is_final_tier": bool(is_final),
            "dynamic_state": state.value,
            "n_production_frames": int(metrics.get("n_production_frames", 0)),
            "n_usable_frames": int(metrics.get("n_usable_frames", 0)),
            "reasons": list(reasons),
        })
        stop = True if aborted else tier_stop_decision(state, is_final)
        head = "; ".join(reasons[:2]) if reasons else "-"
        print(f"[p2] stage={tier_index} batch={batch_id} "
              f"production={prod_completed}/{limit} result={state.value} "
              f"stop={str(stop).lower()} reasons={head}", flush=True)
        if not stop:
            nxt = tiers[tier_index] if tier_index < len(tiers) else limit
            print(f"[p2] stage={tier_index + 1} batch={batch_id} start "
                  f"production={prod_completed}/{nxt}", flush=True)
        outcome["state"] = state
        outcome["reasons"] = list(reasons)
        return stop

    record = _run_nvt_segments(
        structure_dict, calc, protocol, seed,
        batch_id=batch_id, step_hook=step_hook, profiler=profiler,
        equil_steps=equil, prod_segments=deltas,
        segment_callback=on_segment)
    prod_completed = int(record.get("production_steps", 0))
    last = tier_traces[-1] if tier_traces else None
    if last is not None:
        # The stop reason follows the actual stop decision: the last tier's
        # verdict for a clean decision stop (PASS/FAIL, or a completed final
        # tier), the abort evidence when the trajectory died mid-extension.
        stop_reason = infer_early_stop_reason(
            DynamicState(last["dynamic_state"]), last["reasons"], record, None)
        if last["dynamic_state"] in ("PASS", "FAIL") \
                and not record.get("termination_note"):
            # A scientifically decided stop is a valid final result even
            # when fewer than the limit steps ran; only genuine aborts stay
            # incomplete (never silently treated as completed PASS).
            record["completed"] = True
    else:
        stop_reason = infer_early_stop_reason(
            DynamicState.INDETERMINATE, [], record, None)
    record["adaptive"] = {
        "trajectory_policy": str(protocol.get("trajectory_policy",
                                              P2_TRAJECTORY_POLICY)),
        "p2_protocol_version": str(protocol.get("p2_protocol_version",
                                                P2_PROTOCOL_VERSION)),
        "tiers": list(tiers),
        "tier_evaluations": tier_traces,
        "production_steps_completed": prod_completed,
        "production_stage_reached": int(tier_traces[-1]["tier_production_steps"])
        if tier_traces else 0,
        "production_stage_limit": int(limit),
        "early_stop_reason": stop_reason,
    }
    return record


# ---------------------------------------------------------------------------
# Pure evaluation: trajectory record + protocol -> state, metrics, reasons.
# Fully unit-testable without ASE/MACE (replay harness territory).
# ---------------------------------------------------------------------------
def evaluate_p2(record: Dict[str, Any],
                protocol: Dict[str, Any]) -> Tuple[DynamicState, Dict[str, Any], List[str]]:
    """Judge a sampled trajectory. Returns (dynamic_state, metrics, reasons).

    Order: explicit numerical failure -> FAIL; insufficient evidence ->
    INDETERMINATE; structural/thermal gross failure -> FAIL (never transport);
    otherwise PASS. No scores, no ranking, no transport claims.
    """
    g = protocol
    reasons: List[str] = []
    metrics: Dict[str, Any] = {}
    prod = [f for f in record["frames"] if f.get("phase") == "production"]
    metrics["n_sampled_frames"] = len(record["frames"])
    metrics["n_production_frames"] = len(prod)
    metrics["completed"] = bool(record.get("completed", False))
    metrics["termination_note"] = record.get("termination_note")

    finite_flags = [bool(f.get("finite", False)) for f in prod]
    metrics["n_nonfinite_frames"] = int(len(prod) - sum(finite_flags))
    good = [f for f in prod if f.get("finite", False)]
    metrics["n_usable_frames"] = len(good)

    part = partition_host_mobile(record["species"],
                                 g.get("mobile_species", "Li"))
    metrics.update({k: v for k, v in part.items() if k != "host_idx"
                    and k != "mobile_idx"})
    host_idx = np.array(part["host_idx"], dtype=int)
    mobile_idx = np.array(part["mobile_idx"], dtype=int)

    # --- numerical health gate (explicit FAIL) ---
    if metrics["n_nonfinite_frames"] > 0:
        reasons.append(f"numerical-failure: {metrics['n_nonfinite_frames']} "
                       "non-finite production frames")
        metrics.update(_empty_structure_metrics())
        return DynamicState.FAIL, metrics, reasons
    if not record.get("completed", False) and not good:
        reasons.append("no usable production frames (aborted in equilibration)")
        metrics.update(_empty_structure_metrics())
        return DynamicState.FAIL, metrics, reasons

    if not good:
        reasons.append("no usable production frames")
        metrics.update(_empty_structure_metrics())
        return DynamicState.INDETERMINATE, metrics, reasons

    cell = np.asarray(record["cell"], dtype=float)
    wrapped = np.array([f["positions"] for f in good])
    unwrapped = unwrap_trajectory(wrapped, cell)
    temps = np.array([f["temperature_K"] for f in good], dtype=float)
    energies = np.array([f["energy_ev"] for f in good], dtype=float)
    volumes = np.array([f["volume_A3"] for f in good], dtype=float)
    pressures = np.array([f["pressure_GPa"] if f["pressure_GPa"] is not None
                          else np.nan for f in good], dtype=float)
    n_atoms = wrapped.shape[1]
    t_ps = np.arange(len(good)) * float(record["sample_interval_steps"]) \
        * float(record["timestep_fs"]) / 1000.0

    # --- structural metrics (host framework) ---
    disp = unwrapped - unwrapped[0]
    host_disp = disp[:, host_idx, :] if len(host_idx) else np.zeros((len(good), 0, 3))
    host_rms_final = float(np.sqrt((host_disp[-1] ** 2).sum(axis=1).mean())) \
        if len(host_idx) else 0.0
    host_rms_max = float(np.sqrt((host_disp ** 2).sum(axis=2).mean(axis=1)).max()) \
        if len(host_idx) else 0.0
    pctl = [float(x) for x in np.percentile(
        np.sqrt((host_disp[-1] ** 2).sum(axis=1)), [50, 90, 99])] \
        if len(host_idx) else [0.0, 0.0, 0.0]
    d0 = min_image_distances(np.asarray(good[0]["positions"]), cell)
    iu = np.triu_indices(n_atoms, k=1)
    init_min = float(d0[iu].min()) if n_atoms > 1 else 0.0
    host_nn = []
    if len(host_idx):
        for i in host_idx:
            row = np.delete(d0[i], i)
            row = row[np.isfinite(row)]
            if len(row):
                host_nn.append(float(row.min()))
    mean_nn = float(np.mean(host_nn)) if host_nn else init_min
    lindemann = float(host_rms_final / mean_nn) if mean_nn > 0 else 0.0
    vol_drift = float(abs(volumes[-1] - volumes[0]) / volumes[0]) if volumes[0] else 0.0
    min_d = init_min
    for f in good:
        dd = min_image_distances(np.asarray(f["positions"]), cell)
        m = float(dd[iu].min()) if n_atoms > 1 else 0.0
        min_d = min(min_d, m)
    # coordination diagnostic: global cutoff from initial geometry (PROVISIONAL)
    rcut = 1.35 * init_min if init_min > 0 else 0.0
    cn0 = _coordination_numbers(np.asarray(good[0]["positions"]), cell, rcut)
    cn1 = _coordination_numbers(np.asarray(good[-1]["positions"]), cell, rcut)
    cn_mean_change = float(np.mean(cn1 - cn0)) if n_atoms else 0.0
    cn_max_change = float(np.max(np.abs(cn1 - cn0))) if n_atoms else 0.0

    metrics.update({
        "host_rmsd_final_A": host_rms_final,
        "host_rmsd_max_A": host_rms_max,
        "host_disp_p50_p90_p99_A": pctl,
        "lindemann_provisional": lindemann,
        "initial_min_distance_A": init_min,
        "min_distance_traj_A": min_d,
        "volume_drift_fraction": vol_drift,
        "volume_mean_A3": float(volumes.mean()),
        "coord_cutoff_A_provisional": rcut,
        "coord_mean_change": cn_mean_change,
        "coord_max_change": cn_max_change,
    })

    # --- thermal metrics ---
    e_per_atom = energies / max(1, n_atoms)
    slope = float(np.polyfit(t_ps, e_per_atom, 1)[0]) if len(good) >= 3 else 0.0
    metrics.update({
        "temp_mean_K": float(temps.mean()),
        "temp_std_K": float(temps.std()),
        "energy_mean_ev_per_atom": float(e_per_atom.mean()),
        "energy_drift_ev_per_ps_per_atom": slope,
        "pressure_mean_GPa": (None if bool(np.isnan(pressures).all())
                              else float(np.nanmean(pressures))),
        "pressure_std_GPa": (None if bool(np.isnan(pressures).all())
                             else float(np.nanstd(pressures))),
    })

    # --- mobile-ion displacement (REPORT ONLY for P2.5; never a verdict) ---
    if len(mobile_idx):
        mob = unwrapped[:, mobile_idx, :]
        _, msd = compute_msd_curve(mob)
        single = np.sqrt(((mob[-1] - mob[0]) ** 2).sum(axis=1))
        metrics.update({
            "mobile_ms_final_A2": float(msd[-1]) if len(msd) else 0.0,
            "mobile_max_displacement_A": float(single.max()) if len(single) else 0.0,
            "mobile_mean_displacement_A": float(single.mean()) if len(single) else 0.0,
        })
    else:
        metrics.update({"mobile_ms_final_A2": None,
                        "mobile_max_displacement_A": None,
                        "mobile_mean_displacement_A": None})

    # --- explosive abort (explicit FAIL with metrics intact as evidence) ---
    if "explosive-step" in (record.get("termination_note") or ""):
        reasons.append("numerical-failure: trajectory aborted (explosive-step); "
                       "metrics below describe the exploding trajectory")
        return DynamicState.FAIL, metrics, reasons

    # --- sufficiency gate (INDETERMINATE, never forced PASS/FAIL) ---
    insufficient = []
    if len(good) < int(g["min_production_frames_provisional"]):
        insufficient.append(
            f"only {len(good)} usable production frames "
            f"(< {g['min_production_frames_provisional']} PROVISIONAL minimum)")
    if not part["mobile_species_absent"] and \
            part["n_mobile"] < int(g["min_mobile_ions_provisional"]):
        insufficient.append(
            f"only {part['n_mobile']} mobile ions "
            f"(< {g['min_mobile_ions_provisional']} PROVISIONAL minimum)")
    if not record.get("completed", False):
        insufficient.append("trajectory terminated before configured end "
                            f"({record.get('termination_note')})")
    if insufficient:
        reasons.extend("insufficient-evidence: " + s for s in insufficient)
        return DynamicState.INDETERMINATE, metrics, reasons

    # --- structural/thermal gross-failure gates (FAIL, never transport) ---
    # Volume drift is RECORDED but never gated: fixed-cell NVT makes it
    # identically zero on physics (Task 2: 0.00e+00 across all runs), so a
    # hard gate would be vacuous. It remains as a code-error sanity monitor
    # in the metrics, not a verdict.
    # Lindemann requires corroboration (Task 3 falsification): an uncorro-
    # borated excursion means conflicting evidence (mobile-but-intact vs
    # collapse) and is held INDETERMINATE, never PASS and never FAIL.
    fail = []
    marginal = []
    tmean = float(temps.mean())
    tstd = float(temps.std())
    thermal_bad = (
        abs(tmean - float(g.get("temperature_K", 550.0))) > float(g["temp_mean_tol_K_provisional"])
        or tstd > float(g["temp_std_fail_K_provisional"])
        or abs(slope) > float(g["energy_drift_fail_ev_per_ps_per_atom_provisional"]))
    if host_rms_final > float(g["host_rmsd_fail_A_provisional"]):
        fail.append(f"host RMSD {host_rms_final:.3f} A exceeds PROVISIONAL limit")
    thermal_bad = (
        abs(tmean - float(g.get("temperature_K", 550.0))) > float(g["temp_mean_tol_K_provisional"])
        or float(temps.std()) > float(g["temp_std_fail_K_provisional"])
        or abs(slope) > float(g["energy_drift_fail_ev_per_ps_per_atom_provisional"]))
    if lindemann > float(g["lindemann_fail_provisional"]):
        corroborated = (
            host_rms_final > float(g["lindemann_corr_rmsd_A_provisional"])
            or min_d < float(g["lindemann_corr_min_dist_A_provisional"])
            or abs(cn_mean_change) > float(g["lindemann_corr_coord_provisional"])
            or thermal_bad)
        if corroborated:
            fail.append(f"Lindemann {lindemann:.3f} exceeds PROVISIONAL limit "
                        f"with corroborating evidence")
        else:
            marginal.append(
                f"marginal-lindemann-uncorroborated: Lindemann {lindemann:.3f} "
                f"exceeds PROVISIONAL {float(g['lindemann_fail_provisional']):.2f} "
                f"without corroborating RMSD/min-distance/coordination/thermal "
                f"evidence; held INDETERMINATE, not PASS")
    if min_d < float(g["min_distance_fail_A_provisional"]):
        fail.append(f"min distance {min_d:.3f} A below PROVISIONAL floor (overlap)")
    if abs(cn_mean_change) > float(g["coord_mean_change_fail_provisional"]):
        fail.append(f"mean coordination change {cn_mean_change:.2f} exceeds "
                    "PROVISIONAL limit (bond-network collapse)")
    if abs(tmean - float(g.get("temperature_K", 550.0))) > float(g["temp_mean_tol_K_provisional"]):
        fail.append(f"mean T {tmean:.0f} K outside PROVISIONAL thermostat window")
    if float(temps.std()) > float(g["temp_std_fail_K_provisional"]):        fail.append("temperature std exceeds PROVISIONAL limit (thermostat failure)")
    if abs(slope) > float(g["energy_drift_fail_ev_per_ps_per_atom_provisional"]):
        fail.append(f"energy drift {slope:.4f} eV/ps/atom exceeds PROVISIONAL limit")
    if fail:
        reasons.extend("instability: " + s for s in fail)
        return DynamicState.FAIL, metrics, reasons
    if marginal:
        reasons.extend("insufficient-evidence: " + s for s in marginal)
        return DynamicState.INDETERMINATE, metrics, reasons

    reasons.append("trajectory complete, sufficient, no gross failure detected")
    return DynamicState.PASS, metrics, reasons


def _empty_structure_metrics() -> Dict[str, Any]:
    keys = ["host_rmsd_final_A", "host_rmsd_max_A", "host_disp_p50_p90_p99_A",
            "lindemann_provisional", "initial_min_distance_A",
            "min_distance_traj_A", "volume_drift_fraction", "volume_mean_A3",
            "coord_cutoff_A_provisional", "coord_mean_change",
            "coord_max_change", "temp_mean_K", "temp_std_K",
            "energy_mean_ev_per_atom", "energy_drift_ev_per_ps_per_atom",
            "pressure_mean_GPa", "pressure_std_GPa", "mobile_ms_final_A2",
            "mobile_max_displacement_A", "mobile_mean_displacement_A"]
    out = {k: None for k in keys}
    out["n_host"] = 0
    return out


def _coordination_numbers(pos: np.ndarray, cell: np.ndarray,
                          rcut: float) -> np.ndarray:
    """Neighbor counts within rcut (minimum image); diagnostic only."""
    if rcut <= 0:
        return np.zeros(len(pos))
    dm = min_image_distances(pos, cell)
    n = len(pos)
    cn = np.zeros(n)
    for i in range(n):
        row = np.delete(dm[i], i)
        cn[i] = int((row[np.isfinite(row)] < rcut).sum())
    return cn


def build_p2_result(job: Dict[str, Any], record: Dict[str, Any],
                    calc_info: Dict[str, Any],
                    worker_info: Optional[Dict[str, Any]] = None,
                    adaptive_info: Optional[Dict[str, Any]] = None,
                    traj_artifact_dir: Optional[Union[str, Path]] = None,
                    ) -> Dict[str, Any]:
    """Assemble the atomic P2 result: provenance, metrics, dynamic state.

    Sets dynamic_state (NOT_RUN/FAIL/INDETERMINATE/PASS) and appends one P2
    EvidenceEvent. NEVER sets transport_state or any diffusion claim.

    When ``traj_artifact_dir`` is given (production path), the canonical
    production trajectory artifact is persisted atomically to
    ``<traj_artifact_dir>/<batch_id>.npz`` and the result is bound to its
    deterministic SHA256: ``provenance.trajectory_sha256``,
    ``evidence_events[0].artifact_hash``, and the additive
    ``trajectory_artifact`` block all carry the artifact hash, and the
    block records the repository-relative artifact path so a future P2.5
    worker can locate, rehash, and verify it. Any persistence failure
    raises (fail closed): no falsely artifact-bound result is produced
    and the legacy dangling hash is never silently substituted.

    When ``traj_artifact_dir`` is None (historical results and offline
    harnesses), the legacy behavior is preserved byte-compatibly:
    ``trajectory_sha256`` is the hash of rounded in-memory positions and
    no ``trajectory_artifact`` block is emitted.

    Adaptive provenance (additive, backward-readable): when the trajectory
    ran under :func:`run_nvt_adaptive`, the result records
    ``p2_protocol_version``, ``equilibration_steps``,
    ``production_steps_completed``, ``production_stage_reached``,
    ``production_stage_limit``, ``early_stop_reason``, and
    ``trajectory_policy`` so any stop can be audited. Fixed-length records
    get the same keys with the configured final length (completed_final_tier
    semantics); no existing field is renamed or removed.
    """
    protocol = job["p2_protocol"]
    state, metrics, reasons = evaluate_p2(record, protocol)
    adaptive = adaptive_info or record.get("adaptive") or {}
    prod_limit = int(protocol.get("production_steps",
                                 record.get("production_steps", 0)))
    prod_completed = int(adaptive.get("production_steps_completed",
                                      record.get("production_steps",
                                                 prod_limit)))
    stage_reached = int(adaptive.get("production_stage_reached",
                                     prod_completed))
    stage_limit = int(adaptive.get("production_stage_limit", prod_limit))
    stop_reason = infer_early_stop_reason(state, reasons, record, adaptive)
    trajectory_policy = str(adaptive.get(
        "trajectory_policy",
        protocol.get("trajectory_policy", "fixed-production")))
    protocol_version = str(adaptive.get(
        "p2_protocol_version",
        protocol.get("p2_protocol_version", "p2-fixed-v0")))
    tier_traces = list(adaptive.get("tier_evaluations", []))
    traj_hash: str
    traj_block: Optional[Dict[str, Any]]
    if traj_artifact_dir is not None:
        # Artifact-bound path (new contract for newly executed P2 jobs):
        # persist the canonical production trajectory, then bind. Raises
        # on any persistence defect (fail closed, never dangling).
        traj_payload = build_traj_payload(record, job)
        traj_target = Path(traj_artifact_dir) / f"{job['batch_id']}.npz"
        traj_hash = write_traj_artifact(traj_target, traj_payload)
        traj_rel = Path(os.path.relpath(os.path.abspath(traj_target),
                                        os.getcwd())).as_posix()
        traj_block = {
            "path": traj_rel,
            "sha256": traj_hash,
            "format_version": P2_TRAJ_FORMAT_VERSION,
            "n_production_frames": int(
                traj_payload["n_production_frames"]),
        }
    else:
        # Legacy path: hash of rounded in-memory positions only. No
        # verifiable bytes; preserved for historical results and harnesses.
        traj_block = None
        traj_hash = hashlib.sha256(
            np.round(np.array([f["positions"] for f in record["frames"]]),
                     6).tobytes()).hexdigest() if record["frames"] else ""
    event = EvidenceEvent(
        level="P2",
        method="nvt_550K_stability",
        conditions={"temperature_K": protocol["temperature_K"],
                    "timestep_fs": protocol["timestep_fs"],
                    "equil_steps": protocol["equil_steps"],
                    "production_steps": protocol["production_steps"],
                    "production_steps_completed": prod_completed,
                    "production_stage_reached": stage_reached,
                    "production_stage_limit": stage_limit,
                    "early_stop_reason": stop_reason,
                    "trajectory_policy": trajectory_policy,
                    "p2_protocol_version": protocol_version,
                    "sample_interval_steps": protocol["sample_interval_steps"],
                    "thermostat": protocol["thermostat"],
                    "friction_fs_inv_provisional":
                        protocol["friction_fs_inv_provisional"],
                    "seed": job["seed"],
                    "p2_config_hash": job["p2_config_hash"],
                    "trajectory_frames": len(record["frames"])},
        uncertainty=None,
        source=str((worker_info or {}).get("session", "")),
        artifact_hash=traj_hash,
        model_or_data_version=str(calc_info.get("checkpoint_name", "")),
    )
    result: Dict[str, Any] = {
        "candidate_material_id": job.get("child_material_id"),
        "batch_id": job["batch_id"],
        "parent_id": job.get("parent_id"),
        "p2_input_relaxed_sha256": job["relaxed_structure_sha256"],
        "p1_relaxed_structure_sha256": job["relaxed_structure_sha256"],
        "p2_config_hash": job["p2_config_hash"],
        "p2_protocol": protocol,
        "p2_protocol_version": protocol_version,
        "trajectory_policy": trajectory_policy,
        "equilibration_steps": int(protocol.get("equil_steps",
                                                record.get("equil_steps", 0))),
        "production_steps_completed": prod_completed,
        "production_stage_reached": stage_reached,
        "production_stage_limit": stage_limit,
        "early_stop_reason": stop_reason,
        "tier_evaluations": tier_traces,
        "seed": job["seed"],
        "temperature_K": protocol["temperature_K"],
        "timestep_fs": protocol["timestep_fs"],
        "termination": {"completed": bool(record.get("completed", False)),
                        "note": record.get("termination_note")},
        "dynamic_state": state.value,
        "p2_verdict": state.value,  # alias for worker-side filtering
        "host_framework_metrics": {k: metrics[k] for k in
                                   ["host_rmsd_final_A", "host_rmsd_max_A",
                                    "host_disp_p50_p90_p99_A",
                                    "lindemann_provisional",
                                    "initial_min_distance_A",
                                    "min_distance_traj_A",
                                    "volume_drift_fraction",
                                    "volume_mean_A3",
                                    "coord_cutoff_A_provisional",
                                    "coord_mean_change", "coord_max_change"]},
        "thermal_metrics": {k: metrics[k] for k in
                            ["temp_mean_K", "temp_std_K",
                             "energy_mean_ev_per_atom",
                             "energy_drift_ev_per_ps_per_atom",
                             "pressure_mean_GPa", "pressure_std_GPa"]},
        "mobile_ion_metrics": {k: metrics[k] for k in
                               ["n_mobile", "mobile_species_absent",
                                "mobile_ms_final_A2",
                                "mobile_max_displacement_A",
                                "mobile_mean_displacement_A"]},
        "sampling_metrics": {k: metrics[k] for k in
                             ["n_sampled_frames", "n_production_frames",
                              "n_usable_frames", "n_nonfinite_frames",
                              "completed", "termination_note"]},
        "error_info": None,
        "reasons": reasons,
        "provenance": {"p1_checkpoint": job.get("p1_checkpoint"),
                       "p1_worker": job.get("p1_worker"),
                       "calc": calc_info,
                       "trajectory_sha256": traj_hash,
                       "wall_clock_s": record.get("wall_clock_s")},
        "evidence_events": [event.to_dict()],
    }
    if traj_block is not None:
        # Additive binding for artifact-bound results only. Legacy results
        # carry no such key (never backfilled, never fabricated).
        result["trajectory_artifact"] = traj_block
    return result


# ---------------------------------------------------------------------------
# P2 batch runner (own loop; P1 run_batches is frozen for P1 semantics).
# Consumes P1 done records (KEEP_FOR_P2 + relaxed structure); writes atomic
# data/batches/p2/<batch_id>.json. Resume/retry mirror the hash-bound P1
# philosophy: DONE (PASS/FAIL/INDETERMINATE) skips iff relaxed-sha AND
# config-hash match; ERROR recomputes only with retry_errors=True.
# ---------------------------------------------------------------------------
def p2_job_seed(base_seed: int, batch_id: str) -> int:
    """Deterministic per-batch MD seed (recorded in every result)."""
    return (int(base_seed) + int(batch_id[:8], 16)) % (2 ** 32)


# ---------------------------------------------------------------------------
# Production authorization allowlist (operational, not scientific).
# run_p2_batches processes ONLY P1 records whose batch_id is explicitly
# listed in the authorization manifest. Anything else is counted as
# skipped_unauthorized and never executed. Missing/malformed manifests
# fail closed before any MD.
# ---------------------------------------------------------------------------
def load_authorization_manifest(path: Union[str, Path]) -> set:
    """Load authorized batch IDs; fail closed on any defect.

    Requires: parseable JSON with a non-empty `candidates` list whose
    entries each carry a `batch_id`, no duplicate IDs, and
    `decision.verdict == "AUTHORIZED".
    """
    path = Path(path)
    if not path.exists():
        raise ValueError(f"authorization manifest missing: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        raise ValueError(f"authorization manifest malformed: {path}: {e}")
    if not isinstance(manifest, dict):
        raise ValueError(f"authorization manifest malformed: {path}: not an object")
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError(f"authorization manifest malformed: {path}: empty candidates")
    verdict = (manifest.get("decision") or {}).get("verdict")
    if verdict != "AUTHORIZED":
        raise ValueError(
            f"authorization manifest not AUTHORIZED: {path}: verdict={verdict!r}")
    ids = [c.get("batch_id") for c in candidates
           if isinstance(c, dict)]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(candidates):
        raise ValueError(f"authorization manifest malformed: {path}: bad batch_id entry")
    if len(set(ids)) != len(ids):
        raise ValueError(f"authorization manifest inconsistent: {path}: duplicate IDs")
    return set(ids)


def run_p2_batches(
    p1_done_dir: Union[str, Path],
    p2_dir: Union[str, Path],
    shard_index: int,
    n_shards: int,
    md_runner: Callable[[Dict[str, Any]], Dict[str, Any]],
    protocol: Dict[str, Any],
    worker_info: Optional[Dict[str, Any]] = None,
    retry_errors: bool = False,
    allowlist: Optional[set] = None,
) -> Dict[str, int]:
    """Run one P2 shard over P1 KEEP_FOR_P2 records. No locks, no queue."""
    from rudeus.mlip.sharding import assign_shard

    p1_done_dir, p2_dir = Path(p1_done_dir), Path(p2_dir)
    cfg_hash = protocol_config_hash(protocol)
    counts: Dict[str, Any] = {"processed": 0, "errored": 0, "skipped_done": 0,
                              "skipped_shard": 0, "skipped_ineligible": 0,
                              "skipped_p0_rejected": 0,
                              "skipped_unauthorized": 0,
                              "stale_recomputed": 0, "retried_errors": 0,
                              # Persistence (additive, non-scientific): batch
                              # IDs whose result file THIS invocation wrote
                              # (processed + errored + stale recomputes).
                              # Consumed by run_p2 --git-commit so only this
                              # worker's files are ever staged. Skipped
                              # (resume) IDs never appear here.
                              "wrote": []}
    for done_file in sorted(Path(p1_done_dir).glob("*.json")):
        batch_id = done_file.stem
        if not assign_shard(batch_id, shard_index, n_shards):
            counts["skipped_shard"] += 1
            continue
        if allowlist is not None and batch_id not in allowlist:
            counts["skipped_unauthorized"] += 1
            continue
        try:
            with open(done_file, encoding="utf-8") as f:
                prec = json.load(f)
            pres = prec.get("result") or {}
            # P0 is the early existence/plausibility gate. An explicit P0
            # rejection is terminal for downstream P2 execution, even if an
            # operational authorization manifest still contains the batch.
            # Missing p0_state is tolerated for backward-compatible P1
            # records created before the field was surfaced at top level.
            p0_state = prec.get("p0_state", pres.get("p0_state"))
            if p0_state == "FAIL":
                counts["skipped_p0_rejected"] += 1
                continue
            relaxed = pres.get("relaxed_structure_dict")
            if (pres.get("p1_verdict") != "KEEP_FOR_P2" or not relaxed
                    or not pres.get("relaxed_structure_sha256")):
                raise ValueError("not a KEEP_FOR_P2 record with relaxed structure")
            job = {"batch_id": batch_id,
                   "child_material_id": prec.get("child_material_id"),
                   "parent_id": prec.get("parent_id"),
                   "relaxed_structure_dict": relaxed,
                   "relaxed_structure_sha256": pres["relaxed_structure_sha256"],
                   "p1_checkpoint": pres.get("mlip_checkpoint"),
                   "p1_worker": prec.get("worker"),
                   "p2_protocol": protocol,
                   "p2_config_hash": cfg_hash,
                   "seed": p2_job_seed(int(protocol.get("base_seed", 550)), batch_id)}
        except Exception as e:  # malformed/ineligible P1 record: count, move on
            counts["skipped_ineligible"] += 1
            continue
        out_file = p2_dir / f"{batch_id}.json"
        if out_file.exists():
            try:
                with open(out_file, encoding="utf-8") as f:
                    prior = json.load(f)
                prior_res = prior.get("result") or {}
                same_input = (prior_res.get("p2_input_relaxed_sha256")
                              == job["relaxed_structure_sha256"])
                same_cfg = (prior_res.get("p2_config_hash") == cfg_hash)
                prior_verdict = prior_res.get("p2_verdict")
            except Exception:
                same_input, same_cfg, prior_verdict = False, False, None
            if not (same_input and same_cfg) or prior_verdict == "ERROR":
                if prior_verdict == "ERROR" and not retry_errors:
                    counts["skipped_done"] += 1
                    continue
                counts["stale_recomputed"] += 1
                if prior_verdict == "ERROR":
                    counts["retried_errors"] += 1
                # fall through: recompute
            else:
                counts["skipped_done"] += 1
                continue
        try:
            result = md_runner(job)
        except Exception as e:
            result = {"p2_verdict": "ERROR",
                      "dynamic_state": DynamicState.NOT_RUN.value,
                      "error_type": type(e).__name__,
                      "error_message": str(e)[:500],
                      "p2_input_relaxed_sha256": job["relaxed_structure_sha256"],
                      "p2_config_hash": cfg_hash}
            counts["errored"] += 1
        else:
            counts["processed"] += 1
        payload = {"batch_id": batch_id, "job": job, "result": result,
                   "worker": worker_info or {}}
        write_json_atomic(out_file, payload)
        # Persistence contract: a result counts as written only once the
        # final file parses back as JSON (atomic temp+replace alone does not
        # prove readability). A failed read-back fails loudly; the local
        # file is preserved for inspection, never deleted or retried here.
        try:
            with open(out_file, encoding="utf-8") as f:
                json.load(f)
        except Exception as e:
            raise IOError(f"p2 result not readable after atomic write: "
                          f"{out_file}: {e}")
        counts["wrote"].append(batch_id)
    counts["wrote"] = sorted(counts["wrote"])
    return counts

