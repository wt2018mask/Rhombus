"""0134 cannot turn artificial 1e-15 surrogates into exact benchmark truth."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts.science.obelix_censor_aware_policy import (
    CENSOR, POINT, SCHEMA, build_train_label_policy,
    interval_constraint_check, interval_exceedance_log10, main,
)
from scripts.science.obelix_raw_censor_lineage import build_original_censor_audit
from tests.test_phase3_obelix_raw_censor_lineage import fixture


def source(tmp_path):
    checkout, bundle = fixture(tmp_path)
    rows, report = build_original_censor_audit(
        checkout, bundle, require_official=False
    )
    original = tmp_path / "original-0133"
    original.mkdir()
    (original / "train_raw_measurement_lineage.jsonl").write_bytes(
        b"".join(json.dumps(r, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode() + b"\n" for r in rows)
    )
    (original / "summary.json").write_text(json.dumps(report))
    return checkout, bundle, original


def run(p):
    return build_train_label_policy(*p, require_official=False)


def test_label_census_respects_original_censored_measurement(tmp_path):
    data = source(tmp_path)
    rows, report = run(data)
    assert len(rows) == 3
    assert report["source_train_records"] == 3
    assert report["original_censored_train_records"] == 1
    assert report["original_numeric_unverified_train_records"] == 2
    assert report["original_other_unresolved_train_records"] == 0
    assert report["original_test_reserved_aggregate"] == 1
    assert report["original_test_censored_aggregate"] == 1
    assert report["point_targets_scientifically_qualified"] == 0
    assert report["scientifically_qualified_material_count"] is None
    assert report["scientific_qualification_authorized"] is False
    assert "c" not in {r["source_entry_id"] for r in rows}
    b = next(r for r in rows if r["source_entry_id"] == "b")
    assert b["raw_measurement_policy_kind"] == CENSOR
    assert b["original_inequality_text"] == "<1E-10"
    assert b["exclusive_upper_bound_s_per_cm"] == "1E-10"
    assert b["source_numeric_metadata_s_per_cm"] is None
    assert b["processed_surrogate_must_not_be_scored"] is True
    assert not b["point_estimate_benchmark_scoring_permitted"]
    a = next(r for r in rows if r["source_entry_id"] == "a")
    assert a["raw_measurement_policy_kind"] == POINT
    assert a["source_numeric_metadata_s_per_cm"] == "0.001"
    assert a["exclusive_upper_bound_s_per_cm"] is None
    assert not a["point_estimate_benchmark_scoring_permitted"]
    assert all(not x["scientific_material_qualified"] for x in rows)


def test_bound_violation_is_diagnostic_only_and_exclusive(tmp_path):
    below = interval_constraint_check("9e-11", "1e-10")
    equal = interval_constraint_check("1e-10", "1e-10")
    above = interval_constraint_check("1e-9", "1e-10")
    assert below["satisfies_exclusive_bound"]
    assert below["diagnostic_violation_log10"] == "0"
    assert equal["satisfies_exclusive_bound"] is False
    assert equal["diagnostic_violation_log10"] == "0"
    assert above["satisfies_exclusive_bound"] is False
    assert above["diagnostic_violation_log10"] == "1"
    assert all(x["scientific_metric_authorized"] is False
               and x["independent_material_score"] is None
               for x in (below, equal, above))


@pytest.mark.parametrize("prediction,upper", [
    ("NaN", "1e-10"), ("Infinity", "1e-10"),
    ("0", "1e-10"), ("-1e-5", "1e-10"),
    ("1e-5", "0"), ("1e-5", "-1e-10"),
    ("1e-5", "<1e-10"), ("1e100", "1e-10"),
    (100, "1e-10"), ("3e-9", "nan"),
])
def test_bad_interval_inputs_fail_closed(prediction, upper):
    with pytest.raises(ValueError):
        interval_constraint_check(prediction, upper)


def test_rehashed_fabricated_0133_raw_row_refused(tmp_path):
    data = source(tmp_path)
    path = data[2] / "train_raw_measurement_lineage.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]["original_raw_measurement_text"] = "1e-15"
    raw = b"".join(json.dumps(r, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")).encode() + b"\n" for r in rows)
    path.write_bytes(raw)
    prior = data[2] / "summary.json"
    s = json.loads(prior.read_text())
    s["train_record_evidence_sha256"] = hashlib.sha256(raw).hexdigest()
    prior.write_text(json.dumps(s))
    with pytest.raises(ValueError, match="differ from independently recomputed"):
        run(data)


def test_unmodified_source_reproducible_and_output_digest(tmp_path):
    data = source(tmp_path)
    x = run(data)
    y = run(data)
    assert x == y
    rows, report = x
    content = b"".join(json.dumps(r, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode() + b"\n" for r in rows)
    assert hashlib.sha256(content).hexdigest() == report["train_label_policy_jsonl_sha256"]


def test_original_test_id_and_value_never_exposed(tmp_path):
    data = source(tmp_path)
    rows, report = run(data)
    assert len(rows) == 3
    assert all(r["official_original_split"] == "TRAIN" for r in rows)
    assert set(x["source_entry_id"] for x in rows) == {"a", "b", "d"}
    assert "c" not in json.dumps(rows)
    assert not any(k.endswith("_test_ids") or k.endswith("_test_values")
                   for k in report)


def test_public_cli_cannot_bypass_exact_pinned_source(tmp_path):
    data = source(tmp_path)
    destination = tmp_path / "no-output"
    with pytest.raises(SystemExit):
        main([
            "--obelix-checkout", str(data[0]),
            "--evidence-dir", str(data[1]),
            "--raw-lineage-dir", str(data[2]),
            "--output-dir", str(destination),
        ])
    assert not destination.exists()
