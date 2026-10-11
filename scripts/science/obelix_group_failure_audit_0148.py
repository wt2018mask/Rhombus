"""0148: explain failed real public TRAIN models without changing frozen splits.

Purely retrospective, aggregate-only, per-source-group and composition-proxy
analysis. Does NOT independently validate physical samples or author scores.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import _json_bytes, SOURCE_COMMIT
from scripts.science.obelix_real_grouped_oof_0146 import run_official_original_oof
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import evaluate_frozen_baselines

SCHEMA = "rhombus-public-obelix-real-0148-failure-diagnostic-v1"
ANION_PROXY_BINS = (
    "O_AND_S", "O_ONLY", "S_ONLY", "HALIDE_NO_O_S", "OTHER_NO_O_S_HALIDE"
)
PAIRED_BOOTSTRAPS = 512
PUBLISHER_CODE = (
    "benchmark/parse.py", "benchmark/RF.py", "benchmark/MLP.py"
)
MIN_FAMILY_ROWS = 10
MIN_FAMILY_CONNECTED_GROUPS = 3
MODELS = ("training_fold_mean_0146", "random_forest", "mlp", "ridge_0146")


def _approx(x):
    v = float(x)
    if not math.isfinite(v):
        raise ValueError("invalid empirical aggregate")
    return round(v, 8)


def _family_proxy(row):
    """Mutually exclusive formula element PRESENCE only (not phases/families)."""
    if row.shape != (118,) or not np.isfinite(row).all():
        raise ValueError("invalid frozen elemental descriptor")
    o, s = row[7] > 0, row[15] > 0
    if o and s:
        return "O_AND_S"
    if o:
        return "O_ONLY"
    if s:
        return "S_ONLY"
    if any(row[z - 1] > 0 for z in (9, 17, 35, 53)):
        return "HALIDE_NO_O_S"
    return "OTHER_NO_O_S_HALIDE"


def _publisher_protocol_inspection(original: Path):
    """Read, NEVER import/run, official author scripts at verified git commit."""
    root = Path(original).resolve(strict=True)
    sections = {}
    markers = {
        "benchmark/parse.py": ("flatten_comp", "Space group number", "mendeleev", "usecols"),
        "benchmark/RF.py": ("GridSearchCV", "RandomForestRegressor", "StandardScaler", "train_idx.csv"),
        "benchmark/MLP.py": ("GridSearchCV", "MLPRegressor", "StandardScaler", "train_idx.csv"),
    }
    for relative in PUBLISHER_CODE:
        p = root / relative
        if p.is_symlink() or not p.is_file() or root not in p.resolve(strict=True).parents:
            raise ValueError("publisher source script absent, symlinked or escaped")
        with p.open("rb") as f:
            raw = f.read(100_001)
        if not raw or len(raw) > 100_000:
            raise ValueError("publisher source script empty or oversized")
        source = raw.decode("utf-8")
        if any(k not in source for k in markers[relative]):
            raise ValueError("publisher actual original source protocol drift")
        sections[relative] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "source_bytes": len(raw),
            "interpreted_as_executable": False,
        }
    return {
        "pinned_original_source_commit": SOURCE_COMMIT,
        "author_source_code_verified_readonly": sections,
        "original_author_features": "RAW_ELEMENTAL_STOICHIOMETRIC_COUNTS_PLUS_SPACEGROUP_AND_SIX_CELL_PARAMS",
        "0146_0147_features": "118_NORMALIZED_ELEMENTAL_FRACTIONS_WITHOUT_SPACEGROUP_OR_LATTICE",
        "author_cv": "SEPARATE_TUNING_GRID_SEARCH_CV5_WITH_ORIGINAL_OFFICIAL_TRAIN_TEST",
        "rhombus_cv": "FROZEN_0146_CONNECTED_DOI_FORMULA_GROUP_FOLDS_5",
        "original_upper_bound_surrogate_training_exposure": "POTENTIALLY_INCLUDES_ORIGINAL_PROCESSED_SOURCE_TRANSFORMED_VALUES",
        "rhombus_original_upper_bound_policy": "EXCLUDE_29_ORIGINAL_STRICT_UPPER_BOUNDS_FROM_POINT_SCORING",
        "exact_publisher_paper_protocol_reproduced": False,
        "source_author_paper_performance_comparison_authorized": False,
    }


def _family_scores(x, y, groups, predictions):
    out = {}
    flags = [_family_proxy(row) for row in x]
    for family in ANION_PROXY_BINS:
        idx = np.array([i for i, f in enumerate(flags) if f == family], dtype=int)
        subset_groups = len({groups[i] for i in idx})
        row = {
            "proxy": family,
            "source_record_count": int(len(idx)),
            "connected_group_count": int(subset_groups),
            "scientific_structural_family_qualified": False,
            "score_suppressed_by_minimum_coverage": len(idx) < MIN_FAMILY_ROWS or subset_groups < MIN_FAMILY_CONNECTED_GROUPS,
        }
        if not row["score_suppressed_by_minimum_coverage"]:
            row["model_log10_MAE"] = {
                name: _approx(np.mean(np.abs(predictions[name][idx] - y[idx])))
                for name in MODELS
            }
            row["rf_minus_mean_log10_MAE"] = _approx(
                row["model_log10_MAE"]["random_forest"]
                - row["model_log10_MAE"]["training_fold_mean_0146"])
        out[family] = row
    if sum(v["source_record_count"] for v in out.values()) != len(y):
        raise ValueError("formula category silently loses source records")
    return out


def _paired_group_delta(y, groups, predictions, *, seed=148):
    """Source-group deltas; *not* IID material CI or confirmed statistical power."""
    members = defaultdict(list)
    for i, g in enumerate(groups):
        members[g].append(i)
    ordered = [members[key] for key in sorted(members)]
    rng = np.random.default_rng(seed)
    row = {}
    base_err = np.abs(predictions["training_fold_mean_0146"] - y)
    for name in ("random_forest", "mlp", "ridge_0146"):
        model_err = np.abs(predictions[name] - y)
        per_group = np.array([
            np.mean((model_err - base_err)[indices]) for indices in ordered
        ], dtype=float)
        if len(per_group) < 5 or not np.isfinite(per_group).all():
            raise ValueError("not enough source groups for paired error audit")
        sample_means = np.mean(rng.choice(
            per_group, size=(PAIRED_BOOTSTRAPS, len(per_group)), replace=True
        ), axis=1)
        row[name] = {
            "record_weighted_model_minus_mean_log10_MAE": _approx(np.mean(model_err - base_err)),
            "equal_connected_group_macro_model_minus_mean_log10_MAE": _approx(np.mean(per_group)),
            "heuristic_paired_group_resample_95pct_interval": [
                _approx(x) for x in np.quantile(sample_means, [0.025, 0.975])
            ],
            "positive_difference_means_model_worse": True,
            "is_independent_material_statistical_CI": False,
            "paired_source_groups": len(per_group),
            "group_bootstraps": PAIRED_BOOTSTRAPS,
        }
    return row


def inspect_actual_failure_causes(original: Path, prior: dict, ephemeral: dict, baseline: dict, predictions: dict, *, strict_official=True):
    x, y, groups = ephemeral["x"], ephemeral["y"], ephemeral["groups"]
    if (
        x.ndim != 2 or x.shape != (len(y), 118) or
        len(groups) != len(y) or len(y) < 10 or
        set(predictions) != set(MODELS) or
        not all(p.shape == y.shape and np.isfinite(p).all() for p in predictions.values())
    ):
        raise ValueError("unmatched prior actual source, model or prediction population")
    if (
        prior["out_of_fold_numeric_source_records_scored"] != len(y)
        or baseline["real_out_of_fold_source_record_predictions_per_model"] != len(y)
        or baseline["source_DOI_formula_connected_groups_scored"] != len(set(groups))
        or prior["original_official_test_reserved_unread"] != baseline["original_official_test_reserved_unread"]
        or (strict_official and prior["original_official_test_reserved_unread"] != 121)
        or prior["original_official_test_reserved_unread"] < 1
        or baseline["official_public_TEST_predictions"] != 0
        or prior["scientific_qualification_authorized"] is not False
    ):
        raise ValueError("real previous source/fold-scoring test embargo drift")

    members = Counter(groups)
    sizes = sorted(members.values(), reverse=True)
    n = len(y)
    concentration = {
        "original_scored_public_source_records": n,
        "connected_DOI_formula_groups": len(sizes),
        "largest_connected_group_source_row_count": sizes[0],
        "top_5_groups_source_rows": sum(sizes[:5]),
        "top_5_groups_fraction_of_scored_source_records": _approx(sum(sizes[:5]) / n),
        "singleton_connected_groups": sum(x == 1 for x in sizes),
        "source_row_group_size_kish_effective_count": _approx(n * n / sum(v * v for v in sizes)),
        "independent_material_count_authenticated": None,
        "group_components_are_not_independent_experimental_samples": True,
    }
    folds = []
    seen = set()
    for fi, indices in enumerate(ephemeral["fold_indices"]):
        ids = np.asarray(indices, dtype=int)
        if set(map(int, ids)) & seen or (ids < 0).any() or (ids >= n).any():
            raise ValueError("frozen fold overlap or out of range")
        seen.update(map(int, ids))
        if len(ids) != prior["grouped_folds"][fi]["heldout_record_count"]:
            raise ValueError("frozen 0146 fold drift")
        folds.append({
            "fold": fi + 1,
            "source_records": len(ids),
            "connected_groups": len({groups[i] for i in ids}),
            "observed_public_source_log10_mean": _approx(np.mean(y[ids])),
            "observed_public_source_log10_sd": _approx(np.std(y[ids])),
            "observed_public_source_log10_min": _approx(np.min(y[ids])),
            "observed_public_source_log10_max": _approx(np.max(y[ids])),
            "MAE": {
                name: _approx(np.mean(np.abs(predictions[name][ids] - y[ids])))
                for name in MODELS
            },
        })
    if seen != set(range(n)):
        raise ValueError("some source records omitted from frozen folds")

    out = {
        "schema_version": SCHEMA,
        "diagnostic_scope": "REAL_PUBLIC_OBELIX_TRAIN_OOF_FAILURE_CAUSE_AUDIT",
        "underlying_original_source": prior["original_upstream_commit"],
        "original_processed_csv_sha256": prior["source_processed_csv_sha256"],
        "original_raw_workbook_sha256": prior["original_raw_workbook_sha256"],
        "original_official_train_count": prior["original_source_train_count"],
        "official_public_TEST_reserved_unread": prior["original_official_test_reserved_unread"],
        "original_censored_upper_bound_source_records_excluded": prior["original_raw_censored_upper_bounds_excluded"],
        "original_public_TRAIN_numeric_source_rows_predicted_per_model": n,
        "original_identity_connected_groups": len(sizes),
        "fixed_0146_folds_and_original_0147_models_unchanged": True,
        "source_group_size_concentration": concentration,
        "per_fold_error_and_raw_label_spread": folds,
        "predeclared_anion_element_presence_proxy_bins": _family_scores(x, y, groups, predictions),
        "paired_model_minus_mean_group_error_diagnostics": _paired_group_delta(y, groups, predictions),
        "author_protocol_difference": _publisher_protocol_inspection(original),
        "model_global_log10_MAE": {
            name: _approx(np.mean(np.abs(predictions[name] - y)))
            for name in MODELS
        },
        "new_models_trained_or_hyperparameters_selected_after_seeing_results": False,
        "raw_measurement_paper_temperature_phase_verified": False,
        "scientific_structural_family_certified": False,
        "new_external_blind_specimens": 0,
        "actual_independent_physical_specimen_count": None,
        "official_public_TEST_predictions": 0,
        "scientific_claim_GO": False,
        "P0_01_status": "BLOCKED",
        "P0_02_status": "BLOCKED",
        "P0_03_status": "BLOCKED",
    }
    if (
        out["model_global_log10_MAE"]["random_forest"] != baseline["out_of_fold_metrics"]["random_forest"]["log10_MAE"]
        or out["model_global_log10_MAE"]["mlp"] != baseline["out_of_fold_metrics"]["mlp"]["log10_MAE"]
        or out["model_global_log10_MAE"]["ridge_0146"] != 2.29511512 and n == 449
        or out["model_global_log10_MAE"]["training_fold_mean_0146"] != baseline["out_of_fold_metrics"]["training_fold_mean_0146"]["log10_MAE"]
    ):
        raise ValueError("actual previously published model baseline scores drift")
    return out


def run_original_failure_audit(original: Path, output_dir: Path):
    root = Path(original).resolve(strict=True)
    out = Path(output_dir).resolve()
    if out.exists() or out == root or root in out.parents:
        raise ValueError("source must remain immutable and output new")
    with tempfile.TemporaryDirectory(prefix="rhombus-0148-source-private-") as temp:
        t = Path(temp)
        prior, ephemeral = run_official_original_oof(root, t / "prior-real-fold", return_internal=True)
        baseline, predictions = evaluate_frozen_baselines(prior, ephemeral, return_internal=True)
        report = inspect_actual_failure_causes(root, prior, ephemeral, baseline, predictions)
        out.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".rhombus-0148-out-", dir=out.parent))
        try:
            (stage / "real_source_failure_aggregate.json").write_bytes(_json_bytes(report) + b"\n")
            if out.exists():
                raise ValueError("output unexpectedly exists")
            stage.rename(out)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-obelix-checkout", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        report = run_original_failure_audit(args.original_obelix_checkout, args.output_dir)
    except (ValueError, OSError, TypeError) as exc:
        p.error(str(exc))
    print(json.dumps({
        "source_rows": report["original_public_TRAIN_numeric_source_rows_predicted_per_model"],
        "connected_groups": report["original_identity_connected_groups"],
        "top5_group_fraction": report["source_group_size_concentration"]["top_5_groups_fraction_of_scored_source_records"],
        "MAE": report["model_global_log10_MAE"],
        "science_GO": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
