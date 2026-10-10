"""Adversarial bounded nested ZIP/gzip credential-audit tests (synthetic only)."""
from __future__ import annotations

import gzip
import io
import zipfile

import pytest

from scripts.security import audit_credential_history as audit


def make_zip(entries: dict[str, bytes]) -> bytes:
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED) as arc:
        for name, data in entries.items():
            arc.writestr(name, data)
    return result.getvalue()


def synthetic_bearer() -> bytes:
    return b"Authorization: " + b"Bearer " + b"q" * 28


def test_nested_zip_detects_compressed_secret_even_without_zip_extension():
    container = make_zip({"secret.txt": synthetic_bearer()})
    assert audit.classify(container) == []
    rules, reason = audit.inspect_bounded_nested(container, "disguised.txt")
    assert rules == ["authorization_bearer"]
    assert reason is None
    assert "q" * 28 not in str((rules, reason))


def test_nested_gzip_detects_secret_by_magic_and_extension():
    compressed = gzip.compress(synthetic_bearer())
    for name in ("upload.txt", "upload.gz"):
        rules, reason = audit.inspect_bounded_nested(compressed, name)
        assert rules == ["authorization_bearer"]
        assert reason is None


def test_zip_containing_gzip_detects_two_levels_of_compression():
    container = make_zip({"inside.gz": gzip.compress(synthetic_bearer())})
    rules, reason = audit.inspect_bounded_nested(container, "top.zip")
    assert rules == ["authorization_bearer"]
    assert reason is None


def test_bounded_plaintext_zip_can_pass_without_nested_exclusions():
    container = make_zip({"readme.txt": b"benign text"})
    assert audit.inspect_bounded_nested(container, "top.zip") == ([], None)


def test_opaque_sqlite_and_zstd_are_not_confidentiality_cleared():
    for name, blob in (("database.sqlite", b"SQLite format 3\x00" + b"placeholder"),
                       ("archive.zst", b"\x28\xb5\x2f\xfd" + b"placeholder")):
        rules, reason = audit.inspect_bounded_nested(blob, name)
        assert rules == []
        assert reason is not None


def test_zip_traversal_entry_never_clears_archive():
    archive = make_zip({"../outside.txt": synthetic_bearer()})
    rules, reason = audit.inspect_bounded_nested(archive, "candidate.zip")
    assert rules == []
    assert reason == "nested_unsafe_entry"


def test_nested_entry_budget_fails_closed(monkeypatch):
    monkeypatch.setattr(audit, "MAX_NESTED_ENTRIES", 1)
    archive = make_zip({"a.txt": b"first", "b.txt": b"second"})
    assert audit.inspect_bounded_nested(archive, "many.zip")[1] == "nested_budget"


def test_nested_expanded_byte_budget_fails_closed(monkeypatch):
    monkeypatch.setattr(audit, "MAX_NESTED_TOTAL_BYTES", 4)
    archive = make_zip({"a.txt": b"benign archive text"})
    assert audit.inspect_bounded_nested(archive, "large.zip")[1] == "nested_budget"


def test_nested_compression_ratio_bomb_is_not_cleared(monkeypatch):
    monkeypatch.setattr(audit, "MAX_NESTED_COMPRESSION_RATIO", 2)
    archive = make_zip({"bomb.txt": b"x" * 1000})
    assert audit.inspect_bounded_nested(archive, "bomb.zip")[1] == "nested_budget"


def test_nested_depth_budget_fails_closed(monkeypatch):
    monkeypatch.setattr(audit, "MAX_NESTED_DEPTH", 1)
    archive = make_zip({"second.zip": make_zip({"secret.txt": synthetic_bearer()})})
    rules, reason = audit.inspect_bounded_nested(archive, "first.zip")
    assert reason == "nested_depth_budget"
    assert rules == []  # no false claim of scanning the unreadable child


def test_corrupt_gzip_and_disguised_zip_are_not_cleared():
    for blob, name in ((b"\x1f\x8b\x08" + b"corrupt", "a.gz"),
                       (b"ordinary plaintext", "misleading.zip")):
        rules, reason = audit.inspect_bounded_nested(blob, name)
        assert reason == "nested_unreadable"
        assert rules == []


def test_gzip_pattern_and_broken_sibling_preserve_fail_closed_verdict():
    archive = make_zip({
        "clear.txt": synthetic_bearer(),
        "unknown.sqlite": b"SQLite format 3\x00" + b"test",
    })
    rules, reason = audit.inspect_bounded_nested(archive, "bundle.zip")
    assert rules == ["authorization_bearer"]
    assert reason is not None


def test_nested_zip_in_git_history_reports_only_rule_names(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    oid = "e" * 40
    archive = make_zip({"inner.txt": synthetic_bearer()})

    def git_output(command, **kwargs):
        if command[:3] == ["git", "rev-list", "--objects"]:
            return oid + " innocuous.dat\n"
        if command[:3] == ["git", "cat-file", "-t"]:
            return "blob\n"
        if command[:3] == ["git", "cat-file", "-s"]:
            return str(len(archive)) + "\n"
        if command[:3] == ["git", "cat-file", "blob"]:
            return archive
        raise AssertionError(command)

    monkeypatch.setattr(audit.subprocess, "check_output", git_output)
    outcome = audit.scan_git()
    assert outcome["status"] == "COMPLETE"
    assert outcome["opaque_blobs"] == 0
    assert outcome["findings"] == [{"blob_id": oid, "path": "innocuous.dat",
                                    "rule": "authorization_bearer"}]


def test_zip_body_declared_gzip_mismatch_does_not_get_cleared():
    archive = make_zip({"safe.txt": b"ordinary"})
    rules, reason = audit.inspect_bounded_nested(archive, "disguised.gz")
    assert rules == []
    assert reason == "nested_type_mismatch"


def test_opaque_first_sibling_does_not_hide_later_secret():
    archive = make_zip({
        "opaque.sqlite": b"SQLite format 3\x00" + b"test",
        "later.txt": synthetic_bearer(),
    })
    rules, reason = audit.inspect_bounded_nested(archive, "bundle.zip")
    assert rules == ["authorization_bearer"]
    assert reason is not None


def test_non_utf8_leaf_without_nul_must_not_be_cleared():
    rules, reason = audit.inspect_bounded_nested(b"\xff\xfe" * 5, "payload.txt")
    assert rules == []
    assert reason == "nested_nontext"


def test_nested_zip_non_utf8_leaf_is_incomplete():
    archive = make_zip({"nested.txt": b"\xff\xfe" * 8})
    rules, reason = audit.inspect_bounded_nested(archive, "bundle.zip")
    assert rules == []
    assert reason == "nested_nontext"
