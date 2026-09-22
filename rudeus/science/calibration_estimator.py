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


__all__ = ["ESTIMATOR_NAME", "ESTIMATOR_MODULE", "ESTIMATOR_RESULT_FORMAT",
           "estimate_calibration_replicate"]
