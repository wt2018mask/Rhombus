"""S2 v2 Stage-B pure builders: score records, package freeze, pre-HELDOUT identity.

Pure record-construction logic over explicitly supplied inputs. No
filesystem access, no materialization, no estimator calls, no DEV/DEV-B/
HELD_OUT execution, no learned content from real evidence. The conformal
quantile is always recomputed from supplied score records by the frozen
rank rule -- never trusted from caller input, never interpolated.

Stage boundary: persistence and the DEV-A runner arrive in the NEXT task.
"""

from __future__ import annotations

import math

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration_s2v2 import (
    S2V2_CRITERION_HASH,
    S2V2_METHOD,
    S2V2_METHOD_HASH,
    S2V2_TARGET_COVERAGE,
    conformal_rank,
)
from rudeus.science.calibration_s2v2_populations import (
    S2V2_DEV_A_HASH,
    S2V2_DEV_A_SEEDS,
    S2V2_DEV_B_HASH,
    S2V2_HELDOUT_HASH,
    S2V2_POPULATIONS_HASH,
)
from rudeus.science.contracts import digest, require_hash

SCORE_FORMAT = "s2v2-conformal-score-v1"
SCORE_DEFINITION = "abs(D_hat-D_true)"
SCORE_UNITS = "m2/s"
PACKAGE_FORMAT = "s2v2-calibration-package-v1"
PACKAGE_STATUS = "FROZEN-DESCRIPTIVE-NOT-QUALIFICATION"
IDENTITY_FORMAT = "s2v2-pre-heldout-identity-v1"


def _reject(message):
    raise ExecutionError(message, "UNSUPPORTED_INPUT")


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _require_hash(value, name):
    try:
        require_hash(value)
    except (ValueError, TypeError) as exc:
        _reject(f"conformal score {name} must be a content hash: {exc}")


def _require_code_revision(value):
    if not isinstance(value, str) or not value:
        _reject("conformal score code_revision must be a nonempty string")


def _require_finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _reject(f"conformal score {name} must be numeric")
    if not math.isfinite(value):
        _reject(f"conformal score {name} must be finite")


def build_s2v2_score_record(*, replicate_id, replicate_manifest_hash,
                            estimator_result_hash, truth_record_hash,
                            estimate_D, truth_D,
                            method_hash=S2V2_METHOD_HASH,
                            population_hash=S2V2_DEV_A_HASH,
                            code_revision):
    """Build one versioned DEV-A conformal score record (pure).

    Computes score_value = abs(estimate_D - truth_D) internally; caller
    values are never trusted. Only DEV-A replicate IDs are accepted.
    """
    if replicate_id not in S2V2_DEV_A_SEEDS:
        _reject(f"conformal score replicate {replicate_id!r} is not DEV-A evidence")
    if method_hash != S2V2_METHOD_HASH:
        _reject("conformal score method hash does not match the frozen v2 method")
    if population_hash != S2V2_DEV_A_HASH:
        _reject("conformal score population hash does not match frozen DEV-A")
    _require_hash(replicate_manifest_hash, "replicate_manifest_hash")
    _require_hash(estimator_result_hash, "estimator_result_hash")
    _require_hash(truth_record_hash, "truth_record_hash")
    _require_code_revision(code_revision)
    _require_finite_number(estimate_D, "estimate_D")
    _require_finite_number(truth_D, "truth_D")
    score = abs(estimate_D - truth_D)
    if not math.isfinite(score) or score < 0:
        _reject("conformal score is not a finite nonnegative value")
    return {
        "format": SCORE_FORMAT,
        "replicate_id": replicate_id,
        "replicate_manifest_hash": replicate_manifest_hash,
        "estimator_result_hash": estimator_result_hash,
        "truth_record_hash": truth_record_hash,
        "method_hash": S2V2_METHOD_HASH,
        "population_hash": S2V2_DEV_A_HASH,
        "score_definition": SCORE_DEFINITION,
        "score_value": float(score),
        "units": SCORE_UNITS,
        "code_revision": code_revision,
    }


def _require_score_record(record):
    for key in ("replicate_id", "replicate_manifest_hash", "estimator_result_hash",
                "truth_record_hash", "method_hash", "population_hash",
                "score_definition", "score_value", "units", "code_revision"):
        if key not in record:
            _reject(f"conformal score record is missing {key}")
    if record["method_hash"] != S2V2_METHOD_HASH:
        _reject("conformal score record binds a foreign method")
    if record["population_hash"] != S2V2_DEV_A_HASH:
        _reject("conformal score record binds a foreign population")
    if record["score_definition"] != SCORE_DEFINITION:
        _reject("conformal score record uses a foreign score definition")
    if record["units"] != SCORE_UNITS:
        _reject("conformal score record uses foreign units")
    _require_finite_number(record["score_value"], "score_value")
    if record["score_value"] < 0:
        _reject("conformal score record carries a negative score")


def freeze_s2v2_calibration_package(*, score_records, code_revision):
    """Freeze the DEV-A calibration package (pure).

    Requires exactly the 99 frozen DEV-A score records (order-independent
    input; canonical DEV-A replicate order inside). Recomputes k and q_hat
    from the validated scores; q_hat is the k-th ascending order statistic
    (1-based), never interpolated, never caller-supplied.
    """
    _require_code_revision(code_revision)
    records = list(score_records)
    if len(records) != len(S2V2_DEV_A_SEEDS):
        _reject(f"calibration freeze requires 99 DEV-A scores, got {len(records)}")
    seen = [record.get("replicate_id") for record in records
            if isinstance(record, dict)]
    if len(seen) != len(records) or len(set(seen)) != len(records):
        _reject("calibration freeze found duplicate or malformed replicate IDs")
    if set(seen) != set(S2V2_DEV_A_SEEDS):
        _reject("calibration freeze IDs do not equal the frozen DEV-A set")
    for record in records:
        _require_score_record(record)
        if record["code_revision"] != code_revision:
            _reject("calibration freeze found a score record from a different "
                    "code revision")
    if len({record["truth_record_hash"] for record in records}) != 1:
        _reject("calibration freeze found multiple truth lineages")
    ordered = sorted(records, key=lambda record: record["replicate_id"])
    values = [float(record["score_value"]) for record in ordered]
    rank = conformal_rank(len(values), target_coverage=S2V2_TARGET_COVERAGE)
    if rank != 90:
        _fail(f"calibration freeze rank is {rank}, frozen policy requires 90")
    ordered_values = sorted(values)
    q_hat = ordered_values[rank - 1]
    estimator = S2V2_METHOD["estimator"]
    truth = S2V2_METHOD["truth"]
    return {
        "format": PACKAGE_FORMAT,
        "method_hash": S2V2_METHOD_HASH,
        "criterion_hash": S2V2_CRITERION_HASH,
        "dev_a_population_hash": S2V2_DEV_A_HASH,
        "score_record_hashes": [digest(record) for record in ordered],
        "score_definition": SCORE_DEFINITION,
        "target_coverage": S2V2_TARGET_COVERAGE,
        "rank_rule": "ceil((n + 1) * target_coverage)",
        "n": len(values),
        "k": rank,
        "q_hat": q_hat,
        "q_hat_units": SCORE_UNITS,
        "estimator": {"name": estimator["name"], "module": estimator["module"],
                      "config_hash": estimator["config_hash"]},
        "truth": dict(truth),
        "scope": dict(S2V2_METHOD["scope"]),
        "generator_protocol": dict(S2V2_METHOD["generator_protocol"]),
        "code_revision": code_revision,
        "package_status": PACKAGE_STATUS,
    }


def build_complete_pre_heldout_identity(*, calibration_package_hash,
                                        code_revision,
                                        method_hash=S2V2_METHOD_HASH,
                                        criterion_hash=S2V2_CRITERION_HASH):
    """Build the COMPLETE PRE-HELDOUT IDENTITY record (pure).

    Binds already-frozen scientific state only. Phase text records process
    state (calibration frozen, DEV-B unevaluated, HELD_OUT unopened); it is
    not a qualification verdict. DEV-B never modifies this identity.
    """
    _require_hash(calibration_package_hash, "calibration_package_hash")
    _require_code_revision(code_revision)
    if method_hash != S2V2_METHOD_HASH:
        _reject("pre-HELDOUT identity method hash is not the frozen v2 method")
    if criterion_hash != S2V2_CRITERION_HASH:
        _reject("pre-HELDOUT identity criterion hash is not frozen")
    return {
        "format": IDENTITY_FORMAT,
        "method_hash": S2V2_METHOD_HASH,
        "criterion_hash": S2V2_CRITERION_HASH,
        "dev_a_population_hash": S2V2_DEV_A_HASH,
        "dev_b_population_hash": S2V2_DEV_B_HASH,
        "heldout_population_hash": S2V2_HELDOUT_HASH,
        "populations_hash": S2V2_POPULATIONS_HASH,
        "calibration_package_hash": calibration_package_hash,
        "code_revision": code_revision,
        "phase": {"calibration": "frozen", "dev_b": "not-evaluated",
                  "heldout": "unopened"},
    }


__all__ = [
    "SCORE_FORMAT", "SCORE_DEFINITION", "SCORE_UNITS",
    "PACKAGE_FORMAT", "PACKAGE_STATUS", "IDENTITY_FORMAT",
    "build_s2v2_score_record", "freeze_s2v2_calibration_package",
    "build_complete_pre_heldout_identity",
]
