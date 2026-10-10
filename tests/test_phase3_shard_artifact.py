"""Offline SQLite artifact checks; no Kaggle credentials or network."""
import hashlib
from pathlib import Path
import sqlite3

import pytest

from rhombus.domain.shard_artifact import verify_membership_shard_file

SOURCE = "a" * 64


def make_artifact(tmp_path, *, rows=3, source=SOURCE):
    path = tmp_path / "membership.sqlite"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    con.executemany("INSERT INTO metadata VALUES (?, ?)", [
        ("dataset_id", "sAlex"), ("source_file_sha256", source),
        ("row_count", str(rows)),
    ])
    con.execute("""CREATE TABLE membership (
        dataset_id TEXT, record_id TEXT, source_locator TEXT,
        composition_key TEXT, site_count INTEGER,
        structure_fingerprint_sha256 TEXT, prototype_group TEXT
    )""")
    con.executemany("INSERT INTO membership VALUES (?, ?, ?, ?, ?, ?, ?)", [
        ("sAlex", str(i), str(i), "Li2O", 3, "f" * 64, "prototype")
        for i in range(rows)
    ])
    con.commit()
    con.close()
    return path


def verify(path, rows=3):
    return verify_membership_shard_file(
        trusted_path=path,
        expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        expected_source_sha256=SOURCE,
        expected_row_count=rows,
    )


def test_finalized_db_verified_but_not_scientific_pass(tmp_path):
    out = verify(make_artifact(tmp_path))
    assert out["artifact_bytes_verified"] is True
    assert out["sqlite_integrity_verified"] is True
    assert out["source_stream_verified"] is False
    assert out["claim_authorized"] is False
    assert out["scientific_verdict"] == "UNKNOWN"


def test_wrong_digest_rejected(tmp_path):
    path = make_artifact(tmp_path)
    with pytest.raises(ValueError, match="SHA256"):
        verify_membership_shard_file(
            trusted_path=path, expected_sha256="b"*64,
            expected_source_sha256=SOURCE, expected_row_count=3,
        )


def test_wrong_source_or_row_count_rejected(tmp_path):
    path = make_artifact(tmp_path)
    with pytest.raises(ValueError, match="source identity"):
        verify_membership_shard_file(
            trusted_path=path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            expected_source_sha256="c"*64, expected_row_count=3,
        )
    with pytest.raises(ValueError, match="row count"):
        verify(path, rows=2)


def test_diagnostic_corrupt_db_and_wal_rejected(tmp_path):
    path = make_artifact(tmp_path)
    Path(str(path) + "-wal").write_bytes(b"partial")
    with pytest.raises(ValueError, match="WAL"):
        verify(path)
    Path(str(path) + "-wal").unlink()
    path.write_bytes(b"not sqlite")
    with pytest.raises(ValueError, match="SQLite"):
        verify(path)


def test_wrong_path_and_bounds_rejected(tmp_path):
    path = make_artifact(tmp_path)
    with pytest.raises(ValueError, match="trusted_path"):
        verify_membership_shard_file(
            trusted_path=str(path), expected_sha256="b"*64,
            expected_source_sha256=SOURCE, expected_row_count=3,
        )
    with pytest.raises(ValueError, match="expected_row_count"):
        verify_membership_shard_file(
            trusted_path=path, expected_sha256="b"*64,
            expected_source_sha256=SOURCE, expected_row_count=True,
        )


def test_duplicate_membership_records_are_not_complete_coverage(tmp_path):
    path = make_artifact(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE membership SET record_id='duplicate'")
    with pytest.raises(ValueError, match='duplicate'):
        verify(path)
