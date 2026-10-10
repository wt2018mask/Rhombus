"""Offline C2 LOCO/LOFO material-level diagnostics with explicit group exclusion.

Validates a *declared* fold plan and aggregates precomputed public diagnostic
predictions. Does not retrain models, inspect real secret cohorts, or attest
source/group independence. No generalization or scientific PASS is awarded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from rhombus.qualification.sealed_evaluation import OUTCOMES

SCHEMA = "rhombus-group-exclusion-evaluation-v1"
REPORT_SCHEMA = "rhombus-group-exclusion-report-v1"
MAX_INPUT_BYTES = 1024 * 1024
MAX_GROUPS = 512
MAX_MATERIALS = 10000
_TRUTH = frozenset(("POSITIVE", "NEGATIVE", "BORDERLINE"))
_HARD_FAILURE = frozenset(("UNKNOWN", "FAILED", "INDETERMINATE", "NONDIFFUSIVE"))
_OPERATIONAL = frozenset(("SUCCEEDED", "ERROR", "CANCELLED"))
_HEX = re.compile(r"^[a-f0-9]{64}$")


def _exact(obj: Any, keys: set[str], kind: str) -> dict[str, Any]:
    if not isinstance(obj, dict) or set(obj) != keys:
        raise ValueError("invalid " + kind + " field contract")
    return obj


def _id(value: Any, kind: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError("invalid " + kind + " identifier")
    return value


def _unique_ids(value: Any, kind: str) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_GROUPS:
        raise ValueError("invalid " + kind + " group identifiers")
    result = [_id(item, kind) for item in value]
    if len(result) != len(set(result)):
        raise ValueError("duplicate " + kind + " identifiers")
    return result


def evaluate_group_exclusion(evaluation: dict[str, Any]) -> dict[str, Any]:
    """Check every declared train/holdout group and retain all material outcomes."""
    _exact(evaluation, {
        "schema_version", "scope", "method", "cohort_id",
        "model_checkpoint_sha256", "folds",
    }, "group-exclusion evaluation")
    if (evaluation["schema_version"] != SCHEMA
            or evaluation["scope"] != "PUBLIC_DIAGNOSTIC_ONLY"
            or evaluation["method"] not in ("LOCO", "LOFO")):
        raise ValueError("unsupported group-exclusion method or scope")
    _id(evaluation["cohort_id"], "cohort")
    sha = evaluation["model_checkpoint_sha256"]
    if not isinstance(sha, str) or _HEX.fullmatch(sha) is None:
        raise ValueError("invalid model checkpoint digest")
    folds = evaluation["folds"]
    if not isinstance(folds, list) or not 2 <= len(folds) <= MAX_GROUPS:
        raise ValueError("at least two distinct held-out groups required")
    fold_by_group: dict[str, dict[str, Any]] = {}
    for fold in folds:
        _exact(fold, {
            "held_out_group_id", "declared_training_group_ids", "materials",
        }, "fold")
        name = _id(fold["held_out_group_id"], "held-out group")
        if name in fold_by_group:
            raise ValueError("duplicate held-out group")
        fold_by_group[name] = fold

    all_groups = set(fold_by_group)
    seen_materials: set[str] = set()
    summaries = []
    all_counts = {outcome: 0 for outcome in OUTCOMES}
    all_operations = {status: 0 for status in sorted(_OPERATIONAL)}
    total = 0
    correct_total = 0
    for group in sorted(all_groups):
        fold = fold_by_group[group]
        declared = _unique_ids(fold["declared_training_group_ids"], "training")
        if set(declared) != all_groups - {group}:
            raise ValueError("held-out fold overlap, gap or inconsistent train groups")
        materials = fold["materials"]
        if not isinstance(materials, list) or not materials:
            raise ValueError("each group requires material-level observations")
        counts = {outcome: 0 for outcome in OUTCOMES}
        operations = {status: 0 for status in sorted(_OPERATIONAL)}
        ncorrect = 0
        for material in materials:
            _exact(material, {
                "material_id", "observed_truth", "predicted_outcome", "operational_status",
            }, "material")
            mid = _id(material["material_id"], "material")
            if mid in seen_materials:
                raise ValueError("material duplicate across held-out groups")
            seen_materials.add(mid)
            truth = material["observed_truth"]
            outcome = material["predicted_outcome"]
            operation = material["operational_status"]
            if truth not in _TRUTH or outcome not in OUTCOMES or operation not in _OPERATIONAL:
                raise ValueError("invalid material truth, outcome or operational status")
            if operation != "SUCCEEDED" and outcome not in _HARD_FAILURE:
                raise ValueError("failed/cancelled work cannot report conclusive predictions")
            counts[outcome] += 1
            all_counts[outcome] += 1
            operations[operation] += 1
            all_operations[operation] += 1
            if operation == "SUCCEEDED" and outcome == truth:
                ncorrect += 1
            total += 1
            if total > MAX_MATERIALS:
                raise ValueError("evaluation material budget exceeded")
        correct_total += ncorrect
        summaries.append({
            "held_out_group_id": group,
            "material_count": len(materials),
            "correct_count": ncorrect,
            "diagnostic_correct_fraction": ncorrect / len(materials),
            "prediction_outcome_counts": counts,
            "operational_status_counts": operations,
            "excluded_training_group": True,
        })

    canonical = json.dumps(
        evaluation, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return {
        "schema_version": REPORT_SCHEMA,
        "method": evaluation["method"],
        "scope": "PUBLIC_DIAGNOSTIC_ONLY",
        "cohort_id": evaluation["cohort_id"],
        "model_checkpoint_sha256": sha,
        "evaluation_input_sha256": hashlib.sha256(canonical).hexdigest(),
        "group_count": len(summaries),
        "material_count": total,
        "correct_count": correct_total,
        "diagnostic_correct_fraction": correct_total / total,
        "prediction_outcome_counts": all_counts,
        "operational_status_counts": all_operations,
        "fold_results": summaries,
        "declared_group_exclusion_consistent": True,
        "actual_model_training_exclusion_independently_attested": False,
        "observed_materials_independently_sampled": False,
        "calibrated_error_estimate_available": False,
        "scientific_verdict": "INDETERMINATE",
        "claim_authorized": False,
        "unseen_generalization_authorized": False,
        "limitations": [
            "PRECOMPUTED_PUBLIC_DIAGNOSTIC_RESULTS_ONLY",
            "DECLARED_TRAINING_GROUPS_NOT_INDEPENDENTLY_AUTHENTICATED",
            "MATERIAL_IDENTITY_GROUP_MEMBERSHIP_NOT_EXTERNALLY_ATTESTED",
            "OLD_B3_HELD_OUT_IS_NOT_INDEPENDENT_BLIND_EVALUATION",
            "NO_CALIBRATED_OUT_OF_DOMAIN_OR_UNSEEN_GENERALIZATION_METRIC",
            "NO_IID_OR_STATISTICAL_PRECISION_ASSERTION",
        ],
    }


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value = {}
    for name, item in pairs:
        if name in value:
            raise ValueError("duplicate evaluation field")
        value[name] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite evaluation numeric constant")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-json", required=True, type=Path,
                        help="Precomputed PUBLIC_DIAGNOSTIC_ONLY LOCO/LOFO rows")
    args = parser.parse_args(argv)
    with args.evaluation_json.open("rb") as stream:
        blob = stream.read(MAX_INPUT_BYTES + 1)
    if len(blob) > MAX_INPUT_BYTES:
        parser.error("group evaluation input size budget exceeded")
    try:
        data = json.loads(blob, object_pairs_hook=_reject_duplicates,
                          parse_constant=_reject_constant)
        result = evaluate_group_exclusion(data)
    except (ValueError, UnicodeError, TypeError) as exc:
        parser.error("invalid or inconsistent group-exclusion diagnostic input")
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
