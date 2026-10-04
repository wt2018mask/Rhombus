"""Explicit resampling and repeated-experiment diagnostics; never auto-qualified.

Block length, counts, intervals, seeds and confidence levels have NO defaults.
The origin-block method preserves legacy semantics but is a new explicit method
identifier because its supplied lag/window support need not match legacy defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
import numpy as np
from scipy.stats import beta
from rudeus.science.contracts import Record, UNRESOLVED, digest
from rudeus.science.transport import analyze_trajectory

COMMON_ORIGIN_BLOCKS_V1 = "explicit_common_origin_blocks-v1-unqualified"
MATCHED_ORIGIN_BLOCKS_V2 = "joint_contiguous_full_origin_blocks-v2-diagnostic"


@dataclass(frozen=True, kw_only=True)
class ResamplingSpec(Record):
    block_origins: int
    min_blocks_provisional: int
    n_resamples: int
    nominal_coverage_provisional: float
    seed: int
    replica_scheme: str
    joint_quantities: tuple[str, ...]
    method: str = COMMON_ORIGIN_BLOCKS_V1

    def validate(self):
        super().validate()
        for value in (self.block_origins, self.min_blocks_provisional, self.n_resamples, self.seed):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("resampling counts and seed must be integers")
        if min(self.block_origins, self.min_blocks_provisional, self.n_resamples) < 1:
            raise ValueError("positive resampling counts required")
        if not 0 < self.nominal_coverage_provisional < 1:
            raise ValueError("invalid nominal coverage")
        if self.replica_scheme != "single_trajectory_no_replica_resampling":
            raise ValueError("nested replica scheme is not qualified or implemented")
        if self.method not in (COMMON_ORIGIN_BLOCKS_V1, MATCHED_ORIGIN_BLOCKS_V2):
            raise ValueError("unsupported resampling method")
        if (not self.joint_quantities or len(set(self.joint_quantities)) != len(self.joint_quantities)
                or any(not isinstance(value, str) or not value for value in self.joint_quantities)):
            raise ValueError("joint quantities must be nonempty unique names")


def _quantities(result):
    values = {f"D:{s}": v["D_m2_per_s"] for s, v in result["self_diffusion_by_species"].items()}
    ne, collective = result["conductivity_estimate"], result["collective_transport"]
    values["sigma_NE"] = ne.get("value_S_per_m")
    values["sigma_collective"] = collective.get("sigma_S_per_m")
    values["correlation"] = collective.get("correlation", {}).get("factor")
    return values


def joint_origin_bootstrap(positions, species, frame_steps, timestep_fs, lag_steps, *,
                           spec: ResamplingSpec, expected_population_hash=None, **analysis_kwargs):
    if spec.method != COMMON_ORIGIN_BLOCKS_V1:
        raise ValueError("legacy common-origin bootstrap requires its versioned method")
    lags = np.asarray(lag_steps)
    if not len(lags) or np.any(lags != np.floor(lags)) or lags.max() >= len(positions) or lags.min() < 1:
        raise ValueError("invalid bootstrap lag support")
    n_origins = len(positions) - int(lags.max())
    n_blocks, discarded = divmod(n_origins, spec.block_origins)
    base = {"implementation_status": "IMPLEMENTED", "scientific_qualification": UNRESOLVED,
            "method": spec.method, "resampling_spec": spec.to_dict(),
            "origin_policy": "explicit_common_pool_complete_blocks", "candidate_origins": n_origins,
            "used_origins": n_blocks * spec.block_origins, "discarded_origins": discarded,
            "n_complete_blocks": n_blocks, "effective_independent_blocks": None,
            "maximum_lag_frames": int(lags.max()),
            "block_data_span_frames": spec.block_origins + int(lags.max()),
            "joint_ion_resampling": True, "nested_replica_resampling": False,
            "calibration_reference": None, "status": "INSUFFICIENT", "intervals": {}, "draws": {}}
    if n_blocks < spec.min_blocks_provisional:
        return {**base, "reason": "fewer_than_provisional_minimum_blocks"}
    complete = np.arange(n_blocks * spec.block_origins)
    point = analyze_trajectory(positions, species, frame_steps, timestep_fs, lag_steps,
                               origins=complete, **analysis_kwargs)
    population_hash = next(iter(point["self_diffusion_by_species"].values()))["origin_population_hash"]
    if expected_population_hash is not None and expected_population_hash != population_hash:
        raise ValueError("resampling population differs from requested point estimator")
    supported = _quantities(point)
    if any(name not in supported for name in spec.joint_quantities):
        raise ValueError("unknown joint quantity")
    draws = {key: [] for key in spec.joint_quantities}
    failures = []
    rng = np.random.default_rng(spec.seed)
    for index in range(spec.n_resamples):
        picks = rng.integers(0, n_blocks, size=n_blocks)
        rows = np.concatenate([np.arange(b * spec.block_origins, (b + 1) * spec.block_origins)
                               for b in picks])
        try:
            values = _quantities(analyze_trajectory(positions, species, frame_steps, timestep_fs,
                                                   lag_steps, origins=rows, **analysis_kwargs))
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            failures.append({"draw": index, "reason": type(exc).__name__})
            values = {}
        for key in draws:
            value = values.get(key)
            draws[key].append(float(value) if value is not None and np.isfinite(value) else None)
    tail = (1 - spec.nominal_coverage_provisional) / 2
    intervals = {}
    for key, values in draws.items():
        # No deletion of failed draws or nonpositive log inputs to improve a CI.
        intervals[key] = (np.quantile(values, [tail, 1-tail], method="linear").tolist()
                          if len(values) >= 2 and all(v is not None for v in values) else None)
    return {**base, "status": "DIAGNOSTIC_ONLY", "reason": "coverage_not_qualified",
            "point_origin_population_hash": population_hash,
            "point_estimates_same_origin_pool": supported, "draws": draws, "intervals": intervals,
            "failed_draws": failures, "quantile_method": "linear", "numpy_version": np.__version__}


def _full_origin_blocks(n_origins, block_origins):
    """Partition every eligible origin; the short final block is retained."""
    return tuple((start, min(start + block_origins, n_origins))
                 for start in range(0, n_origins, block_origins))


def _weighted_analysis(positions, species, frame_steps, timestep_fs, lag_steps, weights,
                       analysis_kwargs):
    """One seam for testing failure preservation; no trajectory is concatenated."""
    return analyze_trajectory(positions, species, frame_steps, timestep_fs, lag_steps,
                              origin_weights=weights, **analysis_kwargs)


def matched_origin_block_bootstrap(positions, species, frame_steps, timestep_fs, lag_steps, *,
                                   spec: ResamplingSpec, expected_population_hash,
                                   **analysis_kwargs):
    """Diagnostic block resampling of the primary estimator's full origin population.

    Blocks define joint integer weights on original origins. They never splice
    coordinate arrays, and each lag keeps its own valid prefix of origins. This
    is an implementation contract, not a coverage or independence claim.
    """
    if spec.method != MATCHED_ORIGIN_BLOCKS_V2:
        raise ValueError("matched full-origin bootstrap requires its versioned method")
    lags = np.asarray(lag_steps)
    if (lags.ndim != 1 or not len(lags) or lags.dtype.kind not in "iu"
            or np.any(lags < 1) or np.any(np.diff(lags) <= 0) or lags.max() >= len(positions)):
        raise ValueError("invalid bootstrap lag support")
    point = analyze_trajectory(positions, species, frame_steps, timestep_fs, lag_steps,
                               **analysis_kwargs)
    species_results = point["self_diffusion_by_species"]
    population_hashes = {value["origin_population_hash"] for value in species_results.values()}
    if len(population_hashes) != 1:
        raise ValueError("species do not share one primary origin population")
    population_hash = population_hashes.pop()
    if expected_population_hash != population_hash:
        raise ValueError("resampling population differs from requested point estimator")
    supported = {f"D:{name}": value["D_m2_per_s"] for name, value in species_results.items()}
    if any(name not in supported for name in spec.joint_quantities):
        raise ValueError("full-origin Phase 2 resampling supports species self-diffusion only")

    n_union = len(positions) - int(lags.min())
    blocks = _full_origin_blocks(n_union, spec.block_origins)
    support_counts = {str(int(lag)): len(positions) - int(lag) for lag in lags}
    block_support = {str(int(lag)): [max(0, min(end, len(positions)-int(lag)) - start)
                                          for start, end in blocks]
                     for lag in lags}
    reference_ranges = [[start, min(len(positions), end + int(lags.max()))]
                        for start, end in blocks]
    estimator_specification = {
        "frame_steps": [int(value) for value in frame_steps],
        "integration_timestep_fs": float(timestep_fs),
        "lag_steps": [int(value) for value in lags],
        "fit_window_ps": [float(value) for value in analysis_kwargs["fit_window_ps"]],
        "selected_species": list(analysis_kwargs["selected_species"]),
        "reference_frame": analysis_kwargs["reference_frame"],
        "volume_A3": float(analysis_kwargs["volume_A3"]),
        "temperature_K": float(analysis_kwargs["temperature_K"]),
        "charge_numbers": ({key: float(value) for key, value in analysis_kwargs["charge_numbers"].items()}
                           if analysis_kwargs.get("charge_numbers") is not None else None),
        "estimator": "free_intercept_OLS_MSD", "signed_slopes": True,
        "slope_clipping": False, "psd_projection": False, "forced_zero_intercept": False,
    }
    base = {
        "implementation_status": "IMPLEMENTED", "scientific_qualification": UNRESOLVED,
        "status": "DIAGNOSTIC_ONLY", "reason": "coverage_not_qualified",
        "method": spec.method, "method_version": "2", "resampling_spec": spec.to_dict(),
        "origin_policy": "all_available_per_lag_joint_block_weights",
        "original_population_hash": population_hash,
        "estimator_specification": estimator_specification,
        "estimator_specification_hash": digest(estimator_specification),
        "point_estimates_same_population": supported,
        "eligible_origin_union": n_union, "lag_support_counts": support_counts,
        "lag_block_support_counts": block_support,
        "block_boundaries": [list(pair) for pair in blocks],
        "block_length_origins_provisional": spec.block_origins,
        "tail_block_policy": "preserve_short_final_block",
        "n_blocks": len(blocks), "effective_independent_blocks": None,
        "maximum_lag_frames": int(lags.max()),
        "displacement_reference_ranges": reference_ranges,
        "joint_weight_scope": "all_species_atoms_lags_tensor_components",
        "coordinate_joining": False, "nested_replica_resampling": False,
        "replica_pooling_rule": UNRESOLVED, "calibration_reference": None,
        "planned_draws": spec.n_resamples, "rng": "numpy.random.Generator(PCG64)",
        "seed": spec.seed, "nominal_interval_level_provisional": spec.nominal_coverage_provisional,
        "interval_semantics": "diagnostic_percentile_not_validated_confidence_interval",
        "quantile_method": "linear", "numpy_version": np.__version__,
    }
    rng = np.random.default_rng(spec.seed)
    draws = {key: [] for key in spec.joint_quantities}
    tensor_draws = {name: [] for name in species_results}
    records, failures = [], []
    for draw_index in range(spec.n_resamples):
        picks = rng.integers(0, len(blocks), size=len(blocks)).tolist()
        weights = np.zeros(n_union, dtype=np.int64)
        for block_index in picks:
            start, end = blocks[block_index]
            weights[start:end] += 1
        support_weight_sums = {str(int(lag)): int(weights[:len(positions)-int(lag)].sum())
                               for lag in lags}
        record = {"draw": draw_index, "block_indices": picks,
                  "origin_weight_hash": digest(weights.tolist()),
                  "lag_support_weight_sums": support_weight_sums}
        try:
            if any(value == 0 for value in support_weight_sums.values()):
                raise ValueError("zero_lag_support_weight")
            result = _weighted_analysis(positions, species, frame_steps, timestep_fs, lag_steps,
                                        weights, analysis_kwargs)
            values = {f"D:{name}": value["D_m2_per_s"]
                      for name, value in result["self_diffusion_by_species"].items()}
            tensors = {name: value["D_tensor_m2_per_s"]
                       for name, value in result["self_diffusion_by_species"].items()}
            if any(key not in values or not np.isfinite(values[key]) for key in draws):
                raise ValueError("nonfinite_or_missing_resampled_quantity")
            if any(not np.isfinite(value).all() for value in map(np.asarray, tensors.values())):
                raise ValueError("nonfinite_resampled_tensor")
            for key in draws:
                draws[key].append(float(values[key]))
            for name in tensor_draws:
                tensor_draws[name].append(tensors[name])
            records.append({**record, "status": "COMPLETED", "failure_reason": None})
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            reason = str(exc) if str(exc) else type(exc).__name__
            failures.append({"draw": draw_index, "reason": reason})
            records.append({**record, "status": "FAILED", "failure_reason": reason})
            for key in draws:
                draws[key].append(None)
            for name in tensor_draws:
                tensor_draws[name].append(None)

    tail = (1 - spec.nominal_coverage_provisional) / 2
    intervals = {}
    for key, values in draws.items():
        intervals[key] = (np.quantile(values, [tail, 1-tail], method="linear").tolist()
                          if len(values) >= 2 and all(value is not None for value in values) else None)
    return {**base, "draws": draws, "tensor_draws": tensor_draws,
            "draw_records": records, "failed_draws": failures, "intervals": intervals,
            "diagnostic_interval_available": all(value is not None for value in intervals.values())}


def resample_replicas(replica_ids, *, n_resamples, seed, independence_evidence, exchangeability_evidence):
    """Outer-only index draws; no inferred pooling weights or nested resampling."""
    if not independence_evidence or not exchangeability_evidence:
        raise ValueError("explicit independence and exchangeability evidence required")
    if len(set(replica_ids)) != len(replica_ids) or len(replica_ids) < 2 or n_resamples < 1:
        raise ValueError("distinct replica support and positive resample count required")
    rng = np.random.default_rng(seed)
    return {"replica_ids": list(replica_ids), "indices": rng.integers(
        0, len(replica_ids), (n_resamples, len(replica_ids))).tolist(),
        "independence_evidence": independence_evidence, "exchangeability_evidence": exchangeability_evidence,
        "pooling_rule": UNRESOLVED, "scientific_qualification": UNRESOLVED}


def binomial_interval(successes, total, confidence):
    """Clopper-Pearson Monte Carlo interval; confidence is explicitly supplied."""
    if not 0 < confidence < 1 or not 0 <= successes <= total:
        raise ValueError("invalid binomial counts/confidence")
    if total == 0:
        return None
    tail = (1-confidence)/2
    return [0.0 if successes == 0 else float(beta.ppf(tail, successes, total-successes+1)),
            1.0 if successes == total else float(beta.ppf(1-tail, successes+1, total-successes))]


def coverage_experiment(generator, estimator, *, seeds, truth, nominal_coverage,
                        monte_carlo_confidence, generating_protocol: Mapping,
                        registered_criteria: Mapping | None = None):
    """Repeated independent datasets. Criteria are recorded, NEVER auto-certified.

    Estimator returns estimate, interval and optional decision_correct (boolean).
    Missing intervals count as no coverage in unconditional reporting. Conditional
    reporting and abstention counts are also retained to expose selection effects.
    """
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("independent experiment seeds must be explicit and unique")
    if not np.isfinite(truth) or not 0 < nominal_coverage < 1:
        raise ValueError("finite truth and explicit nominal coverage required")
    records = []
    for seed in seeds:
        try:
            output = estimator(generator(seed))
            estimate, interval = output.get("estimate"), output.get("interval")
            if estimate is not None and not np.isfinite(estimate):
                raise ValueError("nonfinite estimate")
            if interval is not None and (len(interval) != 2 or not np.isfinite(interval).all() or interval[0] > interval[1]):
                raise ValueError("invalid interval")
            records.append({"seed": seed, "estimate": estimate, "interval": interval,
                            "decision_correct": output.get("decision_correct"), "error": None})
        except Exception as exc:
            records.append({"seed": seed, "estimate": None, "interval": None,
                            "decision_correct": None, "error": type(exc).__name__})
    intervals = [r["interval"] for r in records if r["interval"] is not None]
    estimates = [r["estimate"] for r in records if r["estimate"] is not None]
    covered = sum(lo <= truth <= hi for lo, hi in intervals)
    decisions = [r["decision_correct"] for r in records if isinstance(r["decision_correct"], bool)]
    n = len(records)
    return {"records": records, "truth": truth, "nominal_coverage": nominal_coverage,
            "coverage_unconditional": covered/n, "coverage_conditional": covered/len(intervals) if intervals else None,
            "coverage_monte_carlo_interval": binomial_interval(covered, n, monte_carlo_confidence),
            "monte_carlo_confidence": monte_carlo_confidence,
            "bias": float(np.mean(estimates)-truth) if estimates else None,
            "mean_interval_width": float(np.mean([hi-lo for lo, hi in intervals])) if intervals else None,
            "abstention_rate": (n-len(intervals))/n, "false_decision_count": decisions.count(False),
            "decision_count": len(decisions), "false_decision_rate": decisions.count(False)/len(decisions) if decisions else None,
            "generating_protocol": dict(generating_protocol), "registered_criteria": registered_criteria,
            "experiment_hash": digest({"seeds": seeds, "protocol": generating_protocol, "truth": truth}),
            "scientific_qualification": UNRESOLVED,
            "qualification_reason": "registered_evaluation_and_physical_applicability_not_established"}
