"""0133 original raw Excel upper-limit recovery, with official TEST quarantine."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile
from xml.sax.saxutils import escape

import pytest

from scripts.science.obelix_raw_censor_lineage import (
    _xlsx_cells, build_original_censor_audit, main,
)
from scripts.science.obelix_real_source_pipeline import run_three_stage_obelix
from tests.test_phase3_obelix_benchmark_intake import checkout, _git


def make_excel(path, rows, *, with_shared_strings=False):
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    header = ["ID", "Ionic conductivity (S cm-1)", "IC (Total)", "IC (Bulk)"]
    data = [header, *rows]
    all_strings = list(dict.fromkeys(str(x) for row in data for x in row))
    lookup = {s: i for i, s in enumerate(all_strings)}
    body = []
    for i, row in enumerate(data, 1):
        cs = []
        for col, value in zip("ABCD", row):
            raw = escape(str(value))
            if with_shared_strings:
                cs.append(f'<c r="{col}{i}" t="s"><v>{lookup[str(value)]}</v></c>')
            else:
                cs.append(f'<c r="{col}{i}" t="inlineStr"><is><t>{raw}</t></is></c>')
        body.append(f'<row r="{i}">{"".join(cs)}</row>')
    sheet = f'<worksheet xmlns="{ns}"><sheetData>{"".join(body)}</sheetData></worksheet>'
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        if with_shared_strings:
            si = "".join(f"<si><t>{escape(x)}</t></si>" for x in all_strings)
            z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{ns}">{si}</sst>')


def fixture(tmp_path, *, b_source="<1E-10", b_processed="1e-15", c_source="<1E-8"):
    rows = [
        "ID,Composition,Space group number,a,b,c,alpha,beta,gamma,"
        "Ionic conductivity (S cm-1),DOI,CIF",
        "a,Li2S,225,5,5,5,90,90,90,0.001,10.1234/alpha,Match",
        f"b,Li3N,191,3,3,4,90,90,120,{b_processed},10.1234/beta,No Match",
        "c,Li6PS5Cl,216,9,9,9,90,90,90,1e-15,10.1234/gamma,Close Match",
        "d,Li3PO4,1,4,5,6,80,100,110,1e-8,10.1234/delta|10.1234/second,No Match",
    ]
    root, _ = checkout(tmp_path, rows=rows)
    make_excel(root / "data/raw.xlsx", [
        ("a", "0.001", "0.0005", "0.001"),
        ("b", b_source, "", ""),
        ("c", c_source, "", ""),
        ("d", "1e-8", "", ""),
    ])
    _git(root, "add", ".")
    _git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
         "commit", "-qm", "source workbook")
    sha = _git(root, "rev-parse", "HEAD")
    bundle = tmp_path / "pipeline"
    run_three_stage_obelix(root, bundle, expected_commit=sha,
                           require_official_counts=False)
    return root, bundle


def test_raw_source_upper_bounds_are_recovered_without_promoting_science(tmp_path):
    root, bundle = fixture(tmp_path)
    rows, report = build_original_censor_audit(root, bundle,
                                                require_official=False)
    assert len(rows) == 3
    assert report["processed_source_record_count"] == 4
    assert report["processed_numeric_floor_1e_minus_15_count"] == 2
    assert report["raw_upper_bound_count"] == 2
    assert report["raw_train_censored_records"] == 1
    assert report["raw_test_censored_records_reserved"] == 1
    assert report["original_train_records"] == 3
    assert report["original_test_records_reserved"] == 1
    assert report["new_scientifically_qualified_materials"] == 0
    assert report["scientific_qualification_authorized"] is False
    assert {r["source_entry_id"] for r in rows} == {"a", "b", "d"}
    b = next(r for r in rows if r["source_entry_id"] == "b")
    assert b["original_raw_measurement_text"] == "<1E-10"
    assert b["processed_numeric_text"] == "1e-15"
    assert b["raw_measurement_kind"] == "ORIGINAL_UPPER_BOUND_NUMERIC_PLACEHOLDER"
    assert b["raw_censor_upper_bound_is_a_point_value"] is False
    assert all("c" != r["source_entry_id"] for r in rows)
    assert "original_test_ids" not in report
    a = next(r for r in rows if r["source_entry_id"] == "a")
    assert a["raw_total_component_text"] == "0.0005"
    assert a["raw_bulk_component_text"] == "0.001"


def test_original_xlsx_shared_string_reader(tmp_path):
    p = tmp_path / "raw.xlsx"
    make_excel(p, [("A1", "<1E-8", "", "2.5e-3")], with_shared_strings=True)
    headers, rows = _xlsx_cells(p.read_bytes())
    assert "IC (Bulk)" in headers
    assert rows[0]["ID"] == "A1"
    assert rows[0]["Ionic conductivity (S cm-1)"] == "<1E-8"
    assert rows[0]["IC (Bulk)"] == "2.5e-3"


def test_upper_bound_cannot_become_ordinary_point_value(tmp_path):
    root, bundle = fixture(tmp_path, b_processed="3e-12")
    with pytest.raises(ValueError, match="numeric 1e-15 proxy"):
        build_original_censor_audit(root, bundle, require_official=False)


def test_no_synthetic_censor_when_raw_reports_exact_positive_numeric(tmp_path):
    root, bundle = fixture(tmp_path, b_source="1e-15", c_source="1e-15")
    rows, report = build_original_censor_audit(root, bundle,
                                                require_official=False)
    assert report["raw_upper_bound_count"] == 0
    assert report["processed_numeric_floor_1e_minus_15_count"] == 2
    assert all(r["raw_measurement_kind"] == "RAW_REPORTED_NUMERIC" for r in rows)


def test_noncanonical_original_upper_bound_fails_closed(tmp_path):
    root, bundle = fixture(tmp_path, b_source="<4E-11")
    with pytest.raises(ValueError, match="noncanonical"):
        build_original_censor_audit(root, bundle, require_official=False)


def test_official_source_pin_cannot_be_bypassed_by_fixture(tmp_path):
    root, bundle = fixture(tmp_path)
    with pytest.raises(ValueError, match="official source"):
        build_original_censor_audit(root, bundle)


def test_modified_source_workbook_without_commit_is_not_accepted(tmp_path):
    root, bundle = fixture(tmp_path)
    with (root / "data/raw.xlsx").open("ab") as f:
        f.write(b"x")
    with pytest.raises(ValueError, match="clean"):
        build_original_censor_audit(root, bundle, require_official=False)


def test_changed_prior_pipeline_artifact_is_rejected(tmp_path):
    root, bundle = fixture(tmp_path)
    p = bundle / "0127/records.jsonl"
    p.write_bytes(p.read_bytes().replace(b"Li2S", b"Li2O"))
    with pytest.raises(ValueError, match="digest"):
        build_original_censor_audit(root, bundle, require_official=False)


def test_deterministic_provenance_of_original_workbook_and_train_rows(tmp_path):
    root, bundle = fixture(tmp_path)
    first = build_original_censor_audit(root, bundle, require_official=False)
    second = build_original_censor_audit(root, bundle, require_official=False)
    assert first == second
    r, report = first
    assert report["original_raw_workbook_sha256"] == hashlib.sha256(
        (root / "data/raw.xlsx").read_bytes()).hexdigest()
    assert report["train_record_evidence_sha256"] == hashlib.sha256(
        b"".join(json.dumps(row, ensure_ascii=False, sort_keys=True,
                 separators=(",", ":")).encode() + b"\n" for row in r)
    ).hexdigest()


def test_public_cli_refuses_synthetic_source(tmp_path):
    root, bundle = fixture(tmp_path)
    out = tmp_path / "report"
    with pytest.raises(SystemExit):
        main(["--obelix-checkout", str(root),
              "--evidence-dir", str(bundle), "--output-dir", str(out)])
    assert not out.exists()
