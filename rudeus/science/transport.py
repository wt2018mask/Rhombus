"""Fixed-cell displacement estimators. Every output is an UNQUALIFIED diagnostic.

No fit window, charge map, drift removal or scientific threshold is inferred.
Coordinates use Angstrom and actual recorded MD step times use femtoseconds.
"""
from __future__ import annotations

import numpy as np
from rudeus.science.contracts import UNRESOLVED
from rudeus.mlip.p3_transport import E_CHARGE_C, K_B_J_PER_K, fit_self_diffusion


def unavailable(reason):
    return {"available": False, "status": "UNKNOWN", "reason": reason,
            "scientific_qualification": UNRESOLVED}


def validate_trajectory(positions, species, frame_steps, timestep_fs, lag_steps):
    pos = np.asarray(positions, dtype=float)
    steps = np.asarray(frame_steps)
    lags = np.asarray(lag_steps)
    if pos.ndim != 3 or pos.shape[2] != 3 or pos.shape[1] != len(species):
        raise ValueError("trajectory/species shape mismatch")
    if not np.isfinite(pos).all() or len(pos) < 2:
        raise ValueError("at least two finite frames are required")
    if steps.shape != (len(pos),) or not np.isfinite(steps).all():
        raise ValueError("frame steps must be finite and aligned")
    if np.any(steps != np.floor(steps)) or np.any(np.diff(steps) <= 0):
        raise ValueError("frame steps must be increasing integers")
    if not np.all(np.diff(steps) == np.diff(steps)[0]):
        raise ValueError("irregular cadence requires an explicit lag-pair protocol; unsupported")
    if not np.isfinite(timestep_fs) or timestep_fs <= 0:
        raise ValueError("physical timestep must be positive")
    if (lags.ndim != 1 or len(lags) < 2 or not np.isfinite(lags).all()
            or np.any(lags != np.floor(lags)) or np.any(np.diff(lags) <= 0)
            or lags[0] < 1 or lags[-1] >= len(pos)):
        raise ValueError("supply at least two increasing integer lag steps within trajectory")
    return pos, steps, lags.astype(int)


def displacement_moments(positions, species, frame_steps, timestep_fs, lag_steps,
                         *, selected_species, charge_numbers=None, origins=None):
    pos, steps, lags = validate_trajectory(positions, species, frame_steps,
                                         timestep_fs, lag_steps)
    selected = tuple(selected_species)
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("species selection must be nonempty and unique")
    indices = {s: np.flatnonzero(np.asarray(species) == s) for s in selected}
    if any(len(idx) == 0 for idx in indices.values()):
        raise ValueError("selected species absent from trajectory")
    if charge_numbers is not None:
        if set(charge_numbers) != set(selected) or not all(
                np.isfinite(q) and not isinstance(q, bool) for q in charge_numbers.values()):
            raise ValueError("explicit finite charge map must exactly cover selected species")
    tensors = {s: [] for s in selected}
    cross = {s: {t: [] for t in selected} for s in selected}
    counts = []
    used_origins = []
    for lag in lags:
        rows = np.arange(len(pos) - lag) if origins is None else np.asarray(origins)
        if (rows.ndim != 1 or not len(rows) or np.any(rows != np.floor(rows))
                or np.any(rows < 0) or np.any(rows + lag >= len(pos))):
            raise ValueError("invalid time-origin support")
        rows = rows.astype(int)
        delta = pos[rows + lag] - pos[rows]
        counts.append(len(rows))
        used_origins.append(rows.tolist())
        charges = {}
        for s, idx in indices.items():
            displacement = delta[:, idx, :]
            tensors[s].append(np.einsum("nia,nib->ab", displacement, displacement)
                              / (len(rows) * len(idx)))
            if charge_numbers is not None:
                charges[s] = displacement.sum(axis=1) * charge_numbers[s]
        if charge_numbers is not None:
            for s in selected:
                for t in selected:
                    cross[s][t].append(np.einsum("na,nb->ab", charges[s], charges[t]) / len(rows))
    return {"time_ps": lags * (steps[1] - steps[0]) * timestep_fs / 1000,
            "self_tensors_A2": {s: np.asarray(v) for s, v in tensors.items()},
            "charge_cross_e2_A2": {s: {t: np.asarray(v) for t, v in c.items()}
                                    for s, c in cross.items()} if charge_numbers is not None else None,
            "counts": {s: len(v) for s, v in indices.items()},
            "origin_counts": counts, "origin_indices": used_origins,
            "origin_policy": "all_available_per_lag" if origins is None else "explicit_common_pool",
            "n_frames": len(pos), "lag_steps": lags.tolist()}


def fit_moments(moments, fit_window_ps, *, volume_A3, temperature_K,
                charge_numbers=None, reference_frame):
    if reference_frame != "simulation_cell":
        raise ValueError("only the explicit simulation_cell frame is implemented; no drift subtraction")
    time = moments["time_ps"]
    window = np.asarray(fit_window_ps, dtype=float)
    if window.shape != (2,) or not np.isfinite(window).all() or not 0 <= window[0] < window[1]:
        raise ValueError("explicit physical fit-window bounds required")
    mask = (time >= window[0]) & (time <= window[1])
    if mask.sum() < 2:
        raise ValueError("fit window has fewer than two distinct physical lags")
    if not np.isfinite(volume_A3) or volume_A3 <= 0 or not np.isfinite(temperature_K) or temperature_K <= 0:
        raise ValueError("positive finite fixed volume and temperature required")
    self_results = {}
    for s, tensors in moments["self_tensors_A2"].items():
        fit = fit_self_diffusion(time_ps=time[mask], msd_A2=np.trace(tensors[mask], axis1=1, axis2=2))
        slope, intercept = np.polyfit(time[mask], tensors[mask].reshape(-1, 9), 1)
        self_results[s] = {**fit, "species": s, "available": True, "status": "DIAGNOSTIC_ONLY",
                           "D_tensor_m2_per_s": (slope.reshape(3, 3) / 2 * 1e-8).tolist(),
                           "intercept_tensor_A2": intercept.reshape(3, 3).tolist(),
                           "fit_window_ps": window.tolist(), "fitted_lag_times_ps": time[mask].tolist(),
                           "n_mobile_ions": moments["counts"][s], "n_frames": moments["n_frames"],
                           "origin_policy": moments["origin_policy"],
                           "origin_counts": moments["origin_counts"],
                           "reference_frame": reference_frame, "scalar_definition": "trace(D_tensor)/3",
                           "uncertainty": None, "scientific_qualification": UNRESOLVED}
    ne = unavailable("charge_specification_missing")
    collective = unavailable("charge_specification_missing")
    if charge_numbers is not None:
        # A^2/ps -> m^2/s; A^3 -> m^3. Cross tensors are in e^2 A^2.
        factor = E_CHARGE_C ** 2 * 1e-8 / (2 * volume_A3 * 1e-30 * K_B_J_PER_K * temperature_K)
        cross_sigma = {}
        total = np.zeros((3, 3))
        for s, other in moments["charge_cross_e2_A2"].items():
            cross_sigma[s] = {}
            for t, tensors in other.items():
                slope, _ = np.polyfit(time[mask], tensors[mask].reshape(-1, 9), 1)
                contribution = slope.reshape(3, 3) * factor
                cross_sigma[s][t] = contribution.tolist()
                total += contribution
        ne_tensor = sum(moments["counts"][s] * charge_numbers[s] ** 2 * E_CHARGE_C ** 2
                        * np.asarray(r["D_tensor_m2_per_s"]) /
                        (volume_A3 * 1e-30 * K_B_J_PER_K * temperature_K)
                        for s, r in self_results.items())
        ne_scalar = float(np.trace(ne_tensor) / 3)
        sigma = float(np.trace(total) / 3)
        ne = {"available": True, "status": "DIAGNOSTIC_ONLY", "method": "nernst_einstein",
              "claim_status": "estimate", "value_S_per_m": ne_scalar,
              "tensor_S_per_m": ne_tensor.tolist(), "scientific_qualification": UNRESOLVED,
              "uncertainty": None}
        if any(r["D_A2_per_ps"] < 0 for r in self_results.values()):
            ne = {**unavailable("negative_self_slope"), "raw_signed_value_S_per_m": ne_scalar,
                  "raw_signed_tensor_S_per_m": ne_tensor.tolist(), "claim_status": "estimate"}
        ratio = ({"available": True, "factor": sigma / ne_scalar,
                  "factor_definition": "trace(sigma_collective)/trace(sigma_NE); same species/frame/conditions",
                  "status": "DIAGNOSTIC_ONLY", "uncertainty": None,
                  "scientific_qualification": UNRESOLVED}
                 if ne.get("available") and ne_scalar > 0 and sigma >= 0
                 else unavailable("ratio_denominator_or_numerator_unresolved"))
        collective = {"available": True, "status": "DIAGNOSTIC_ONLY",
                      "method": "collective_charge_displacement_einstein",
                      "sigma_S_per_m": sigma, "tensor_S_per_m": total.tolist(),
                      "cross_species_tensor_S_per_m": cross_sigma,
                      "charge_displacement_definition": "sum_i q_i*(R_i(t+tau)-R_i(t)); fixed charges",
                      "charge_numbers": dict(charge_numbers), "species": list(self_results),
                      "reference_frame": reference_frame, "volume_A3": volume_A3,
                      "temperature_K": temperature_K, "fit_window_ps": window.tolist(),
                      "uncertainty": None, "scientific_qualification": UNRESOLVED, "correlation": ratio}
    return {"self_diffusion_by_species": self_results, "conductivity_estimate": ne,
            "collective_transport": collective}


def analyze_trajectory(positions, species, frame_steps, timestep_fs, lag_steps, *,
                       selected_species, fit_window_ps, volume_A3, temperature_K,
                       reference_frame, charge_numbers=None, origins=None):
    moments = displacement_moments(positions, species, frame_steps, timestep_fs, lag_steps,
                                  selected_species=selected_species, charge_numbers=charge_numbers,
                                  origins=origins)
    return fit_moments(moments, fit_window_ps, volume_A3=volume_A3, temperature_K=temperature_K,
                       charge_numbers=charge_numbers, reference_frame=reference_frame)
