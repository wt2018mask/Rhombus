"""Explicit test generators; their parameters are not production scientific gates."""
from __future__ import annotations
import numpy as np


def brownian(*, n_frames, n_ions, diffusion_tensor, dt_ps, seed):
    covariance = 2 * np.asarray(diffusion_tensor, dtype=float) * dt_ps
    if covariance.shape != (3, 3) or dt_ps <= 0:
        raise ValueError("3D diffusion tensor and positive timestep required")
    rng = np.random.default_rng(seed)
    increments = rng.multivariate_normal(np.zeros(3), covariance, (n_frames-1, n_ions), check_valid="raise")
    return np.concatenate([np.zeros((1, n_ions, 3)), np.cumsum(increments, axis=0)])


def caged(*, n_frames, n_ions, retention, stationary_std_A, seed):
    if not abs(retention) < 1 or stationary_std_A < 0:
        raise ValueError("stationary cage requires |retention|<1 and nonnegative width")
    rng = np.random.default_rng(seed)
    out = np.empty((n_frames, n_ions, 3))
    out[0] = rng.normal(0, stationary_std_A, (n_ions, 3))
    for t in range(1, n_frames):
        out[t] = retention*out[t-1] + rng.normal(0, stationary_std_A*np.sqrt(1-retention**2), (n_ions, 3))
    return out


def hopping(*, n_frames, n_ions, jump_length_A, rate_per_ps, dt_ps, seed):
    """Exact Poisson event counts per interval, including multiple jumps."""
    if min(jump_length_A, rate_per_ps) < 0 or dt_ps <= 0:
        raise ValueError("invalid hopping parameters")
    rng = np.random.default_rng(seed)
    directions = np.concatenate([np.eye(3), -np.eye(3)]) * jump_length_A
    increments = np.zeros((n_frames-1, n_ions, 3))
    for t in range(n_frames-1):
        for ion in range(n_ions):
            count = rng.poisson(rate_per_ps*dt_ps)
            increments[t, ion] = directions[rng.integers(0, 6, count)].sum(axis=0)
    return np.concatenate([np.zeros((1, n_ions, 3)), np.cumsum(increments, axis=0)])


def correlated_motion(*, n_frames, n_ions, spatial_covariance, retention, dt_ps, seed):
    """Stationary AR(1) increments; covariance ordered (ion, Cartesian axis).

    Long-time displacement covariance rate is C*(1+r)/(1-r)/dt_ps.
    """
    covariance = np.asarray(spatial_covariance, dtype=float)
    if covariance.shape != (3*n_ions, 3*n_ions) or not abs(retention) < 1 or dt_ps <= 0:
        raise ValueError("invalid correlated-process parameters")
    rng = np.random.default_rng(seed)
    previous = rng.multivariate_normal(np.zeros(3*n_ions), covariance, check_valid="raise")
    increments = []
    for _ in range(n_frames-1):
        previous = retention*previous + rng.multivariate_normal(
            np.zeros(3*n_ions), covariance*(1-retention**2), check_valid="raise")
        increments.append(previous.reshape(n_ions, 3))
    return np.concatenate([np.zeros((1, n_ions, 3)), np.cumsum(increments, axis=0)])


def wrap(positions, cell):
    cell = np.asarray(cell)
    return np.mod(np.asarray(positions) @ np.linalg.inv(cell), 1) @ cell


def temperature_series(*, temperatures_K, prefactor, activation_energy_eV, log_noise_std, seed,
                       curvature=0.0):
    from rudeus.mlip.p3_transport import K_B_EV_PER_K
    temperatures = np.asarray(temperatures_K, dtype=float)
    if np.any(temperatures <= 0) or prefactor <= 0 or log_noise_std < 0:
        raise ValueError("invalid temperature generating process")
    inverse = 1/temperatures
    return prefactor*np.exp(-activation_energy_eV/K_B_EV_PER_K*inverse
                           + curvature*(inverse-inverse.mean())**2
                           + np.random.default_rng(seed).normal(0, log_noise_std, len(temperatures)))
