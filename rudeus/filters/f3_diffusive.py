"""F3 Diffusive-Regime Validator.

CRITICAL PHYSICAL & ALGORITHMIC PRINCIPLE:
Mean-squared displacement (MSD) MUST be evaluated on the mobile-ion sublattice (e.g. Li)
only. All-atom MSD masks true diffusive behavior with framework vibration noise, which has
led to false-negative and false-positive errors in prior iterations.

Log-log slope ≈ 1 is necessary but not sufficient evidence of diffusive motion (it cannot
distinguish sustained hopping from caging/vibration/transient motion alone). Therefore,
this validator couples mobile-ion MSD log-log slope with the non-Gaussian parameter (alpha_2)
to confirm genuine continuous diffusion rather than localized jump-cage rattling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union
import numpy as np

from rudeus.schema import DynamicState, EvidenceEvent, TransportState


@dataclass(frozen=True)
class DiffusiveValidationResult:
    """Evaluation result from the F3 diffusive regime validator.

    Attributes:
        transport_state: TransportState verdict (DIFFUSIVE, NONDIFFUSIVE, INDETERMINATE).
        log_slope: d(ln MSD)/d(ln t) slope in the evaluation window.
        alpha2: Non-Gaussian parameter alpha_2 in the evaluation window.
        target_species: Species evaluated (e.g. 'Li').
        n_mobile_ions: Number of mobile ions evaluated.
        is_diffusive: True if passing provisional slope and alpha_2 gates.
        diagnostics: Additional diagnostic metrics.
    """
    transport_state: TransportState
    log_slope: float
    alpha2: float
    target_species: str
    n_mobile_ions: int
    is_diffusive: bool
    diagnostics: Dict[str, float]


def compute_msd_curve(
    displacements: np.ndarray,
    max_lag: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute time-averaged Mean Squared Displacement (MSD) and 4th moment for a set of atom trajectories.

    Args:
        displacements: Array of shape (n_frames, n_atoms, 3) representing unwrapped Cartesian
                       coordinates r(t) for each atom over time.
        max_lag: Maximum lag time frame index to compute (default: n_frames // 2).

    Returns:
        lags: 1D array of frame lag indices.
        msd: 1D array of MSD values at each lag index.
    """
    n_frames, n_atoms, _ = displacements.shape
    if n_frames < 2:
        return np.zeros(1), np.zeros(1)

    if max_lag is None:
        max_lag = max(1, n_frames // 2)
    max_lag = min(max_lag, n_frames - 1)

    lags = np.arange(1, max_lag + 1)
    msd = np.zeros(len(lags))

    for idx, lag in enumerate(lags):
        # Displacement vectors delta_r = r(t + lag) - r(t)
        delta_r = displacements[lag:] - displacements[:-lag]  # (n_samples, n_atoms, 3)
        sq_dist = np.sum(delta_r**2, axis=-1)  # (n_samples, n_atoms)
        msd[idx] = np.mean(sq_dist)

    return lags, msd


def compute_non_gaussian_alpha2(
    displacements: np.ndarray,
    max_lag: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute the 3D non-Gaussian parameter alpha_2(tau):

        alpha_2(tau) = (3 * <delta_r^4>) / (5 * <delta_r^2>^2) - 1

    For isotropic, continuous Gaussian diffusion (Brownian / Fickian), alpha_2 -> 0.
    Values significantly greater than 0 indicate dynamic heterogeneity, localized caging,
    intermittent rattling, or anomalous non-diffusive transport.

    Args:
        displacements: Array of shape (n_frames, n_atoms, 3) representing unwrapped coordinates.
        max_lag: Maximum lag time frame index to compute.

    Returns:
        lags: 1D array of frame lag indices.
        alpha2: 1D array of alpha_2 values at each lag index.
    """
    n_frames, n_atoms, _ = displacements.shape
    if n_frames < 2:
        return np.zeros(1), np.zeros(1)

    if max_lag is None:
        max_lag = max(1, n_frames // 2)
    max_lag = min(max_lag, n_frames - 1)

    lags = np.arange(1, max_lag + 1)
    alpha2 = np.zeros(len(lags))

    for idx, lag in enumerate(lags):
        delta_r = displacements[lag:] - displacements[:-lag]  # (n_samples, n_atoms, 3)
        sq_dist = np.sum(delta_r**2, axis=-1)  # r^2, shape (n_samples, n_atoms)
        quad_dist = sq_dist**2  # r^4

        mean_r2 = np.mean(sq_dist)
        mean_r4 = np.mean(quad_dist)

        if mean_r2 > 1e-12:
            alpha2[idx] = (3.0 * mean_r4) / (5.0 * (mean_r2**2)) - 1.0
        else:
            alpha2[idx] = 0.0

    return lags, alpha2


def compute_species_resolved_msd(
    trajectory: np.ndarray,
    species: Sequence[str],
    target_species: Optional[str] = "Li",
    max_lag: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract and compute MSD specifically for a designated species (or all atoms if None).

    Args:
        trajectory: Unwrapped atomic coordinates array of shape (n_frames, n_atoms, 3).
        species: List or array of elemental symbols for each atom (length n_atoms).
        target_species: Symbol of mobile sublattice (e.g. 'Li'). If None, computes all-atom MSD.
        max_lag: Maximum lag frames.

    Returns:
        (lags, msd, alpha2)
    """
    if len(species) != trajectory.shape[1]:
        raise ValueError(
            f"Species count ({len(species)}) does not match trajectory atoms ({trajectory.shape[1]})"
        )

    if target_species is not None:
        indices = [i for i, s in enumerate(species) if s == target_species]
        if len(indices) == 0:
            raise ValueError(f"No atoms of target species '{target_species}' found in trajectory.")
        sub_trajectory = trajectory[:, indices, :]
    else:
        sub_trajectory = trajectory

    lags, msd = compute_msd_curve(sub_trajectory, max_lag=max_lag)
    _, alpha2 = compute_non_gaussian_alpha2(sub_trajectory, max_lag=max_lag)

    return lags, msd, alpha2


def fit_log_log_slope(
    lags: np.ndarray,
    msd: np.ndarray,
    fit_window_fraction: Tuple[float, float] = (0.3, 0.9),
) -> float:
    """Calculate the log-log slope d(ln MSD)/d(ln t) over a specified time window.

    A slope near 1.0 indicates diffusive scaling (MSD ~ t^1).
    A slope near 0 indicates sub-diffusive caging or lattice vibration.
    A slope near 2 indicates ballistic motion.

    NOTE: log-log slope ≈ 1 is necessary but not sufficient evidence of diffusive motion
    (it cannot distinguish sustained hopping from caging/vibration/transient motion alone).

    Args:
        lags: 1D array of lag indices or times.
        msd: 1D array of MSD values.
        fit_window_fraction: (start_fraction, end_fraction) of lag range to fit.

    Returns:
        Estimated slope (float).
    """
    valid = (lags > 0) & (msd > 1e-12)
    lags_valid = lags[valid]
    msd_valid = msd[valid]

    if len(lags_valid) < 3:
        return 0.0

    n_pts = len(lags_valid)
    start_idx = int(n_pts * fit_window_fraction[0])
    end_idx = max(start_idx + 2, int(n_pts * fit_window_fraction[1]))

    window_lags = lags_valid[start_idx:end_idx]
    window_msd = msd_valid[start_idx:end_idx]

    if len(window_lags) < 2:
        return 0.0

    log_l = np.log(window_lags)
    log_m = np.log(window_msd)

    slope, _ = np.polyfit(log_l, log_m, 1)
    return float(slope)


def validate_diffusive_regime(
    trajectory: np.ndarray,
    species: Sequence[str],
    target_species: str = "Li",
    min_slope_provisional: float = 0.75,  # PROVISIONAL: Log-log slope cutoff
    max_slope_provisional: float = 1.30,  # PROVISIONAL: Ballistic motion cutoff
    max_alpha2_provisional: float = 0.35,  # PROVISIONAL: Non-Gaussian parameter cutoff
    fit_window_fraction: Tuple[float, float] = (0.3, 0.9),
) -> DiffusiveValidationResult:
    """Validate whether the mobile-ion sublattice has entered a genuine diffusive regime.

    CRITICAL REQUIREMENTS:
    1. Evaluates ONLY the target mobile-ion sublattice (e.g. 'Li').
    2. Enforces that log-log slope is within the diffusive window [min_slope, max_slope].
    3. Confirms that alpha_2 does not exceed the non-Gaussian threshold (ruling out cage trapping).

    NOTE: log-log slope ≈ 1 is necessary but not sufficient evidence of diffusive motion
    (it cannot distinguish sustained hopping from caging/vibration/transient motion alone).

    Args:
        trajectory: Unwrapped coordinates (n_frames, n_atoms, 3).
        species: Atom species symbols.
        target_species: Target mobile species (default: "Li").
        min_slope_provisional: Lower cutoff for log-log slope (PROVISIONAL).
        max_slope_provisional: Upper cutoff for log-log slope (PROVISIONAL).
        max_alpha2_provisional: Upper cutoff for alpha_2 (PROVISIONAL).
        fit_window_fraction: Window fraction for fitting slope.

    Returns:
        DiffusiveValidationResult with TransportState verdict and diagnostic values.
    """
    indices = [i for i, s in enumerate(species) if s == target_species]
    if len(indices) == 0:
        return DiffusiveValidationResult(
            transport_state=TransportState.NONDIFFUSIVE,
            log_slope=0.0,
            alpha2=0.0,
            target_species=target_species,
            n_mobile_ions=0,
            is_diffusive=False,
            diagnostics={"error": "no_target_ions_found"},
        )

    lags, msd, alpha2_curve = compute_species_resolved_msd(
        trajectory, species, target_species=target_species
    )

    slope = fit_log_log_slope(lags, msd, fit_window_fraction=fit_window_fraction)

    # Average alpha_2 in the second half of the evaluation window
    mid_idx = len(alpha2_curve) // 2
    tail_alpha2 = float(np.mean(alpha2_curve[mid_idx:])) if len(alpha2_curve) > mid_idx else float(alpha2_curve[-1])

    # Check diffusive criteria
    slope_ok = (min_slope_provisional <= slope <= max_slope_provisional)
    alpha2_ok = (tail_alpha2 <= max_alpha2_provisional)

    is_diffusive = bool(slope_ok and alpha2_ok)

    if is_diffusive:
        transport_state = TransportState.DIFFUSIVE
    elif slope < 0.4:
        transport_state = TransportState.NONDIFFUSIVE
    else:
        # Slope between 0.4 and 0.75 or high alpha_2: ambiguous/caged
        transport_state = TransportState.INDETERMINATE

    return DiffusiveValidationResult(
        transport_state=transport_state,
        log_slope=slope,
        alpha2=tail_alpha2,
        target_species=target_species,
        n_mobile_ions=len(indices),
        is_diffusive=is_diffusive,
        diagnostics={
            "final_msd": float(msd[-1]) if len(msd) > 0 else 0.0,
            "min_slope_provisional": min_slope_provisional,
            "max_alpha2_provisional": max_alpha2_provisional,
            "slope_ok": float(slope_ok),
            "alpha2_ok": float(alpha2_ok),
        },
    )
