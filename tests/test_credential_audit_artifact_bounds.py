"""Fail-closed regression tests for historical Actions credential-audit coverage.

Artificial token strings are assembled at runtime; no real credential is used.
"""
from __future__ import annotations

import io
import zipfile
import urllib.request

import pytest

from scripts.security import audit_credential_history as audit


def make_zip(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in entries.items():
            archive.writestr(name, body)
    return output.getvalue()


def fake_artifacts(monkeypatch, fixtures: list[dict], zip_payload: bytes):
    calls = []

    def fake_inventory(url, token):
        assert token == "test-only-credential"
        return {"artifacts": fixtures} if "page=1" in url else {"artifacts": []}

    class Opener:
        def open(self, request, timeout):
            calls.append((request.full_url, timeout))
            return io.BytesIO(zip_payload)

    monkeypatch.setattr(audit, "api_json", fake_inventory)
    monkeypatch.setattr(audit.urllib.request, "build_opener", lambda *handlers: Opener())
    return calls


def test_cross_origin_artifact_redirect_never_forwards_authorization():
    request = urllib.request.Request(
        "https://api.github.com/repos/example/repo/actions/artifacts/1/zip",
        headers={"Authorization": "Bearer test-only-credential"},
    )
    policy = audit.ArtifactRedirectPolicy()
    moved = policy.redirect_request(request, None, 302, "Found", {},
                                    "https://objects.example.invalid/artifact")
    assert moved.get_header("Authorization") is None
    assert "Authorization" not in moved.unredirected_hdrs
    same_host = policy.redirect_request(request, None, 302, "Found", {},
                                        "https://api.github.com/next")
    assert same_host.get_header("Authorization") is not None


def test_plain_http_artifact_redirect_fails_closed():
    request = urllib.request.Request("https://api.github.com/source",
                                     headers={"Authorization": "Bearer placeholder"})
    with pytest.raises(ValueError, match="insecure_artifact_redirect"):
        audit.ArtifactRedirectPolicy().redirect_request(
            request, None, 302, "Found", {}, "http://objects.example.invalid/archive")


def test_bounded_zip_entry_count_is_uninspected_not_clean(monkeypatch):
    payload = make_zip({"first.txt": b"a", "second.txt": b"b"})
    calls = fake_artifacts(monkeypatch, [{"id": 1, "size_in_bytes": len(payload)}], payload)
    monkeypatch.setattr(audit, "MAX_ARCHIVE_ENTRIES", 1)
    outcome = audit.scan_artifacts("example/repo", "test-only-credential")
    assert outcome["status"] == "INCOMPLETE"
    assert outcome["scanned_archives"] == 0
    assert outcome["skip_reasons"] == {"entry_count_budget": 1}
    assert len(calls) == 1


def test_bounded_zip_expansion_is_uninspected_not_clean(monkeypatch):
    payload = make_zip({"payload.txt": b"a" * 12})
    fake_artifacts(monkeypatch, [{"id": 2, "size_in_bytes": len(payload)}], payload)
    monkeypatch.setattr(audit, "MAX_TOTAL_EXPANDED_BYTES", 8)
    outcome = audit.scan_artifacts("example/repo", "test-only-credential")
    assert outcome["status"] == "INCOMPLETE"
    assert outcome["skip_reasons"] == {"expanded_size_budget": 1}
    assert outcome["scanned_entries"] == 0


def test_oversized_entry_retains_partial_coverage(monkeypatch):
    payload = make_zip({"large.txt": b"12345", "small.txt": b"ab"})
    fake_artifacts(monkeypatch, [{"id": 3, "size_in_bytes": len(payload)}], payload)
    monkeypatch.setattr(audit, "MAX_ENTRY_BYTES", 4)
    outcome = audit.scan_artifacts("example/repo", "test-only-credential")
    assert outcome["status"] == "INCOMPLETE"
    assert outcome["scanned_archives"] == 1
    assert outcome["scanned_entries"] == 1
    assert outcome["skipped_entries"] == 1
    assert outcome["skip_reasons"] == {}


def test_clean_bounded_archive_is_scanned_and_findings_preserved(monkeypatch):
    token_body = b"Authorization: " + b"Bearer " + (b"x" * 28)
    payload = make_zip({"tiny.txt": token_body})
    fake_artifacts(monkeypatch, [{"id": 4, "size_in_bytes": len(payload)}], payload)
    outcome = audit.scan_artifacts("example/repo", "test-only-credential")
    assert outcome["status"] == "COMPLETE"
    assert outcome["scanned_archives"] == 1
    assert outcome["skipped_archives"] == 0
    assert outcome["findings"] == [{"artifact_id": 4, "entry_name": "tiny.txt",
                                    "rule": "authorization_bearer"}]
    assert "x" * 28 not in str(outcome)


def test_unknown_zip_compression_is_incomplete_not_a_crash(monkeypatch):
    payload = bytearray(make_zip({"unknown.txt": b"abc"}))
    # Modify only the ZIP local/central compression-method fields to a
    # deliberately unsupported value; the fixture is synthetic and offline.
    for marker, offset in ((b"PK\\x03\\x04", 8), (b"PK\\x01\\x02", 10)):
        position = payload.find(marker)
        assert position >= 0
        payload[position + offset:position + offset + 2] = (99).to_bytes(2, "little")
    fake_artifacts(monkeypatch, [{"id": 6, "size_in_bytes": len(payload)}],
                   bytes(payload))
    outcome = audit.scan_artifacts("example/repo", "test-only-credential")
    assert outcome["status"] == "INCOMPLETE"
    assert outcome["scanned_archives"] == 0
    assert outcome["skipped_archives"] == 1
    assert outcome["skip_reasons"] == {"unreadable_archive": 1}


def test_expired_archives_remain_explicitly_incomplete(monkeypatch):
    fake_artifacts(monkeypatch, [{"id": 5, "expired": True}], b"")
    outcome = audit.scan_artifacts("example/repo", "test-only-credential")
    assert outcome["status"] == "INCOMPLETE"
    assert outcome["skipped_archives"] == 1
    assert outcome["skip_reasons"] == {"expired": 1}
