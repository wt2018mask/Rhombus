"""0138: original Shon schema metadata only; adversarial science non-promotion."""
import json
import pytest
from scripts.science.public_transport_shon_original_audit import _git_blob_sha
from scripts.science.public_transport_shon_schema_funnel import audit_shon_schema, SCHEMA

def run(rows):
    raw = json.dumps(rows).encode()
    return audit_shon_schema(raw, exact_blob_sha1=_git_blob_sha(raw), expected_size=len(raw))

def test_nested_field_names_report_no_original_data_or_scientific_go():
    report = run([
        {"container": [{"formula": "PRIVATE_Li3N", "ionic_conductivity": 0.0001,
                        "temperature": 300, "doi": "10.1/private",
                        "icsd": "RESTRICTED-ICSD", "method": "private_method"}]},
        {"formula": "Na3PS4", "doi": "10.2/private"},
        {"unknown": "secret"},
    ])
    assert report["schema_version"] == SCHEMA
    assert report["root_entries_NOT_material_or_measurement_count"] == 3
    assert report["root_entry_shapes"] == {"object": 3}
    assert report["all_six_indicators_NOT_qualified"] == 1
    assert report["no_recognized_indicators"] == 1
    assert report["field_name_indicator_presence_NOT_validated_values"]["chemistry"] == 2
    assert report["confirmed_independent_material_samples"] is None
    assert report["confirmed_experimental_Li_measurements"] is None
    assert report["newly_scientifically_qualified_materials"] == 0
    assert report["scientific_score_authorized"] is False
    assert report["original_rows_keys_and_values_republished"] is False
    report_text = json.dumps(report)
    for raw in ("Li3N", "Na3PS4", "RESTRICTED-ICSD", "10.1/private", "0.0001", "300"):
        assert raw not in report_text

def test_metadata_keys_do_not_validate_corrupt_measurements():
    report = run([{"ionicConductivity": "NOT A MEASUREMENT",
                   "temperature": None, "formula": None, "doi": None,
                   "cif": None, "experimentalMethod": None}])
    assert report["all_six_indicators_NOT_qualified"] == 1
    assert report["scientific_score_authorized"] is False
    assert report["confirmed_independent_material_samples"] is None

def test_no_leak_of_unrecognized_source_keys():
    r = run([{"super_secret_original_key": "secret value"}])
    assert "super_secret_original_key" not in str(r)
    assert r["no_recognized_indicators"] == 1

def test_root_shapes_do_not_equal_independent_samples():
    r = run([[{"conductivity": 1}], "opaque", None])
    assert r["root_entry_shapes"] == {"array": 1, "scalar_or_null": 2}
    assert r["confirmed_independent_material_samples"] is None

def test_attested_file_identity_must_match():
    raw = b'[{"formula":"Li"}]'
    with pytest.raises(ValueError, match="blob SHA"):
        audit_shon_schema(raw, exact_blob_sha1="0"*40, expected_size=len(raw))
    with pytest.raises(ValueError, match="byte size"):
        audit_shon_schema(raw, exact_blob_sha1=_git_blob_sha(raw),
                          expected_size=len(raw)+1)

def test_root_shape_and_nan_rejected():
    raw = b'{"formula":"Li"}'
    with pytest.raises(ValueError, match="ARRAY root"):
        audit_shon_schema(raw, exact_blob_sha1=_git_blob_sha(raw), expected_size=len(raw))
    invalid = b'[NaN]'
    with pytest.raises(ValueError, match="non-JSON numeric"):
        audit_shon_schema(invalid, exact_blob_sha1=_git_blob_sha(invalid),
                          expected_size=len(invalid))
