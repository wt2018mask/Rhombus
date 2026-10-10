"""No-network synthetic tests for official-split-preserving OBELiX intake."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from rhombus.qualification.obelix_benchmark_intake import (
    build_obelix_benchmark_intake, main, SOURCE_COMMIT,
)


def _git(root: Path, *args: str) -> str:
    x = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                       text=True, check=True)
    return x.stdout.strip()


def checkout(tmp_path, *, rows=None, train=None, test=None, cifs=None, mutate=None):
    root = tmp_path / "upstream"
    (root / "data/randomized_cifs").mkdir(parents=True)
    default = [
        "ID,Composition,Space group number,a,b,c,alpha,beta,gamma,"
        "Ionic conductivity (S cm-1),DOI,CIF",
        "a,Li2S,225,5,5,5,90,90,90,0.001,10.1234/alpha,Match",
        "b,Li3N,191,3,3,4,90,90,120,<1e-10,10.1234/beta,No Match",
        "c,Li6PS5Cl,216,9,9,9,90,90,90,0.2,10.1234/gamma,Close Match",
        "d,Li3PO4,1,4,5,6,80,100,110,1e-8,10.1234/delta|10.1234/second,No Match",
    ]
    data = root / "data"
    (data / "processed.csv").write_text(
        "\n".join(rows if rows is not None else default) + "\n", encoding="utf-8"
    )
    (data / "train_idx.csv").write_text(
        "ID\n" + "\n".join(train if train is not None else ["a", "b", "d"]) + "\n",
        encoding="utf-8",
    )
    (data / "test_idx.csv").write_text(
        "ID\n" + "\n".join(test if test is not None else ["c"]) + "\n",
        encoding="utf-8",
    )
    for name, blob in (cifs if cifs is not None else {
        "a.cif": b"synthetic a", "c.cif": b"synthetic c"
    }).items():
        (data / "randomized_cifs" / name).write_bytes(blob)
    if mutate:
        mutate(root)
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
         "commit", "-qm", "fixture")
    return root, _git(root, "rev-parse", "HEAD")


def test_official_split_source_and_conditional_measurements_preserved(tmp_path):
    root, sha = checkout(tmp_path)
    entries, summary = build_obelix_benchmark_intake(root, expected_commit=sha)
    assert len(entries) == 4
    assert [x["source_entry_id"] for x in entries] == ["a", "b", "c", "d"]
    assert [x["official_split"] for x in entries] == ["TRAIN", "TRAIN", "TEST", "TRAIN"]
    assert summary["official_train_count"] == 3
    assert summary["official_test_count"] == 1
    assert summary["available_cif_count"] == 2
    assert summary["cif_category_counts"] == {"Close Match": 1, "Match": 1, "No Match": 2}
    assert summary["reported_measurement_kind_counts"] == {
        "PROCESSED_REPORTED_POINT": 3, "UPPER_BOUND": 1,
    }
    assert entries[1]["reported_ionic_conductivity_text"] == "<1e-10"
    assert entries[1]["measurement_kind"] == "UPPER_BOUND"
    assert entries[2]["source_cif_match_status"] == "Close Match"
    assert entries[2]["cif_relative_path"] == "data/randomized_cifs/c.cif"
    assert entries[3]["reference_dois"] == ["10.1234/delta", "10.1234/second"]
    assert summary["official_train_test_direct_composition_overlap"] == 0
    assert summary["independent_material_count"] is None
    assert summary["qualified_benchmark_material_count"] == 0
    assert summary["scientific_qualification_authorized"] is False
    assert all(not row["qualified_transport_truth"] for row in entries)


def test_cli_writes_independently_recomputable_hashes_outside_checkout(tmp_path, capsys):
    root, sha = checkout(tmp_path)
    out = tmp_path / "output"
    assert main(["--obelix-checkout", str(root), "--output-dir", str(out),
                 "--expected-commit", sha]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["record_count"] == 4
    assert hashlib.sha256((out / "records.jsonl").read_bytes()).hexdigest() == report["records_jsonl_sha256"]
    assert hashlib.sha256((root / "data/processed.csv").read_bytes()).hexdigest() == report["processed_csv_sha256"]
    assert hashlib.sha256((root / "data/train_idx.csv").read_bytes()).hexdigest() == report["train_idx_sha256"]
    assert hashlib.sha256((root / "data/test_idx.csv").read_bytes()).hexdigest() == report["test_idx_sha256"]
    assert json.loads((out / "summary.json").read_text()) == report
    assert _git(root, "status", "--porcelain") == ""
    with pytest.raises(SystemExit):
        main(["--obelix-checkout", str(root), "--output-dir", str(out),
              "--expected-commit", sha])


def test_output_cannot_dirty_checkout(tmp_path):
    root, sha = checkout(tmp_path)
    with pytest.raises(SystemExit):
        main(["--obelix-checkout", str(root), "--output-dir", str(root / "results"),
              "--expected-commit", sha])


def test_unpinned_checkout_does_not_get_misattributed(tmp_path):
    root, sha = checkout(tmp_path)
    with pytest.raises(ValueError, match="pinned"):
        build_obelix_benchmark_intake(root)
    with pytest.raises(ValueError):
        build_obelix_benchmark_intake(root, expected_commit="synthetic")


@pytest.mark.parametrize("train,test", [
    (["a", "b", "c", "d"], ["c"]),
    (["a", "b"], ["c"]),
    (["a", "b", "d", "a"], ["c"]),
    (["a", "b", "d"], ["c", "missing"]),
])
def test_official_split_overlap_gap_duplicate_foreign_id_rejected(tmp_path, train, test):
    root, sha = checkout(tmp_path, train=train, test=test)
    with pytest.raises(ValueError):
        build_obelix_benchmark_intake(root, expected_commit=sha)


@pytest.mark.parametrize("source", [
    "0", "-1", "NaN", "Infinity", "garbled", ">1e-8", "<0",
])
def test_conductivity_not_silently_converted_to_scored_value(tmp_path, source):
    baseline = [
        "ID,Composition,Space group number,a,b,c,alpha,beta,gamma,"
        "Ionic conductivity (S cm-1),DOI,CIF",
        f"a,Li2S,225,5,5,5,90,90,90,{source},10.1234/alpha,Match",
        "b,Li3N,191,3,3,4,90,90,120,1e-9,10.1234/beta,No Match",
    ]
    root, sha = checkout(tmp_path, rows=baseline, train=["a"], test=["b"],
                         cifs={"a.cif": b"synthetic"})
    with pytest.raises(ValueError):
        build_obelix_benchmark_intake(root, expected_commit=sha)


def test_absent_cif_matching_or_orphan_cif_rejected(tmp_path):
    root, sha = checkout(tmp_path, cifs={"a.cif": b"only a"})
    with pytest.raises(ValueError, match="CIF"):
        build_obelix_benchmark_intake(root, expected_commit=sha)
    root2, sha2 = checkout(tmp_path / "another", cifs={
        "a.cif": b"a", "c.cif": b"c", "unknown.cif": b"unknown",
    })
    with pytest.raises(ValueError, match="unreferenced"):
        build_obelix_benchmark_intake(root2, expected_commit=sha2)


def test_doi_and_exact_composition_overlap_reported_not_hidden(tmp_path):
    root, sha = checkout(tmp_path)
    csv_path = root / "data/processed.csv"
    src = csv_path.read_text().replace(
        "c,Li6PS5Cl,216", "c,Li2S,216"
    ).replace("10.1234/gamma", "10.1234/alpha")
    csv_path.write_text(src, encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
         "commit", "-qm", "modified source")
    sha2 = _git(root, "rev-parse", "HEAD")
    _, summary = build_obelix_benchmark_intake(root, expected_commit=sha2)
    assert summary["official_train_test_direct_composition_overlap"] == 1
    assert summary["official_train_test_doi_overlap"] == 1
    assert summary["scientific_qualification_authorized"] is False


def test_dirty_checkout_rejected_even_if_commit_matches(tmp_path):
    root, sha = checkout(tmp_path)
    (root / "data/processed.csv").write_text("tamper\n")
    with pytest.raises(ValueError):
        build_obelix_benchmark_intake(root, expected_commit=sha)


def test_intake_has_no_gpu_or_network_calls(tmp_path, monkeypatch):
    root, sha = checkout(tmp_path)
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("intake unexpectedly used network")
    ))
    records, report = build_obelix_benchmark_intake(root, expected_commit=sha)
    assert records and report["record_count"] == 4
