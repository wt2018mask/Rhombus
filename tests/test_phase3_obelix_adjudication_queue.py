"""0131 real-evidence curation queue tests: public TEST is never development."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts.science.obelix_adjudication_queue import (
    SCHEMA, _jsonl, build_adjudication_queue, main,
)
from scripts.science.obelix_real_source_pipeline import run_three_stage_obelix
from tests.test_phase3_obelix_benchmark_intake import checkout


def fixture(tmp_path):
    root, sha = checkout(tmp_path)
    evidence = tmp_path / "evidence"
    run_three_stage_obelix(root, evidence, expected_commit=sha,
                           require_official_counts=False)
    return evidence


def test_worklist_retains_all_records_and_reserves_public_test(tmp_path):
    evidence = fixture(tmp_path)
    rows, studies, summary = build_adjudication_queue(
        evidence, require_official=False)
    assert summary["schema_version"] == SCHEMA
    assert summary["record_count"] == 4
    assert summary["official_train_records_in_review"] == 3
    assert summary["official_test_records_reserved"] == 1
    assert summary["source_paper_review_groups"] == 4
    assert summary["source_paper_groups_independently_verified"] == 0
    assert summary["all_lanes"] == {
        "TRAIN_A_EXACT_CIF_NO_SIGNAL": 1,
        "TRAIN_B_EXACT_CIF_REVIEW_OVERLAP": 0,
        "TRAIN_C_EXPERIMENTAL_PHASE_REVIEW": 0,
        "TRAIN_D_STRUCTURE_ACQUISITION": 2,
        "TRAIN_E_SOURCE_VALUE_REVIEW": 0,
        "TEST_RESERVED_AUDIT_ONLY": 1,
    }
    assert rows[0]["source_entry_id"] == "a"
    assert rows[-1]["source_entry_id"] == "c"
    assert rows[-1]["access_policy"] == "AUDIT_ONLY_NO_DEVELOPMENT_TUNING"
    assert rows[-1]["original_reference_dois"] == ["10.1234/gamma"]
    assert all("c" not in study["official_train_record_ids"] for study in studies)
    assert all("gamma" not in study["reference_doi_or_missing_id"]
               for study in studies)
    assert all(not row["source_qualified_as_scientific_truth"] for row in rows)
    assert summary["independent_material_count"] is None
    assert summary["qualified_experimental_conductivity_count"] is None
    assert summary["new_external_blinded_materials"] == 0
    assert summary["scientific_qualification_authorized"] is False


def test_study_queue_does_not_merge_multi_doi_materials(tmp_path):
    evidence = fixture(tmp_path)
    _, studies, _ = build_adjudication_queue(evidence, require_official=False)
    two = [s for s in studies if "d" in s["official_train_record_ids"]]
    assert len(two) == 2
    assert set(s["reference_doi_or_missing_id"] for s in two) == {
        "10.1234/delta", "10.1234/second",
    }
    assert all(s["independent_material_count"] is None for s in two)


def test_ranking_never_uses_conductivity_truth(tmp_path):
    evidence = fixture(tmp_path)
    rows, _, report = build_adjudication_queue(evidence, require_official=False)
    assert all("reported_ionic_conductivity_text" not in r for r in rows)
    assert "scientific_truth" not in str(report)
    assert rows[0]["curation_lane"] == "TRAIN_A_EXACT_CIF_NO_SIGNAL"


def test_cannot_claim_synthetic_source_is_official(tmp_path):
    evidence = fixture(tmp_path)
    with pytest.raises(ValueError, match="wrong evidence scope"):
        build_adjudication_queue(evidence)
    # Scope cannot be changed without satisfying the exact original commit.
    p = evidence / "manifest.json"
    obj = json.loads(p.read_text())
    obj["scope"] = "OFFICIAL_PUBLIC_DIAGNOSTIC"
    p.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="commit mismatch"):
        build_adjudication_queue(evidence)


def test_modified_source_record_is_rejected_even_with_same_manifest(tmp_path):
    evidence = fixture(tmp_path)
    p = evidence / "0127/records.jsonl"
    p.write_bytes(p.read_bytes().replace(b"Li2S", b"Li2O"))
    with pytest.raises(ValueError, match="digest/length mismatch"):
        build_adjudication_queue(evidence, require_official=False)


def test_modified_overlap_records_rejected_even_after_hash_rebinding(tmp_path):
    evidence = fixture(tmp_path)
    path = evidence / "0128/review_pairs.jsonl"
    fake = {"left_source_identity": "OBELiX:a",
            "right_source_identity": "OBELiX:c"}
    content = json.dumps(fake).encode() + b"\n"
    path.write_bytes(content)
    manifest_path = evidence / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["0128/review_pairs.jsonl"] = {
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="0128 identity records"):
        build_adjudication_queue(evidence, require_official=False)


def test_modified_scoreability_payload_fails_even_after_digest_rebinding(tmp_path):
    evidence = fixture(tmp_path)
    p = evidence / "0129/scoreability_records.jsonl"
    rows = [json.loads(x) for x in p.read_text().splitlines()]
    rows[0]["independent_transport_truth_qualified"] = True
    content = _jsonl(rows)
    p.write_bytes(content)
    m = evidence / "manifest.json"
    obj = json.loads(m.read_text())
    obj["files"]["0129/scoreability_records.jsonl"] = {
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }
    m.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="scoreability rows/summary"):
        build_adjudication_queue(evidence, require_official=False)


def test_result_determinism_and_file_hash(tmp_path):
    evidence = fixture(tmp_path)
    first = build_adjudication_queue(evidence, require_official=False)
    second = build_adjudication_queue(evidence, require_official=False)
    assert first == second
    rows, studies, s = first
    assert s["record_worklist_sha256"] == hashlib.sha256(_jsonl(rows)).hexdigest()
    assert s["study_worklist_sha256"] == hashlib.sha256(_jsonl(studies)).hexdigest()


def test_bad_manifest_scientific_promotion_is_rejected(tmp_path):
    evidence = fixture(tmp_path)
    p = evidence / "manifest.json"
    obj = json.loads(p.read_text())
    obj["scientific_qualification_authorized"] = True
    p.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="not a scientific diagnostic"):
        build_adjudication_queue(evidence, require_official=False)


def test_cli_never_bypasses_official_commit_gate(tmp_path):
    evidence = fixture(tmp_path)
    out = tmp_path / "new_results"
    with pytest.raises(SystemExit):
        main(["--evidence-dir", str(evidence), "--output-dir", str(out)])
    assert not out.exists()


def test_cross_split_original_ids_remain_untouched_in_fixture(tmp_path):
    evidence = fixture(tmp_path)
    before = (evidence / "0127/records.jsonl").read_bytes()
    work, _, result = build_adjudication_queue(evidence, require_official=False)
    assert before == (evidence / "0127/records.jsonl").read_bytes()
    assert {r["source_entry_id"] for r in work} == {"a", "b", "c", "d"}
    assert result["new_independently_adjudicated_materials"] == 0
