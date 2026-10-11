"""0152-B real publisher-abstract/CIF join adversarial contracts (fixture synthetic)."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import pytest

from scripts.science.obelix_publisher_abstract_review_0152 import (
    EVIDENCE_PATH, SCHEMA, SOURCE_AUDIT_SHA256,
    review_exact_original_publisher_abstracts,
)


def fixture():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    dois = [x["doi"] for x in evidence["publisher_abstracts"]]
    # Ten source rows across exactly eight publisher papers, two duplicated.
    paper_assignment = [dois[0], dois[1], dois[2], dois[3], dois[1],
                        dois[4], dois[5], dois[2], dois[6], dois[7]]
    queue = []
    for i, doi in enumerate(paper_assignment):
        queue.append({
            "source_entry_id": "fixture_%02d" % i,
            "source_dois": [doi],
            "original_cif_sha256": "%064x" % (i+1),
            "original_cif_match": "Match",
            "paper_review_status": "NOT_REVIEWED",
            "phase_identity": "UNATTESTED",
            "fractional_site_count": i+1,
            # Never copy source conductivity when joining publisher article!
            "reported_ionic_conductivity_text": "SECRET_0146_LABEL",
        })
    audit = {
        "original_commit": "fixture-commit-not-pinned-original",
        "original_processed_csv_sha256": "a"*64,
        "source_CIF_inventory_sha256": "b"*64,
        "original_all_source_rows": 599,
        "original_official_train_rows": 478,
        "original_official_test_rows_reserved_unparsed": 121,
        "train_exact_match_source_CIF_count": 202,
        "train_close_match_CIF_count_NOT_phase_qualified": 52,
        "reproduced_0145_train_model_eligible_ORDERED_source_structures": 39,
        "review_queue_first_party_public_DOI_and_source_CIF_links_ONLY": queue,
        "scientific_qualification_authorized": False,
        "partial_occupancy_rounded_into_ordered_model": False,
        "geometry_CIF_close_match_promoted_to_exact_phase": False,
        "primary_source_papers_actually_read": 0,
        "specimen_phase_and_exact_measurement_temperature_verified": 0,
    }
    return audit, evidence


def review(audit=None, evidence=None):
    if audit is None or evidence is None:
        audit, evidence = fixture()
    return review_exact_original_publisher_abstracts(
        audit, evidence, enforce_real_source=False)


def test_all_eight_actual_reviewed_DOI_sources_present_in_public_evidence():
    _, source = fixture()
    assert len(source["publisher_abstracts"]) == 8
    assert SOURCE_AUDIT_SHA256 == (
        "960cf078fcac71b244a087f0e73d781614aa515d38e6964dcfffcd654f90070a"
    )
    for paper in source["publisher_abstracts"]:
        assert paper["publisher_url"].startswith("https://pubs.")
        assert paper["doi"].startswith("10.")
        assert paper["literature_risks"]
        assert paper["abstract_methods"]


def test_exact_join_counts_10_source_rows_only_eight_unique_abstract_papers():
    result = review()
    assert result["schema_version"] == SCHEMA
    assert result["source_CIF_review_queue_rows_linked_to_paper_abstract"] == 10
    assert result["unique_publisher_DOIs_whose_indexed_abstracts_actually_inspected"] == 8
    assert sorted(result["actual_DOI_paper_to_original_CIF_source_row_counts"].values()) == [
        1, 1, 1, 1, 1, 1, 2, 2
    ]
    assert len(result["first_party_original_source_CIF_abstract_review_entries"]) == 10
    assert result["official_original_public_TEST_rows_reserved_unparsed"] == 121
    assert result["specific_experimental_sample_to_CIF_phase_independently_matched"] == 0
    assert result["specific_measured_temperature_bulk_total_to_source_row_matched"] == 0
    assert result["new_independently_qualified_experimental_materials"] == 0
    assert result["scientific_GO"] is False
    assert result["P0_01_status"] == result["P0_02_status"] == result["P0_03_status"] == "BLOCKED"


def test_never_misattribute_article_series_values_to_specific_source_rows():
    source, evidence = fixture()
    result = review(source, evidence)
    raw = json.dumps(result)
    assert "SECRET_0146_LABEL" not in raw
    assert "2.5e-3 S/cm" not in raw
    assert "18.4" not in raw
    assert "row_specific_reported_numeric_conductivity" in raw
    assert all(
        row["row_specific_reported_numeric_conductivity"] is None and
        row["row_specific_published_temperature"] is None and
        row["row_specific_bulk_vs_total"] == "UNVERIFIED" and
        row["independent_paper_full_text_and_SI_review"] == "NOT_DONE"
        for row in result["first_party_original_source_CIF_abstract_review_entries"]
    )


def test_source_identity_or_cif_hash_incorrect_cannot_join():
    a, e = fixture()
    a["review_queue_first_party_public_DOI_and_source_CIF_links_ONLY"][0]["original_cif_sha256"] = "not-a-sha"
    with pytest.raises(ValueError, match="SHA256"):
        review(a, e)
    a, e = fixture()
    a["review_queue_first_party_public_DOI_and_source_CIF_links_ONLY"][1]["source_entry_id"] = "fixture_00"
    with pytest.raises(ValueError, match="duplicate"):
        review(a, e)


def test_unknown_doi_and_multiple_citations_never_choose_first_arbitrarily():
    a,e = fixture()
    a["review_queue_first_party_public_DOI_and_source_CIF_links_ONLY"][1]["source_dois"] = ["10.1234/unseen"]
    with pytest.raises(ValueError, match="lacks inspected"):
        review(a,e)
    a,e = fixture()
    a["review_queue_first_party_public_DOI_and_source_CIF_links_ONLY"][1]["source_dois"].append("10.1234/other")
    with pytest.raises(ValueError, match="ambiguous"):
        review(a,e)


def test_publisher_metadata_url_and_doi_must_bind():
    a,e = fixture()
    e["publisher_abstracts"][0]["publisher_url"] = "https://evil.example.com/doi/10.1021/ic400577v"
    with pytest.raises(ValueError, match="publication URL"):
        review(a,e)
    a,e = fixture()
    e["publisher_abstracts"][0]["publisher_url"] = "https://pubs.acs.org/doi/10.1021/other"
    with pytest.raises(ValueError, match="publication URL"):
        review(a,e)
    a,e = fixture()
    e["publisher_abstracts"][0]["doi"] = "NOT_A_DOI"
    with pytest.raises(ValueError, match="DOI"):
        review(a,e)


def test_duplicates_do_not_create_fake_distinct_publications():
    a,e=fixture()
    e["publisher_abstracts"].append(copy.deepcopy(e["publisher_abstracts"][0]))
    with pytest.raises(ValueError, match="duplicate DOI"):
        review(a,e)


def test_paper_review_and_scientific_authorization_cannot_be_faked():
    a,e=fixture()
    a["primary_source_papers_actually_read"] = 8
    with pytest.raises(ValueError, match="scientific source"):
        review(a,e)
    a,e=fixture()
    a["review_queue_first_party_public_DOI_and_source_CIF_links_ONLY"][0]["phase_identity"]="QUALIFIED"
    with pytest.raises(ValueError, match="falsely promoted"):
        review(a,e)
    a,e=fixture()
    e["interpretation_contract"]["full_primary_papers_actually_read_count"] = 8
    with pytest.raises(ValueError, match="falsely"):
        review(a,e)
    a,e=fixture()
    e["interpretation_contract"]["physical_independent_specimens_verified_count"] = 10
    with pytest.raises(ValueError, match="falsely"):
        review(a,e)


def test_real_official_pinned_0151_artifact_requires_exact_source_hash():
    a,e=fixture()
    with pytest.raises(ValueError, match="real first-party"):
        review_exact_original_publisher_abstracts(a,e,enforce_real_source=True)


def test_source_classification_cannot_falsely_claim_close_match_experimental_phase():
    a,e=fixture()
    a["geometry_CIF_close_match_promoted_to_exact_phase"]=True
    with pytest.raises(ValueError, match="scientific source"):
        review(a,e)
    a,e=fixture()
    a["review_queue_first_party_public_DOI_and_source_CIF_links_ONLY"][0]["original_cif_match"]="Close Match"
    with pytest.raises(ValueError, match="falsely promoted"):
        review(a,e)
