"""Synthetic-only RT-P1-03 adversarial export fixtures."""
import gzip
import importlib.util
import io
from pathlib import Path
import sqlite3
import zipfile

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/security/scan_outgoing_artifacts.py"
spec = importlib.util.spec_from_file_location("redteam_scan", SCRIPT)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)
SYNTHETIC = ("ghp_" + "x" * 32).encode()


def zip_bytes(name, body):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, body)
    return out.getvalue()


@pytest.mark.parametrize("kind", ["gz", "zip", "nested", "zst", "sqlite-text", "sqlite-blob"])
def test_hidden_synthetic_credential_detected_or_export_denied(tmp_path, kind):
    (tmp_path / "receipt.json").write_text('{"status":"diagnostic"}')
    if kind == "gz":
        (tmp_path / "hidden.txt.gz").write_bytes(gzip.compress(SYNTHETIC))
    elif kind == "zip":
        (tmp_path / "hidden.zip").write_bytes(zip_bytes("hidden.txt", SYNTHETIC))
    elif kind == "nested":
        (tmp_path / "hidden.zip").write_bytes(zip_bytes("inner.txt.gz", gzip.compress(SYNTHETIC)))
    elif kind == "zst":
        (tmp_path / "hidden.zst").write_bytes(b"\x28\xb5\x2f\xfd" + SYNTHETIC)
    else:
        with sqlite3.connect(tmp_path / "hidden.sqlite") as db:
            db.execute("CREATE TABLE secret_payload (value)")
            db.execute("INSERT INTO secret_payload VALUES (?)", (SYNTHETIC if kind.endswith("blob") else SYNTHETIC.decode(),))
    with pytest.raises(ValueError):
        scan.scan_directory(tmp_path)


@pytest.mark.parametrize("kind", ["gzip-bomb", "zip-bomb", "malformed-gz", "malformed-zip", "nested-limit"])
def test_archive_limits_fail_closed(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(scan, "MAX_TEXT_BYTES", 1024)
    body = b"a" * 8192
    if kind == "gzip-bomb":
        data, name = gzip.compress(body), "bomb.txt.gz"
    elif kind == "zip-bomb":
        data, name = zip_bytes("bomb.txt", body), "bomb.zip"
    elif kind == "malformed-gz":
        data, name = b"not gzip", "bad.txt.gz"
    elif kind == "malformed-zip":
        data, name = b"PK\x03\x04", "bad.zip"
    else:
        data, name = b"ok", "leaf.txt"
        for _ in range(6):
            data, name = zip_bytes(name, data), "inner.zip"
    (tmp_path / "receipt.json").write_text("{}")
    (tmp_path / name).write_bytes(data)
    with pytest.raises(ValueError):
        scan.scan_directory(tmp_path)


def test_valid_bounded_text_archives_are_inspected(tmp_path):
    (tmp_path / "receipt.json").write_text("{}")
    (tmp_path / "evidence.zip").write_bytes(zip_bytes("data.txt.gz", gzip.compress(b"safe evidence")))
    assert scan.scan_directory(tmp_path) == (2, 0)


def test_expected_file_allowlist_rejects_unexpected_text(tmp_path):
    (tmp_path / "receipt.json").write_text("{}")
    (tmp_path / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="allowlist"):
        scan.scan_directory(tmp_path, allowed_paths={"receipt.json"})


@pytest.mark.parametrize("name", ["../escape.txt", "/abs.txt", "folder/../../escape.txt", "unrecognized.bin"])
def test_unsafe_archive_entry_denied(tmp_path, name):
    (tmp_path / "evidence.zip").write_bytes(zip_bytes(name, b"safe"))
    with pytest.raises(ValueError):
        scan.scan_directory(tmp_path)


def test_archive_comment_and_json_key_credentials_denied(tmp_path):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("safe.txt", "safe")
        z.comment = SYNTHETIC
    (tmp_path / "evidence.zip").write_bytes(out.getvalue())
    with pytest.raises(ValueError):
        scan.scan_directory(tmp_path)
    (tmp_path / "evidence.zip").unlink()
    (tmp_path / "key.json").write_text('{"api_key":"synthetic_only_value"}')
    with pytest.raises(ValueError):
        scan.scan_directory(tmp_path)


def test_total_bytes_and_entry_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "MAX_TOTAL_BYTES", 8)
    (tmp_path / "one.txt").write_text("abcde")
    (tmp_path / "two.txt").write_text("abcde")
    with pytest.raises(ValueError):
        scan.scan_directory(tmp_path)
    monkeypatch.setattr(scan, "MAX_TOTAL_BYTES", 1024)
    monkeypatch.setattr(scan, "MAX_ENTRIES", 1)
    with pytest.raises(ValueError):
        scan.scan_directory(tmp_path)
