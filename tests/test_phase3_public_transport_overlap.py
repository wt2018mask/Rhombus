"""Source-bound aggregate-only cross-dataset DOI signals; no false independence."""
from __future__ import annotations

import hashlib
import json

import pytest

from scripts.science.public_transport_overlap import (
    SCHEMA, inspect_caltech_vs_obelix_train,
)
from scripts.science.public_transport_benchmark import build_public_benchmark
from tests.test_phase3_public_transport_benchmark import fixture, registry


def data():
    return (
        b"compound,icsd_collectioncode,conductivity_doi,conductivity_siemens_per_cm,lowest_extrapolation_temperature_K\n"
        b"Li3N,551,https://doi.org/10.1234/beta,1e-9,320\n"
        b"LiCl,552,10.1234/new,3e-5,298\n"
    )


def test_overlap_is_aggregate_only_and_never_counts_new_materials(tmp_path):
    r, summ = build_public_benchmark(
        *fixture(tmp_path), registry(), require_official=False)
    blob = data()
    report = inspect_caltech_vs_obelix_train(
        blob, r, summ,
        expected_caltech_md5=hashlib.md5(blob, usedforsecurity=False).hexdigest(),
        expected_caltech_rows=2,
    )
    assert report["schema_version"] == SCHEMA
    assert report["source_caltech_original_rows"] == 2
    assert report["source_obelix_original_train_records"] == 3
    assert report["number_of_exact_distinct_DOI_tokens_shared"] == 1
    assert report["caltech_rows_with_exact_obelix_train_DOI_signal"] == 1
    assert report["caltech_rows_without_exact_obelix_train_DOI_signal"] == 1
    assert report["source_caltech_distinct_raw_formula_strings"] == 2
    assert report["number_of_source_temperature_metadata_numeric"] == 2
    assert report["inferred_independent_new_materials"] is None
    assert report["scientifically_qualified_materials_added"] == 0
    assert report["source_raw_records_redistributed"] is False
    assert report["source_DOI_tokens_disclosed"] is False
    assert not report["scientific_score_authorized"]
    serialized = json.dumps(report)
    assert "10.1234/new" not in serialized
    assert "10.1234/beta" not in serialized
    assert "Li3N" not in serialized


def test_altered_public_train_original_rows_rejected_even_if_digest_rebound(tmp_path):
    rows, summ = build_public_benchmark(
        *fixture(tmp_path), registry(), require_official=False)
    rows[0]["partition"] = "PUBLIC_TEST"
    tampered = b"".join(json.dumps(r, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":")).encode() + b"\n" for r in rows)
    summ["public_train_records_sha256"] = hashlib.sha256(tampered).hexdigest()
    with pytest.raises(ValueError, match="original TRAIN|contamination"):
        inspect_caltech_vs_obelix_train(
            data(), rows, summ,
            expected_caltech_md5=hashlib.md5(data(), usedforsecurity=False).hexdigest(),
            expected_caltech_rows=2)


def test_republished_external_source_is_rejected_by_original_md5(tmp_path):
    rows, summ = build_public_benchmark(*fixture(tmp_path), registry(),
                                        require_official=False)
    with pytest.raises(ValueError, match="checksum"):
        inspect_caltech_vs_obelix_train(data(), rows, summ)


def test_no_original_test_doi_matches_in_dev_reference(tmp_path):
    rows, summ = build_public_benchmark(*fixture(tmp_path), registry(),
                                        require_official=False)
    blob = (
        b"compound,icsd_collectioncode,conductivity_doi,conductivity_siemens_per_cm,lowest_extrapolation_temperature_K\n"
        b"Li6PS5Cl,552,10.1234/gamma,1e-6,298\n"
    )
    report = inspect_caltech_vs_obelix_train(
        blob, rows, summ,
        expected_caltech_md5=hashlib.md5(blob, usedforsecurity=False).hexdigest(),
        expected_caltech_rows=1,
    )
    assert report["caltech_rows_with_exact_obelix_train_DOI_signal"] == 0
    assert report["caltech_rows_without_exact_obelix_train_DOI_signal"] == 1
    assert report["inferred_independent_new_materials"] is None
