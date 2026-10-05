"""Read-only aggregation of independently evidenced P3 temperature/replicate results.

This module does not run trajectories or qualify diagnostic intervals. Every input
remains addressable by its P3 result hash and its P2 trajectory hash.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np

from rudeus.mlip.p3_transport import fit_arrhenius, extrapolate_arrhenius
from rudeus.science.claims import QualificationRecord, evaluate_claim
from rudeus.science.contracts import (ClaimSpec, Observation, ObservableType,
                                      Uncertainty, UNRESOLVED, digest)


_P3_KEYS = {"quantitative_transport", "p3_assessment", "p3_provenance",
            "p3_evidence_events", "p3_scientific_record"}


def _point(entry: Mapping) -> dict:
    """Validate one explicit temperature-point/replicate binding."""
    point_id, replica_id = entry["temperature_point_id"], entry["replicate_id"]
    if not isinstance(point_id, str) or not point_id or not isinstance(replica_id, str) or not replica_id:
        raise ValueError("temperature-point and replicate identities must be nonempty strings")
    result = entry["p3_result"]
    record, provenance = result["p3_scientific_record"], result["p3_provenance"]
    if (result["transport_state"] == "NONDIFFUSIVE"
            or result.get("p25_verdict") == "NONDIFFUSIVE"):
        raise ValueError("P2.5 NONDIFFUSIVE cannot enter P3")
    if provenance["scientific_record_hash"] != digest(record):
        raise ValueError("P3 scientific record hash mismatch")
    p25_result = {k: v for k, v in result.items() if k not in _P3_KEYS}
    if provenance["p25_result_hash"] not in (digest(p25_result), digest({"result": p25_result})):
        # Preserve nonstandard outer envelopes only when supplied explicitly.
        if entry.get("p25_payload") is None or provenance["p25_result_hash"] != digest(entry["p25_payload"]):
            raise ValueError("P2.5 payload binding mismatch")
    observation = record["observation"]
    if observation is None:
        raise ValueError("P3 replicate has no D_self observation")
    obs = Observation.from_dict(observation)
    unc = Uncertainty.from_dict(record["uncertainty"])
    qt = result["quantitative_transport"]
    temperature = float(result["temperature_K"])
    D = float(qt["self_diffusion"]["D_m2_per_s"])
    if not math.isfinite(temperature) or temperature <= 0 or not math.isfinite(D):
        raise ValueError("nonphysical temperature or diffusion value")
    if (obs.value != D or obs.conditions["temperature_K"] != temperature
            or obs.conditions["candidate_id"] != result["candidate_material_id"]
            or obs.protocol_hash != provenance["p3_config_hash"]
            or provenance["trajectory_sha256"] not in obs.artifact_hashes
            or unc.observation_hash != obs.content_hash):
        raise ValueError("P3 observation, protocol, temperature or artifact binding mismatch")
    if obs.conditions["reference_frame"] != obs.reference_frame:
        raise ValueError("mixed reference-frame identity within replicate")
    return {"temperature_point_id": point_id, "replicate_id": replica_id,
            "temperature_K": temperature, "D_m2_per_s": D,
            "candidate_id": result["candidate_material_id"],
            "target_species": result["target_species"], "reference_frame": obs.reference_frame,
            "protocol_hash": obs.protocol_hash, "estimator": obs.estimator,
            "estimator_version": obs.estimator_version,
            "uncertainty_method": unc.method, "uncertainty_method_version": unc.method_version,
            "uncertainty_qualification": unc.qualification,
            "uncertainty_bounds": list(unc.bounds) if unc.bounds is not None else None,
            "uncertainty_unavailable_reasons": list(unc.unavailable_reasons),
            "collective_transport": qt["collective_transport"],
            "conductivity_estimate": qt["conductivity_estimate"],
            "p3_result_hash": digest(result), "trajectory_sha256": provenance["trajectory_sha256"],
            "observation_hash": obs.content_hash, "uncertainty_hash": unc.content_hash}


def analyze_p3_series(entries: Sequence[Mapping], *, target_temperature_K: float | None = None,
                      claim_spec: ClaimSpec | None = None,
                      activation_uncertainty: Uncertainty | None = None,
                      qualification_registry: Mapping[str, QualificationRecord] | None = None,
                      checks: Mapping | None = None) -> dict:
    """Aggregate D(T) without treating fit quality or bootstrap spread as qualification.

    Replicates at a temperature use an equal-weight arithmetic mean. This is an
    explicit diagnostic pooling rule, not an independent-sample or coverage claim.
    At least three distinct temperatures are needed to estimate a line and retain
    one residual degree of freedom; this is a mathematical minimum, not a regime
    acceptance threshold.
    """
    if not entries:
        raise ValueError("P3 series requires at least one evidenced replicate")
    points = [_point(entry) for entry in entries]
    identity = ("candidate_id", "target_species", "reference_frame", "protocol_hash",
                "estimator", "estimator_version")
    for point in points[1:]:
        if any(point[key] != points[0][key] for key in identity):
            raise ValueError("candidate, species, protocol, estimator or reference-frame mismatch")
    groups: dict[str, list[dict]] = {}
    temperatures: dict[float, str] = {}
    for point in points:
        group = groups.setdefault(point["temperature_point_id"], [])
        if group and group[0]["temperature_K"] != point["temperature_K"]:
            raise ValueError("temperature-point identity maps to multiple temperatures")
        previous_id = temperatures.setdefault(point["temperature_K"], point["temperature_point_id"])
        if previous_id != point["temperature_point_id"]:
            raise ValueError("temperature has multiple point identities")
        if any(p["replicate_id"] == point["replicate_id"] for p in group):
            raise ValueError("replicate identity mismatch or duplicate")
        group.append(point)
    aggregated = []
    for point_id, replicas in groups.items():
        values = [p["D_m2_per_s"] for p in replicas]
        aggregated.append({"temperature_point_id": point_id,
                           "temperature_K": replicas[0]["temperature_K"],
                           "D_m2_per_s": float(np.mean(values)),
                           "replicate_count": len(replicas),
                           "replicate_ids": [p["replicate_id"] for p in replicas],
                           "replicate_D_m2_per_s": values,
                           "replicate_spread_m2_per_s": float(np.std(values, ddof=1)) if len(values) > 1 else None,
                           "uncertainty_bounds": None,
                           "uncertainty_status": UNRESOLVED,
                           "pooling_rule": "equal_weight_replicate_mean_diagnostic"})
    aggregated.sort(key=lambda p: p["temperature_K"])
    temperatures_K = [p["temperature_K"] for p in aggregated]
    values = [p["D_m2_per_s"] for p in aggregated]
    fit = {"model": "arrhenius", "available": False, "status": "INSUFFICIENT_TEMPERATURES",
           "required_distinct_temperatures": 3, "observed_distinct_temperatures": len(aggregated)}
    if len(aggregated) >= 3 and all(value > 0 for value in values):
        fit = fit_arrhenius(temperatures_K=temperatures_K, values=values, value_name="D_m2_per_s")
        fit["fit_diagnostics"].update({
            "residual_degrees_of_freedom": len(values) - 2,
            "residuals_log_D": [float(y - (math.log(fit["prefactor"]) -
                                  fit["activation_energy_eV"] / (8.617333262145e-5 * t)))
                                for y, t in zip(np.log(values), temperatures_K)],
            "regime_qualification": UNRESOLVED,
            "residual_acceptance_threshold": None,
            "per_temperature_uncertainty_available": False})
    elif len(aggregated) >= 3:
        fit["status"] = "NONPOSITIVE_DIFFUSION"
    extrapolation = {"available": False, "status": "NOT_REQUESTED"}
    if target_temperature_K is not None:
        extrapolation = extrapolate_arrhenius(fit=fit, target_temperature_K=target_temperature_K,
            source_temperature_range_K=[min(temperatures_K), max(temperatures_K)], quantity="D_m2_per_s")
        extrapolation["uncertainty"] = {"value_ci": None, "qualification": UNRESOLVED}
    series_hash = digest({"protocol_hash": points[0]["protocol_hash"],
                          "point_bindings": sorted((p["temperature_point_id"], p["replicate_id"],
                                                    p["p3_result_hash"]) for p in points)})
    obs = None
    if fit["available"]:
        obs = Observation(quantity="activation_energy", units="eV", value=fit["activation_energy_eV"],
            species=(points[0]["target_species"],),
            conditions={"candidate_id": points[0]["candidate_id"],
                        "species": [points[0]["target_species"]],
                        "reference_frame": points[0]["reference_frame"]},
            reference_frame=points[0]["reference_frame"],
            data_support={"temperature_points": aggregated, "series_hash": series_hash},
            estimator="equal_weight_replicate_mean_then_OLS_log_D_vs_inverse_T",
            estimator_version="p3-series-v1", protocol_hash=series_hash,
            artifact_hashes=tuple(p["trajectory_sha256"] for p in points),
            observable_type=ObservableType.PARAMETER)
    if claim_spec is None:
        claim_spec = ClaimSpec(claim_id="P3.activation_energy", protocol_hash=series_hash,
            estimand="activation_energy", units="eV",
            scope={"candidate_id": points[0]["candidate_id"],
                   "species": [points[0]["target_species"]],
                   "reference_frame": points[0]["reference_frame"]},
            assumptions=("arrhenius_regime_applicable",),
            applicability_requirements=("calibration_population_applicable",),
            sufficiency_requirements=("residuals_qualified",),
            independence_requirements=("replicate_dependence_accounted_for",),
            admissible_evidence=(ObservableType.PARAMETER.value,),
            provenance_identity=series_hash)
    uncertainty = activation_uncertainty or Uncertainty(
        observation_hash=obs.content_hash if obs else None,
        unavailable_reasons=("held_out_qualification_unresolved", "activation_energy_interval_unavailable"))
    registry = qualification_registry or {}
    certificate = registry.get(uncertainty.calibration_reference) if uncertainty.calibration_reference else None
    binding_applies = bool(certificate and obs and certificate.status == "QUALIFIED"
        and certificate.evidence_hashes
        and certificate.content_hash == uncertainty.calibration_reference
        and certificate.protocol_hash == series_hash
        and certificate.estimator == obs.estimator
        and certificate.estimator_version == obs.estimator_version
        and certificate.uncertainty_method == uncertainty.method
        and certificate.uncertainty_method_version == uncertainty.method_version
        and certificate.nominal_coverage == uncertainty.nominal_coverage
        and certificate.requirements_hash == digest(claim_spec.uncertainty_requirements)
        and dict(certificate.scope) == dict(claim_spec.scope)
        and uncertainty.observation_hash == obs.content_hash)
    calibration = {"status": "APPLICABLE" if binding_applies else UNRESOLVED,
                   "qualification_record_hash": certificate.content_hash if binding_applies else None,
                   "held_out_evidence_hashes": list(certificate.evidence_hashes) if binding_applies else [],
                   "population_scope": dict(certificate.scope) if binding_applies else None,
                   "estimator": obs.estimator if obs else None,
                   "uncertainty_method": uncertainty.method}
    assessment = evaluate_claim(claim_spec, obs, uncertainty, checks=checks,
                                qualification_registry=qualification_registry)
    conductivity_points = [{"temperature_point_id": p["temperature_point_id"],
                            "replicate_id": p["replicate_id"],
                            "temperature_K": p["temperature_K"],
                            "estimate": p["conductivity_estimate"],
                            "actual_conductivity_qualified": False}
                           for p in points]
    return {"series_version": "p3-series-v1", "series_hash": series_hash,
            "candidate_id": points[0]["candidate_id"], "target_species": points[0]["target_species"],
            "reference_frame": points[0]["reference_frame"], "protocol_hash": points[0]["protocol_hash"],
            "replicates": points, "temperature_points": aggregated,
            "temperature_dependence": {"temperatures_K": temperatures_K,
                                       "diffusion_points": aggregated,
                                       "conductivity_points": conductivity_points,
                                       "fit": fit},
            "extrapolation": extrapolation,
            "conductivity_semantics": "sigma_NE is an estimate, not automatically actual conductivity",
            "collective_transport_semantics": "per-replicate availability retained; no collective series qualification inferred",
            "calibration_applicability": calibration,
            "claim_spec": claim_spec.to_dict(), "observation": obs.to_dict() if obs else None,
            "uncertainty": uncertainty.to_dict(), "assessment": assessment.to_dict()}
