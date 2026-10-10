"""Synthetic bounded Git blob streaming contracts; no network or real secrets."""
from __future__ import annotations

import io

from scripts.security import audit_credential_history as audit


def fake_history(monkeypatch, tmp_path, records, *, truncate=None, fail=None):
    """Git process substitute that never reads a real credential or repository."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir(exist_ok=True)
    blobs = {oid: data for oid, _path, data in records}
    names = {oid: path for oid, path, _data in records}
    def check_output(command, **_kwargs):
        if command[:3] == ["git", "rev-list", "--objects"]:
            return "".join(f"{oid} {names[oid]}\n" for oid in blobs)
        if command[:3] == ["git", "cat-file", "-t"]:
            return "blob\n"
        if command[:3] == ["git", "cat-file", "-s"]:
            return str(len(blobs[command[3]])) + "\n"
        if command[:3] == ["git", "cat-file", "blob"]:
            return blobs[command[3]]
        raise AssertionError(command)

    class FakeProcess:
        def __init__(self, oid):
            payload = blobs[oid]
            self.stdout = io.BytesIO(payload[:truncate] if oid == truncate_oid else payload)
            self.returncode = 0 if oid != fail else 2
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            self.stdout.close()
        def wait(self, timeout):
            assert timeout <= 60
            return self.returncode

    truncate_oid = records[-1][0] if truncate is not None else None
    def popen(command, **kwargs):
        assert command[:3] == ["git", "cat-file", "blob"]
        return FakeProcess(command[3])

    monkeypatch.setattr(audit.subprocess, "check_output", check_output)
    monkeypatch.setattr(audit.subprocess, "Popen", popen)


def budgets(monkeypatch):
    monkeypatch.setattr(audit, "MAX_BLOB_BYTES", 8)
    monkeypatch.setattr(audit, "MAX_STREAM_BLOB_BYTES", 128)
    monkeypatch.setattr(audit, "MAX_TOTAL_STREAM_BLOB_BYTES", 256)
    monkeypatch.setattr(audit, "STREAM_CHUNK_BYTES", 7)
    monkeypatch.setattr(audit, "STREAM_PATTERN_OVERLAP", 64)


def bearer():
    return b"Authorization: " + b"Bearer " + b"q" * 30


def test_pattern_crossing_many_stream_windows_is_detected(monkeypatch, tmp_path):
    budgets(monkeypatch)
    oid = "a" * 40
    data = b"begin" + bearer() + b"end"
    fake_history(monkeypatch, tmp_path, [(oid, "suspicious.txt", data)])
    result = audit.scan_git()
    assert result["status"] == "COMPLETE"
    assert result["scanned_blobs"] == 1
    assert result["streamed_blobs"] == 1
    assert result["streamed_bytes"] == len(data)
    assert result["skipped_large_blobs"] == 0
    assert result["findings"] == [{"blob_id": oid, "path": "suspicious.txt",
                                   "rule": "authorization_bearer"}]
    assert "q" * 30 not in str(result)


def test_streamed_binary_remains_incomplete_but_reports_signatures(monkeypatch, tmp_path):
    budgets(monkeypatch)
    oid = "b" * 40
    payload = b"\x00" + b"a" * 16 + bearer()
    fake_history(monkeypatch, tmp_path, [(oid, "opaque.bin", payload)])
    result = audit.scan_git()
    assert result["status"] == "INCOMPLETE"
    assert result["opaque_blobs"] == 1
    assert result["opaque_reasons"] == {"binary_nul": 1}
    assert [x["rule"] for x in result["findings"]] == ["authorization_bearer"]


def test_streamed_nested_zip_magic_keeps_incomplete_verdict(monkeypatch, tmp_path):
    budgets(monkeypatch)
    oid = "c" * 40
    fake_history(monkeypatch, tmp_path, [(oid, "nested.txt", b"PK\x03\x04" + b"test" * 15)])
    result = audit.scan_git()
    assert result["status"] == "INCOMPLETE"
    assert result["opaque_reasons"] == {"nested_or_opaque_magic": 1}


def test_object_size_budget_counts_skip_without_loading_data(monkeypatch, tmp_path):
    budgets(monkeypatch)
    monkeypatch.setattr(audit, "MAX_STREAM_BLOB_BYTES", 16)
    oid = "d" * 40
    fake_history(monkeypatch, tmp_path, [(oid, "huge.txt", b"x" * 48)])
    result = audit.scan_git()
    assert result["status"] == "INCOMPLETE"
    assert result["scanned_blobs"] == 0
    assert result["streamed_blobs"] == 0
    assert result["skip_reasons"] == {"object_size_budget": 1}


def test_aggregate_budget_retains_previous_scans(monkeypatch, tmp_path):
    budgets(monkeypatch)
    monkeypatch.setattr(audit, "MAX_TOTAL_STREAM_BLOB_BYTES", 30)
    one, two = "e" * 40, "f" * 40
    fake_history(monkeypatch, tmp_path, [
        (one, "one.txt", b"x" * 25), (two, "two.txt", b"y" * 25),
    ])
    result = audit.scan_git()
    assert result["status"] == "INCOMPLETE"
    assert result["scanned_blobs"] == 1
    assert result["streamed_blobs"] == 1
    assert result["streamed_bytes"] == 25
    assert result["skip_reasons"] == {"aggregate_stream_budget": 1}


def test_truncated_stream_does_not_erase_prior_scanned_findings(monkeypatch, tmp_path):
    budgets(monkeypatch)
    small, large = "1" * 40, "2" * 40
    fake_history(monkeypatch, tmp_path, [
        (small, "short.txt", bearer()),
        (large, "truncated.txt", b"nonsecret" * 6),
    ], truncate=5)
    result = audit.scan_git()
    assert result["status"] == "INCOMPLETE"
    assert result["skipped_large_blobs"] == 1
    assert result["skip_reasons"] == {"stream_unreadable": 1}
    assert len(result["findings"]) == 1
    assert result["findings"][0]["blob_id"] == small


def test_nonzero_git_cat_file_exit_is_incomplete(monkeypatch, tmp_path):
    budgets(monkeypatch)
    oid = "3" * 40
    fake_history(monkeypatch, tmp_path, [(oid, "failed.txt", b"test" * 6)], fail=oid)
    result = audit.scan_git()
    assert result["status"] == "INCOMPLETE"
    assert result["skipped_large_blobs"] == 1
    assert result["skip_reasons"] == {"stream_unreadable": 1}
