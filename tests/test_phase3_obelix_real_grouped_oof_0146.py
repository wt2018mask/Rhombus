"""Synthetic adversarial tests; actual 0146 metrics require original source CI."""
import copy
import math

import numpy as np
import pytest

from scripts.science.obelix_real_grouped_oof_0146 import (
    SCHEMA, FOLDS, _composition, _positive_log10, _ridge_predict,
    evaluate_original_obelix_train,
)
from scripts.science.obelix_censor_aware_policy import POINT, CENSOR, UNRESOLVED


def fixture():
    # Artificial public TRAIN records, not real material measurements.
    elements = [
        "O", "S", "N", "P", "F", "Cl", "Br", "I", "Se", "Te", "As", "Si", "Ge",
        "B", "C", "Al", "Ga", "In", "Zn", "Mg", "Ca", "Sr", "Ba", "Ti", "Zr",
        "Hf", "V", "Nb", "Ta", "Mo", "W", "Mn", "Fe", "Co", "Ni",
    ]
    records, labels = [], []
    for i, element in enumerate(elements):
        sid = "s%03d" % i
        records.append({
            "source_entry_id": sid,
            "official_split": "TRAIN",
            "reported_composition": "Li2" + element,
            "reference_dois": ["10.5555/artificial-%02d" % i],
        })
        labels.append({
            "source_entry_id": sid,
            "official_original_split": "TRAIN",
            "raw_measurement_policy_kind": POINT,
            "source_numeric_metadata_s_per_cm": str(10**(-(i%6+2))),
            "point_estimate_benchmark_scoring_permitted": False,
            "scientific_material_qualified": False,
            "processed_surrogate_must_not_be_scored": False,
        })
    # Reserved public TEST row must never enter source label or feature data.
    records.append({
        "source_entry_id": "nevertest",
        "official_split": "TEST",
        "reported_composition": None,
        "reference_dois": "forbidden-secret",
        "reported_ionic_conductivity_text": "UNREAD_PRIVATE_TRUTH",
    })
    return records, labels


def report(records=None, labels=None):
    if records is None or labels is None:
        records, labels = fixture()
    return evaluate_original_obelix_train(records, labels, strict_official=False)


def test_35_actual_synthetic_record_grouped_predictions_are_computed():
    r = report()
    assert r["schema_version"] == SCHEMA
    assert r["evaluation"] == "PUBLIC_SOURCE_DIAGNOSTIC_REAL_GROUPED_OUT_OF_FOLD"
    assert r["original_source_train_count"] == 35
    assert r["original_official_test_reserved_unread"] == 1
    assert r["out_of_fold_numeric_source_records_scored"] == 35
    assert r["shared_doi_formula_connected_components_scored"] == 35
    assert len(r["grouped_folds"]) == FOLDS
    assert sum(v["heldout_record_count"] for v in r["grouped_folds"]) == 35
    assert all(v["group_leakage_count"] == 0 for v in r["grouped_folds"])
    assert r["trained_ridge_oof_metrics"]["log10_MAE"] >= 0
    assert math.isfinite(r["trained_ridge_oof_metrics"]["log10_RMSE"])
    assert r["official_public_TEST_predictions"] == 0
    assert r["model_is_MACE_transport_prediction"] is False
    assert r["P0_01_status"] == r["P0_02_status"] == r["P0_03_status"] == "BLOCKED"
    assert r["scientific_qualification_authorized"] is False


def test_original_source_grouping_is_reproducible():
    a, b = report(), report()
    assert a == b


def test_common_source_doi_connects_distinct_formulae():
    records, labels = fixture()
    records[0]["reference_dois"] = ["10.5555/shared"]
    records[1]["reference_dois"] = ["10.5555/shared"]
    result = report(records, labels)
    assert result["shared_doi_formula_connected_components_scored"] == 34
    assert result["all_folds_have_zero_group_identity_leakage"] is True


def test_transitive_bridge_through_censored_source_record():
    records, labels = fixture()
    # s000 connected to censored s001 via DOI, s001 to s002 via formula.
    records[0]["reference_dois"] = ["10.5555/together"]
    records[1]["reference_dois"] = ["10.5555/together"]
    records[1]["reported_composition"] = records[2]["reported_composition"]
    labels[1]["raw_measurement_policy_kind"] = CENSOR
    labels[1]["source_numeric_metadata_s_per_cm"] = None
    labels[1]["processed_surrogate_must_not_be_scored"] = True
    result = report(records, labels)
    assert result["original_raw_censored_upper_bounds_excluded"] == 1
    assert result["out_of_fold_numeric_source_records_scored"] == 34
    assert result["shared_doi_formula_connected_components_scored"] == 33
    assert result["original_numeric_but_invalid_excluded"] == 0


def test_original_censoring_is_not_point_target_even_with_surrogate_value():
    records, labels = fixture()
    labels[0]["raw_measurement_policy_kind"] = CENSOR
    labels[0]["source_numeric_metadata_s_per_cm"] = "1e-15"
    labels[0]["processed_surrogate_must_not_be_scored"] = True
    labels[1]["raw_measurement_policy_kind"] = UNRESOLVED
    labels[1]["source_numeric_metadata_s_per_cm"] = None
    r = report(records, labels)
    assert r["out_of_fold_numeric_source_records_scored"] == 33
    assert r["original_raw_censored_upper_bounds_excluded"] == 1
    assert r["original_raw_unresolved_excluded"] == 1
    assert r["original_raw_point_source_records"] == 33


@pytest.mark.parametrize("field, value", [
    ("source_numeric_metadata_s_per_cm", "NaN"),
    ("source_numeric_metadata_s_per_cm", "-1"),
    ("source_numeric_metadata_s_per_cm", ""),
    ("source_numeric_metadata_s_per_cm", None),
    ("source_numeric_metadata_s_per_cm", "Infinity"),
])
def test_invalid_numerics_are_counted_not_scored(field, value):
    records, labels = fixture()
    labels[0][field] = value
    r = report(records, labels)
    assert r["original_numeric_but_invalid_excluded"] == 1
    assert r["out_of_fold_numeric_source_records_scored"] == 34


def test_unparseable_composition_excluded_from_numerator_not_denominator():
    records, labels = fixture()
    records[0]["reported_composition"] = "NOPE???"
    r = report(records, labels)
    assert r["original_numeric_but_formula_unparseable"] == 1
    assert r["out_of_fold_numeric_source_records_scored"] == 34
    assert r["original_source_train_count"] == 35


@pytest.mark.parametrize("mutator", [
    lambda x, y: x.append(copy.deepcopy(x[0])),
    lambda x, y: x[0].update(official_split="TEST"),
    lambda x, y: x[0].update(official_split="DEVELOPMENT"),
    lambda x, y: x[0].update(reference_dois=["not-doi"]),
    lambda x, y: x[0].update(reference_dois=None),
    lambda x, y: y[0].update(official_original_split="TEST"),
    lambda x, y: y[0].update(point_estimate_benchmark_scoring_permitted=True),
    lambda x, y: y[0].update(scientific_material_qualified=True),
    lambda x, y: y[0].update(processed_surrogate_must_not_be_scored=True),
    lambda x, y: y[0].update(raw_measurement_policy_kind="SYNTHETIC_TEST_LABEL"),
    lambda x, y: y[1].update(source_entry_id=y[0]["source_entry_id"]),
])
def test_invalid_original_split_source_measurement_or_fake_science_fails(mutator):
    x, y = fixture()
    mutator(x, y)
    with pytest.raises(ValueError):
        report(x, y)


def test_less_than_five_identity_groups_not_pseudoreplicated():
    x, y = fixture()
    for i, row in enumerate(x[:-1]):
        row["reference_dois"] = ["10.5555/group-%d" % (i % 4)]
    with pytest.raises(ValueError, match="non-overlapping DOI/formula groups"):
        report(x, y)


def test_public_test_field_contents_never_appear_in_report():
    r = report()
    raw = str(r)
    assert "UNREAD_PRIVATE_TRUTH" not in raw
    assert "nevertest" not in raw
    assert "10.5555/artificial" not in raw
    assert "Li2O" not in raw


def test_fixed_ridge_does_not_look_at_test_statistics():
    X_train = np.zeros((12,118), dtype=float)
    X_train[:6,0] = 1
    X_hold = np.zeros((2,118), dtype=float)
    yy = np.arange(12, dtype=float)
    a = _ridge_predict(X_train, yy, X_hold)
    b = _ridge_predict(X_train, yy, X_hold)
    assert np.isfinite(a).all()
    assert np.array_equal(a, b)


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-1", "0", "", "<1e-6", None])
def test_nonpositive_censor_and_nonfinite_never_numeric_labels(raw):
    assert _positive_log10(raw) is None


def test_species_parser_and_identity_descriptor_dim():
    formula, v = _composition("Li2O")
    assert formula == "Li2O"
    assert v.shape == (118,)
    assert sum(v) == pytest.approx(1.0)
    assert _composition("INVALID???") is None
