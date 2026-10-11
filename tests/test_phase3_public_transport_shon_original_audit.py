"""0137 Shon primary JSON source authenticity and non-redistribution."""
from __future__ import annotations

import hashlib
import json

import pytest

from scripts.science.public_transport_shon_original_audit import (
    SCHEMA, _git_blob_sha, inspect_shon_primary_json,
)


def fixture():
    return (b'{"Ionical Conductivity": [{"compound": "Li3N",'
            b' "sample_source": "10.1234/example", "sigma": 0.00001},'
            b' {"compound": "Na3PS4", "sigma": null}], "metadata":'
            b' {"count": 2, "notes": "raw third-party data"}}')


def inspect(raw):
    return inspect_shon_primary_json(
        raw, exact_blob_sha1=_git_blob_sha(raw),
        expected_size=len(raw),
    )


def test_git_blob_identity_and_no_original_measurements_republished():
    raw = fixture()
    report = inspect(raw)
    assert report["schema_version"] == SCHEMA
    assert report["original_git_blob_sha1_verified"] == _git_blob_sha(raw)
    assert report["original_file_sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["original_file_size_bytes"] == len(raw)
    assert report["original_json_top_level_type"] == "OBJECT"
    assert report["original_json_top_level_entry_count_NOT_MEASUREMENT_COUNT"] == 2
    assert report["original_json_total_value_nodes"] > 5
    assert report["original_json_type_counts"]["arrays"] > 0
    assert report["original_json_type_counts"]["nulls"] == 1
    assert report["confirmed_experimental_Li_solid_state_measurements"] is None
    assert report["identical_to_obelix_sample_overlap_count"] is None
    assert report["newly_qualified_independent_materials"] == 0
    assert report["original_source_rows_republished"] is False
    assert report["data_license_permission_to_republish_verified"] is False
    assert report["official_scientific_benchmark_scoring_authorized"] is False
    s = json.dumps(report)
    for secret in ("Li3N", "Na3PS4", "10.1234/example", "raw third-party"):
        assert secret not in s


def test_source_tampering_rejected_even_if_json_valid():
    raw = fixture()
    modified = raw.replace(b"Li3N", b"Li3P")
    assert len(raw) == len(modified)
    with pytest.raises(ValueError, match="blob SHA"):
        inspect_shon_primary_json(
            modified, exact_blob_sha1=_git_blob_sha(raw),
            expected_size=len(raw),
        )


def test_invalid_json_rejected_after_valid_source_blob_attestation():
    raw = b'{"items": [NaN]}'
    with pytest.raises(ValueError, match="non-JSON numeric"):
        inspect(raw)
    with pytest.raises(ValueError, match="malformed"):
        inspect(b'{broken')


def test_top_level_scalar_rejected():
    with pytest.raises(ValueError, match="top-level"):
        inspect(b'"not a dataset"')


def test_nesting_budget_is_enforced():
    raw = b"[" * 34 + b"0" + b"]" * 34
    with pytest.raises(ValueError, match="resource budget"):
        inspect(raw)


def test_byte_length_and_sha_are_required():
    raw = fixture()
    with pytest.raises(ValueError, match="byte size"):
        inspect_shon_primary_json(
            raw, exact_blob_sha1=_git_blob_sha(raw),
            expected_size=len(raw) - 1,
        )
    with pytest.raises(ValueError, match="blob SHA"):
        inspect_shon_primary_json(
            raw, exact_blob_sha1="0" * 40,
            expected_size=len(raw),
        )


def test_array_root_support_and_no_sample_claims():
    raw = b'[{"doi": "10.1/a"}, {"doi": "10.1/b"}]'
    report = inspect(raw)
    assert report["original_json_top_level_type"] == "ARRAY"
    assert report["original_json_top_level_entry_count_NOT_MEASUREMENT_COUNT"] == 2
    assert report["newly_qualified_independent_materials"] == 0
