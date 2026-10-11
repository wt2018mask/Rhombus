"""0136 conservative primary Caltech sample/measurement metadata review tests."""
from __future__ import annotations

import hashlib
import json

import pytest

from scripts.science.public_transport_benchmark import build_public_benchmark
from scripts.science.public_transport_quality_funnel import (
    SCHEMA, build_external_quality_funnel,
)
from tests.test_phase3_public_transport_benchmark import fixture, registry


def synthetic_source():
    return (
        b"compound,icsd_collectioncode,conductivity_doi,conductivity_siemens_per_cm,lowest_extrapolation_temperature_K\n"
        b"Li3N,551,https://doi.org/10.1234/beta,1e-9,300\n"
        b"Li2S,555,10.1234/new,2e-3,\n"
        b"Li2S,555,10.1234/new,3e-3,298\n"
    )


def sample(tmp_path):
    rows, summary = build_public_benchmark(
        *fixture(tmp_path), registry(), require_official=False
    )
    return rows, summary


def run(blob, reference, *, official=False):
    return build_external_quality_funnel(
        blob, reference[0], reference[1], require_official=official,
        expected_source_md5=hashlib.md5(blob, usedforsecurity=False).hexdigest(),
        expected_source_rows=3,
    )


def test_funnel_does_not_claim_independent_materials(tmp_path):
    result = run(synthetic_source(), sample(tmp_path))
    assert result["schema_version"] == SCHEMA
    assert result["source_original_records"] == 3
    assert result["source_reported_formula_string_count"] == 2
    assert result["source_reported_DOI_token_count"] == 2
    assert result["source_formula_icsd_proxy_key_count"] == 2
    assert result["source_formula_icsd_doi_proxy_key_count"] == 2
    assert result["repeated_exact_formula_icsd_doi_proxy_rows"] == 1
    counts = result["data_quality_counters"]
    assert counts["source_record_without_exact_DOI_overlap"] == 2
    assert counts["doi_overlap_with_public_obelix_train"] == 1
    assert counts["positive_finite_lowest_extrapolation_K"] == 2
    assert counts["extrapolation_temperature_missing_or_nonpositive"] == 1
    assert counts["positive_finite_original_source_conductivity"] == 3
    assert counts["complete_five_field_metadata_review_candidates"] == 2
    assert counts["complete_five_fields_no_exact_obelix_train_doi_signal"] == 1
    assert result["new_scientifically_qualified_materials"] == 0
    assert result["independent_material_identity_count"] is None
    assert result["certified_sample_bound_crystal_structure_count"] == 0
    assert result["certified_exact_measurement_temperature_count"] == 0
    assert result["source_reuse_rights_verified"] is False
    assert result["scientific_score_authorized"] is False


def test_only_aggregate_no_raw_caltech_values_or_public_test(tmp_path):
    blob = synthetic_source()
    result = run(blob, sample(tmp_path))
    report = json.dumps(result)
    for sensitive in ["10.1234/beta", "10.1234/new", "Li3N", "Li2S"]:
        # No row-level external data or original source identifiers emitted.
        assert sensitive not in report
    assert result["public_test_identity_and_truth_exposed"] is False
    assert result["external_original_rows_redistributed"] is False


@pytest.mark.parametrize("bad_value,column", [
    ("NaN", "conductivity_siemens_per_cm"),
    ("Infinity", "conductivity_siemens_per_cm"),
    ("-3e-7", "conductivity_siemens_per_cm"),
    ("0", "conductivity_siemens_per_cm"),
    ("<1e-10", "conductivity_siemens_per_cm"),
    ("UNKNOWN", "lowest_extrapolation_temperature_K"),
    ("-273", "lowest_extrapolation_temperature_K"),
])
def test_bad_measurements_are_flagged_not_fabricated(tmp_path, bad_value, column):
    reference = sample(tmp_path)
    lines = synthetic_source().decode().splitlines()
    header = lines[0].split(",")
    fields = lines[1].split(",")
    fields[header.index(column)] = bad_value
    rows = [lines[0], ",".join(fields), *lines[2:]]
    raw = ("\n".join(rows) + "\n").encode()
    report = run(raw, reference)
    flags = report["data_quality_counters"]
    if column == "conductivity_siemens_per_cm":
        assert flags["unparseable_or_nonpositive_conductivity"] == 1
        assert flags["positive_finite_original_source_conductivity"] == 2
    else:
        assert flags["extrapolation_temperature_missing_or_nonpositive"] == 2
        assert flags["positive_finite_lowest_extrapolation_K"] == 1
    assert report["scientific_score_authorized"] is False


def test_source_body_change_with_official_checksum_is_blocked(tmp_path):
    with pytest.raises(ValueError, match="checksum"):
        build_external_quality_funnel(
            synthetic_source(), *sample(tmp_path), require_official=True
        )


def test_train_test_promotion_cannot_be_bypassed_by_rehash(tmp_path):
    rows, summary = sample(tmp_path)
    rows[0]["partition"] = "ORIGINAL_PUBLIC_TEST"
    changed = b"".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode() + b"\n" for row in rows
    )
    summary["public_train_records_sha256"] = hashlib.sha256(changed).hexdigest()
    with pytest.raises(ValueError, match="public test contamination"):
        run(synthetic_source(), (rows, summary))


def test_repeated_source_rows_cannot_be_counted_as_independent_samples(tmp_path):
    result = run(synthetic_source(), sample(tmp_path))
    assert result["source_original_records"] == 3
    assert result["repeated_exact_formula_icsd_doi_proxy_rows"] == 1
    assert result["independent_material_identity_count"] is None
    assert result["new_external_blind_materials"] == 0


def test_exact_0135_reference_hash_failure(tmp_path):
    rows, summary = sample(tmp_path)
    rows[0]["numeric_source_unverified_s_per_cm"] = "999"
    with pytest.raises(ValueError, match="hash"):
        run(synthetic_source(), (rows, summary))
