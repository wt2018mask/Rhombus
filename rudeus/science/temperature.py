"""Temperature-indexed diagnostics; no adequacy or extrapolation criteria invented."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from rudeus.science.contracts import Record, UNRESOLVED, require_hash
from rudeus.mlip.p3_transport import K_B_EV_PER_K


@dataclass(frozen=True, kw_only=True)
class TemperaturePoint(Record):
    candidate_id: str
    phase_id: str
    comparison_scope_hash: str
    temperature_K: float
    quantity: str
    units: str
    value: float | None
    source_artifacts: tuple[str, ...]
    protocol_hash: str
    replica_id: str
    sampling_independence_evidence: str | None = None
    status: str = "DIAGNOSTIC_ONLY"
    uncertainty: dict | None = None

    def validate(self):
        super().validate()
        if self.temperature_K <= 0:
            raise ValueError("positive temperature required")
        for h in (self.protocol_hash, self.comparison_scope_hash) + self.source_artifacts:
            require_hash(h)


def analyze_temperature(points, *, fit_quantity, target_temperature_K=None,
                        joint_draws=None, nominal_coverage=None, resampling_provenance=None):
    points = tuple(sorted(points, key=lambda p: (p.temperature_K, p.replica_id)))
    base = {"points": [p.to_dict() for p in points], "fit_quantity": fit_quantity,
            "fit": {"available": False, "status": "UNKNOWN"},
            "parameter_uncertainty": None, "model_discrepancy_uncertainty": None,
            "model_discrepancy_status": UNRESOLVED, "scientific_qualification": UNRESOLVED,
            "prediction": {"available": False, "status": "NOT_REQUESTED" if target_temperature_K is None else "UNAVAILABLE"}}
    if target_temperature_K is not None and (not np.isfinite(target_temperature_K) or target_temperature_K <= 0):
        raise ValueError("positive finite target temperature required")
    if fit_quantity not in ("D_self", "sigma_NE", "sigma_collective", "sigma_NE*T", "sigma_collective*T"):
        raise ValueError("fitted observable must be explicitly defined")
    reason = None
    if len(points) < 2:
        reason = "two_distinct_temperatures_required_for_algebraic_identification"
    elif len({p.temperature_K for p in points}) != len(points):
        reason = "replica_aggregation_unresolved"
    elif len({(p.candidate_id, p.phase_id, p.comparison_scope_hash, p.quantity, p.units) for p in points}) != 1:
        reason = "incompatible_phase_or_observable_scope"
    elif points[0].quantity != fit_quantity.removesuffix("*T"):
        reason = "fitted_quantity_does_not_match_observations"
    elif any(p.value is None or p.value <= 0 or p.status not in ("DIAGNOSTIC_ONLY", "QUALIFIED") for p in points):
        reason = "unresolved_or_nonpositive_temperature_points_not_dropped"
    elif any(not p.source_artifacts for p in points):
        reason = "missing_temperature_provenance"
    elif len({h for p in points for h in p.source_artifacts}) != sum(len(p.source_artifacts) for p in points):
        reason = "reused_temperature_artifacts"
    if reason:
        return {**base, "unavailable_reason": reason}
    temperatures = np.array([p.temperature_K for p in points])
    raw = np.array([p.value for p in points])
    transform = temperatures if fit_quantity.endswith("*T") else np.ones(len(points))
    values = raw*transform
    x, y = 1/temperatures, np.log(values)
    slope, intercept = np.polyfit(x, y, 1)
    residual = y-(intercept+slope*x)
    with np.errstate(over="raise", invalid="raise"):
        prefactor = float(np.exp(intercept))
    fit = {"available": True, "model": "arrhenius", "status": "DIAGNOSTIC_ONLY",
           "fit_method": "unweighted_OLS_log_quantity_vs_inverse_T_free_intercept",
           "value_name": fit_quantity, "log_intercept": float(intercept), "slope_K": float(slope),
           "prefactor": prefactor, "activation_energy_eV": float(-slope*K_B_EV_PER_K),
           "residual_log_quantity": residual.tolist(), "residual_sum_squares": float(residual@residual),
           "n_distinct_temperatures": len(points), "residual_degrees_of_freedom": len(points)-2,
           "adequacy_status": UNRESOLVED, "sampling_independence_status": "DOCUMENTED" if all(
               p.sampling_independence_evidence for p in points) else UNRESOLVED,
           "source_temperature_range_K": [float(temperatures.min()), float(temperatures.max())],
           "shared_model_error_independence": UNRESOLVED}
    base["fit"] = fit
    parameters = None
    if joint_draws is not None:
        if nominal_coverage is None or not 0 < nominal_coverage < 1 or not resampling_provenance:
            raise ValueError("joint draws require coverage and resampling provenance")
        draws = np.asarray(joint_draws, dtype=float)
        if draws.ndim != 2 or draws.shape[1] != len(points):
            raise ValueError("joint draws must use the recorded sorted temperature order")
        if len(draws) < 2 or not np.isfinite(draws).all() or np.any(draws <= 0):
            base["parameter_uncertainty_unavailable_reason"] = "invalid_or_nonpositive_draws_not_discarded"
        else:
            parameters = np.array([np.polyfit(x, np.log(row*transform), 1) for row in draws])
            tails = [(1-nominal_coverage)/2, (1+nominal_coverage)/2]
            base["parameter_uncertainty"] = {
                "method": "propagated_joint_draws", "nominal_coverage": nominal_coverage,
                "parameter_order": ["slope_K", "log_intercept"],
                "covariance": np.cov(parameters, rowvar=False).tolist(),
                "activation_energy_ci_eV": np.quantile(-parameters[:, 0]*K_B_EV_PER_K, tails).tolist(),
                "resampling_provenance": resampling_provenance, "scientific_qualification": UNRESOLVED,
                "covered_error_sources": ["supplied_sampling_draws_only"]}
    if target_temperature_K is not None:
        target = target_temperature_K
        lo, hi = temperatures.min(), temperatures.max()
        outside = target < lo or target > hi
        log_prediction = intercept+slope/target
        with np.errstate(over="raise", invalid="raise"):
            value = float(np.exp(log_prediction))
        pred = {"available": True, "status": "EXTRAPOLATED" if outside else "WITHIN_SOURCE_RANGE_PREDICTION",
                "quantity": fit_quantity, "value": value, "target_temperature_K": target,
                "source_temperature_range_K": [float(lo), float(hi)],
                "extrapolation_distance_K": float(max(lo-target, 0, target-hi)),
                "inverse_temperature_distance_per_K": float(max(1/hi-1/target, 0, 1/target-1/lo)),
                "parameter_only_interval": None, "model_discrepancy_uncertainty": None,
                "scientific_qualification": UNRESOLVED}
        if parameters is not None:
            logs = parameters[:, 1]+parameters[:, 0]/target
            with np.errstate(over="raise", invalid="raise"):
                pred["parameter_only_interval"] = np.exp(np.quantile(logs, tails)).tolist()
        base["prediction"] = pred
    return base
