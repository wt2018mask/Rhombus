"""0134: source-verified TRAIN-only conductivity label policies.

This module is an *evidence-preserving diagnostic*, not a benchmark score.
Original upper-limit measurements are open intervals and cannot be exact
regression targets. Numerical source fields are unverified experimental
metadata until paper/phase/quantity and model training exposure are audited.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from rhombus.qualification.measurement_identity import (
    _json_bytes, _parse_json, _read_input, _records_from_jsonl,
)
from scripts.science.obelix_raw_censor_lineage import (
    SCHEMA as RAW_SCHEMA, build_original_censor_audit,
)

SCHEMA = "rhombus-train-censor-aware-evaluation-policy-0134-v1"
POLICY = "NO_SCIENTIFIC_SCORE_UNTIL_INDEPENDENT_EXPERIMENT_REVIEW"
CENSOR = "UPPER_BOUND_EXCLUSIVE"
POINT = "SOURCE_NUMERIC_UNVERIFIED"
UNRESOLVED = "SOURCE_NONNUMERIC_UNRESOLVED"
_MAX_CONDUCTIVITY = Decimal("1e12")


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _canonical_rows(rows: list[dict]) -> bytes:
    return b"".join(_json_bytes(row) + b"\n" for row in rows)


def _positive_decimal(raw: str, *, label: str) -> Decimal:
    if not isinstance(raw, str) or not raw or len(raw) > 100:
        raise ValueError("invalid " + label)
    try:
        n = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("unparseable " + label) from exc
    if not n.is_finite() or not Decimal("0") < n <= _MAX_CONDUCTIVITY:
        raise ValueError("nonfinite/out-of-range " + label)
    return n


def interval_exceedance_log10(
    predicted_conductivity_s_per_cm: str, original_exclusive_upper_bound_s_per_cm: str
) -> str:
    """Nonnegative log10 bound violation; DIAGNOSTIC ONLY.

    Zero when predicted sigma < original upper limit. Equality to a strict
    exclusive upper bound is defined as zero distance but NONSATISFYING
    evidence; callers must check "satisfies_exclusive_bound" separately.
    This is NOT a scientific benchmark performance metric.
    """
    prediction = _positive_decimal(predicted_conductivity_s_per_cm,
                                   label="predicted conductivity")
    limit = _positive_decimal(original_exclusive_upper_bound_s_per_cm,
                              label="original upper bound")
    if prediction <= limit:
        return "0"
    with localcontext() as context:
        context.prec = 28
        return str((prediction / limit).log10().normalize())


def interval_constraint_check(
    predicted_conductivity_s_per_cm: str, original_exclusive_upper_bound_s_per_cm: str
) -> dict:
    prediction = _positive_decimal(predicted_conductivity_s_per_cm,
                                   label="predicted conductivity")
    bound = _positive_decimal(original_exclusive_upper_bound_s_per_cm,
                              label="original upper bound")
    return {
        "schema_version": SCHEMA,
        "constraint": CENSOR,
        "satisfies_exclusive_bound": prediction < bound,
        "diagnostic_violation_log10": interval_exceedance_log10(
            predicted_conductivity_s_per_cm, original_exclusive_upper_bound_s_per_cm
        ),
        "independent_material_score": None,
        "scientific_metric_authorized": False,
    }


def _read_existing_raw(root: Path) -> tuple[list[dict], dict]:
    raw = _read_input(root / "train_raw_measurement_lineage.jsonl")
    summary = _parse_json(_read_input(root / "summary.json"))
    rows = _records_from_jsonl(raw)
    if (not isinstance(summary, dict)
            or summary.get("schema_version") != RAW_SCHEMA
            or summary.get("scientific_qualification_authorized") is not False
            or summary.get("train_record_evidence_sha256") != _sha(raw)
            or summary.get("original_train_records") != len(rows)):
        raise ValueError("0133 raw source artifact not hash-bound and unqualified")
    return rows, summary


def build_train_label_policy(
    original_checkout: Path,
    evidence_dir: Path,
    raw_lineage_dir: Path,
    *,
    require_official: bool = True,
) -> tuple[list[dict], dict]:
    """Cross-recompute full 0133 from checkout, then derive diagnostic rules."""
    exact_rows, exact_summary = build_original_censor_audit(
        original_checkout, evidence_dir, require_official=require_official
    )
    preserved_rows, preserved_summary = _read_existing_raw(Path(raw_lineage_dir))
    if preserved_rows != exact_rows or preserved_summary != exact_summary:
        raise ValueError("0133 original raw measurements differ from independently recomputed source")
    output: list[dict] = []
    censored = 0
    numeric = 0
    unresolved = 0
    for row in exact_rows:
        if row["schema_version"] != RAW_SCHEMA or row["official_original_split"] != "TRAIN":
            raise ValueError("unrecognized 0133 TRAIN source")
        typ = row["raw_measurement_kind"]
        raw = row["original_raw_measurement_text"]
        substitute = row["processed_numeric_text"]
        if typ == "ORIGINAL_UPPER_BOUND_NUMERIC_PLACEHOLDER":
            if not raw.startswith("<"):
                raise ValueError("original source upper bound missing")
            bound = _positive_decimal(raw[1:], label="upper-bound conductivity")
            if _positive_decimal(substitute, label="processed surrogate") != Decimal("1e-15"):
                raise ValueError("unexpected fake numeric surrogate")
            kind, endpoint, value, diagnostic = CENSOR, str(bound.normalize()), None, True
            censored += 1
        elif typ == "RAW_REPORTED_NUMERIC":
            # A *reported* numeric value does not prove original paper/specific
            # physical quantity, sample, phase, temperature or independence.
            value = str(_positive_decimal(raw, label="original point metadata").normalize())
            kind, endpoint, diagnostic = POINT, None, False
            numeric += 1
        elif typ == "RAW_NONNUMERIC_UNRESOLVED":
            kind, endpoint, value, diagnostic = UNRESOLVED, None, None, False
            unresolved += 1
        else:
            raise ValueError("unrecognized original source censoring classification")
        output.append({
            "schema_version": SCHEMA,
            "source_dataset": "OBELiX",
            "source_entry_id": row["source_entry_id"],
            "source_record_sha256": row["source_record_sha256"],
            "source_raw_workbook_sha256": row["original_raw_workbook_sha256"],
            "official_original_split": "TRAIN",
            "measurement_quantity_status": "REPORTED_IONIC_CONDUCTIVITY_UNVERIFIED_BULK_VS_TOTAL",
            "raw_measurement_policy_kind": kind,
            "original_inequality_text": raw if kind == CENSOR else None,
            "exclusive_upper_bound_s_per_cm": endpoint,
            "source_numeric_metadata_s_per_cm": value,
            "processed_surrogate_must_not_be_scored": kind == CENSOR,
            "diagnostic_constraint_check_permitted": diagnostic,
            "point_estimate_benchmark_scoring_permitted": False,
            "temperature_phase_paper_review_completed": False,
            "material_independence_verified": False,
            "model_training_nonexposure_verified": False,
            "scientific_material_qualified": False,
        })
    if len(output) != exact_summary["original_train_records"]:
        raise ValueError("dropped original TRAIN record")
    if censored != exact_summary["raw_train_censored_records"]:
        raise ValueError("censored source count inconsistent with 0133 evidence")
    output.sort(key=lambda x: x["source_entry_id"])
    blob = _canonical_rows(output)
    summary = {
        "schema_version": SCHEMA,
        "source_commit": exact_summary["source_commit"],
        "source_workbook_sha256": exact_summary["original_raw_workbook_sha256"],
        "source_train_raw_evidence_sha256": exact_summary["train_record_evidence_sha256"],
        "train_label_policy_jsonl_sha256": _sha(blob),
        "source_train_records": len(output),
        "original_censored_train_records": censored,
        "original_numeric_unverified_train_records": numeric,
        "original_other_unresolved_train_records": unresolved,
        "original_test_reserved_aggregate": exact_summary["original_test_records_reserved"],
        "original_test_censored_aggregate": exact_summary["raw_test_censored_records_reserved"],
        "point_targets_scientifically_qualified": 0,
        "scientifically_qualified_material_count": None,
        "new_external_blind_materials": 0,
        "scientific_verdict": "INDETERMINATE",
        "scientific_qualification_authorized": False,
        "policy": POLICY,
        "limitations": [
            "CENSORED_UPPER_BOUND_IS_NOT_AN_EXACT_LABEL",
            "NUMERIC_SOURCE_FIELD_IS_NOT_AUTHENTICATED_EXPERIMENTAL_TRUTH",
            "LOG_BOUND_VIOLATION_DIAGNOSTIC_ONLY_NOT_MODEL_VALIDATION",
            "NO_PUBLIC_TEST_ROW_VALUES_OR_IDS_IN_DEVELOPER_ARTIFACT",
            "QUANTITY_PHASE_TEMPERATURE_MACE_TRAINING_EXPOSURE_UNATTESTED",
        ],
    }
    return output, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obelix-checkout", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--raw-lineage-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        inputs = (args.obelix_checkout.resolve(strict=True),
                  args.evidence_dir.resolve(strict=True),
                  args.raw_lineage_dir.resolve(strict=True))
        output = args.output_dir.resolve()
        if output.exists():
            raise ValueError("output must not pre-exist")
        if any(output == i or i in output.parents for i in inputs):
            raise ValueError("output cannot be written inside original evidence")
        rows, summary = build_train_label_policy(*inputs)
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".obelix-0134-", dir=output.parent))
        try:
            (staging / "train_label_policy.jsonl").write_bytes(_canonical_rows(rows))
            (staging / "summary.json").write_bytes(_json_bytes(summary) + b"\n")
            if output.exists():
                raise ValueError("output changed before evidence commit")
            staging.rename(output)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
