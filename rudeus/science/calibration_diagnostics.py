"""Truth-linked raw error/bias diagnostics for verified estimator results.

Descriptive only: pairs each successful per-replicate scalar estimate with
the scalar value of its declared ``TruthRecord`` and records raw numerical
discrepancies (signed/absolute error plus a mean-signed-error aggregate).
No thresholds, no bias acceptance, no coverage, no qualification, no
verdicts. Truth survives as hashes and raw values; it is never compared to
make a scientific decision.

Scalar-truth extraction rule (documented, no scientific content): the truth
``value`` mapping must contain exactly one finite numeric entry, which is
used as the scalar truth. Anything else fails closed. No key convention is
assumed, and no relative error is defined — the frozen truth contract
specifies no zero-value convention, so relative error is omitted entirely.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

import numpy as np

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration import (
    CalibrationDatasetManifest,
    CalibrationReplicateManifest,
    CalibrationScope,
    TruthRecord,
)
from rudeus.science.calibration_statistics import _estimator_candidates
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import VALID, validate_dataset
from rudeus.science.contracts import canonical_bytes, digest, require_hash
from rudeus.science.evidence import append_file, inside, integrity_errors, require


ESTIMATOR_NAME = "analyze_trajectory"
ESTIMATOR_MODULE = "rudeus.science.transport"
DIAGNOSTIC_FORMAT = "calibration-error-diagnostic-v1"


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _scalar_truth(truth):
    value = truth.value
    if not isinstance(value, Mapping) or len(value) != 1:
        _fail("calibration truth value must hold exactly one scalar entry")
    scalar = next(iter(value.values()))
    if isinstance(scalar, bool) or not isinstance(scalar, (int, float)):
        _fail("calibration truth value must be numeric")
    if not np.isfinite(scalar):
        _fail("calibration truth value must be finite")
    return float(scalar)


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


def _resolve_truth(store, truth_hash):
    try:
        return store.retrieve(TruthRecord, truth_hash), None
    except ExecutionError:
        try:
            exists = store.path(f"truth_records/{truth_hash}.json").exists()
        except (ValueError, OSError):
            exists = False
        if exists:
            raise
        return None, "unresolved_truth"


def diagnose_calibration_errors(
    *,
    calibration_store: CalibrationStore,
    artifact_root,
    dataset_manifest_hash: str,
    replicate_manifest_hashes,
    species: str,
    estimator_config,
    code_revision: str,
) -> dict:
    """Compute raw estimate-vs-truth discrepancies for one dataset.

    Args:
        replicate_manifest_hashes: explicit mapping of replicate ID to the
            replicate manifest hash to consume. Unmapped declared replicates
            are reported missing, never invented.
        species: scalar species whose estimate is paired with truth.
        estimator_config: exact estimator configuration; only results with
            identical estimator identity and configuration are consumed.
        code_revision: required code revision recorded on every consumed
            estimator result.

    Returns ``{"diagnostic_hash", "dataset_manifest_hash", "n_diagnostics",
    "n_missing_or_failed", "artifact_status": "DIAGNOSED"}``. Any lineage,
    binding, or ambiguity failure raises ``ExecutionError`` fail-closed.
    """
    from pathlib import Path
    root = Path(artifact_root).resolve()
    if not isinstance(species, str) or not species:
        _fail("calibration diagnostic species must be a nonempty string")
    if not isinstance(code_revision, str) or not code_revision:
        _fail("calibration diagnostic code revision must be a nonempty string")
    if not isinstance(estimator_config, dict):
        _fail("calibration diagnostic estimator configuration must be a mapping")
    if not isinstance(replicate_manifest_hashes, dict):
        _fail("calibration diagnostic replicate selection must be a mapping")
    try:
        require_hash(dataset_manifest_hash)
    except ValueError:
        _fail("calibration dataset identity must be a content hash")
    if validate_dataset(calibration_store, dataset_manifest_hash).status != VALID:
        _fail("calibration dataset lineage is not valid")
    try:
        dataset = calibration_store.retrieve(
            CalibrationDatasetManifest, dataset_manifest_hash)
        scope = calibration_store.retrieve(CalibrationScope, dataset.scope_hash)
    except ExecutionError:
        _fail("calibration dataset lineage is not valid")
    try:
        expected_config = canonical_bytes(
            {**estimator_config, "charge_numbers": estimator_config.get("charge_numbers")})
    except (ValueError, TypeError):
        _fail("calibration diagnostic estimator configuration is not canonical")

    declared = sorted(dataset.attempted_replicate_ids)
    if set(replicate_manifest_hashes) - set(declared):
        _fail("calibration diagnostic selection references undeclared replicates")

    entries, truths = {}, {}
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
        if (replicate.replicate_id != replicate_id
                or replicate.dataset_id != dataset.dataset_id
                or replicate.parameter_cell_id not in set(dataset.parameter_cell_ids)):
            _fail("calibration replicate does not belong to the dataset")
        truth, reason = _resolve_truth(calibration_store, replicate.truth_record_hash) \
            if replicate.truth_record_hash is not None else (None, "unresolved_truth")
        if truth is None:
            failed[replicate_id] = reason
            continue
        if (truth.estimand != scope.estimand or truth.units != scope.units
                or truth.truth_type != scope.truth_type):
            _fail("calibration truth is incompatible with the scope")
        candidates, forged = _estimator_candidates(root, manifest_hash)
        if forged:
            _fail("calibration estimator result failed verification")
        if not candidates:
            failed[replicate_id] = "missing_estimator_result"
            continue
        if len({name for name, _ in candidates}) > 1:
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
        estimate = _scalar_estimate(decoded, species)
        truth_value = _scalar_truth(truth)
        signed = estimate - truth_value
        entries[replicate_id] = {
            "estimate": estimate,
            "truth": truth_value,
            "signed_error": signed,
            "absolute_error": abs(signed),
            "estimator_result_hash": candidates[0][0],
            "truth_record_hash": replicate.truth_record_hash,
            "parameter_cell_id": replicate.parameter_cell_id,
        }
        truths[replicate_id] = replicate.truth_record_hash

    signed_errors = [entries[rep]["signed_error"] for rep in sorted(entries)]
    diagnostic = {
        "format": DIAGNOSTIC_FORMAT,
        "dataset_manifest_hash": dataset_manifest_hash,
        "replicate_ids": declared,
        "species": species,
        "estimator": ESTIMATOR_NAME,
        "estimator_module": ESTIMATOR_MODULE,
        "estimator_config": json.loads(expected_config.decode("utf-8")),
        "estimator_config_hash": digest(json.loads(expected_config.decode("utf-8"))),
        "entries": {rep: entries[rep] for rep in sorted(entries)},
        "truth_record_hashes": {rep: truths[rep] for rep in sorted(truths)},
        "missing_ids": {rep: missing[rep] for rep in sorted(missing)},
        "failed_ids": {rep: failed[rep] for rep in sorted(failed)},
        "aggregate": {
            "n": len(signed_errors),
            "mean_signed_error": (float(np.mean(signed_errors))
                                  if signed_errors else None),
        },
        "code_revision": code_revision,
        "numpy_version": np.__version__,
    }
    with integrity_errors():
        data = canonical_bytes(diagnostic)
        identity = digest(diagnostic)
        append_file(inside(root, f"calibration_diagnostics/{identity}.json"), data)
        stored = inside(root, f"calibration_diagnostics/{identity}.json").read_bytes()
        require(stored == data, "stored diagnostic differs from canonical diagnostic")
    return {"diagnostic_hash": identity,
            "dataset_manifest_hash": dataset_manifest_hash,
            "n_diagnostics": len(entries),
            "n_missing_or_failed": len(missing) + len(failed),
            "artifact_status": "DIAGNOSED"}


__all__ = ["ESTIMATOR_NAME", "ESTIMATOR_MODULE", "DIAGNOSTIC_FORMAT",
           "diagnose_calibration_errors"]
