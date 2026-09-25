"""P3 quantitative transport calculation core.

Pure numerical helpers only.

Scientific conventions:
- 3D Einstein relation:
      D = (1/6) * d(MSD)/dt
- 1 A^2 / ps = 1e-8 m^2 / s
- Nernst-Einstein:
      sigma_NE = n q^2 D / (k_B T)
- Arrhenius:
      ln(D) = ln(D0) - Ea / (k_B T)

Nernst-Einstein conductivity is explicitly an estimate.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np


E_CHARGE_C = 1.602176634e-19
K_B_J_PER_K = 1.380649e-23
K_B_EV_PER_K = 8.617333262145e-5


def _as_finite_1d(values: Sequence[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)

    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")

    if array.size < 2:
        raise ValueError(f"{name} requires at least two points")

    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains non-finite values")

    return array


def diffusion_A2_per_ps_to_m2_per_s(
    D_A2_per_ps: float,
) -> float:
    """Convert diffusion coefficient from A^2/ps to m^2/s."""
    value = float(D_A2_per_ps)

    if not math.isfinite(value):
        raise ValueError("D_A2_per_ps must be finite")

    return value * 1.0e-8


def fit_self_diffusion(
    *,
    time_ps: Sequence[float],
    msd_A2: Sequence[float],
    time_unit: str = "ps",
) -> dict:
    """Estimate tracer/self diffusion from a linear MSD-vs-time fit.

    For isotropic 3D diffusion:
        MSD(t) = 6 D t + intercept
    """
    if time_unit != "ps":
        raise ValueError("time_unit must be 'ps'")

    time = _as_finite_1d(time_ps, "time_ps")
    msd = _as_finite_1d(msd_A2, "msd_A2")

    if time.size != msd.size:
        raise ValueError("time_ps and msd_A2 must have the same length")

    if np.any(np.diff(time) <= 0.0):
        raise ValueError("time_ps must be strictly increasing")

    slope, intercept = np.polyfit(time, msd, 1)
    D_A2_per_ps = float(slope / 6.0)

    if not math.isfinite(D_A2_per_ps):
        raise ValueError("self-diffusion fit produced a non-finite value")

    return {
        "fit_method": "linear_msd_vs_time",
        "D_A2_per_ps": D_A2_per_ps,
        "D_m2_per_s": diffusion_A2_per_ps_to_m2_per_s(D_A2_per_ps),
        "slope_A2_per_ps": float(slope),
        "intercept_A2": float(intercept),
        "n_points": int(time.size),
    }


def nernst_einstein_conductivity(
    *,
    D_m2_per_s: float,
    carrier_density_per_m3: float,
    temperature_K: float,
    charge_number: int = 1,
) -> dict:
    """Calculate the Nernst-Einstein conductivity estimate."""
    D = float(D_m2_per_s)
    density = float(carrier_density_per_m3)
    temperature = float(temperature_K)
    z = int(charge_number)

    if not math.isfinite(D) or D < 0.0:
        raise ValueError("D_m2_per_s must be finite and non-negative")

    if not math.isfinite(density) or density < 0.0:
        raise ValueError(
            "carrier_density_per_m3 must be finite and non-negative"
        )

    if not math.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("temperature_K must be positive and finite")

    if z == 0:
        raise ValueError("charge_number must be non-zero")

    charge_C = z * E_CHARGE_C

    value = (
        density
        * charge_C**2
        * D
        / (K_B_J_PER_K * temperature)
    )

    return {
        "method": "nernst_einstein",
        "value_S_per_m": float(value),
        "temperature_K": temperature,
        "carrier_density_per_m3": density,
        "D_m2_per_s": D,
        "charge_number": z,
        "claim_status": "estimate",
    }


def fit_arrhenius(
    *,
    temperatures_K: Sequence[float],
    values: Sequence[float],
    value_name: str,
    uncertainty_ci: Sequence[Sequence[float]] | None = None,
) -> dict:
    """Fit ln(value) = ln(prefactor) - Ea/(k_B*T).

    The returned activation energy is in eV.
    """
    temperatures = _as_finite_1d(temperatures_K, "temperatures_K")
    transport_values = _as_finite_1d(values, "values")

    if temperatures.size != transport_values.size:
        raise ValueError(
            "temperatures_K and values must have the same length"
        )

    if np.any(temperatures <= 0.0):
        raise ValueError("temperatures_K must be positive")

    if np.any(transport_values <= 0.0):
        raise ValueError("values must be strictly positive")

    if not isinstance(value_name, str) or not value_name:
        raise ValueError("value_name must be a non-empty string")

    x = 1.0 / temperatures
    y = np.log(transport_values)

    slope, intercept = np.polyfit(x, y, 1)

    activation_energy_eV = float(-slope * K_B_EV_PER_K)
    prefactor = float(np.exp(intercept))

    y_pred = slope * x + intercept
    residuals = y - y_pred
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - np.mean(y))**2))

    if ss_tot > 0.0:
        r_squared = float(1.0 - ss_res / ss_tot)
    else:
        r_squared = float("nan")

    diagnostics = {
        "status": "SUPPORTED_BY_DATA",
        "n_points": int(temperatures.size),
        "uncertainty_method": (
            "input_per_temperature_ci"
            if uncertainty_ci is not None
            else None
        ),
        "r_squared": r_squared,
        "residual_sum_squares": ss_res,
    }

    result = {
        "model": "arrhenius",
        "available": True,
        "activation_energy_eV": activation_energy_eV,
        "prefactor": prefactor,
        "value_name": value_name,
        "fit_diagnostics": diagnostics,
    }

    if uncertainty_ci is not None:
        ci = np.asarray(uncertainty_ci, dtype=float)

        if ci.shape != (temperatures.size, 2):
            raise ValueError(
                "uncertainty_ci must have shape (n_points, 2)"
            )

        if not np.all(np.isfinite(ci)):
            raise ValueError("uncertainty_ci contains non-finite values")

        if np.any(ci[:, 0] <= 0.0) or np.any(ci[:, 1] <= 0.0):
            raise ValueError(
                "uncertainty_ci bounds must be strictly positive"
            )

        if np.any(ci[:, 0] > ci[:, 1]):
            raise ValueError(
                "uncertainty_ci lower bounds must not exceed upper bounds"
            )

        result["fit_diagnostics"]["input_uncertainty_ci"] = ci.tolist()

    return result


def extrapolate_arrhenius(
    *,
    fit: dict,
    target_temperature_K: float,
    source_temperature_range_K: Sequence[float],
    quantity: str,
) -> dict:
    """Evaluate an Arrhenius fit at a target temperature.

    Values outside the supplied source-temperature range are explicitly
    labelled EXTRAPOLATED. No value is produced when the fit is unavailable.
    """
    target = float(target_temperature_K)

    if not math.isfinite(target) or target <= 0.0:
        raise ValueError("target_temperature_K must be positive and finite")

    source = _as_finite_1d(
        source_temperature_range_K,
        "source_temperature_range_K",
    )

    if np.any(source <= 0.0):
        raise ValueError(
            "source_temperature_range_K must contain positive temperatures"
        )

    if source.size != 2 or source[0] > source[1]:
        raise ValueError(
            "source_temperature_range_K must be [minimum, maximum]"
        )

    if not isinstance(quantity, str) or not quantity:
        raise ValueError("quantity must be a non-empty string")

    if not fit.get("available", False):
        return {
            "available": False,
            "target_temperature_K": target,
            "source_temperature_range_K": source.tolist(),
            "quantity": quantity,
            "model": fit.get("model", "arrhenius"),
            "status": "INDETERMINATE",
        }

    if fit.get("model") != "arrhenius":
        raise ValueError("fit model must be 'arrhenius'")

    Ea = float(fit["activation_energy_eV"])
    prefactor = float(fit["prefactor"])

    if not math.isfinite(Ea) or not math.isfinite(prefactor):
        raise ValueError("Arrhenius fit parameters must be finite")

    value = prefactor * math.exp(
        -Ea / (K_B_EV_PER_K * target)
    )

    minimum, maximum = float(source[0]), float(source[1])

    if target < minimum:
        distance = minimum - target
        status = "EXTRAPOLATED"
    elif target > maximum:
        distance = target - maximum
        status = "EXTRAPOLATED"
    else:
        distance = 0.0
        status = "WITHIN_SOURCE_RANGE"

    return {
        "available": True,
        "target_temperature_K": target,
        "source_temperature_range_K": [minimum, maximum],
        "extrapolation_distance_K": float(distance),
        "quantity": quantity,
        "value": float(value),
        "model": "arrhenius",
        "status": status,
    }

def block_bootstrap_self_diffusion(
    mobile_unwrapped: np.ndarray,
    fit_window_fraction: Sequence[float],
    block_origins: int,
    n_bootstrap: int,
    ci_level: float,
    seed: int,
    min_blocks: int = 4,
    dt_ps_per_lag_step: float = 1.0,
) -> dict:
    """Block-bootstrap CI for 3D self-diffusion from Einstein MSD.

    Uses the same contiguous time-origin block-bootstrap principle as P2.5.
    Each bootstrap replicate recomputes the multi-origin MSD, fits MSD versus
    physical time in the requested window, and converts the slope to the
    3D self-diffusion coefficient through D = slope / 6.
    """
    trajectory = np.asarray(mobile_unwrapped, dtype=float)

    if trajectory.ndim != 3 or trajectory.shape[2] != 3:
        raise ValueError("mobile_unwrapped must have shape (n_frames, n_ions, 3)")

    if not np.all(np.isfinite(trajectory)):
        raise ValueError("mobile_unwrapped contains non-finite values")

    n_frames, n_ions, _ = trajectory.shape

    dt = float(dt_ps_per_lag_step)
    if not math.isfinite(dt) or dt <= 0.0:
        raise ValueError("dt_ps_per_lag_step must be positive and finite")

    if (
        len(fit_window_fraction) != 2
        or not all(math.isfinite(float(x)) for x in fit_window_fraction)
        or not 0.0 <= float(fit_window_fraction[0]) < float(fit_window_fraction[1]) <= 1.0
    ):
        raise ValueError(
            "fit_window_fraction must satisfy 0 <= low < high <= 1"
        )

    base = {
        "method": "block_bootstrap_origins",
        "block_length_origins": int(block_origins),
        "n_bootstrap": int(n_bootstrap),
        "ci_level": float(ci_level),
        "status": "insufficient",
        "reason": "not_evaluated",
        "dt_ps_per_lag_step": dt,
    }

    if not 0.0 < float(ci_level) < 1.0:
        raise ValueError("ci_level must be between 0 and 1")

    if (
        n_frames < 2
        or n_ions < 1
        or block_origins < 1
        or n_bootstrap < 1
    ):
        base["reason"] = "degenerate_trajectory_or_parameters"
        return base

    max_lag = min(max(1, n_frames // 2), n_frames - 1)
    n_origins = n_frames - max_lag
    n_blocks = n_origins // int(block_origins)

    base["n_origins"] = int(n_origins)
    base["n_blocks"] = int(n_blocks)

    if n_blocks < 1:
        base["reason"] = "no_complete_block"
        return base

    if n_blocks < int(min_blocks):
        base["reason"] = "fewer_blocks_than_minimum"
        return base

    rng = np.random.default_rng(int(seed) % (2 ** 32))
    lags = np.arange(1, max_lag + 1, dtype=float)
    bootstrap_D = []

    low_fraction = float(fit_window_fraction[0])
    high_fraction = float(fit_window_fraction[1])

    start = max(0, int(np.floor(low_fraction * len(lags))))
    stop = min(len(lags), int(np.ceil(high_fraction * len(lags))))

    if stop - start < 2:
        base["reason"] = "insufficient_fit_points"
        return base

    for _ in range(int(n_bootstrap)):
        picks = rng.integers(0, n_blocks, size=n_blocks)

        rows = np.concatenate(
            [
                np.arange(
                    block_index * block_origins,
                    (block_index + 1) * block_origins,
                )
                for block_index in picks
            ]
        )

        msd = np.empty(len(lags), dtype=float)

        for index, lag_value in enumerate(lags.astype(int)):
            delta = (
                trajectory[lag_value:]
                - trajectory[:-lag_value]
            )
            squared_displacement = np.sum(delta ** 2, axis=-1)
            msd[index] = float(
                np.mean(squared_displacement[rows])
            )

        time_ps = lags[start:stop] * dt
        msd_fit = msd[start:stop]

        slope, _ = np.polyfit(time_ps, msd_fit, 1)
        D_A2_per_ps = float(slope / 6.0)

        if math.isfinite(D_A2_per_ps):
            bootstrap_D.append(D_A2_per_ps)

    if len(bootstrap_D) < 2:
        base["reason"] = "insufficient_valid_bootstrap_replicates"
        return base

    tail_probability = (1.0 - float(ci_level)) / 2.0

    return {
        **base,
        "status": "sufficient",
        "reason": None,
        "D_A2_per_ps_ci": [
            float(np.quantile(bootstrap_D, tail_probability)),
            float(np.quantile(bootstrap_D, 1.0 - tail_probability)),
        ],
        "D_A2_per_ps_bootstrap_mean": float(np.mean(bootstrap_D)),
        "n_valid_bootstrap_replicates": int(len(bootstrap_D)),
    }

