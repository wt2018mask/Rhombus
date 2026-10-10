"""Adversarial synthetic tests: raw signatures cannot clear opaque evidence."""
from __future__ import annotations

import io
import subprocess
import zipfile

import pytest

from scripts.security import audit_credential_history as audit


def zip_bytes(items: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as arc:
        for name, contents in items.items():
            arc.writestr(name, contents)
    return buf.getvalue()


def mock_artifact(monkeypatch, name: str, data: bytes):
    outer = zip_bytes({name: data})
    monkeypatch.setattr(audit, "api_json", lambda url, token: {
        "artifacts": [{"id": 12, "size_in_bytes": len(outer)}] if "page=1" in url else []
    })

    class FakeOpener:
        def open(self, request, timeout):
            return io.BytesIO(outer)

    monkeypatch.setattr(audit.urllib.request, "build_opener", lambda *handlers: FakeOpener())
    return audit.scan_artifacts("owner/repo", "synthetic-token")


def fake_bearer() -> bytes:
    return b"Authorization: " + b"Bearer " + b"q" * 28


def test_nul_prefix_no_longer_suppresses_raw_pattern():
    payload = bytes([0]) + b"unrelated" + fake_bearer()
    assert audit.classify(payload) == ["authorization_bearer"]
    assert audit.opaque_reason(payload) == "binary_nul"


def test_deceptive_zip_magic_is_opaque_without_filename_extension(monkeypatch):
    nested = zip_bytes({"payload.txt": fake_bearer()})
    # A raw-only scan cannot see the compressed inner text.
    assert audit.classify(nested) == []
    assert audit.opaque_reason(nested, "harmless.txt") == "nested_or_opaque_magic"
    result = mock_artifact(monkeypatch, "harmless.txt", nested)
    assert result["status"] == "INCOMPLETE"
    assert result["scanned_entries"] == 1
    assert result["opaque_entries"] == 1
    assert result["opaque_reasons"] == {"nested_or_opaque_magic": 1}
    assert result["findings"] == []


def test_declared_nested_gzip_extension_not_clear(monkeypatch):
    result = mock_artifact(monkeypatch, "capture.GZ", b"plaintext without literal token")
    assert result["status"] == "INCOMPLETE"
    assert result["opaque_entries"] == 1
    assert result["opaque_reasons"] == {"opaque_extension": 1}


def test_gzip_magic_with_disguised_name_not_clear(monkeypatch):
    payload = bytes([0x1F, 0x8B]) + b"synthetic bytes"
    result = mock_artifact(monkeypatch, "undisclosed.txt", payload)
    assert result["status"] == "INCOMPLETE"
    assert result["opaque_reasons"] == {"nested_or_opaque_magic": 1}


def test_opaque_binary_still_reports_visible_secret_signatures(monkeypatch):
    result = mock_artifact(monkeypatch, "mixed.dat", bytes([0]) + fake_bearer())
    assert result["status"] == "INCOMPLETE"
    assert result["opaque_entries"] == 1
    assert result["opaque_reasons"] == {"binary_nul": 1}
    assert result["findings"] == [{"artifact_id": 12, "entry_name": "mixed.dat",
                                   "rule": "authorization_bearer"}]
    assert "q" * 28 not in str(result)


def test_plain_text_keeps_complete_semantics(monkeypatch):
    result = mock_artifact(monkeypatch, "readme.txt", b"non-sensitive synthetic text")
    assert result["status"] == "COMPLETE"
    assert result["opaque_entries"] == 0
    assert result["scanned_entries"] == 1


def test_git_binary_blob_is_flagged_incomplete_without_erasing_findings(
    monkeypatch, tmp_path,
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    blob_id = "a" * 40
    blob = b"\x00" + fake_bearer()
    def fake_check_output(command, **kwargs):
        if command[:3] == ["git", "rev-list", "--objects"]:
            return blob_id + " docs/a.bin\n"
        if command[:3] == ["git", "cat-file", "-t"]:
            return "blob\n"
        if command[:3] == ["git", "cat-file", "-s"]:
            return str(len(blob)) + "\n"
        if command[:3] == ["git", "cat-file", "blob"]:
            return blob
        raise AssertionError(f"unrecognized git command: {command}")

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    result = audit.scan_git()
    assert result["status"] == "INCOMPLETE"
    assert result["scanned_blobs"] == 1
    assert result["opaque_blobs"] == 1
    assert result["opaque_reasons"] == {"binary_nul": 1}
    assert result["findings"] == [{"blob_id": blob_id, "path": "docs/a.bin",
                                   "rule": "authorization_bearer"}]


def test_git_plain_text_blob_is_complete_when_nothing_is_skipped(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    blob_id = "b" * 40
    def fake_check_output(command, **kwargs):
        if command[:3] == ["git", "rev-list", "--objects"]:
            return blob_id + " readme.txt\n"
        if command[:3] == ["git", "cat-file", "-t"]:
            return "blob\n"
        if command[:3] == ["git", "cat-file", "-s"]:
            return "5\n"
        if command[:3] == ["git", "cat-file", "blob"]:
            return b"hello"
        raise AssertionError(command)
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    result = audit.scan_git()
    assert result["status"] == "COMPLETE"
    assert result["opaque_blobs"] == 0
    assert result["findings"] == []
