"""S2 v2 DEV-B pure builders: evaluation records + descriptive summary.

Pure record-construction logic over explicitly supplied inputs. No
filesystem access, no store access, no execution, no DEV-B run, no
HELD_OUT access. The conformal quantile q_hat is always a caller-supplied
frozen value (learned from DEV-A, never recomputed here); builders bind
it, never derive it. No verdict, tolerance comparison, or qualification
state is produced anywhere: descriptive statistics only.

Stage boundary: the DEV-B runner, persistence, owner acknowledgment, and
HELD_OUT gate arrive in later tasks.
"""

from __future__ import annotations

import math

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration_s2v2 import (
    S2V2_CRITERION_HASH,
    S2V2_METHOD_HASH,
)
from rudeus.science.calibration_s2v2_populations import (
    S2V2_DEV_B_HASH,
    S2V2_DEV_B_SEEDS,
    S2V2_HELDOUT_HASH,
    S2V2_POPULATIONS_HASH,
)
from rudeus.science.contracts import digest, require_hash
from rudeus.science.statistics import binomial_interval

EVALUATION_FORMAT = "s2v2-devb-evaluation-v1"
SUMMARY_FORMAT = "s2v2-devb-summary-v1"
SUMMARY_STATUS = "DESCRIPTIVE-NON-QUALIFICATION"
Q_HAT_UNITS = "m2/s"
SUMMARY_COVERAGE_CONFIDENCE = 0.90


def _reject(message):
    raise ExecutionError(message, "UNSUPPORTED_INPUT")


def _require_hash(value, name):
    try:
        require_hash(value)
    except (ValueError, TypeError) as exc:
        _reject(f"DEV-B evaluation {name} must be a content hash: {exc}")


def _require_code_revision(value):
    if not isinstance(value, str) or not value:
        _reject("DEV-B evaluation code_revision must be a nonempty string")


def _require_finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _reject(f"DEV-B evaluation {name} must be numeric")
    if not math.isfinite(value):
        _reject(f"DEV-B evaluation {name} must be finite")


def _require_q_hat(value):
    _require_finite_number(value, "q_hat")
    if value < 0:
        _reject("DEV-B evaluation q_hat must be nonnegative")


def build_s2v2_devb_evaluation(*, replicate_id, replicate_manifest_hash,
                               estimator_result_hash, truth_record_hash,
                               estimate_D, truth_D, calibration_package_hash,
                               q_hat, method_hash=S2V2_METHOD_HASH,
                               population_hash=S2V2_DEV_B_HASH,
                               code_revision):
    """Build one versioned DEV-B evaluation record (pure).

    Applies the frozen interval [D_hat - q_hat, D_hat + q_hat] with CLOSED
    bounds (equality counts as covered) and records signed/absolute error.
    Lower bounds are never clipped: negative values are valid. Only DEV-B
    replicate IDs are accepted. No verdict is produced.
    """
    if replicate_id not in S2V2_DEV_B_SEEDS:
        _reject(f"DEV-B evaluation replicate {replicate_id!r} is not DEV-B evidence")
    if method_hash != S2V2_METHOD_HASH:
        _reject("DEV-B evaluation method hash does not match the frozen v2 method")
    if population_hash != S2V2_DEV_B_HASH:
        _reject("DEV-B evaluation population hash does not match frozen DEV-B")
    _require_hash(replicate_manifest_hash, "replicate_manifest_hash")
    _require_hash(estimator_result_hash, "estimator_result_hash")
    _require_hash(truth_record_hash, "truth_record_hash")
    _require_hash(calibration_package_hash, "calibration_package_hash")
    _require_code_revision(code_revision)
    _require_finite_number(estimate_D, "estimate_D")
    _require_finite_number(truth_D, "truth_D")
    _require_q_hat(q_hat)
    signed_error = estimate_D - truth_D
    lower = estimate_D - q_hat
    upper = estimate_D + q_hat
    if not math.isfinite(signed_error) or not math.isfinite(lower) \
            or not math.isfinite(upper):
        _reject("DEV-B evaluation quantities are not finite")
    return {
        "format": EVALUATION_FORMAT,
        "replicate_id": replicate_id,
        "replicate_manifest_hash": replicate_manifest_hash,
        "estimator_result_hash": estimator_result_hash,
        "truth_record_hash": truth_record_hash,
        "calibration_package_hash": calibration_package_hash,
        "method_hash": S2V2_METHOD_HASH,
        "population_hash": S2V2_DEV_B_HASH,
        "q_hat": float(q_hat),
        "q_hat_units": Q_HAT_UNITS,
        "interval_lower": float(lower),
        "interval_upper": float(upper),
        "covered": bool(truth_D >= lower and truth_D <= upper),
        "signed_error": float(signed_error),
        "absolute_error": float(abs(signed_error)),
        "units": Q_HAT_UNITS,
        "code_revision": code_revision,
    }


def _require_evaluation_record(record):
    for key in ("replicate_id", "replicate_manifest_hash", "estimator_result_hash",
                "truth_record_hash", "calibration_package_hash", "method_hash",
                "population_hash", "q_hat", "interval_lower", "interval_upper",
                "covered", "signed_error", "absolute_error", "units",
                "code_revision"):
        if key not in record:
            _reject(f"DEV-B evaluation record is missing {key}")
    if record["method_hash"] != S2V2_METHOD_HASH:
        _reject("DEV-B evaluation record binds a foreign method")
    if record["population_hash"] != S2V2_DEV_B_HASH:
        _reject("DEV-B evaluation record binds a foreign population")
    if record["units"] != Q_HAT_UNITS:
        _reject("DEV-B evaluation record uses foreign units")
    _require_q_hat(record["q_hat"])
    _require_finite_number(record["interval_lower"], "interval_lower")
    _require_finite_number(record["interval_upper"], "interval_upper")
    _require_finite_number(record["signed_error"], "signed_error")
    _require_finite_number(record["absolute_error"], "absolute_error")
    if not isinstance(record["covered"], bool):
        _reject("DEV-B evaluation record covered flag is not boolean")


def build_s2v2_devb_summary(*, evaluation_records, pre_heldout_identity_hash,
                            calibration_package_hash, q_hat, code_revision,
                            method_hash=S2V2_METHOD_HASH,
                            criterion_hash=S2V2_CRITERION_HASH):
    """Build the deterministic DEV-B descriptive summary (pure).

    Requires exactly the 114 frozen DEV-B evaluation records with uniform
    package/method/q_hat/revision bindings. Recomputes every aggregate from
    the records; caller statistics are never trusted. Canonical DEV-B ID
    order inside, so input permutation cannot change identity. Descriptive
    only: no tolerance comparison, no verdict.
    """
    _require_hash(pre_heldout_identity_hash, "pre_heldout_identity_hash")
    _require_hash(calibration_package_hash, "calibration_package_hash")
    _require_code_revision(code_revision)
    if method_hash != S2V2_METHOD_HASH:
        _reject("DEV-B summary method hash is not the frozen v2 method")
    if criterion_hash != S2V2_CRITERION_HASH:
        _reject("DEV-B summary criterion hash is not frozen")
    _require_q_hat(q_hat)
    records = list(evaluation_records)
    if len(records) != len(S2V2_DEV_B_SEEDS):
        _reject(f"DEV-B summary requires 114 evaluations, got {len(records)}")
    seen = [record.get("replicate_id") for record in records
            if isinstance(record, dict)]
    if len(seen) != len(records) or len(set(seen)) != len(records):
        _reject("DEV-B summary found duplicate or malformed replicate IDs")
    if set(seen) != set(S2V2_DEV_B_SEEDS):
        _reject("DEV-B summary IDs do not equal the frozen DEV-B set")
    for record in records:
        _require_evaluation_record(record)
        if record["calibration_package_hash"] != calibration_package_hash:
            _reject("DEV-B summary found a foreign calibration package binding")
        if record["q_hat"] != q_hat:
            _reject("DEV-B summary found a foreign q_hat binding")
        if record["code_revision"] != code_revision:
            _reject("DEV-B summary found a foreign code revision binding")
    ordered = sorted(records, key=lambda record: record["replicate_id"])
    covered = sum(1 for record in ordered if record["covered"])
    missed = len(ordered) - covered
    interval = binomial_interval(covered, len(ordered), SUMMARY_COVERAGE_CONFIDENCE)
    signed = [float(record["signed_error"]) for record in ordered]
    absolute = [float(record["absolute_error"]) for record in ordered]
    mean_signed = sum(signed) / len(signed)
    return {
        "format": SUMMARY_FORMAT,
        "population_hash": S2V2_DEV_B_HASH,
        "calibration_package_hash": calibration_package_hash,
        "pre_heldout_identity_hash": pre_heldout_identity_hash,
        "method_hash": S2V2_METHOD_HASH,
        "criterion_hash": S2V2_CRITERION_HASH,
        "q_hat": float(q_hat),
        "q_hat_units": Q_HAT_UNITS,
        "n_attempted": len(ordered),
        "n_valid": len(ordered),
        "n_covered": covered,
        "n_missed": missed,
        "coverage": covered / len(ordered),
        "coverage_ci": [float(interval[0]), float(interval[1])],
        "coverage_ci_confidence": SUMMARY_COVERAGE_CONFIDENCE,
        "coverage_ci_sidedness": "two-sided",
        "mean_signed_error": float(mean_signed),
        "abs_mean_signed_error": float(abs(mean_signed)),
        "mean_absolute_error": float(sum(absolute) / len(absolute)),
        "ordered_evaluation_hashes": [digest(record) for record in ordered],
        "code_revision": code_revision,
        "status": SUMMARY_STATUS,
    }


__all__ = [
    "EVALUATION_FORMAT", "SUMMARY_FORMAT", "SUMMARY_STATUS",
    "Q_HAT_UNITS", "SUMMARY_COVERAGE_CONFIDENCE",
    "build_s2v2_devb_evaluation", "build_s2v2_devb_summary",
]
