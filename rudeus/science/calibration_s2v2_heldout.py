"""Pure per-replicate S2 v2 HELDOUT evaluation records.

This module records individual errors and prediction intervals only. It does
not aggregate coverage, evaluate acceptance criteria, or emit a verdict.
"""
from __future__ import annotations

import math

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration_s2v2 import S2V2_METHOD_HASH
from rudeus.science.calibration_s2v2_populations import (
    S2V2_HELDOUT_HASH, S2V2_HELDOUT_SEEDS,
)
from rudeus.science.contracts import require_hash

EVALUATION_FORMAT = "s2v2-heldout-evaluation-v2"
Q_HAT_UNITS = "m2/s"


def _reject(message):
    raise ExecutionError(message, "UNSUPPORTED_INPUT")


def _hash(value, name):
    try:
        require_hash(value)
    except (ValueError, TypeError) as exc:
        _reject(f"HELDOUT evaluation {name} must be a content hash: {exc}")


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value):
        _reject(f"HELDOUT evaluation {name} must be finite numeric")


def build_s2v2_heldout_evaluation(*, replicate_id, replicate_manifest_hash,
                                  estimator_result_hash, truth_record_hash,
                                  estimate_D, truth_D,
                                  pre_heldout_acknowledgment_hash,
                                  calibration_package_hash, q_hat,
                                  code_revision):
    """Build one frozen-ID evaluation with closed, un-clipped bounds."""
    if replicate_id not in S2V2_HELDOUT_SEEDS:
        _reject(f"replicate {replicate_id!r} is not frozen HELDOUT evidence")
    for value, name in (
            (replicate_manifest_hash, "replicate_manifest_hash"),
            (estimator_result_hash, "estimator_result_hash"),
            (truth_record_hash, "truth_record_hash"),
            (pre_heldout_acknowledgment_hash,
             "pre_heldout_acknowledgment_hash"),
            (calibration_package_hash, "calibration_package_hash")):
        _hash(value, name)
    if not isinstance(code_revision, str) or not code_revision:
        _reject("HELDOUT evaluation code_revision must be explicit")
    _finite(estimate_D, "estimate_D")
    _finite(truth_D, "truth_D")
    _finite(q_hat, "q_hat")
    if q_hat < 0:
        _reject("HELDOUT evaluation q_hat must be nonnegative")
    lower, upper = estimate_D - q_hat, estimate_D + q_hat
    signed = estimate_D - truth_D
    if not all(math.isfinite(value) for value in (lower, upper, signed)):
        _reject("HELDOUT evaluation derived values must be finite")
    return {
        "format": EVALUATION_FORMAT,
        "replicate_id": replicate_id,
        "replicate_manifest_hash": replicate_manifest_hash,
        "estimator_result_hash": estimator_result_hash,
        "truth_record_hash": truth_record_hash,
        "pre_heldout_acknowledgment_hash": pre_heldout_acknowledgment_hash,
        "calibration_package_hash": calibration_package_hash,
        "method_hash": S2V2_METHOD_HASH,
        "population_hash": S2V2_HELDOUT_HASH,
        "q_hat": float(q_hat),
        "q_hat_units": Q_HAT_UNITS,
        "interval_lower": float(lower),
        "interval_upper": float(upper),
        "covered": bool(lower <= truth_D <= upper),
        "signed_error": float(signed),
        "absolute_error": float(abs(signed)),
        "units": Q_HAT_UNITS,
        "code_revision": code_revision,
    }


__all__ = ["EVALUATION_FORMAT", "Q_HAT_UNITS",
           "build_s2v2_heldout_evaluation"]
