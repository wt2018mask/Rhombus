"""0146: actual original OBELiX TRAIN-only grouped out-of-fold regression.

DOI + composition connected components are held out together. Original
upper-bounds are NOT point targets. Predictions are real numerical model
outputs, but experimental source labels and their provenance are unqualified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import (
    SOURCE_COMMIT, _json_bytes, build_obelix_benchmark_intake,
)
from scripts.science.obelix_real_source_pipeline import run_three_stage_obelix
from scripts.science.obelix_raw_censor_lineage import build_original_censor_audit
from scripts.science.obelix_censor_aware_policy import (
    CENSOR, POINT, UNRESOLVED, build_train_label_policy,
)

SCHEMA = "rhombus-original-obelix-train-grouped-oof-0146-v1"
TARGET = "LOG10_ORIGINAL_SOURCE_NUMERIC_CONDUCTIVITY_S_PER_CM"
FOLDS = 5
RIDGE_ALPHA = 10.0
FEATURES = 118


def _fingerprint(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _composition(raw):
    from pymatgen.core import Composition
    if not isinstance(raw, str) or not raw or len(raw) > 256:
        return None
    try:
        comp = Composition(raw)
        entries = comp.get_el_amt_dict()
        if not entries or len(entries) > FEATURES or not comp.valid:
            return None
        reduced = comp.reduced_formula
        normalized = comp.fractional_composition.get_el_amt_dict()
        v = np.zeros(FEATURES, dtype=np.float64)
        from pymatgen.core.periodic_table import Element
        for symbol, value in normalized.items():
            z = Element(symbol).Z
            if not 1 <= z <= FEATURES or not math.isfinite(float(value)) or value <= 0:
                return None
            v[z-1] = float(value)
        if not np.isfinite(v).all() or abs(float(v.sum()) - 1) > 1e-8:
            return None
        return reduced, v
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return None


def _positive_log10(text):
    if not isinstance(text, str) or not 1 <= len(text) <= 120:
        return None
    try:
        val = Decimal(text)
        if not val.is_finite() or not Decimal("0") < val <= Decimal("1e12"):
            return None
        y = float(val.log10())
        return y if math.isfinite(y) and -100 <= y <= 12 else None
    except (InvalidOperation, OverflowError, ValueError, ArithmeticError):
        return None


def _ridge_predict(x_train, y_train, x_hold, alpha=RIDGE_ALPHA):
    """Fixed ridge on training-standardized elemental fractional descriptors."""
    if type(alpha) not in (int, float) or alpha <= 0 or not math.isfinite(alpha):
        raise ValueError("invalid fixed ridge regularization")
    center = np.mean(x_train, axis=0)
    scale = np.std(x_train, axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    xt = (x_train - center) / scale
    xv = (x_hold - center) / scale
    mean = float(np.mean(y_train))
    matrix = xt.T @ xt + float(alpha) * np.eye(x_train.shape[1])
    weights = np.linalg.solve(matrix, xt.T @ (y_train - mean))
    out = xv @ weights + mean
    if not np.isfinite(out).all():
        raise ValueError("nonfinite prediction")
    return out


def evaluate_original_obelix_train(records, policy, *, strict_official=True, return_internal=False):
    """Actual OOF predictions. Only public TRAIN rows may enter this interface."""
    if not isinstance(records, list) or not isinstance(policy, list):
        raise ValueError("records and source-label policies must be arrays")
    if strict_official and (len(records) != 599 or len(policy) != 478):
        raise ValueError("official OBELiX population drift")
    if len(records) > 50000 or len(policy) > 50000:
        raise ValueError("over budget source record population")
    train = {}
    test_count = 0
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("invalid original source row")
        sid = row.get("source_entry_id")
        if not isinstance(sid, str) or not sid or len(sid) > 256:
            raise ValueError("invalid source ID")
        split = row.get("official_split")
        if split == "TEST":
            test_count += 1
            continue  # Never inspect held-out source labels, formula, structure or DOI.
        if split != "TRAIN" or sid in train:
            raise ValueError("original TRAIN split/ID compromised")
        train[sid] = row
    if strict_official and (len(train), test_count) != (478, 121):
        raise ValueError("official public split count mismatch")
    labels = {}
    for p in policy:
        if not isinstance(p, dict) or p.get("official_original_split") != "TRAIN":
            raise ValueError("official TEST in original raw label policy")
        sid = p.get("source_entry_id")
        if sid not in train or sid in labels:
            raise ValueError("source TRAIN label absent or duplicated")
        if p.get("point_estimate_benchmark_scoring_permitted") is not False or (
            p.get("scientific_material_qualified") is not False
        ):
            raise ValueError("source metadata falsely promoted to scientific truth")
        if p.get("raw_measurement_policy_kind") not in (POINT, CENSOR, UNRESOLVED):
            raise ValueError("unknown original measurement censoring status")
        labels[sid] = p
    if set(labels) != set(train):
        raise ValueError("original TRAIN source/label join lost rows")

    # Build transitive graph over ALL original TRAIN, including censored and
    # nonnumeric rows, so bridges do not leak DOI/composition identity.
    parent = {sid: sid for sid in train}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)
    shared = {}
    comp = {}
    for sid, row in sorted(train.items()):
        raw_formula = row.get("reported_composition")
        parsed = _composition(raw_formula)
        comp[sid] = parsed
        keys = []
        if isinstance(raw_formula, str) and raw_formula.strip():
            keys.append("RAW:" + raw_formula.strip().casefold())
        if parsed is not None:
            keys.append("REDUCED:" + parsed[0])
        dois = row.get("reference_dois")
        if not isinstance(dois, list) or any(not isinstance(x, str) for x in dois):
            raise ValueError("invalid frozen source DOI group")
        for doi in dois:
            if not doi.startswith("10.") or len(doi) > 512:
                raise ValueError("invalid original DOI")
            keys.append("DOI:" + doi.casefold())
        for key in set(keys):
            if key in shared:
                union(sid, shared[key])
            else:
                shared[key] = sid
    bygroup = defaultdict(list)
    counters = Counter()
    numeric_records = []
    for sid in sorted(train):
        p = labels[sid]
        kind = p["raw_measurement_policy_kind"]
        counters[kind] += 1
        if kind != POINT:
            continue  # Upper bound not a point, regardless processed surrogate.
        if p.get("processed_surrogate_must_not_be_scored") is not False:
            raise ValueError("numeric point is marked synthetic surrogate")
        y = _positive_log10(p.get("source_numeric_metadata_s_per_cm"))
        if y is None:
            counters["SOURCE_POINT_NONNUMERIC_UNUSABLE"] += 1
            continue
        parsed = comp[sid]
        if parsed is None:
            counters["SOURCE_COMPOSITION_UNPARSEABLE"] += 1
            continue
        numeric_records.append((sid, parsed[1], y, find(sid)))
    if len(numeric_records) < 10:
        raise ValueError("insufficient legitimate original numeric TRAIN inputs")

    group_members = defaultdict(list)
    for idx, (_, _, _, group) in enumerate(numeric_records):
        group_members[group].append(idx)
    if len(group_members) < FOLDS:
        raise ValueError("insufficient non-overlapping DOI/formula groups")
    heldout = [[] for _ in range(FOLDS)]
    for group, indices in sorted(group_members.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        dest = min(range(FOLDS), key=lambda i: (len(heldout[i]), i))
        heldout[dest].extend(indices)
    if not all(heldout):
        raise ValueError("empty grouped held-out fold")
    xs = np.stack([r[1] for r in numeric_records])
    ys = np.asarray([r[2] for r in numeric_records], dtype=float)
    grouped = [r[3] for r in numeric_records]
    all_idx = set(range(len(numeric_records)))
    pred = np.full(len(numeric_records), np.nan)
    baseline = np.full(len(numeric_records), np.nan)
    per_fold = []
    for i, test in enumerate(heldout):
        train_indices = np.array(sorted(all_idx - set(test)), dtype=int)
        test_indices = np.array(sorted(test), dtype=int)
        if set(grouped[j] for j in test_indices) & set(grouped[j] for j in train_indices):
            raise ValueError("DOI/formula component leakage across folds")
        pred[test_indices] = _ridge_predict(
            xs[train_indices], ys[train_indices], xs[test_indices])
        baseline[test_indices] = float(ys[train_indices].mean())
        per_fold.append({
            "fold": i + 1,
            "heldout_record_count": len(test_indices),
            "heldout_connected_identity_groups": len({grouped[j] for j in test_indices}),
            "training_record_count": len(train_indices),
            "group_leakage_count": 0,
        })
    if not np.isfinite(pred).all() or not np.isfinite(baseline).all():
        raise ValueError("incomplete or invalid out-of-fold predictions")
    if len(set(grouped)) != sum(f["heldout_connected_identity_groups"] for f in per_fold):
        raise ValueError("held-out groups not one-to-one assigned")
    def metrics(values):
        error = values - ys
        return {
            "log10_MAE": round(float(np.mean(np.abs(error))), 8),
            "log10_RMSE": round(float(np.sqrt(np.mean(error ** 2))), 8),
        }
    report = {
        "schema_version": SCHEMA,
        "evaluation": "PUBLIC_SOURCE_DIAGNOSTIC_REAL_GROUPED_OUT_OF_FOLD",
        "training_data_role": "PUBLIC_OBELIX_OFFICIAL_TRAIN_ONLY",
        "target": TARGET,
        "model": "NUMPY_ELEMENT_FRACTION_STANDARDIZED_RIDGE_ALPHA_10",
        "baseline": "TRAINING_FOLD_MEAN_LOG10_CONDUCTIVITY",
        "split_contract": "TRANSITIVE_SHARED_DOI_OR_RAW_OR_REDUCED_FORMULA_COMPONENTS",
        "original_source_records": len(records),
        "original_source_train_count": len(train),
        "original_official_test_reserved_unread": test_count,
        "original_raw_point_source_records": counters[POINT],
        "original_raw_censored_upper_bounds_excluded": counters[CENSOR],
        "original_raw_unresolved_excluded": counters[UNRESOLVED],
        "original_numeric_but_formula_unparseable": counters["SOURCE_COMPOSITION_UNPARSEABLE"],
        "original_numeric_but_invalid_excluded": counters["SOURCE_POINT_NONNUMERIC_UNUSABLE"],
        "out_of_fold_numeric_source_records_scored": len(numeric_records),
        "shared_doi_formula_connected_components_scored": len(group_members),
        "grouped_folds": per_fold,
        "trained_ridge_oof_metrics": metrics(pred),
        "training_fold_mean_oof_metrics": metrics(baseline),
        "all_folds_have_zero_group_identity_leakage": True,
        "independent_physical_material_count_verified": None,
        "source_measurements_original_papers_attested": False,
        "bulk_total_phase_temperature_normalized": False,
        "exact_MACE_checkpoint_selected_training_exposure_verified": False,
        "model_is_MACE_transport_prediction": False,
        "official_public_TEST_predictions": 0,
        "new_independently_blind_materials": 0,
        "P0_01_status": "BLOCKED",
        "P0_02_status": "BLOCKED",
        "P0_03_status": "BLOCKED",
        "scientific_qualification_authorized": False,
        "experimental_generalization_claim_authorized": False,
    }
    if sum(report[k] for k in (
        "original_raw_point_source_records",
        "original_raw_censored_upper_bounds_excluded",
        "original_raw_unresolved_excluded",
    )) != len(train):
        raise ValueError("raw original measurement categories do not sum to TRAIN")
    if report["out_of_fold_numeric_source_records_scored"] + (
        report["original_numeric_but_formula_unparseable"]
        + report["original_numeric_but_invalid_excluded"]
    ) != report["original_raw_point_source_records"]:
        raise ValueError("original point target inclusion coverage mismatch")
    if return_internal:
        # Transient arrays from original source. NEVER publish source-row truth or group IDs.
        return report, {
            "x": xs.copy(), "y": ys.copy(),
            "groups": tuple(grouped),
            "fold_indices": tuple(np.asarray(fold, dtype=int) for fold in heldout),
            "ridge_oof": pred.copy(), "mean_oof": baseline.copy(),
        }
    return report


def run_official_original_oof(source_checkout: Path, output_dir: Path, *, return_internal=False):
    original = Path(source_checkout).resolve(strict=True)
    out = Path(output_dir).resolve()
    if out.exists() or out == original or original in out.parents:
        raise ValueError("source and report must be separate, output must be new")
    # Temporary source-linked raw labels are NEVER artifacts or uploaded;
    # original TEST source-row values remain outside the evaluation function.
    with tempfile.TemporaryDirectory(prefix="obelix-0146-work-") as tmp:
        t = Path(tmp)
        run_three_stage_obelix(original, t / "source0130")
        raw_rows, raw_summary = build_original_censor_audit(
            original, t / "source0130")
        (t / "raw0133").mkdir()
        (t / "raw0133" / "train_raw_measurement_lineage.jsonl").write_bytes(
            b"".join(_json_bytes(x) + b"\n" for x in raw_rows)
        )
        (t / "raw0133" / "summary.json").write_bytes(
            _json_bytes(raw_summary) + b"\n")
        policy_rows, policy_summary = build_train_label_policy(
            original, t / "source0130", t / "raw0133")
        if policy_summary["source_train_records"] != 478:
            raise ValueError("official original 0134 label population mismatch")
        records, source = build_obelix_benchmark_intake(original, expected_commit=SOURCE_COMMIT)
        evaluation = evaluate_original_obelix_train(
            records, policy_rows, return_internal=return_internal)
        report, internal = evaluation if return_internal else (evaluation, None)
        report.update({
            "original_upstream_commit": SOURCE_COMMIT,
            "source_processed_csv_sha256": source["processed_csv_sha256"],
            "original_raw_workbook_sha256": raw_summary["original_raw_workbook_sha256"],
            "original_raw_train_label_policy_sha256": policy_summary["train_label_policy_jsonl_sha256"],
        })
        out.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".obelix-0146-report-", dir=out.parent))
        try:
            (staging / "original_train_grouped_oof.json").write_bytes(
                _json_bytes(report) + b"\n")
            if out.exists():
                raise ValueError("output claimed while evaluating original source")
            staging.rename(out)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    return (report, internal) if return_internal else report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-obelix-checkout", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_official_original_oof(args.original_obelix_checkout, args.output_dir)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "out_of_fold_source_records": result["out_of_fold_numeric_source_records_scored"],
        "group_components": result["shared_doi_formula_connected_components_scored"],
        "ridge_log10_MAE": result["trained_ridge_oof_metrics"]["log10_MAE"],
        "source_train_total": result["original_source_train_count"],
        "scientific_go": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
