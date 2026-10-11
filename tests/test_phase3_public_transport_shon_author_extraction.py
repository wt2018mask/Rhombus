"""0139 Shon original-author schema: source identity, counts, no false science."""
import json
import pytest

from scripts.science.public_transport_shon_original_audit import _git_blob_sha
from scripts.science.public_transport_shon_author_extraction import (
    SCHEMA, audit_shon_author_extractions,
)


def inspect(rows):
    raw = json.dumps(rows).encode("utf-8")
    return audit_shon_author_extractions(
        raw, exact_blob_sha1=_git_blob_sha(raw), expected_size=len(raw))


def test_author_nested_extracted_numeric_is_not_measured_truth_or_material():
    rows = [
        {"BatteryConductivity": {"names": "SECRET Li7P3S11",
                                 "value": 0.002, "units": "S/cm"},
         "metadata": {"doi": "10.1234/PRIVATE", "paper_title": "NO_REPUBLISH"}},
        {"BatteryConductivity": {"names": "SECRET Li7P3S11",
                                 "value": 0.003},
         "metadata": {"doi": "10.1234/PRIVATE"}},
    ]
    r = inspect(rows)
    n = r["author_metadata_presence_counts_NOT_scientific_confirmation"]
    assert r["schema_version"] == SCHEMA
    assert r["original_root_entries_NOT_independent_samples"] == 2
    assert n["positive_extracted_numeric_scalar_NOT_MEASURED_TRUTH"] == 2
    assert n["nonempty_author_extracted_name"] == 2
    assert n["syntactically_plausible_paper_DOI"] == 2
    assert n["three_signal_manual_literature_review_candidates_NOT_SAMPLES"] == 2
    assert r["independent_material_count"] is None
    assert r["physical_experiment_specimen_identity_attested"] == 0
    assert r["scientific_score_authorized"] is False
    assert r["original_source_republication_rights_verified"] is False
    assert r["original_source_rows_keys_DOIs_values_republished"] is False
    assert r["author_code_may_expand_name_value_combinations"] is True
    exported = json.dumps(r)
    for forbidden in ("Li7P3S11", "0.002", "10.1234/PRIVATE",
                      "NO_REPUBLISH", "S/cm"):
        assert forbidden not in exported


def test_scalar_value_type_partition_excludes_bool_text_zero_negative():
    rows = [{"BatteryConductivity": {"value": v, "names": "Li"}},
            {"BatteryConductivity": {"value": False, "names": "Li"}},
            {"BatteryConductivity": {"value": 0, "names": "Li"}},
            {"BatteryConductivity": {"value": -1.0, "names": "Li"}},
            {"BatteryConductivity": {"value": "1e-3", "names": "Li"}},
            {"BatteryConductivity": {"value": None, "names": "Li"}},
            {"BatteryConductivity": {"value": [0.1], "names": "Li"}},
            {"BatteryConductivity": {"names": "Li"}}]
    r = inspect(rows)
    assert r["author_extracted_value_type_counts"] == {
        "missing": 1, "null": 1, "boolean": 1,
        "finite_positive": 1, "finite_nonpositive": 2,
        "nonfinite": 0, "unparsed_text": 1, "container_or_other": 1,
    }
    assert r["scientific_score_authorized"] is False


def test_bad_container_and_root_types_count_separately():
    r = inspect([{"BatteryConductivity": {}},
                 {"BatteryConductivity": "secret"},
                 {"unrelated": "secret"}, 8, None])
    s = r["author_schema_shape_counts"]
    assert s["object_root_entries"] == 3
    assert s["non_object_root_entries"] == 2
    assert s["author_container_object"] == 1
    assert s["author_container_not_object"] == 1
    assert s["author_container_missing"] == 1
    assert r["author_extracted_value_type_counts"]["missing"] == 1


def test_doi_is_paper_syntax_only_not_material_uniqueness():
    rows = [
        {"BatteryConductivity": {"value": 1, "names": "Li"},
         "metadata": {"doi": "None"}},
        {"BatteryConductivity": {"value": 1, "names": "Li"},
         "metadata": {"doi": "https://doi.org/10.1234/requires_normalization"}},
        {"BatteryConductivity": {"value": 1, "names": "Li"},
         "metadata": {"doi": "10.1234/usable"}},
    ]
    r = inspect(rows)
    n = r["author_metadata_presence_counts_NOT_scientific_confirmation"]
    assert n["metadata_field_present"] == 3
    assert n["syntactically_plausible_paper_DOI"] == 1
    assert n["three_signal_manual_literature_review_candidates_NOT_SAMPLES"] == 1
    assert r["independent_material_count"] is None


def test_tampered_hash_rejected_before_parsing_and_metrics():
    raw = b'[{"BatteryConductivity":{"value":1}}]'
    with pytest.raises(ValueError, match="blob SHA"):
        audit_shon_author_extractions(
            raw, expected_size=len(raw), exact_blob_sha1="0" * 40)
    with pytest.raises(ValueError, match="byte size"):
        audit_shon_author_extractions(
            raw, expected_size=len(raw) + 1,
            exact_blob_sha1=_git_blob_sha(raw))


def test_invalid_json_nonfinite_and_wrong_root_are_fail_closed():
    for bad in (b'[NaN]', b'[Infinity]'):
        with pytest.raises(ValueError, match="non-JSON numeric"):
            audit_shon_author_extractions(
                bad, expected_size=len(bad),
                exact_blob_sha1=_git_blob_sha(bad))
    raw = b'{"BatteryConductivity":{"value":2}}'
    with pytest.raises(ValueError, match="ARRAY root"):
        audit_shon_author_extractions(
            raw, expected_size=len(raw), exact_blob_sha1=_git_blob_sha(raw))
    # An overflowed legal JSON exponent can be parsed as inf; never score it.
    inf = b'[{"BatteryConductivity":{"value":1e400}}]'
    report = audit_shon_author_extractions(
        inf, expected_size=len(inf), exact_blob_sha1=_git_blob_sha(inf))
    assert report["author_extracted_value_type_counts"]["nonfinite"] == 1


def test_long_extracted_name_and_source_record_never_republished():
    marker = "PRIVATE_PERSON_IDENTIFIER_HIDDEN"
    r = inspect([{"BatteryConductivity": {
        "names": marker, "value": 17, "specifier": "SECRET",
        "compound": {"Compound": {"names": [marker]}}}, "metadata": {
            "doi": "10.1111/PERSONAL", "other": marker}}])
    out = json.dumps(r)
    assert marker not in out
    assert "PERSONAL" not in out
    assert r["newly_scientifically_qualified_materials"] == 0
    assert r["external_new_sealed_blind_cohort_qualified"] is False
    assert r["selected_MACE_training_frames_authenticated"] is False
    assert r["original_OBELiX_public_TEST_excluded"] is True
