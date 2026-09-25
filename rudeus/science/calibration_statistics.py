"""Replicate-level descriptive statistics over verified estimator results.

Aggregation only: collects successful per-replicate scalar estimates from a
declared calibration dataset and computes deterministic descriptive
statistics (count, mean, sample standard deviation, min, max). Missing or
failed replicates are explicitly recorded, never fabricated, never dropped
silently. No truth comparison, no bias/coverage analysis, no bootstrap, no
qualification, no verdicts. Truth survives only as content hashes.
"""

from __future__ import annotations

import json

import numpy as np

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration import CalibrationDatasetManifest, CalibrationReplicateManifest
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import VALID, validate_dataset
from rudeus.science.contracts import canonical_bytes, digest, require_hash
from rudeus.science.evidence import append_file, inside, integrity_errors, require


ESTIMATOR_NAME = "analyze_trajectory"
ESTIMATOR_MODULE = "rudeus.science.transport"
SUMMARY_FORMAT = "calibration-estimate-summary-v1"


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _scalar_estimate(payload, species):
    try:
        entry = payload["result"]["self_diffusion_by_species"][species]
        value = entry["D_m2_per_s"]
    except (KeyError, TypeError):
        _fail("calibration estimator result has no scalar estimate for the species")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("calibration scalar estimate must be numeric")
    if not np.isfinite(value):
        _fail("calibration scalar estimate must be finite")
    return float(value)


def _estimator_candidates(artifact_root, replicate_hash):
    """Verified estimator records bound to one replicate plus forgery count.

    Returns ``(matches, forged)`` where matches are ``(hash, decoded)`` pairs
    whose bytes verify, and forged counts files claiming the replicate whose
    bytes do not verify. Any forgery fails closed at the call site.
    """
    matches, forged = [], 0
    base = inside(artifact_root, "estimator_results")
    try:
        names = sorted(path.name for path in base.iterdir() if path.is_file())
    except OSError:
        return matches, forged
    for name in names:
        try:
            data = (base / name).read_bytes()
            decoded = json.loads(data)
        except (OSError, ValueError):
            continue
        if not isinstance(decoded, dict):
            continue
        if decoded.get("replicate_manifest_hash") != replicate_hash:
            continue
        try:
            require(digest(decoded) == name.removesuffix(".json"),
                    "estimator result filename does not match content")
            require(canonical_bytes(decoded) == data,
                    "estimator result bytes are not canonical")
        except ExecutionError:
            forged += 1
            continue
        matches.append((name.removesuffix(".json"), decoded))
    return matches, forged


def summarize_calibration_estimates(
    *,
    calibration_store: CalibrationStore,
    artifact_root,
    dataset_manifest_hash: str,
    replicate_manifest_hashes,
    species: str,
    estimator_config,
    code_revision: str,
) -> dict:
    """Summarize verified per-replicate scalar estimates for one dataset.

    Args:
        replicate_manifest_hashes: explicit mapping of replicate ID to the
            replicate manifest hash to consume. Declared replicates absent
            from the mapping are reported missing, never invented.
        species: scalar species whose ``D_m2_per_s`` is summarized.
        estimator_config: exact estimator configuration; only results with
            identical estimator identity and configuration are consumed.
        code_revision: required code revision recorded on every consumed
            estimator result.

    Returns ``{"summary_hash", "dataset_manifest_hash", "n_successful",
    "n_missing_or_failed", "artifact_status": "SUMMARIZED"}``. Any lineage,
    binding, or ambiguity failure raises ``ExecutionError`` fail-closed.
    """
    from pathlib import Path
    root = Path(artifact_root).resolve()
    if not isinstance(species, str) or not species:
        _fail("calibration summary species must be a nonempty string")
    if not isinstance(code_revision, str) or not code_revision:
        _fail("calibration summary code revision must be a nonempty string")
    if not isinstance(estimator_config, dict):
        _fail("calibration summary estimator configuration must be a mapping")
    if not isinstance(replicate_manifest_hashes, dict):
        _fail("calibration summary replicate selection must be a mapping")
    try:
        require_hash(dataset_manifest_hash)
    except ValueError:
        _fail("calibration dataset identity must be a content hash")
    if validate_dataset(calibration_store, dataset_manifest_hash).status != VALID:
        _fail("calibration dataset lineage is not valid")
    try:
        dataset = calibration_store.retrieve(
            CalibrationDatasetManifest, dataset_manifest_hash)
    except ExecutionError:
        _fail("calibration dataset lineage is not valid")

    declared = sorted(dataset.attempted_replicate_ids)
    if set(replicate_manifest_hashes) - set(declared):
        _fail("calibration summary selection references undeclared replicates")
    try:
        expected_config = canonical_bytes(
            {**estimator_config, "charge_numbers": estimator_config.get("charge_numbers")})
    except (ValueError, TypeError):
        _fail("calibration summary estimator configuration is not canonical")

    values, sources, truths, cells = [], {}, {}, {}
    missing, failed = {}, {}
    for replicate_id in declared:
        if replicate_id not in replicate_manifest_hashes:
            missing[replicate_id] = "undeclared_selection"
            continue
        manifest_hash = replicate_manifest_hashes[replicate_id]
        try:
            require_hash(manifest_hash)
            replicate = calibration_store.retrieve(
                CalibrationReplicateManifest, manifest_hash)
        except (ValueError, ExecutionError):
            missing[replicate_id] = "unresolved_manifest"
            continue
        if replicate.replicate_id != replicate_id or replicate.dataset_id != dataset.dataset_id:
            _fail("calibration replicate does not belong to the dataset")
        candidates, forged = _estimator_candidates(root, manifest_hash)
        if forged:
            _fail("calibration estimator result failed verification")
        if not candidates:
            failed[replicate_id] = "missing_estimator_result"
            continue
        distinct = {name for name, _ in candidates}
        if len(distinct) > 1:
            _fail("calibration replicate has ambiguous estimator results")
        _, decoded = candidates[0]
        if (decoded.get("estimator") != ESTIMATOR_NAME
                or decoded.get("estimator_module") != ESTIMATOR_MODULE
                or decoded.get("code_revision") != code_revision
                or decoded.get("numpy_version") != np.__version__
                or canonical_bytes(decoded.get("estimator_config")) != expected_config
                or decoded.get("trajectory_artifact_hash")
                != replicate.trajectory_artifact_hash):
            _fail("calibration estimator result does not match the requested identity")
        try:
            values.append(_scalar_estimate(decoded, species))
        except ExecutionError:
            failed[replicate_id] = "invalid_estimator_result"
            continue
        sources[replicate_id] = distinct.pop()
        truths[replicate_id] = replicate.truth_record_hash
        cells[replicate_id] = replicate.parameter_cell_id

    count = len(values)
    if count == 0:
        statistics = {"n": 0, "mean": None, "std": None, "min": None, "max": None}
    else:
        sample = np.asarray(values, dtype=float)
        statistics = {
            "n": count,
            "mean": float(np.mean(sample)),
            "std": float(np.std(sample, ddof=1)) if count >= 2 else None,
            "min": float(np.min(sample)),
            "max": float(np.max(sample)),
        }
    estimator_config_hash = digest(json.loads(expected_config.decode("utf-8")))
    summary = {
        "format": SUMMARY_FORMAT,
        "dataset_manifest_hash": dataset_manifest_hash,
        "replicate_ids": declared,
        "species": species,
        "estimator": ESTIMATOR_NAME,
        "estimator_module": ESTIMATOR_MODULE,
        "estimator_config": json.loads(expected_config.decode("utf-8")),
        "estimator_config_hash": estimator_config_hash,
        "source_estimator_result_hashes": {rep: sources[rep] for rep in sorted(sources)},
        "truth_record_hashes": {rep: truths[rep] for rep in sorted(truths)},
        "parameter_cells": {rep: cells[rep] for rep in sorted(cells)},
        "successful_ids": sorted(sources),
        "missing_ids": {rep: missing[rep] for rep in sorted(missing)},
        "failed_ids": {rep: failed[rep] for rep in sorted(failed)},
        "statistics": statistics,
        "code_revision": code_revision,
        "numpy_version": np.__version__,
    }
    with integrity_errors():
        data = canonical_bytes(summary)
        identity = digest(summary)
        append_file(inside(root, f"estimate_summaries/{identity}.json"), data)
        stored = inside(root, f"estimate_summaries/{identity}.json").read_bytes()
        require(stored == data, "stored summary differs from canonical summary")
    return {"summary_hash": identity,
            "dataset_manifest_hash": dataset_manifest_hash,
            "n_successful": count,
            "n_missing_or_failed": len(missing) + len(failed),
            "artifact_status": "SUMMARIZED"}


__all__ = ["ESTIMATOR_NAME", "ESTIMATOR_MODULE", "SUMMARY_FORMAT",
           "summarize_calibration_estimates"]
