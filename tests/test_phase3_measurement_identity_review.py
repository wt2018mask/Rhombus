"""Adversarial source and split leakage diagnostics for the 0128 benchmark lane."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from rhombus.qualification.obelix_benchmark_intake import (
    build_obelix_benchmark_intake,
)
from rhombus.qualification.measurement_identity import (
    LIION_SCHEMA,
    review_measurement_identity,
    main,
)
from tests.test_phase3_obelix_benchmark_intake import checkout


def fixture(tmp_path):
    root, sha = checkout(tmp_path)
    return build_obelix_benchmark_intake(root, expected_commit=sha)


def rebound(rows, summary):
    s = dict(summary)
    raw = b"".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":"), allow_nan=False).encode() + b"\n"
        for row in rows
    )
    s["records_jsonl_sha256"] = hashlib.sha256(raw).hexdigest()
    s["record_count"] = len(rows)
    s["official_train_count"] = sum(r["official_split"] == "TRAIN" for r in rows)
    s["official_test_count"] = sum(r["official_split"] == "TEST" for r in rows)
    return s


def liion(*, rec="l001", comp="Li2S", doi="10.1234/alpha", temp="298.15"):
    return {
        "schema_version": LIION_SCHEMA,
        "source_dataset": "LiIon",
        "source_record_id": rec,
        "source_artifact_sha256": "f" * 64,
        "reported_composition": comp,
        "reference_dois": [doi],
        "measurement_temperature_K": temp,
        "reported_ionic_conductivity_text": "0.0001",
        "measurement_kind": "PROCESSED_REPORTED_POINT",
    }


def test_unmodified_source_has_no_false_overlap_claim(tmp_path):
    rows, summary = fixture(tmp_path)
    pairs, result = review_measurement_identity(rows, obelix_summary=summary)
    assert pairs == []
    assert result["source_record_counts"] == {"OBELiX": 4, "LiIon": 0}
    assert result["cross_official_split_potential_overlap_pairs"] == 0
    assert result["independent_material_count"] is None
    assert result["qualified_transport_material_count"] is None
    assert result["scientific_qualification_authorized"] is False


def test_same_formula_and_doi_cross_official_split_flagged_not_resplit(tmp_path):
    rows, summary = fixture(tmp_path)
    rows = copy.deepcopy(rows)
    test = next(r for r in rows if r["source_entry_id"] == "c")
    test["reported_composition"] = "Li2S"
    test["reference_dois"] = ["10.1234/alpha"]
    pairs, result = review_measurement_identity(
        rows, obelix_summary=rebound(rows, summary))
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair["left_source_identity"] == "OBELiX:a"
    assert pair["right_source_identity"] == "OBELiX:c"
    assert pair["left_original_split"] == "TRAIN"
    assert pair["right_original_split"] == "TEST"
    assert pair["signals"] == ["EXACT_REPORTED_COMPOSITION", "SAME_REFERENCE_DOI"]
    assert pair["review_class"] == "PUBLIC_OFFICIAL_SPLIT_POTENTIAL_LEAKAGE"
    assert pair["material_identity_resolved"] is False
    assert pair["merge_authorized"] is False
    assert result["cross_official_split_potential_overlap_pairs"] == 1


def test_same_cif_bytes_not_automatically_same_material(tmp_path):
    rows, summary = fixture(tmp_path)
    rows = copy.deepcopy(rows)
    b = next(r for r in rows if r["source_entry_id"] == "c")
    a = next(r for r in rows if r["source_entry_id"] == "a")
    b["cif_content_sha256"] = a["cif_content_sha256"]
    pairs, result = review_measurement_identity(
        rows, obelix_summary=rebound(rows, summary))
    assert any("IDENTICAL_CIF_FILE_BYTES" in p["signals"] for p in pairs)
    assert result["independent_material_count"] is None
    assert all(not p["merge_authorized"] for p in pairs)


def test_doi_only_covers_different_compositions_without_merging(tmp_path):
    rows, summary = fixture(tmp_path)
    rows = copy.deepcopy(rows)
    rows[1]["reference_dois"] = ["10.1234/alpha"]
    pairs, _ = review_measurement_identity(
        rows, obelix_summary=rebound(rows, summary))
    assert len(pairs) == 1
    assert pairs[0]["signals"] == ["SAME_REFERENCE_DOI"]
    assert pairs[0]["review_class"] == "WITHIN_SOURCE_REVIEW"
    assert not pairs[0]["merge_authorized"]


def test_optional_liion_is_separate_temperature_scoped_source(tmp_path):
    rows, summary = fixture(tmp_path)
    pairs, result = review_measurement_identity(
        rows, obelix_summary=summary,
        liion_records=[liion(), liion(rec="l002", temp="350.0")],
    )
    assert result["source_record_counts"] == {"OBELiX": 4, "LiIon": 2}
    assert result["cross_source_potential_overlap_pairs"] == 2
    assert result["cross_official_split_potential_overlap_pairs"] == 0
    cross = [p for p in pairs if p["review_class"] == "CROSS_SOURCE_POSSIBLE_OVERLAP"]
    assert len(cross) == 2
    assert all(p["same_reported_temperature_scope"] is False for p in cross)
    assert all("OBELiX:" in p["left_source_identity"] + p["right_source_identity"]
               and "LiIon:" in p["left_source_identity"] + p["right_source_identity"]
               for p in cross)
    assert result["independent_material_count"] is None


def test_deterministic_input_order_produces_same_review(tmp_path):
    rows, summary = fixture(tmp_path)
    li = [liion(rec="x"), liion(rec="y", doi="10.1234/beta")]
    first = review_measurement_identity(rows, obelix_summary=summary, liion_records=li)
    second = review_measurement_identity(rows, obelix_summary=summary, liion_records=list(reversed(li)))
    assert first == second


def test_stale_obelix_summary_or_unauthorized_public_split_modification_rejected(tmp_path):
    rows, summary = fixture(tmp_path)
    wrong = copy.deepcopy(rows)
    wrong[0]["reported_composition"] = "unexpected"
    with pytest.raises(ValueError, match="frozen 0127"):
        review_measurement_identity(wrong, obelix_summary=summary)
    wrong = copy.deepcopy(rows)
    wrong[0]["official_split"] = "TEST"
    with pytest.raises(ValueError, match="split counts"):
        review_measurement_identity(wrong, obelix_summary=summary)


@pytest.mark.parametrize("mutation", [
    lambda rows: rows[0].update(source_material_independence_verified=True),
    lambda rows: rows[0].update(qualified_transport_truth=True),
    lambda rows: rows[0].update(independently_blinded=True),
    lambda rows: rows[0].update(reported_ionic_conductivity_unit="mS/cm"),
    lambda rows: rows[0].update(source_cif_match_status="No Match"),
    lambda rows: rows[0].update(official_split="HELD_OUT"),
    lambda rows: rows[0].update(extra="fake"),
    lambda rows: rows[1].update(source_entry_id="a"),
])
def test_untrusted_obelix_claim_mutation_rejected(tmp_path, mutation):
    rows, summary = fixture(tmp_path)
    rows = copy.deepcopy(rows)
    mutation(rows)
    with pytest.raises(ValueError):
        review_measurement_identity(rows, obelix_summary=rebound(rows, summary))


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(measurement_temperature_K="NaN"),
    lambda r: r.update(measurement_temperature_K="-23"),
    lambda r: r.update(measurement_temperature_K=""),
    lambda r: r.update(source_artifact_sha256="unsigned"),
    lambda r: r.update(measurement_kind="EXACT_CERTIFIED"),
    lambda r: r.update(reported_ionic_conductivity_text="<1e-8"),
    lambda r: r.update(extra="unapproved"),
])
def test_bad_optional_liion_temperature_or_truth_rejected(tmp_path, mutation):
    rows, summary = fixture(tmp_path)
    r = liion()
    mutation(r)
    with pytest.raises(ValueError):
        review_measurement_identity(rows, obelix_summary=summary, liion_records=[r])


def test_duplicate_liion_record_id_rejected(tmp_path):
    rows, summary = fixture(tmp_path)
    with pytest.raises(ValueError, match="duplicate identity"):
        review_measurement_identity(rows, obelix_summary=summary,
                                    liion_records=[liion(), liion()])


def test_budget_excess_requires_review_not_false_clearance(tmp_path, monkeypatch):
    import rhombus.qualification.measurement_identity as mod
    rows, summary = fixture(tmp_path)
    rows = copy.deepcopy(rows)
    for r in rows:
        r["reference_dois"] = ["10.1234/common"]
    monkeypatch.setattr(mod, "MAX_REVIEW_PAIRS", 2)
    with pytest.raises(ValueError, match="budget"):
        review_measurement_identity(rows, obelix_summary=rebound(rows, summary))


def test_cli_outputs_bounded_reproducible_pair_file(tmp_path, capsys):
    rows, summary = fixture(tmp_path)
    source = tmp_path / "obelix_records.jsonl"
    summary_path = tmp_path / "obelix_summary.json"
    source.write_bytes(b"".join(
        json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()+b"\n"
        for r in rows))
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    liion_path = tmp_path / "liion.jsonl"
    liion_path.write_text(json.dumps(liion())+"\n", encoding="utf-8")
    out = tmp_path / "review_output"
    assert main([
        "--obelix-records-jsonl", str(source),
        "--obelix-summary-json", str(summary_path),
        "--liion-records-jsonl", str(liion_path),
        "--output-dir", str(out),
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    raw = (out / "review_pairs.jsonl").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == report["review_pairs_sha256"]
    assert report["cross_source_potential_overlap_pairs"] == 1
    with pytest.raises(SystemExit):
        main([
            "--obelix-records-jsonl", str(source),
            "--obelix-summary-json", str(summary_path),
            "--output-dir", str(out),
        ])


def test_no_signal_is_not_independent_material_attestation(tmp_path):
    rows, summary = fixture(tmp_path)
    _, report = review_measurement_identity(rows, obelix_summary=summary)
    assert report["no_signal_is_proof_of_independence"] is True
    assert report["scientific_verdict"] == "INDETERMINATE"
    assert report["independent_material_count"] is None
