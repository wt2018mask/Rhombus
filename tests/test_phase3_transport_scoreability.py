"""0129 experimental reference readiness, no synthetic-to-science promotion."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from rhombus.qualification.transport_scoreability import (
    REVIEW_SCHEMA, SCHEMA, assess_transport_scoreability, main,
)
from rhombus.qualification.measurement_identity import review_measurement_identity
from rhombus.qualification.obelix_benchmark_intake import build_obelix_benchmark_intake
from tests.test_phase3_obelix_benchmark_intake import checkout


def fixture(tmp_path):
    root, commit = checkout(tmp_path)
    records, source_summary = build_obelix_benchmark_intake(
        root, expected_commit=commit,
    )
    pairs, identity_summary = review_measurement_identity(
        records, obelix_summary=source_summary,
    )
    return records, source_summary, pairs, identity_summary


def run(data, *, reviews=None):
    records, source, pairs, identity = data
    return assess_transport_scoreability(
        records, obelix_summary=source,
        review_pairs=pairs, identity_summary=identity,
        review_declarations=reviews,
    )


def declaration(row, **overrides):
    record_hash = hashlib.sha256(
        json.dumps(row, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    result = {
        "schema_version": REVIEW_SCHEMA,
        "source_entry_id": row["source_entry_id"],
        "source_record_sha256": record_hash,
        "evidence_artifact_sha256": "b" * 64,
        "measurement_quantity": "TOTAL_IONIC_CONDUCTIVITY_S_PER_CM",
        "measurement_temperature_K": "298.15",
        "phase_assessment": "EXACT_EXPERIMENTAL_PHASE_DECLARED",
        "experimental_value_assessment": "POINT_MEASUREMENT_REVIEWED",
        "independent_material_assessment": "DISTINCT_MATERIAL_DECLARED",
        "training_exposure_assessment": "NOT_IN_TRAINING_DECLARED",
    }
    result.update(overrides)
    return result


def test_no_external_review_reports_all_records_and_science_nonclaims(tmp_path):
    rows, summary = run(fixture(tmp_path))
    assert len(rows) == 4
    assert summary["schema_version"] == SCHEMA
    assert summary["records_inspected"] == 4
    assert summary["official_train_records"] == 3
    assert summary["official_test_records"] == 1
    assert summary["source_cif_exact_match_records"] == 1
    assert summary["source_cif_close_match_records"] == 1
    assert summary["source_cif_absent_records"] == 2
    assert summary["source_processed_point_records"] == 3
    assert summary["independent_material_count"] is None
    assert summary["independent_transport_qualified_material_count"] is None
    assert summary["scientific_qualification_authorized"] is False
    assert all(row["scoreability_preflight_status"] == "EVIDENCE_GAPS"
               and not row["independent_transport_truth_qualified"]
               for row in rows)
    assert "EXACT_MEASUREMENT_TEMPERATURE_K_UNATTESTED" in rows[0][
        "missing_or_unverified_requirements"
    ]
    assert "NO_SOURCE_CIF_FOR_MODEL_STRUCTURE" in rows[1][
        "missing_or_unverified_requirements"
    ]
    assert summary["scoreability_records_sha256"] == hashlib.sha256(b"".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8") + b"\n"
        for r in rows
    )).hexdigest()


def test_censored_record_never_becomes_point_truth(tmp_path):
    data = fixture(tmp_path)
    row = next(r for r in data[0] if r["source_entry_id"] == "b")
    reports, _ = run(data)
    assert "CENSORED_VALUE_NOT_POINT_GROUND_TRUTH" in next(
        r for r in reports if r["source_entry_id"] == "b"
    )["missing_or_unverified_requirements"]
    with pytest.raises(ValueError, match="censored"):
        run(data, reviews=[declaration(
            row, phase_assessment="UNKNOWN",
            experimental_value_assessment="POINT_MEASUREMENT_REVIEWED",
        )])


def test_complete_synthetic_declaration_is_still_untrusted(tmp_path):
    data = fixture(tmp_path)
    row = data[0][0]  # source entry "a", exact-match CIF, point value
    result, report = run(data, reviews=[declaration(row)])
    selected = next(x for x in result if x["source_entry_id"] == "a")
    assert selected["scoreability_preflight_status"] == (
        "DECLARATION_COMPLETE_INDEPENDENT_AUTHENTICATION_REQUIRED"
    )
    assert "CURATION_DECLARATION_NOT_INDEPENDENTLY_AUTHENTICATED" in (
        selected["missing_or_unverified_requirements"]
    )
    assert report["declaration_complete_but_unattested_records"] == 1
    assert report["independently_unauthenticated_curated_declarations"] == 1
    assert report["scientific_verdict"] == "INDETERMINATE"
    assert report["independent_transport_qualified_material_count"] is None
    assert report["independently_blinded_material_count"] == 0


def test_near_match_cif_cannot_claim_exact_experimental_phase(tmp_path):
    data = fixture(tmp_path)
    row = next(r for r in data[0] if r["source_entry_id"] == "c")
    with pytest.raises(ValueError, match="nonexact CIF"):
        run(data, reviews=[declaration(row)])
    result, _ = run(data, reviews=[declaration(
        row, phase_assessment="UNKNOWN"
    )])
    assert "SOURCE_CIF_CLOSE_MATCH_NOT_EXACT_PHASE" in next(
        r for r in result if r["source_entry_id"] == "c"
    )["missing_or_unverified_requirements"]


def test_source_does_not_claim_diffusion_from_conductivity(tmp_path):
    data = fixture(tmp_path)
    with pytest.raises(ValueError, match="diffusion"):
        run(data, reviews=[declaration(
            data[0][0], measurement_quantity="SELF_DIFFUSION_COEFFICIENT"
        )])


@pytest.mark.parametrize("field,value", [
    ("measurement_temperature_K", "NaN"),
    ("measurement_temperature_K", "0"),
    ("measurement_temperature_K", 300),
    ("measurement_quantity", "CORRECT_300K_CONDUCTIVITY"),
    ("phase_assessment", "SCIENTIFIC_PASS"),
    ("experimental_value_assessment", "MEASURED_BY_MLIP"),
    ("independent_material_assessment", "MODEL_CONFIRMED"),
    ("training_exposure_assessment", "SCIENCE_PASS"),
    ("evidence_artifact_sha256", "fake"),
    ("source_record_sha256", "a" * 64),
    ("source_entry_id", "missing-id"),
])
def test_unsupported_or_tampered_external_claim_rejected(tmp_path, field, value):
    data = fixture(tmp_path)
    with pytest.raises(ValueError):
        run(data, reviews=[declaration(data[0][0], **{field: value})])


def test_duplicate_external_declarations_rejected(tmp_path):
    data = fixture(tmp_path)
    r = declaration(data[0][0])
    with pytest.raises(ValueError, match="duplicate"):
        run(data, reviews=[r, copy.deepcopy(r)])


def test_transitive_or_false_material_merge_never_permitted(tmp_path):
    data = fixture(tmp_path)
    records, original, _pairs, _identity = data
    modified = copy.deepcopy(records)
    a = modified[0]
    c = next(row for row in modified if row["source_entry_id"] == "c")
    c["reported_composition"] = a["reported_composition"]
    from tests.test_phase3_measurement_identity_review import rebound
    updated = rebound(modified, original)
    pairs, identity = review_measurement_identity(modified, obelix_summary=updated)
    result, report = run((modified, updated, pairs, identity))
    assert report["records_with_possible_identity_collision"] == 2
    assert report["independent_material_count"] is None
    assert all(x["scoreability_preflight_status"] ==
               "POTENTIAL_IDENTITY_CONFLICT_REQUIRES_REVIEW"
               for x in result if x["source_entry_id"] in ("a", "c"))
    assert all(x["new_external_blind_material"] is False for x in result)


def test_modified_identity_pair_or_summary_fails_closed(tmp_path):
    data = fixture(tmp_path)
    records, upstream, pairs, identity = data
    broken = dict(identity, review_pairs_sha256="0" * 64)
    with pytest.raises(ValueError, match="0128"):
        assess_transport_scoreability(
            records, obelix_summary=upstream,
            review_pairs=pairs, identity_summary=broken,
        )
    with pytest.raises(ValueError, match="0128"):
        assess_transport_scoreability(
            records, obelix_summary=upstream,
            review_pairs=[{"fake": "pair"}], identity_summary=identity,
        )


def test_changed_upstream_rows_are_rejected_against_frozen_snapshot(tmp_path):
    data = fixture(tmp_path)
    altered = copy.deepcopy(data[0])
    altered[0]["reported_ionic_conductivity_text"] = "999"
    with pytest.raises(ValueError, match="frozen 0127"):
        assess_transport_scoreability(
            altered, obelix_summary=data[1], review_pairs=data[2],
            identity_summary=data[3],
        )


def test_cli_reproduces_hash_bound_scoreability(tmp_path, capsys):
    data = fixture(tmp_path)
    source = tmp_path / "source.jsonl"
    source_summary = tmp_path / "source_summary.json"
    review = tmp_path / "pairs.jsonl"
    review_summary = tmp_path / "identity_summary.json"
    source.write_bytes(b"".join(
        json.dumps(r, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for r in data[0]))
    source_summary.write_text(json.dumps(data[1]))
    review.write_bytes(b"".join(
        json.dumps(r, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for r in data[2]))
    review_summary.write_text(json.dumps(data[3]))
    out = tmp_path / "out"
    assert main([
        "--obelix-records-jsonl", str(source),
        "--obelix-summary-json", str(source_summary),
        "--review-pairs-jsonl", str(review),
        "--identity-summary-json", str(review_summary),
        "--output-dir", str(out),
    ]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["records_inspected"] == 4
    assert output["scoreability_records_sha256"] == hashlib.sha256(
        (out / "scoreability_records.jsonl").read_bytes()
    ).hexdigest()
    with pytest.raises(SystemExit):
        main([
            "--obelix-records-jsonl", str(source),
            "--obelix-summary-json", str(source_summary),
            "--review-pairs-jsonl", str(review),
            "--identity-summary-json", str(review_summary),
            "--output-dir", str(out),
        ])


@pytest.mark.parametrize("invalid", ['{"x":NaN}', '{"x":1,"x":2}', '[]'])
def test_cli_malformed_scientific_summary_fails(tmp_path, invalid):
    data = fixture(tmp_path)
    input_paths = [tmp_path / x for x in ("rows.jsonl", "source.json", "pairs.jsonl", "report.json")]
    input_paths[0].write_bytes(b"".join(
        json.dumps(r, sort_keys=True, separators=(",", ":")).encode()+b"\n"
        for r in data[0]))
    input_paths[1].write_text(json.dumps(data[1]))
    input_paths[2].write_bytes(b"")
    input_paths[3].write_text(invalid)
    with pytest.raises(SystemExit):
        main([
            "--obelix-records-jsonl", str(input_paths[0]),
            "--obelix-summary-json", str(input_paths[1]),
            "--review-pairs-jsonl", str(input_paths[2]),
            "--identity-summary-json", str(input_paths[3]),
            "--output-dir", str(tmp_path / "out"),
        ])
