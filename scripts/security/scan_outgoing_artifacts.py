"""Fail-closed outgoing artifact scanner for Kaggle recovery workflow.

Checks text artifacts for credential patterns without printing any secret values.
Opaque compressed science payloads are left untouched; their hashes are verified
by the independent retrieval step, not by this confidentiality scan.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys

TEXT_SUFFIXES = {".json", ".jsonl", ".txt", ".log", ".md", ".yaml", ".yml", ".csv", ".html"}
MAX_TEXT_BYTES = 16 * 1024 * 1024
PATTERNS = (
    re.compile(r"(?i)authorization\s*[:=]\s*['\"]?bearer\s+[^\s'\",;]+"),
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|password|kaggle_api_token|secret)\s*[:=]\s*['\"]?[^\s'\",;}{]+"),
    re.compile(r"(?:ghp_|gho_|ghu_|ghs_|github_pat_)[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)https?://[^/\s:@]+:[^@/\s]+@"),
)
OPAQUE_SUFFIXES = {".zst", ".sqlite", ".gz", ".zip"}


def scan_directory(root: Path) -> tuple[int, int]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("missing or unsafe artifact directory")
    scanned = 0
    opaque = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlink in artifact tree")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("non-regular artifact")
        name = path.name.lower()
        is_opaque = path.suffix.lower() in OPAQUE_SUFFIXES or ".zst.part" in name
        if is_opaque:
            opaque += 1
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            raise ValueError("unrecognized artifact extension")
        if path.stat().st_size > MAX_TEXT_BYTES:
            raise ValueError("oversized artifact text")
        raw = path.read_bytes()
        if b"\0" in raw:
            raise ValueError("unexpected binary text artifact")
        body = raw.decode("utf-8", errors="strict")
        for name in ("KAGGLE_API_TOKEN", "KAGGLE_KEY", "GH_TOKEN", "GITHUB_TOKEN"):
            value = os.environ.get(name, "")
            if len(value) >= 6 and value in body:
                raise ValueError("credential detected in outgoing artifact")
        if any(rule.search(body) for rule in PATTERNS):
            raise ValueError("credential-like text detected in outgoing artifact")
        scanned += 1
    if scanned == 0:
        raise ValueError("no text evidence found to scan")
    return scanned, opaque


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: scan_outgoing_artifacts.py DIRECTORY", file=sys.stderr)
        return 2
    try:
        scanned, opaque = scan_directory(Path(sys.argv[1]))
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"OUTGOING_ARTIFACT_SCAN_REJECTED: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"OUTGOING_ARTIFACT_SCAN_PASS text={scanned} opaque={opaque}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
