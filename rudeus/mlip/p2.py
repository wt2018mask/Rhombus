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
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from rudeus.filters.f3_diffusive import compute_msd_curve
from rudeus.mlip.sharding import (
    assign_shard,
    structure_dict_sha256,
    write_json_atomic,
)
from rudeus.schema import DynamicState, EvidenceEvent

# ---------------------------------------------------------------------------
# Protocol: one clearly identifiable configuration structure (550 K NVT).
# Durations are step counts (timestep 1 fs). Defaults target GPU sessions;
# pilot/CI runs override equil/production steps via CLI (same code path).
# ---------------------------------------------------------------------------
P2_PROTOCOL_DEFAULTS: Dict[str, Any] = {
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


def protocol_config_hash(protocol: Dict[str, Any]) -> str:
    """Deterministic hash of the physics-defining protocol (no wall-clock)."""
    payload = json.dumps(protocol, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def batch_seed(base_seed: int, batch_id: str) -> int:
    """Deterministic per-batch seed (recorded in every result)."""
    return (int(base_seed) + int(batch_id[:8], 16)) % (2 ** 32)


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
def run_nvt(structure_dict: Dict[str, Any], calc,
            protocol: Dict[str, Any], seed: int) -> Dict[str, Any]:
    """Run deterministic 550 K NVT (Langevin) MD; return the sampled record.

    Samples: wrapped positions, temperature, potential energy, volume,
    pressure (None when the calculator offers no stress), max force.
    Aborts with termination flags on non-finite data or explosive motion.
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
    equil = int(protocol["equil_steps"])
    prod = int(protocol["production_steps"])
    interval = int(protocol["sample_interval_steps"])

    rng_init = np.random.default_rng(seed + 1)
    rng_dyn = np.random.default_rng(seed + 2)
    MaxwellBoltzmannDistribution(atoms, temperature_K=temp, rng=rng_init)
    dyn = Langevin(atoms, timestep=dt, temperature_K=temp, friction=fric,
                   fixcm=bool(protocol["fix_center_of_mass"]), rng=rng_dyn)

    frames: List[Dict[str, Any]] = []
    state = {"phase": "equil", "aborted": False, "abort_reason": None,
             "prev": None}

    def sample():
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
            return
        finite = bool(np.all(np.isfinite(pos)) and np.isfinite(t)
                      and np.isfinite(e) and np.isfinite(fmax))
        step_jump = 0.0
        if state["prev"] is not None and finite:
            step_jump = mic_step_jump(state["prev"], pos,
                                      np.asarray(atoms.cell.array, dtype=float))
        state["prev"] = pos
        frames.append({"phase": state["phase"], "positions": pos,
                       "temperature_K": t, "energy_ev": e, "volume_A3": v,
                       "pressure_GPa": press, "max_force_ev_A": fmax,
                       "finite": finite, "step_jump_A": step_jump})
        if (not finite or step_jump > float(protocol["explosion_abort_A_provisional"])):
            state["aborted"] = state["aborted"] or True
            state["abort_reason"] = state["abort_reason"] or (
                "non-finite-data" if not finite else "explosive-step")
            dyn.abort = True

    dyn.attach(sample, interval=interval)
    t0 = time.time()
    state["phase"] = "equil"
    dyn.run(equil)
    state["phase"] = "production"
    state["prev"] = None
    if not state["aborted"]:
        dyn.run(prod)
    wall_s = time.time() - t0
    return {"species": species, "cell": np.asarray(atoms.cell.array, dtype=float),
            "frames": frames, "wall_clock_s": wall_s,
            "completed": not state["aborted"],
            "termination_note": state["abort_reason"],
            "timestep_fs": dt, "sample_interval_steps": interval,
            "equil_steps": equil, "production_steps": prod,
            "thermostat": protocol["thermostat"],
            "friction_fs_inv": fric, "seed": seed}


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
                    worker_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Assemble the atomic P2 result: provenance, metrics, dynamic state.

    Sets dynamic_state (NOT_RUN/FAIL/INDETERMINATE/PASS) and appends one P2
    EvidenceEvent. NEVER sets transport_state or any diffusion claim.
    """
    protocol = job["p2_protocol"]
    state, metrics, reasons = evaluate_p2(record, protocol)
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
    return {
        "candidate_material_id": job.get("child_material_id"),
        "batch_id": job["batch_id"],
        "parent_id": job.get("parent_id"),
        "p2_input_relaxed_sha256": job["relaxed_structure_sha256"],
        "p1_relaxed_structure_sha256": job["relaxed_structure_sha256"],
        "p2_config_hash": job["p2_config_hash"],
        "p2_protocol": protocol,
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


def run_p2_batches(
    p1_done_dir: Union[str, Path],
    p2_dir: Union[str, Path],
    shard_index: int,
    n_shards: int,
    md_runner: Callable[[Dict[str, Any]], Dict[str, Any]],
    protocol: Dict[str, Any],
    worker_info: Optional[Dict[str, Any]] = None,
    retry_errors: bool = False,
) -> Dict[str, int]:
    """Run one P2 shard over P1 KEEP_FOR_P2 records. No locks, no queue."""
    from rudeus.mlip.sharding import assign_shard

    p1_done_dir, p2_dir = Path(p1_done_dir), Path(p2_dir)
    cfg_hash = protocol_config_hash(protocol)
    counts = {"processed": 0, "errored": 0, "skipped_done": 0,
              "skipped_shard": 0, "skipped_ineligible": 0,
              "stale_recomputed": 0, "retried_errors": 0}
    for done_file in sorted(Path(p1_done_dir).glob("*.json")):
        batch_id = done_file.stem
        if not assign_shard(batch_id, shard_index, n_shards):
            counts["skipped_shard"] += 1
            continue
        try:
            with open(done_file, encoding="utf-8") as f:
                prec = json.load(f)
            pres = prec.get("result") or {}
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
    return counts
