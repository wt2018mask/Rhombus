"""Read-only P2/P2.5 -> additive P3 analysis. Never executes MD or revises history."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Mapping
import numpy as np

from rudeus.schema import EvidenceEvent
from rudeus.science.trajectory import validate_schedule, reconstruct_fixed_cell
from rudeus.mlip.p2_traj import verify_traj_artifact
from rudeus.science.contracts import (Record, UNRESOLVED, digest, Observation, ObservableType,
                                      ClaimSpec, Uncertainty, canonical_bytes)
from rudeus.science.claims import evaluate_claim
from rudeus.science.statistics import (ResamplingSpec, joint_origin_bootstrap,
                                       matched_origin_block_bootstrap,
                                       MATCHED_ORIGIN_BLOCKS_V2)
from rudeus.science.transport import analyze_trajectory, unavailable
from rudeus.execution.contracts import ExecutionError, FailureClass


@dataclass(frozen=True, kw_only=True)
class P3Protocol(Record):
    target_species: str
    lag_steps: tuple[int, ...] | None = None
    fit_window_ps: tuple[float, float] | None = None
    reference_frame: str | None = None
    charge_numbers: Mapping | None = None
    charge_species: tuple[str, ...] | None = None
    charge_justification: str | None = None
    resampling: ResamplingSpec | None = None
    reconstruction: Mapping | None = field(default=None, metadata={"omit_none": True})
    version: str = "p3-integrated-v1-unqualified"

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        if value.get("resampling") is not None:
            value["resampling"] = ResamplingSpec.from_dict(value["resampling"])
        return cls(**value)

    def validate(self):
        super().validate()
        if not self.target_species or self.version != "p3-integrated-v1-unqualified":
            raise ValueError("unsupported P3 protocol identity")
        if self.resampling is not None and not isinstance(self.resampling, ResamplingSpec):
            raise ValueError("resampling must be a typed ResamplingSpec")
        if self.reconstruction is not None and not isinstance(self.reconstruction, Mapping):
            raise ValueError("reconstruction must be an explicit mapping")
        if self.lag_steps is not None and (len(self.lag_steps) < 2 or any(
                isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in self.lag_steps)
                or any(a >= b for a, b in zip(self.lag_steps, self.lag_steps[1:]))):
            raise ValueError("supply at least two increasing positive integer lag steps")
        if self.fit_window_ps is not None and (len(self.fit_window_ps) != 2
                or not 0 <= self.fit_window_ps[0] < self.fit_window_ps[1]):
            raise ValueError("invalid explicit fit window")


def _verified_inputs(p2, p25, root):
    result = p2["result"]
    source = p25["result"] if "result" in p25 else p25
    binding = result["trajectory_artifact"]
    provenance = source["provenance"]
    pairs = ((source["candidate_material_id"], result["candidate_material_id"]),
             (source["batch_id"], p2["batch_id"]),
             (provenance["trajectory_artifact_sha256"], binding["sha256"]),
             (provenance["p2_config_hash"], result["p2_config_hash"]),
             (provenance["p2_protocol_version"], result["p2_protocol_version"]),
             (provenance["artifact_format_version"], binding["format_version"]),
             (provenance["p2_seed"], result["seed"]),
             (source["p2_verdict"], result["p2_verdict"]),
             (source["p2_dynamic_state"], result["dynamic_state"]),
             (source["temperature_K"], result["temperature_K"]))
    if any(a != b for a, b in pairs):
        raise ExecutionError("P2/P2.5 identity binding mismatch", FailureClass.INTEGRITY)
    if binding["format_version"] != "p2-traj-v1":
        raise ExecutionError("unsupported trajectory format", FailureClass.INTEGRITY)
    path = (Path(root) / binding["path"]).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ExecutionError("artifact path outside input root", FailureClass.INTEGRITY)
    artifact = verify_traj_artifact(path, binding["sha256"])
    # The legacy loader coerces frame steps to int64. Reject noninteger stored
    # arrays before that coercion can conceal an invalid physical time axis.
    with np.load(path, allow_pickle=False) as stored:
        if stored["frame_steps"].dtype.kind not in "iu":
            raise ExecutionError("stored frame steps must be integers", FailureClass.INTEGRITY)
    for key, expected in (("batch_id", p2["batch_id"]), ("p2_config_hash", result["p2_config_hash"]),
                           ("seed", result["seed"]), ("p2_protocol_version", result["p2_protocol_version"])):
        if artifact[key] != expected:
            raise ExecutionError(f"trajectory {key} mismatch", FailureClass.INTEGRITY)
    return result, source, artifact


def analyze_p3(p2_payload, p25_payload, protocol: P3Protocol, *, artifact_root, timestamp,
               claim_spec: ClaimSpec | None = None):
    try:
        p2, source, artifact = _verified_inputs(p2_payload, p25_payload, artifact_root)
    except ExecutionError:
        raise
    except Exception as exc:
        raise ExecutionError(f"unverifiable P3 input: {type(exc).__name__}", FailureClass.INTEGRITY) from exc
    result = copy.deepcopy(source)
    try:
        sampling = validate_schedule(artifact, p2)
    except ValueError as exc:
        raise ExecutionError(str(exc), FailureClass.UNSUPPORTED_INPUT) from exc
    if any(key in result for key in ("quantitative_transport", "p3_assessment", "p3_provenance",
                                     "p3_evidence_events", "p3_scientific_record")):
        raise ExecutionError("P3 input already contains P3 evidence; refusing overwrite", FailureClass.INTEGRITY)
    obs = None
    uncertainty = Uncertainty(unavailable_reasons=("observation_not_available",))
    bootstrap = None
    qt = {"self_diffusion": unavailable("analysis_protocol_unresolved"),
          "conductivity_estimate": unavailable("charge_specification_missing"),
          "collective_transport": unavailable("charge_specification_missing"),
          "temperature_dependence": {"available": False, "status": "NOT_RUN"},
          "extrapolation": {"available": False, "status": "NOT_REQUESTED"}}
    missing = [key for key in ("lag_steps", "fit_window_ps", "reference_frame")
               if getattr(protocol, key) is None]
    reasons = ["quantitative_statistical_qualification_unresolved"]
    if source["target_species"] != protocol.target_species:
        raise ExecutionError("target species contradicts protected P2.5 input", FailureClass.UNSUPPORTED_INPUT)
    if p2["p2_verdict"] != "PASS" or p2["dynamic_state"] != "PASS":
        reasons.append("p2_screen_not_passed")
    elif missing:
        reasons.extend(f"unresolved:{key}" for key in missing)
    elif protocol.reconstruction is None:
        qt["self_diffusion"] = unavailable("reconstruction_declaration_unresolved")
        reasons.append("reconstruction_declaration_unresolved")
    elif artifact["n_production_frames"] < 2:
        reasons.append("insufficient_production_frames")
    elif max(protocol.lag_steps) >= artifact["n_production_frames"]:
        reasons.append("insufficient_frames_for_requested_lags")
    elif sum(protocol.fit_window_ps[0] <= (
            int(artifact["frame_steps"][lag]) - int(artifact["frame_steps"][0])) * artifact["timestep_fs"] / 1000
            <= protocol.fit_window_ps[1] for lag in protocol.lag_steps) < 2:
        reasons.append("insufficient_lags_in_requested_fit_window")
    else:
        charge_ok = (protocol.charge_numbers is not None and protocol.charge_species is not None
                     and bool(protocol.charge_justification))
        selection = protocol.charge_species if charge_ok else (protocol.target_species,)
        if protocol.target_species not in selection:
            raise ExecutionError("charge scope omits target species", FailureClass.UNSUPPORTED_INPUT)
        try:
            unwrapped, reconstruction = reconstruct_fixed_cell(artifact, protocol.reconstruction)
            computed = analyze_trajectory(
                unwrapped, artifact["species"], artifact["frame_steps"], artifact["timestep_fs"],
                protocol.lag_steps, selected_species=selection, fit_window_ps=protocol.fit_window_ps,
                volume_A3=float(abs(np.linalg.det(artifact["cell"]))), temperature_K=source["temperature_K"],
                reference_frame=protocol.reference_frame,
                charge_numbers=protocol.charge_numbers if charge_ok else None)
        except (FloatingPointError, np.linalg.LinAlgError) as exc:
            raise ExecutionError(str(exc), FailureClass.NUMERICAL) from exc
        except (ValueError, TypeError) as exc:
            raise ExecutionError(str(exc), FailureClass.UNSUPPORTED_INPUT) from exc
        qt["self_diffusion"] = {**computed["self_diffusion_by_species"][protocol.target_species],
                                "species_results": computed["self_diffusion_by_species"],
                                "reconstruction": reconstruction, "sampling": sampling}
        qt["conductivity_estimate"] = computed["conductivity_estimate"]
        qt["collective_transport"] = computed["collective_transport"]
        qt["collective_transport"]["charge_justification"] = protocol.charge_justification
        obs = Observation(quantity="D_self", units="m2/s", value=qt["self_diffusion"]["D_m2_per_s"],
                          species=(protocol.target_species,), conditions={"temperature_K": source["temperature_K"],
                          "candidate_id": source["candidate_material_id"], "species": [protocol.target_species],
                          "reference_frame": protocol.reference_frame},
                          reference_frame=protocol.reference_frame,
                          data_support={"trajectory_sha256": source["provenance"]["trajectory_artifact_sha256"],
                                        "cell_scope": "finite_simulation_cell",
                                        "lag_steps": protocol.lag_steps,
                                        "fitted_lag_times_ps": qt["self_diffusion"]["fitted_lag_times_ps"],
                                        "origin_policy": "all_available_per_lag",
                                        "origin_ranges": [[0, artifact["n_production_frames"] - lag, 1]
                                                          for lag in protocol.lag_steps],
                                        "origin_population_hash": qt["self_diffusion"]["origin_population_hash"],
                                        "species_atom_indices": qt["self_diffusion"]["species_atom_indices"],
                                        "atom_identity_basis": "persistent_artifact_array_index",
                                        "reconstruction": reconstruction, "sampling": sampling,
                                        "mean_displacement_A": qt["self_diffusion"]["mean_displacement_A"],
                                        "unselected_atom_indices": qt["self_diffusion"]["unselected_atom_indices"],
                                        "unselected_atoms_mean_displacement_A": qt["self_diffusion"]["unselected_atoms_mean_displacement_A"],
                                        "frame_steps": artifact["frame_steps"].tolist(),
                                        "timestep_fs": artifact["timestep_fs"]},
                          estimator="free_intercept_OLS_MSD", estimator_version=protocol.version,
                          protocol_hash=protocol.content_hash,
                          artifact_hashes=(source["provenance"]["trajectory_artifact_sha256"],),
                          observable_type=ObservableType.DERIVED, fit_window=protocol.fit_window_ps,
                          sample_counts={"frames": artifact["n_production_frames"],
                                         "ions": qt["self_diffusion"]["n_mobile_ions"],
                                         "origins_per_lag": qt["self_diffusion"]["origin_counts"]},
                          dependence_counts={"effective_independent_samples": None})
        uncertainty = Uncertainty(observation_hash=obs.content_hash,
                                  unavailable_reasons=("resampling_protocol_unresolved",))
        if protocol.resampling is not None:
            bootstrap_kwargs = dict(selected_species=selection, fit_window_ps=protocol.fit_window_ps,
                volume_A3=float(abs(np.linalg.det(artifact["cell"]))),
                temperature_K=source["temperature_K"], reference_frame=protocol.reference_frame,
                charge_numbers=protocol.charge_numbers if charge_ok else None)
            if protocol.resampling.method == MATCHED_ORIGIN_BLOCKS_V2:
                bootstrap = matched_origin_block_bootstrap(
                    unwrapped, artifact["species"], artifact["frame_steps"], artifact["timestep_fs"],
                    protocol.lag_steps, spec=protocol.resampling,
                    expected_population_hash=qt["self_diffusion"]["origin_population_hash"],
                    **bootstrap_kwargs)
                uncertainty = Uncertainty(
                    observation_hash=obs.content_hash, method=protocol.resampling.method,
                    method_version=bootstrap["method_version"],
                    nominal_coverage=protocol.resampling.nominal_coverage_provisional,
                    bounds=None, seed=protocol.resampling.seed, calibration_reference=None,
                    resampling_scheme={"specification": protocol.resampling.to_dict(),
                        "diagnostic_hash": digest(bootstrap),
                        "estimator_specification_hash": bootstrap["estimator_specification_hash"],
                        "diagnostic_intervals": bootstrap["intervals"],
                        "planned_draws": bootstrap["planned_draws"],
                        "failed_draws": bootstrap["failed_draws"],
                        "rng": bootstrap["rng"], "quantile_method": bootstrap["quantile_method"],
                        "interval_semantics": bootstrap["interval_semantics"],
                        "numpy_version": bootstrap["numpy_version"]},
                    block_scheme={k: bootstrap[k] for k in ("original_population_hash",
                        "eligible_origin_union", "lag_support_counts", "lag_block_support_counts",
                        "block_boundaries", "block_length_origins_provisional", "tail_block_policy",
                        "n_blocks", "effective_independent_blocks", "maximum_lag_frames",
                        "displacement_reference_ranges", "origin_policy", "joint_weight_scope",
                        "coordinate_joining")} | {"population_match": True},
                    replica_scheme={"method": protocol.resampling.replica_scheme,
                                    "pooling_rule": UNRESOLVED},
                    unavailable_reasons=("coverage_not_qualified", "block_length_not_qualified",
                        "effective_information_unknown", "stationarity_and_mixing_unknown") +
                        (("diagnostic_draw_failure",) if bootstrap["failed_draws"] else ()))
            else:
                bootstrap = joint_origin_bootstrap(
                    unwrapped, artifact["species"], artifact["frame_steps"], artifact["timestep_fs"],
                    protocol.lag_steps, spec=protocol.resampling, **bootstrap_kwargs)
                # Legacy diagnostic: truncated common origins do not match the primary population.
                uncertainty = Uncertainty(
                    observation_hash=obs.content_hash, method=protocol.resampling.method,
                    method_version="1", nominal_coverage=protocol.resampling.nominal_coverage_provisional,
                    bounds=None, seed=protocol.resampling.seed,
                    resampling_scheme=protocol.resampling.to_dict(),
                    block_scheme={k: bootstrap[k] for k in ("candidate_origins", "used_origins",
                        "discarded_origins", "n_complete_blocks", "effective_independent_blocks",
                        "block_data_span_frames", "origin_policy")} | {
                        "primary_population_hash": qt["self_diffusion"]["origin_population_hash"],
                        "bootstrap_point_population_hash": bootstrap.get("point_origin_population_hash"),
                        "population_match": bootstrap.get("point_origin_population_hash") ==
                                            qt["self_diffusion"]["origin_population_hash"]},
                    replica_scheme={"method": protocol.resampling.replica_scheme},
                    unavailable_reasons=("coverage_not_qualified", "origin_pool_differs_from_point_estimator",
                                         bootstrap["reason"]))
        qt["self_diffusion"]["observation"] = obs.to_dict()
        qt["self_diffusion"]["uncertainty"] = uncertainty.to_dict()
        qt["self_diffusion"]["resampling_diagnostic"] = bootstrap
        reasons.extend(("window_supplied_not_qualified", "unwrapping_and_drift_applicability_unqualified",
                        "finite_cell_and_duration_not_bulk_convergence"))
    if claim_spec is None:
        # An identified but unresolved claim, not an inferred acceptance criterion.
        claim_spec = ClaimSpec(
            claim_id="P3.D_self", protocol_hash=protocol.content_hash, estimand="D_self", units="m2/s",
            scope={"candidate_id": source["candidate_material_id"], "temperature_K": source["temperature_K"],
                   "species": [protocol.target_species], "reference_frame": protocol.reference_frame},
            assumptions=("unwrapping_applicable", "reference_frame_applicable"),
            applicability_requirements=("finite_cell_scope_applicable",),
            sufficiency_requirements=("fit_window_qualified", "sampling_qualified"),
            independence_requirements=("dependence_accounted_for",),
            admissible_evidence=(ObservableType.DERIVED.value,),
            provenance_identity=digest({"p2": p2_payload, "p25": p25_payload}),
            acceptance=None, uncertainty_requirements=None)
    assessment = evaluate_claim(claim_spec, obs, uncertainty)
    result["quantitative_transport"] = qt
    result["p3_scientific_record"] = {
        "claim_spec": claim_spec.to_dict(), "observation": obs.to_dict() if obs else None,
        "uncertainty": uncertainty.to_dict(), "assessment": assessment.to_dict()}
    result["p3_assessment"] = {"verdict": assessment.verdict.value,
                               "reason_codes": [*assessment.reason_codes, *reasons],
                               "implementation_status": "IMPLEMENTED", "qualification": UNRESOLVED}
    result["p3_provenance"] = {"p3_config_hash": protocol.content_hash, "p3_version": protocol.version,
                               "p2_result_hash": digest(p2_payload), "p25_result_hash": digest(p25_payload),
                               "trajectory_sha256": source["provenance"]["trajectory_artifact_sha256"],
                               "scientific_record_hash": digest(result["p3_scientific_record"]),
                               "protocol": protocol.to_dict()}
    event = EvidenceEvent(level="P3", method="quantitative_transport_diagnostic",
                          conditions={"quantitative_transport": qt, "assessment": result["p3_assessment"]},
                          uncertainty=None, source="verified_p2_p25_artifacts",
                          artifact_hash=digest(result["p3_provenance"]), model_or_data_version=protocol.version,
                          timestamp=timestamp)
    # Original evidence_events and provenance are protected byte-for-byte logical inputs.
    result["p3_evidence_events"] = [event.to_dict()]
    return result


def main(argv=None):
    """Execute read-only artifact analysis, writing one new P3 JSON sidecar."""
    import argparse
    import json
    import os
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("p2", "p25", "protocol", "artifact-root", "timestamp", "output"):
        parser.add_argument(f"--{flag}", required=True)
    parser.add_argument("--claim")
    args = parser.parse_args(argv)
    def read(path):
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    try:
        result = analyze_p3(read(args.p2), read(args.p25), P3Protocol.from_dict(read(args.protocol)),
                            artifact_root=args.artifact_root, timestamp=args.timestamp,
                            claim_spec=ClaimSpec.from_dict(read(args.claim)) if args.claim else None)
        data = canonical_bytes(result)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".p3-pending-", dir=output.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, output)
            except FileExistsError:
                if output.read_bytes() != data:
                    raise ExecutionError("output exists with different content", FailureClass.INTEGRITY)
        finally:
            Path(temporary).unlink(missing_ok=True)
    except (ExecutionError, ValueError, TypeError, OSError, FloatingPointError) as exc:
        from rudeus.execution.contracts import classify_failure
        print(json.dumps({"execution_status": "FAILED", "failure_class": classify_failure(exc).value,
                          "scientific_verdict": "UNKNOWN", "reason": str(exc)}))
        return 1
    print(json.dumps({"execution_status": "COMPLETED", "scientific_verdict": result["p3_assessment"]["verdict"],
                      "output_hash": digest(result), "durable_ingestion": "NOT_ATTESTED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
