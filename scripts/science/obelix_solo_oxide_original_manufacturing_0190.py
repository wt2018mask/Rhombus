"""0190: author-bound O_ONLY Sn-garnet 25 C TOTAL synthesis choice falsification.

A NEW publicly exposed article DOI (not prospective blind) contributes four
nominal formulas with dual-step/mono-step preparation states. Original author
JATS identity, Table 2, units and values are checked before scoring. Frozen
model configurations are REFIT only to original OBELiX TRAIN with a full
connected DOI/formula exclusion, and all 121 official TEST remain opaque.

Selection audit deliberately does NOT train a process-aware model; equal
composition produces equal scores for each manufacturing route.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import tempfile
from pathlib import Path

import numpy as np

from rhombus.qualification.obelix_benchmark_intake import (
    SOURCE_COMMIT, _json_bytes, build_obelix_benchmark_intake,
)
from scripts.science.obelix_real_grouped_oof_0146 import (
    _composition, run_official_original_oof,
)
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_solo_family_specialists_0184 import RIDGE_ALPHA
from scripts.science.obelix_solo_oxide_five_doi_0188 import table_source, embargo
from scripts.science.obelix_solo_oxide_jats_three_doi_0187 import get_jats, norm, simple

SCHEMA = "rhombus-0190-solo-oxide-sn-garnet-manufacturing-choice-v1"
DOI = "10.1021/acsorginorgau.5c00021"
PMC = "PMC12142435"
FORMULAS = (
    "Li6La3Sn0.5Nb0.5Ta0.5Hf0.5O12",
    "Li6.5La3Zr0.5Sn0.5Ta0.5Hf0.5O12",
    "Li6.5La3Zr0.5Nb0.5Sn0.5Hf0.5O12",
    "Li6La3Zr0.5Nb0.5Ta0.5Sn0.5O12",
)
# Exact original author Table 2 25 C TOTAL (S/cm); inspect source bytes again
# at each execution; these constants are tamper detection, not training labels.
AUTHOR_TOTAL = {
    "DS1": 1.41e-4, "DS2": 4.57e-5,
    "DS3": 2.10e-4, "DS4": 1.62e-4,
    "MS1": 8.54e-5, "MS2": 1.75e-4,
    "MS3": 2.12e-4, "MS4": 9.38e-5,
}
MODELS = ("POOLED_RF", "O_ONLY_RF", "O_ONLY_RIDGE", "O_ONLY_TRAIN_MEAN")


def conductivity_cell(value: str) -> float:
    """Parse only a complete finite conductivity cell, never adjacent E_a."""
    v = norm(value).replace(" ", "").replace("^", "")
    if re.fullmatch(r"\d+(?:\.\d+)?[eE]-\d+", v):
        number = float(v)
    else:
        match = re.fullmatch(r"(\d+(?:\.\d+)?)[x*]10-([0-9]+)", v)
        if match is None:
            raise ValueError("invalid original 25 C total conductivity cell")
        number = float(match.group(1)) * 10 ** (-int(match.group(2)))
    if not math.isfinite(number) or not 0 < number < 1:
        raise ValueError("nonphysical conductivity cell")
    return number


def read_author_table(blob: bytes):
    science, caption, table, meta = table_source(blob, DOI, PMC, 2)
    if not ("monostep" in simple(science) and "dualstep" in simple(science)):
        raise ValueError("original two-route manufacturing methods absent")
    if "conductivity" not in simple(caption):
        raise ValueError("original Table 2 conductivity caption not authenticated")
    header = [row for row in table if row and simple(row[0]) == "sample"]
    if len(header) != 1 or len(header[0]) < 2:
        raise ValueError("original Table 2 sample header missing")
    target = simple(header[0][1])
    if not all(t in target for t in ("total", "conductivity", "25c")):
        raise ValueError("original endpoint is not 25 C TOTAL conductivity")
    # A substring check for "scm1" would also accept *mS* cm-1 (1000x error).
    # Require bare SI S, not mS/uS, from the actual author column header.
    raw_unit = norm(header[0][1])
    if re.search(r"(?<![A-Za-zµμ])S\\s*(?:/)?\\s*cm", raw_unit) is None:
        raise ValueError("original unscaled S/cm unit missing or ambiguous")
    found = {}
    for row in table:
        if not row or not re.fullmatch(r"(DS|MS)[1-4]", norm(row[0]).replace(" ", "")):
            continue
        name = norm(row[0]).replace(" ", "")
        if name in found or len(row) < 2:
            raise ValueError("repeated or truncated original sample identity")
        value = conductivity_cell(row[1])
        if not math.isclose(value, AUTHOR_TOTAL[name], rel_tol=1e-8, abs_tol=1e-14):
            raise ValueError("source value swapped, mutated or unit drift")
        found[name] = value
    if set(found) != set(AUTHOR_TOTAL):
        raise ValueError("original 8 condition table incomplete")
    records = []
    for label in AUTHOR_TOTAL:
        i = int(label[-1]) - 1
        route = "DUAL_STEP" if label.startswith("DS") else "MONO_STEP"
        records.append({
            "source_doi": DOI, "sample_code": label,
            "nominal_formula": FORMULAS[i], "manufacturing_route": route,
            "temperature_C": 25, "observable": "TOTAL_IONIC_CONDUCTIVITY_S_CM",
            "conductivity_S_cm": found[label],
            "nominal_not_final_measured_pellet_formula": True,
        })
    meta.update({"source_conditions": 8, "distinct_nominal_formulas": 4,
                 "measured_endpoint": "25C_TOTAL", "source_DOI": DOI,
                 "original_measurement_not_individual_pellet_certification": True})
    return records, meta


def score_original_train(prior, arrays, records, conditions, metadata):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if (prior["original_upstream_commit"] != SOURCE_COMMIT
        or prior["original_source_train_count"] != 478
        or prior["original_official_test_reserved_unread"] != 121
        or prior["original_raw_censored_upper_bounds_excluded"] != 29
        or prior["scientific_qualification_authorized"] is not False):
        raise ValueError("original OBELiX TRAIN-only contract changed")
    if metadata["source_DOI"] != DOI or len(conditions) != 8:
        raise ValueError("unknown source or cohort cardinality")
    rows = [(r["source_doi"], r["sample_code"], r["nominal_formula"],
             r["conductivity_S_cm"]) for r in conditions]
    x, y = np.asarray(arrays["x"]), np.asarray(arrays["y"])
    if x.shape != (449, 118) or y.shape != (449,):
        raise ValueError("original numeric TRAIN shape drift")
    eligible, matched, excluded = embargo(records, arrays, rows)
    train = np.where(eligible)[0]
    oxide = np.array([i for i in train if _family_proxy(x[i]) == "O_ONLY"], dtype=int)
    if len(train) < 250 or len(oxide) < 100:
        raise ValueError("source-separated training too small")
    feats = np.asarray([_composition(r[2])[1] for r in rows])
    if feats.shape != (8, 118) or any(_family_proxy(v) != "O_ONLY" for v in feats):
        raise ValueError("invalid O_ONLY formula source")
    ytruth = np.log10(np.asarray([r[3] for r in rows]))
    predictions = {
        "POOLED_RF": RandomForestRegressor(**RF_PARAMS).fit(x[train], y[train]).predict(feats),
        "O_ONLY_RF": RandomForestRegressor(**RF_PARAMS).fit(x[oxide], y[oxide]).predict(feats),
        "O_ONLY_RIDGE": make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
            .fit(x[oxide], y[oxide]).predict(feats),
        "O_ONLY_TRAIN_MEAN": np.full(8, float(y[oxide].mean())),
    }
    evaluations = {}
    for name, pred in predictions.items():
        if not np.isfinite(pred).all():
            raise ValueError("nonfinite model output")
        deviations = np.abs(pred - ytruth)
        tied_pairs = 0
        for i in range(4):
            if not np.isclose(pred[i], pred[i + 4], atol=1e-12, rtol=0):
                raise ValueError("composition-only model unexpectedly routes by manufacture")
            tied_pairs += 1
        evaluations[name] = {
            "MAE_log10_S_cm": round(float(deviations.mean()), 8),
            "four_same_composition_route_choice_ties": tied_pairs,
        }
    route_winners = {}
    for i in range(4):
        ds, ms = conditions[i], conditions[i + 4]
        if ds["nominal_formula"] != ms["nominal_formula"]:
            raise ValueError("author sample pairing mismatch")
        route_winners[FORMULAS[i]] = ds["sample_code"] if ds["conductivity_S_cm"] > ms["conductivity_S_cm"] else ms["sample_code"]
    return {
        "schema_version": SCHEMA, "original_source": metadata,
        "source_DOI_count": 1, "actual_author_conditions": 8,
        "distinct_nominal_formulas": 4,
        "manufacturing_route_descriptor": ["DUAL_STEP", "MONO_STEP"],
        "route_optimal_authored_labels_visible": route_winners,
        "scoreable_model_comparison": evaluations,
        "original_TRAIN_count": 478, "original_numeric_TRAIN": 449,
        "TRAIN_numeric_after_embargo": len(train),
        "TRAIN_O_ONLY_after_embargo": len(oxide),
        "matched_TRAIN_source_identities": matched,
        "excluded_connected_TRAIN_components": excluded,
        "official_TEST_reserved_unread": 121,
        "official_TEST_fields_parsed": False,
        "model_hyperparameters_frozen_before_this_DOI_scoring": True,
        "process_aware_model_trained": False,
        "unique_unseen_DOI_generalization_proven": False,
        "prospective_blind": False, "physical_independent_pellet_certified": False,
        "O_ONLY_production_enabled": False, "scientific_GO": False,
        "P0_01": "BLOCKED", "P0_02": "BLOCKED", "P0_03": "BLOCKED",
        "next_action": "0191-SOLO-O_ONLY-TRAIN_ONLY_PROCESS_AWARE_MODEL_AND_HELDOUT_SOURCE",
    }


def run(original_checkout: Path, output_dir: Path):
    if output_dir.exists() or original_checkout.resolve(strict=True) in output_dir.resolve().parents:
        raise ValueError("source and output path must be distinct")
    with tempfile.TemporaryDirectory(prefix="rhombus-0190-") as td:
        prior, arr = run_official_original_oof(
            original_checkout.resolve(), Path(td) / "original", return_internal=True)
        train_records, _ = build_obelix_benchmark_intake(
            original_checkout.resolve(), expected_commit=SOURCE_COMMIT)
        source_rows, source_meta = read_author_table(get_jats(PMC))
        result = score_original_train(prior, arr, train_records, source_rows, source_meta)
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "0190_original_manufacturing_choice.json").write_bytes(
        _json_bytes(result) + b"\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-obelix-checkout", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.original_obelix_checkout, args.output_dir)
    print("0190_ACTUAL_ORIGINAL_AUTHOR_SCIENCE", json.dumps({
        "doi_count": result["source_DOI_count"],
        "conditions": result["actual_author_conditions"],
        "models": result["scoreable_model_comparison"],
        "scientific_GO": result["scientific_GO"],
    }, sort_keys=True))
