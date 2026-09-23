"""Estimator integration for one materialized calibration replicate.

Adapter only: resolves a stored replicate through its verified
artifact/provenance chain, runs the existing P3 trajectory/transport
estimator on the verified bytes, and persists a deterministic,
provenance-bound estimator result. No truth comparison, no bias/coverage
analysis, no qualification, no verdicts.

Calibration trajectories are unwrapped Cartesian (`synthetic.brownian`
output); no PBC reconstruction applies. The estimator's own input
validation is the schedule/shape/cell gate — nothing is repaired here.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from rudeus.execution.contracts import (
    ArtifactManifest,
    ExecutionAttempt,
    ExecutionError,
    classify_failure,
)
from rudeus.science.calibration import CalibrationReplicateManifest
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.contracts import canonical_bytes, digest, require_hash
from rudeus.science.evidence import append_file, inside, integrity_errors, require
from rudeus.science.statistics import ResamplingSpec, matched_origin_block_bootstrap
from rudeus.science.transport import analyze_trajectory


ESTIMATOR_NAME = "analyze_trajectory"
ESTIMATOR_MODULE = "rudeus.science.transport"
ESTIMATOR_RESULT_FORMAT = "calibration-estimator-result-v1"
TRAJECTORY_FORMAT = "calibration-trajectory-v1"

_CONFIG_KEYS = (
    "lag_steps",
    "fit_window_ps",
    "selected_species",
    "volume_A3",
    "temperature_K",
    "reference_frame",
)


def _fail(message, failure_class="INTEGRITY"):
    raise ExecutionError(message, failure_class)


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _estimator_config(config):
    if not isinstance(config, dict):
        _fail("calibration estimator configuration must be a mapping")
    for key in _CONFIG_KEYS:
        if key not in config:
            _fail(f"calibration estimator configuration is missing {key}")
    lag_steps = config["lag_steps"]
    if (not isinstance(lag_steps, (list, tuple)) or len(lag_steps) < 2
            or any(isinstance(v, bool) or not isinstance(v, int) or v < 1
                   for v in lag_steps)
            or any(b <= a for a, b in zip(lag_steps, lag_steps[1:]))):
        _fail("calibration estimator lag steps must be increasing positive integers")
    window = config["fit_window_ps"]
    if (not isinstance(window, (list, tuple)) or len(window) != 2
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                       for v in window)
            or not 0 <= window[0] < window[1]):
        _fail("calibration estimator fit window must be explicit physical bounds")
    selected = config["selected_species"]
    if (not isinstance(selected, (list, tuple)) or not selected
            or len(set(selected)) != len(selected)
            or any(not isinstance(s, str) or not s for s in selected)):
        _fail("calibration estimator species selection must be nonempty and unique")
    for key in ("volume_A3", "temperature_K"):
        number = config[key]
        if (isinstance(number, bool) or not isinstance(number, (int, float))
                or not np.isfinite(number) or number <= 0):
            _fail(f"calibration estimator {key} must be positive and finite")
    _require_nonempty_str(config["reference_frame"], "reference_frame")
    charge_numbers = config.get("charge_numbers")
    if charge_numbers is not None and (
            not isinstance(charge_numbers, dict) or set(charge_numbers) != set(selected)):
        _fail("calibration estimator charge map must exactly cover selected species")
    return {"lag_steps": [int(v) for v in lag_steps],
            "fit_window_ps": (float(window[0]), float(window[1])),
            "selected_species": [str(s) for s in selected],
            "volume_A3": float(config["volume_A3"]),
            "temperature_K": float(config["temperature_K"]),
            "reference_frame": str(config["reference_frame"]),
            "charge_numbers": ({str(k): float(v) for k, v in charge_numbers.items()}
                               if charge_numbers is not None else None)}


def _require_nonempty_str(value, name):
    if not isinstance(value, str) or not value:
        _fail(f"calibration estimator {name} must be a nonempty string")


def _resolve_manifest(artifact_root, replicate):
    if replicate.trajectory_artifact_hash is None:
        _fail("calibration replicate has no trajectory artifact")
    if replicate.execution_attempt_hash is None:
        _fail("calibration replicate has no execution attempt")
    try:
        attempt = ExecutionAttempt.from_dict(json.loads(
            inside(artifact_root, f"attempts/{replicate.execution_attempt_hash}.json")
            .read_bytes()))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        _fail(f"calibration execution attempt is unavailable: {type(exc).__name__}")
    outputs = list(attempt.output_manifest.values())
    if len(outputs) != 1:
        _fail("calibration execution attempt must bind exactly one trajectory output")
    try:
        manifest = ArtifactManifest.from_dict(json.loads(
            inside(artifact_root, f"trajectory_manifests/{outputs[0]}.json").read_bytes()))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        _fail(f"calibration trajectory manifest is unavailable: {type(exc).__name__}")
    if manifest.logical_hash != replicate.trajectory_artifact_hash:
        _fail("calibration trajectory manifest does not match the replicate")
    if manifest.producer_attempt != attempt.attempt_id:
        _fail("calibration trajectory manifest does not match the attempt")
    return attempt, manifest


def _verified_trajectory(artifact_root, manifest):
    if manifest.format != "json":
        _fail("calibration trajectory artifact has an unsupported format",
              "UNSUPPORTED_INPUT")
    try:
        data = inside(artifact_root, manifest.durable_locator).read_bytes()
    except (OSError, ValueError) as exc:
        _fail(f"calibration trajectory bytes are unavailable: {type(exc).__name__}")
    if len(data) != manifest.size_bytes:
        _fail("calibration trajectory size mismatch")
    if hashlib.sha256(data).hexdigest() != manifest.raw_hash:
        _fail("calibration trajectory raw hash mismatch")
    try:
        decoded = json.loads(data)
    except ValueError as exc:
        _fail(f"calibration trajectory bytes are not JSON: {exc}")
    if not isinstance(decoded, dict) or decoded.get("format") != TRAJECTORY_FORMAT:
        _fail("calibration trajectory has an unsupported format", "UNSUPPORTED_INPUT")
    try:
        require(digest(decoded) == manifest.logical_hash,
                "calibration trajectory logical hash mismatch")
    except ExecutionError:
        _fail("calibration trajectory logical hash mismatch")
    return decoded


def _trajectory_arrays(trajectory):
    try:
        positions = np.asarray(trajectory["positions"], dtype=float)
        species = list(trajectory["species"])
        frame_steps = [int(v) for v in trajectory["frame_steps"]]
        dt_ps = trajectory["dt_ps"]
    except (KeyError, TypeError, ValueError):
        _fail("calibration trajectory object is malformed")
    if (isinstance(dt_ps, bool) or not isinstance(dt_ps, (int, float))
            or not np.isfinite(dt_ps) or dt_ps <= 0):
        _fail("calibration trajectory timestep must be positive and finite")
    return positions, species, frame_steps, dt_ps


def estimate_calibration_replicate(
    *,
    calibration_store: CalibrationStore,
    artifact_root,
    replicate_manifest_hash: str,
    estimator_config,
    code_revision: str,
) -> dict:
    """Run the existing P3 estimator on one verified calibration trajectory.

    Returns ``{"estimator_result_hash", "replicate_manifest_hash",
    "trajectory_artifact_hash"}``. Every failure raises ``ExecutionError``
    fail-closed; no estimator result file is created on failure and no
    scientific verdict is ever emitted.
    """
    from pathlib import Path
    root = Path(artifact_root).resolve()
    _require_nonempty_str(code_revision, "code_revision")
    config = _estimator_config(estimator_config)
    try:
        require_hash(replicate_manifest_hash)
    except ValueError:
        _fail("calibration replicate identity must be a content hash")
    try:
        replicate = calibration_store.retrieve(
            CalibrationReplicateManifest, replicate_manifest_hash)
    except ExecutionError:
        _fail("calibration replicate manifest is unavailable")
    attempt, manifest = _resolve_manifest(root, replicate)
    trajectory = _verified_trajectory(root, manifest)
    positions, species, frame_steps, dt_ps = _trajectory_arrays(trajectory)
    try:
        estimate = analyze_trajectory(
            positions, species, frame_steps, float(dt_ps) * 1000.0,
            config["lag_steps"], selected_species=config["selected_species"],
            fit_window_ps=config["fit_window_ps"], volume_A3=config["volume_A3"],
            temperature_K=config["temperature_K"],
            reference_frame=config["reference_frame"],
            charge_numbers=config["charge_numbers"])
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        _fail(str(exc), "NUMERICAL")
    except (ValueError, TypeError) as exc:
        _fail(str(exc), "UNSUPPORTED_INPUT")
    except Exception as exc:
        raise ExecutionError(str(exc), classify_failure(exc)) from exc
    result = {
        "format": ESTIMATOR_RESULT_FORMAT,
        "replicate_id": replicate.replicate_id,
        "replicate_manifest_hash": replicate.content_hash,
        "trajectory_artifact_hash": manifest.logical_hash,
        "trajectory_manifest_hash": manifest.content_hash,
        "truth_record_hash": replicate.truth_record_hash,
        "estimator": ESTIMATOR_NAME,
        "estimator_module": ESTIMATOR_MODULE,
        "estimator_config": {**config, "charge_numbers": config["charge_numbers"]},
        "code_revision": code_revision,
        "numpy_version": np.__version__,
        "result": _jsonable(estimate),
    }
    with integrity_errors():
        data = canonical_bytes(result)
        identity = digest(result)
        append_file(inside(root, f"estimator_results/{identity}.json"), data)
        stored = inside(root, f"estimator_results/{identity}.json").read_bytes()
        require(stored == data, "stored estimator result differs from canonical result")
    return {"estimator_result_hash": identity,
            "replicate_manifest_hash": replicate.content_hash,
            "trajectory_artifact_hash": manifest.logical_hash}


INTERVAL_RESULT_FORMAT = "calibration-interval-v1"
COVERAGE_SUMMARY_FORMAT = "calibration-coverage-summary-v1"


def estimate_interval_for_replicate(
    *,
    calibration_store: CalibrationStore,
    artifact_root,
    estimator_result_hash: str,
    resampling_spec,
    code_revision: str,
) -> dict:
    """Run the existing V2 bootstrap on one verified estimator result.

    Resolves the estimator result, its replicate manifest, and the verified
    trajectory through the existing provenance chain, reruns the point
    estimator to recover the origin population hash, then runs the existing
    ``matched_origin_block_bootstrap`` with the caller-supplied frozen
    ``ResamplingSpec``. Persists a deterministic interval record bound to
    the estimator result. No thresholds, no qualification, no verdicts.
    """
    from pathlib import Path
    root = Path(artifact_root).resolve()
    _require_nonempty_str(code_revision, "code_revision")
    if isinstance(resampling_spec, dict):
        try:
            spec = ResamplingSpec.from_dict(resampling_spec)
        except (ValueError, TypeError, KeyError) as exc:
            _fail(f"calibration resampling spec is invalid: {exc}")
    elif isinstance(resampling_spec, ResamplingSpec):
        spec = resampling_spec
    else:
        _fail("calibration resampling spec must be a ResamplingSpec mapping")
    try:
        require_hash(estimator_result_hash)
    except ValueError:
        _fail("calibration estimator result identity must be a content hash")
    try:
        data = inside(root, f"estimator_results/{estimator_result_hash}.json").read_bytes()
        record = json.loads(data)
    except (OSError, ValueError) as exc:
        _fail(f"calibration estimator result is unavailable: {type(exc).__name__}")
    try:
        require(digest(record) == estimator_result_hash,
                "calibration estimator result failed verification")
        require(canonical_bytes(record) == data,
                "calibration estimator result failed verification")
    except ExecutionError:
        _fail("calibration estimator result failed verification")
    try:
        replicate = calibration_store.retrieve(
            CalibrationReplicateManifest, record["replicate_manifest_hash"])
    except (KeyError, ExecutionError):
        _fail("calibration replicate manifest is unavailable")
    if record.get("trajectory_artifact_hash") != replicate.trajectory_artifact_hash:
        _fail("calibration estimator result does not match the replicate")
    if record.get("code_revision") != code_revision:
        _fail("calibration estimator result code revision mismatch")
    attempt, manifest = _resolve_manifest(root, replicate)
    trajectory = _verified_trajectory(root, manifest)
    positions, species, frame_steps, dt_ps = _trajectory_arrays(trajectory)
    stored_config = record.get("estimator_config")
    if not isinstance(stored_config, dict):
        _fail("calibration estimator result has no estimator configuration")
    try:
        point = analyze_trajectory(
            positions, species, frame_steps, float(dt_ps) * 1000.0,
            stored_config["lag_steps"], selected_species=stored_config["selected_species"],
            fit_window_ps=stored_config["fit_window_ps"], volume_A3=stored_config["volume_A3"],
            temperature_K=stored_config["temperature_K"],
            reference_frame=stored_config["reference_frame"],
            charge_numbers=stored_config.get("charge_numbers"))
        population_hash = point["self_diffusion_by_species"][
            stored_config["selected_species"][0]]["origin_population_hash"]
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        _fail(str(exc), "NUMERICAL")
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        _fail(str(exc), "UNSUPPORTED_INPUT")
    try:
        resampled = matched_origin_block_bootstrap(
            positions, species, frame_steps, float(dt_ps) * 1000.0,
            stored_config["lag_steps"], spec=spec,
            expected_population_hash=population_hash,
            selected_species=stored_config["selected_species"],
            fit_window_ps=stored_config["fit_window_ps"], volume_A3=stored_config["volume_A3"],
            temperature_K=stored_config["temperature_K"],
            reference_frame=stored_config["reference_frame"],
            charge_numbers=stored_config.get("charge_numbers"))
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        _fail(str(exc), "NUMERICAL")
    except (ValueError, TypeError) as exc:
        _fail(str(exc), "UNSUPPORTED_INPUT")
    except Exception as exc:
        raise ExecutionError(str(exc), classify_failure(exc)) from exc
    result = {
        "format": INTERVAL_RESULT_FORMAT,
        "estimator_result_hash": estimator_result_hash,
        "replicate_manifest_hash": replicate.content_hash,
        "trajectory_artifact_hash": manifest.logical_hash,
        "resampling_spec_hash": spec.content_hash,
        "resampling_spec": spec.to_dict(),
        "seed": spec.seed,
        "numpy_version": np.__version__,
        "intervals": _jsonable(resampled["intervals"]),
        "failed_draws": _jsonable(resampled["failed_draws"]),
        "code_revision": code_revision,
    }
    with integrity_errors():
        data = canonical_bytes(result)
        identity = digest(result)
        append_file(inside(root, f"calibration_intervals/{identity}.json"), data)
        stored = inside(root, f"calibration_intervals/{identity}.json").read_bytes()
        require(stored == data, "stored interval record differs from canonical record")
    return {"interval_hash": identity,
            "estimator_result_hash": estimator_result_hash,
            "replicate_manifest_hash": replicate.content_hash,
            "trajectory_artifact_hash": manifest.logical_hash}


def persist_coverage_summary(
    *,
    artifact_root,
    coverage,
    s2_procedure_hash: str,
    s2_procedure,
    dataset_manifest_hash: str,
    replicate_ids,
    seeds,
    estimator_identity,
    resampling_identity,
    truth,
) -> dict:
    """Persist a ``coverage_experiment`` output as DEV evidence (descriptive only).

    Binds the existing harness output to the frozen S2 procedure, dataset,
    replicate/seed inventory, estimator/resampling identities, and truth.
    The persisted record describes observed coverage; it never qualifies it.
    """
    from pathlib import Path
    root = Path(artifact_root).resolve()
    if not isinstance(coverage, dict) or not isinstance(coverage.get("records"), list):
        _fail("calibration coverage result must map to per-seed records")
    for name, value in (("s2_procedure_hash", s2_procedure_hash),
                        ("dataset_manifest_hash", dataset_manifest_hash)):
        try:
            require_hash(value)
        except ValueError:
            _fail(f"calibration coverage {name} must be a content hash")
    if not isinstance(s2_procedure, dict):
        _fail("calibration S2 procedure must be a mapping")
    if (not isinstance(replicate_ids, (list, tuple)) or not replicate_ids
            or len(set(replicate_ids)) != len(replicate_ids)
            or any(not isinstance(rep, str) or not rep for rep in replicate_ids)):
        _fail("calibration coverage replicate inventory must be nonempty and unique")
    if not isinstance(seeds, dict) or set(seeds) != set(replicate_ids):
        _fail("calibration coverage seeds must cover exactly the replicate inventory")
    for seed in seeds.values():
        if isinstance(seed, bool) or not isinstance(seed, int):
            _fail("calibration coverage seeds must be integers")
    if not isinstance(estimator_identity, dict):
        _fail("calibration estimator identity must be a mapping")
    for key in ("name", "module", "config_hash"):
        if key not in estimator_identity:
            _fail(f"calibration estimator identity is missing {key}")
    try:
        require_hash(estimator_identity["config_hash"])
    except ValueError:
        _fail("calibration estimator config identity must be a content hash")
    if not isinstance(resampling_identity, dict):
        _fail("calibration resampling identity must be a mapping")
    for key in ("method", "spec_hash"):
        if key not in resampling_identity:
            _fail("calibration resampling identity is missing {key}")
    try:
        require_hash(resampling_identity["spec_hash"])
    except ValueError:
        _fail("calibration resampling spec identity must be a content hash")
    if not isinstance(truth, dict) or "value" not in truth:
        _fail("calibration coverage truth must carry a value")
    if truth.get("record_hash") is not None:
        try:
            require_hash(truth["record_hash"])
        except ValueError:
            _fail("calibration truth record identity must be a content hash")
    payload = {
        "format": COVERAGE_SUMMARY_FORMAT,
        "s2_procedure_hash": s2_procedure_hash,
        "s2_procedure": dict(s2_procedure),
        "dataset_manifest_hash": dataset_manifest_hash,
        "replicate_ids": sorted(replicate_ids),
        "seeds": {rep: seeds[rep] for rep in sorted(replicate_ids)},
        "estimator_identity": dict(estimator_identity),
        "resampling_identity": dict(resampling_identity),
        "truth": dict(truth),
        "coverage": _jsonable(coverage),
    }
    with integrity_errors():
        data = canonical_bytes(payload)
        identity = digest(payload)
        append_file(inside(root, f"calibration_coverage/{identity}.json"), data)
        stored = inside(root, f"calibration_coverage/{identity}.json").read_bytes()
        require(stored == data, "stored coverage summary differs from canonical summary")
    return {"coverage_hash": identity,
            "dataset_manifest_hash": dataset_manifest_hash,
            "s2_procedure_hash": s2_procedure_hash}


__all__ = ["ESTIMATOR_NAME", "ESTIMATOR_MODULE", "ESTIMATOR_RESULT_FORMAT",
           "INTERVAL_RESULT_FORMAT", "COVERAGE_SUMMARY_FORMAT",
           "estimate_calibration_replicate", "estimate_interval_for_replicate",
           "persist_coverage_summary"]
