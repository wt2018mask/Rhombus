"""Bounded, fail-closed confidentiality scan before artifact export.

ZIP/gzip are inspected recursively as UTF-8 text. zstd (including split parts),
SQLite, unknown formats, encrypted entries and over-budget payloads are denied.
Hashes establish identity, never confidentiality. No opaque bytes are cleared.
"""
from __future__ import annotations

import argparse
import gzip
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

TEXT_SUFFIXES = {".json", ".jsonl", ".txt", ".log", ".md", ".yaml", ".yml", ".csv", ".html"}
MAX_TEXT_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_ENTRIES = 128
MAX_ARCHIVE_DEPTH = 3
MAX_COMPRESSION_RATIO = 100
PATTERNS = (
    re.compile(r"(?i)authorization['\"]?\s*[:=]\s*['\"]?bearer\s+[^\s'\",;]+"),
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|password|kaggle_api_token|secret)['\"]?\s*[:=]\s*['\"]?[^\s'\",;}{]+"),
    re.compile(r"(?:ghp_|gho_|ghu_|ghs_|github_pat_)[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)https?://[^/\s:@]+:[^@/\s]+@"),
)


class _Budget:
    def __init__(self):
        self.bytes = 0
        self.entries = 0
        self.scanned = 0

    def charge(self, size):
        self.bytes += size
        if size > MAX_TEXT_BYTES or self.bytes > MAX_TOTAL_BYTES:
            raise ValueError("artifact byte limit exceeded")

    def entry(self):
        self.entries += 1
        if self.entries > MAX_ENTRIES:
            raise ValueError("artifact entry limit exceeded")


def _read_bounded(source, budget):
    raw = source.read(min(MAX_TEXT_BYTES, MAX_TOTAL_BYTES - budget.bytes) + 1)
    budget.charge(len(raw))
    return raw


def _check_credentials(body):
    for name in ("KAGGLE_API_TOKEN", "KAGGLE_KEY", "GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name, "")
        if len(value) >= 6 and value in body:
            raise ValueError("credential detected in outgoing artifact")
    if any(rule.search(body) for rule in PATTERNS):
        raise ValueError("credential-like text detected in outgoing artifact")


def _scan_text(raw, budget):
    if b"\0" in raw:
        raise ValueError("unexpected binary text artifact")
    body = raw.decode("utf-8", errors="strict")
    _check_credentials(body)
    budget.scanned += 1


def _safe_archive_name(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("unsafe archive entry name")


def _inspect(name, raw, budget, depth=0):
    # Archive names/comments/headers can also carry credentials. This check
    # supplements decompression; it never clears opaque binary payloads.
    _check_credentials(raw.decode("utf-8", errors="ignore"))
    suffix = PurePosixPath(name.lower()).suffix
    if suffix in {".zst", ".sqlite", ".db"} or ".zst.part" in name.lower():
        raise ValueError("uninspected opaque artifact denied")
    if depth > MAX_ARCHIVE_DEPTH:
        raise ValueError("archive nesting limit exceeded")
    if suffix == ".gz":
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as source:
            expanded = _read_bounded(source, budget)
        if len(expanded) > max(1, len(raw)) * MAX_COMPRESSION_RATIO:
            raise ValueError("compression ratio limit exceeded")
        _inspect(name[:-3], expanded, budget, depth + 1)
    elif suffix == ".zip":
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ENTRIES - budget.entries:
                raise ValueError("archive entry limit exceeded")
            names = [entry.filename for entry in entries]
            if len(set(names)) != len(names):
                raise ValueError("duplicate archive entry")
            for entry in entries:
                budget.entry()
                _safe_archive_name(entry.filename)
                mode = entry.external_attr >> 16
                if entry.flag_bits & 1 or stat.S_ISLNK(mode):
                    raise ValueError("encrypted or symlink archive entry")
                if entry.is_dir():
                    continue
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                    raise ValueError("non-regular archive entry")
                if entry.file_size > MAX_TEXT_BYTES or entry.file_size > max(1, entry.compress_size) * MAX_COMPRESSION_RATIO:
                    raise ValueError("archive size or compression ratio limit exceeded")
                with archive.open(entry) as source:
                    expanded = _read_bounded(source, budget)
                if len(expanded) != entry.file_size:
                    raise ValueError("archive member size mismatch")
                _inspect(entry.filename, expanded, budget, depth + 1)
    elif suffix in TEXT_SUFFIXES:
        _scan_text(raw, budget)
    else:
        raise ValueError("unrecognized artifact extension")


def scan_directory(root: Path, *, allowed_paths: set[str] | None = None) -> tuple[int, int]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("missing or unsafe artifact directory")
    budget = _Budget()
    found = set()
    try:
        for path in root.rglob("*"):
            budget.entry()
            if path.is_symlink():
                raise ValueError("symlink in artifact tree")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError("non-regular artifact")
            relative = path.relative_to(root).as_posix()
            found.add(relative)
            if allowed_paths is not None and relative not in allowed_paths:
                raise ValueError("artifact not in allowlist")
            if path.stat().st_size > MAX_TEXT_BYTES:
                raise ValueError("oversized artifact")
            # O_NOFOLLOW closes the ordinary final-component symlink race.
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ValueError("non-regular artifact")
                raw = _read_bounded(source, budget)
            _inspect(path.name, raw, budget)
        if allowed_paths is not None and found != allowed_paths:
            raise ValueError("missing allowlist artifact")
        if budget.scanned == 0:
            raise ValueError("no text evidence found to scan")
    except (OSError, UnicodeError, zipfile.BadZipFile, EOFError, RuntimeError, NotImplementedError) as exc:
        raise ValueError("artifact cannot be safely inspected") from exc
    return budget.scanned, 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--allow", action="append", help="exact relative file path; repeat for complete allowlist")
    args = parser.parse_args()
    try:
        scanned, _ = scan_directory(args.directory, allowed_paths=set(args.allow) if args.allow is not None else None)
    except (ValueError, OSError) as exc:
        print(f"OUTGOING_ARTIFACT_SCAN_REJECTED: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"OUTGOING_ARTIFACT_SCAN_PASS text={scanned} opaque=0 uninspected=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
