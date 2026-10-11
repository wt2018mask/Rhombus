"""0135 public benchmark gates: source rights, never public TEST or false science."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.science.public_transport_benchmark import (
    SCHEMA, REGISTRY_SCHEMA, build_public_benchmark, inspect_caltech_original_csv,
    main, validate_registry,
)
from tests.test_phase3_obelix_censor_aware_policy import source as fixture


REGISTRY = Path(__file__).resolve().parents[1] / (
    "data/benchmarks/public_transport/source_registry_0135.json")


def registry():
    return json.loads(REGISTRY.read_text())


def test_0135_all_sources_are_rights_gated():
    sources = validate_registry(registry())
    assert len(sources) == 7
    assert sources["OBELIX"]["local_reuse"] == "TRAIN_ONLY_PUBLIC_DIAGNOSTIC"
    assert sources["MCHAFFIE_2025"]["local_reuse"] == (
        "METADATA_AUDIT_ONLY_NO_SOURCE_REPUBLICATION")
    assert sources["LIVERPOOL_2022"]["phase"] == "RIGHTS_GATED"
    assert all(src["rights"] for src in sources.values())


def test_synthetic_public_train_catalog_keeps_test_and_truth_quarantined(tmp_path):
    inputs = fixture(tmp_path)
    rows, summary = build_public_benchmark(
        *inputs, registry(), require_official=False,
    )
    assert len(rows) == 3
    assert summary["schema_version"] == SCHEMA
    assert summary["development_public_train_records"] == 3
    assert summary["development_original_upper_bound_records"] == 1
    assert summary["development_unverified_numeric_records"] == 2
    assert summary["public_original_test_records_reserved_aggregate"] == 1
    assert summary["original_test_censored_aggregate"] == 1
    assert summary["real_integrated_source_dataset_count"] == 1
    assert summary["registered_candidate_sources"] == 7
    assert summary["independent_material_count"] is None
    assert summary["scientifically_qualified_transport_records"] == 0
    assert not summary["scientific_score_authorized"]
    assert {r["source_entry_id"] for r in rows} == {"a", "b", "d"}
    assert all(r["partition"] == "DEVELOPMENT_TRAIN_ONLY_PUBLIC" for r in rows)
    assert all(not r["eligible_for_scientific_scoring"] for r in rows)
    assert all(not r["material_independence_certified"] for r in rows)
    assert all(r["source_dataset"] == "OBELIX" for r in rows)
    b = next(r for r in rows if r["source_entry_id"] == "b")
    assert b["strict_upper_bound_s_per_cm"] == "1E-10"
    assert b["numeric_source_unverified_s_per_cm"] is None
    assert b["doi_source_tokens"] == ["10.1234/beta"]
    assert b["label_policy"] == "UPPER_BOUND_EXCLUSIVE"
    assert next(r for r in rows if r["source_entry_id"] == "a")[
        "numeric_source_unverified_s_per_cm"] == "0.001"


def test_deterministic_benchmark_hash(tmp_path):
    inputs = fixture(tmp_path)
    rows, summary = build_public_benchmark(
        *inputs, registry(), require_official=False)
    rows2, summary2 = build_public_benchmark(
        *inputs, registry(), require_official=False)
    assert (rows, summary) == (rows2, summary2)
    raw = b"".join(json.dumps(r, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).encode() + b"\n" for r in rows)
    assert hashlib.sha256(raw).hexdigest() == summary["public_train_records_sha256"]


@pytest.mark.parametrize("mutation", [
    lambda r: r.update({"no_unverified_sum_as_unique_materials": False}),
    lambda r: r["benchmark_definition"].update({
        "admitted_scientifically_qualified_materials": 50}),
    lambda r: r["sources"][1].update({"rights": ""}),
    lambda r: r["sources"][1].update({"local_reuse": "FULL_REPUBLICATION_ALLOWED"}),
    lambda r: r["sources"][0].update({"published_record_count": 600}),
    lambda r: r["sources"][1].update({"upstream_file_md5": "0" * 32}),
    lambda r: r["sources"][2].update({"source_url": "http://unsafe.example"}),
])
def test_registry_unapproved_sources_or_claims_rejected(mutation):
    r = registry()
    mutation(r)
    with pytest.raises(ValueError):
        validate_registry(r)


def test_source_tampering_prevents_public_benchmark_generation(tmp_path):
    inputs = fixture(tmp_path)
    p = inputs[1] / "0127/records.jsonl"
    p.write_bytes(p.read_bytes().replace(b"Li2S", b"Li2O"))
    with pytest.raises(ValueError, match="digest"):
        build_public_benchmark(*inputs, registry(), require_official=False)


def test_caltech_schema_audit_only_not_republication():
    csv_bytes = b"formula,doi,ionic_conductivity\nLi3N,10.1234/a,1e-8\nLi2S,10.1234/b,2e-5\n"
    m = hashlib.md5(csv_bytes, usedforsecurity=False).hexdigest()
    result = inspect_caltech_original_csv(csv_bytes, expected_md5=m, expected_rows=2)
    assert result["source_csv_row_count"] == 2
    assert result["source_csv_header_columns"] == ["formula", "doi", "ionic_conductivity"]
    assert result["source_licensing_unresolved"]
    assert not result["raw_source_republished"]
    assert result["source_independent_material_count"] is None
    assert result["source_scientific_qualified_material_count"] == 0
    assert not result["scientific_score_authorized"]
    assert "Li3N" not in json.dumps(result)


def test_caltech_bad_checksum_or_row_count_fails_closed():
    sample = b"a,b\n1,2\n"
    with pytest.raises(ValueError, match="checksum mismatch"):
        inspect_caltech_original_csv(sample)
    with pytest.raises(ValueError, match="571"):
        inspect_caltech_original_csv(
            sample, expected_md5=hashlib.md5(sample, usedforsecurity=False).hexdigest()
        )


@pytest.mark.parametrize("bad", [
    b"a,a\n1,2\n",
    b"a,b\n1,2,3\n",
    b"\xff\xfe\x00\x00",
    b"",
])
def test_bad_caltech_schema_or_encoding_fails_closed(bad):
    md5 = hashlib.md5(bad, usedforsecurity=False).hexdigest()
    with pytest.raises(ValueError):
        inspect_caltech_original_csv(bad, expected_md5=md5, expected_rows=1)


def test_real_cli_does_not_accept_synthetic_fixture(tmp_path):
    src, evidence, raw = fixture(tmp_path)
    output = tmp_path / "should-not-exist"
    with pytest.raises(SystemExit):
        main([
            "build-obelix-public-train", "--obelix-checkout", str(src),
            "--evidence-dir", str(evidence),
            "--raw-lineage-dir", str(raw),
            "--registry-json", str(REGISTRY),
            "--output-dir", str(output),
        ])
    assert not output.exists()
