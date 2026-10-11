"""Bounded 0132 source-bound publisher evidence: science NO-GO always."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts.science.obelix_real_source_pipeline import run_three_stage_obelix
from scripts.science.obelix_publisher_observation_triage import (
    SCHEMA, INPUT_SCHEMA, triage_publisher_observations, main,
)
from tests.test_phase3_obelix_benchmark_intake import checkout


def fixture(tmp_path):
    original = [
        "ID,Composition,Space group number,a,b,c,alpha,beta,gamma,"
        "Ionic conductivity (S cm-1),DOI,CIF",
        "a,Li2S,225,5,5,5,90,90,90,0.001,10.1021/acs.chemmater.1c00157,Match",
        "b,Li3N,191,3,3,4,90,90,120,<1e-10,10.1234/beta,No Match",
        "c,Li6PS5Cl,216,9,9,9,90,90,90,0.2,10.1234/gamma,Close Match",
        "d,Li3PO4,1,4,5,6,80,100,110,1e-8,10.1234/delta,No Match",
    ]
    source, sha = checkout(tmp_path, rows=original)
    bundle = tmp_path / "bundle"
    run_three_stage_obelix(source, bundle, expected_commit=sha,
                           require_official_counts=False)
    rows = [json.loads(line) for line in
            (bundle / "0127/records.jsonl").read_text().splitlines()]
    a = next(x for x in rows if x["source_entry_id"] == "a")
    digest = hashlib.sha256(json.dumps(
        a, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    observations = {
        "schema_version": INPUT_SCHEMA,
        "review_scope":
        "AUTHOR_READ_PUBLISHER_VISIBLE_WEB_PAGE_METADATA_NOT_ORIGINAL_NUMERIC_TABLE_ADJUDICATION",
        "observation_date_utc": "2026-10-11",
        "original_source_commit": sha,
        "declarations": [{
            "source_entry_id": "a",
            "source_record_sha256": digest,
            "reference_doi": "10.1021/acs.chemmater.1c00157",
            "publisher_url": "https://pubs.acs.org/doi/abs/10.1021/acs.chemmater.1c00157",
            "publisher_visible_scope": "APPROX_ROOM_TEMPERATURE_AND_HIGH_T_PHASE_TRANSITION",
            "publisher_visible_summary": "This original publisher page gives approximate room-temperature conductivity but the row is not independently authenticated.",
            "unresolved_review_flags": [
                "EXACT_ROOM_TEMPERATURE_K_UNATTESTED",
                "PHASE_TRANSITION_AND_STRUCTURE_BINDING_REQUIRES_ORIGINAL_TABLE",
            ],
            "evidence_excerpt_level": "PUBLISHER_VISIBLE_ARTICLE_TEXT",
        }],
        "all_observations_independently_authenticated": False,
        "original_tables_or_figures_independently_checked": False,
        "newly_qualified_materials": 0,
        "source_records_are_public_training_only": True,
    }
    return bundle, observations


def test_one_publisher_record_produces_bound_nonqualified_review(tmp_path):
    bundle, evidence = fixture(tmp_path)
    rows, report = triage_publisher_observations(
        bundle, evidence, require_official=False,
    )
    assert len(rows) == 1
    assert rows[0]["source_entry_id"] == "a"
    assert rows[0]["original_official_split"] == "TRAIN"
    assert rows[0]["source_curation_lane"] == "TRAIN_A_EXACT_CIF_NO_SIGNAL"
    assert rows[0]["source_scientific_truth_review_status"] == (
        "ORIGINAL_TABLE_AND_SAMPLE_BINDING_REQUIRED"
    )
    assert rows[0]["exact_temperature_and_extrapolation_verified"] is False
    assert rows[0]["correct_comparable_transport_quantity_verified"] is False
    assert rows[0]["scientific_qualification_authorized"] is False
    assert report["schema_version"] == SCHEMA
    assert report["publisher_page_observations"] == 1
    assert report["official_train_record_count"] == 3
    assert report["official_test_record_count_reserved"] == 1
    assert report["verified_independent_material_count"] is None
    assert report["scientifically_qualified_transport_count"] is None
    assert report["scientific_verdict"] == "INDETERMINATE"


def test_original_public_test_identity_forbidden(tmp_path):
    bundle, evidence = fixture(tmp_path)
    source_rows = [json.loads(line) for line in
                   (bundle / "0127/records.jsonl").read_text().splitlines()]
    c = next(x for x in source_rows if x["source_entry_id"] == "c")
    claimed = copy.deepcopy(evidence)
    claimed["declarations"][0]["source_entry_id"] = "c"
    claimed["declarations"][0]["source_record_sha256"] = hashlib.sha256(
        json.dumps(c, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode()).hexdigest()
    claimed["declarations"][0]["reference_doi"] = "10.1234/gamma"
    with pytest.raises(ValueError, match="official TEST"):
        triage_publisher_observations(bundle, claimed, require_official=False)


@pytest.mark.parametrize("field,new", [
    ("source_record_sha256", "0" * 64),
    ("reference_doi", "10.1021/ic201183e"),
    ("publisher_url", "http://pubs.acs.org/doi/abs/10.1021/acs.chemmater.1c00157"),
    ("publisher_url", "https://evil.example/doi/10.1021/acs.chemmater.1c00157"),
    ("publisher_url", "https://pubs.acs.org/doi/abs/10.1021/ja302255d"),
    ("publisher_visible_scope", "EXPERIMENTAL_PASS"),
    ("evidence_excerpt_level", "AUTHENTICATED_PRIMARY"),
    ("unresolved_review_flags", []),
    ("unresolved_review_flags", ["SCIENTIFIC_PASS"]),
])
def test_fake_or_mismatched_publisher_claim_fails_closed(tmp_path, field, new):
    bundle, evidence = fixture(tmp_path)
    claimed = copy.deepcopy(evidence)
    claimed["declarations"][0][field] = new
    with pytest.raises(ValueError):
        triage_publisher_observations(bundle, claimed, require_official=False)


def test_high_temperature_excerpt_requires_temperature_work_item(tmp_path):
    bundle, evidence = fixture(tmp_path)
    obs = evidence["declarations"][0]
    obs["publisher_visible_scope"] = "EXPLICIT_300_C_EXCERPT"
    with pytest.raises(ValueError, match="high-temperature abstract"):
        triage_publisher_observations(bundle, evidence, require_official=False)
    obs["unresolved_review_flags"].append(
        "TEMPERATURE_PROVENANCE_REQUIRES_ORIGINAL_TABLE"
    )
    _, report = triage_publisher_observations(bundle, evidence,
                                               require_official=False)
    assert report["observation_scope_counts"]["EXPLICIT_300_C_EXCERPT"] == 1
    assert report["scientific_qualification_authorized"] is False


@pytest.mark.parametrize("key,value", [
    ("all_observations_independently_authenticated", True),
    ("original_tables_or_figures_independently_checked", True),
    ("newly_qualified_materials", 1),
    ("source_records_are_public_training_only", False),
])
def test_bundle_cannot_attest_science_by_declaration(tmp_path, key, value):
    bundle, evidence = fixture(tmp_path)
    evidence[key] = value
    with pytest.raises(ValueError, match="unsafe"):
        triage_publisher_observations(bundle, evidence,
                                      require_official=False)


def test_duplicate_source_id_observation_rejected(tmp_path):
    bundle, evidence = fixture(tmp_path)
    evidence["declarations"].append(copy.deepcopy(evidence["declarations"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        triage_publisher_observations(bundle, evidence,
                                      require_official=False)


def test_0130_source_artifact_tampering_refused(tmp_path):
    bundle, evidence = fixture(tmp_path)
    p = bundle / "0127/records.jsonl"
    p.write_bytes(p.read_bytes().replace(b"Li2S", b"Li2O"))
    with pytest.raises(ValueError, match="digest"):
        triage_publisher_observations(bundle, evidence,
                                      require_official=False)


def test_official_source_mode_cannot_accept_synthetic(tmp_path):
    bundle, evidence = fixture(tmp_path)
    with pytest.raises(ValueError, match="wrong evidence scope"):
        triage_publisher_observations(bundle, evidence)


def test_one_observation_bundle_is_deterministic(tmp_path):
    bundle, evidence = fixture(tmp_path)
    x = triage_publisher_observations(bundle, evidence, require_official=False)
    y = triage_publisher_observations(bundle, copy.deepcopy(evidence),
                                     require_official=False)
    assert x == y


def test_cli_has_no_fixture_bypass_and_writes_no_unqualified_output(tmp_path):
    bundle, evidence = fixture(tmp_path)
    observed = tmp_path / "observations.json"
    observed.write_text(json.dumps(evidence))
    target = tmp_path / "out"
    with pytest.raises(SystemExit):
        main(["--evidence-dir", str(bundle), "--observations-json",
              str(observed), "--output-dir", str(target)])
    assert not target.exists()
