"""Read-only secret-pattern audit of Git blobs and GitHub Actions artifacts.

Never prints secret values or source excerpts. Receipt is metadata-only.
A partial audit is explicitly INCOMPLETE, not a clean bill of health.
"""
from __future__ import annotations
import argparse
import gzip
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import zipfile
import zlib

RULES = {
    "github_pat": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "authorization_bearer": re.compile(rb"(?i)Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/-]{20,}"),
    "credential_assignment": re.compile(
        rb"(?i)\b(?:KAGGLE_API_TOKEN|KAGGLE_KEY|GITHUB_TOKEN|GH_TOKEN|AWS_SECRET_ACCESS_KEY)"
        rb"\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{20,}"
    ),
}
MAX_BLOB_BYTES = 2 * 1024 * 1024
MAX_STREAM_BLOB_BYTES = 96 * 1024 * 1024
MAX_TOTAL_STREAM_BLOB_BYTES = 256 * 1024 * 1024
STREAM_CHUNK_BYTES = 256 * 1024
STREAM_PATTERN_OVERLAP = 4096
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_ENTRY_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2048
MAX_TOTAL_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_NESTED_BYTES = 2 * 1024 * 1024
MAX_NESTED_TOTAL_BYTES = 8 * 1024 * 1024
MAX_NESTED_ENTRIES = 128
MAX_NESTED_DEPTH = 2
MAX_NESTED_COMPRESSION_RATIO = 100


class ArtifactRedirectPolicy(urllib.request.HTTPRedirectHandler):
    """Never forward GitHub's Actions token to a different redirect origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None
        original = urlsplit(req.full_url)
        destination = urlsplit(redirected.full_url)
        if destination.scheme != "https":
            raise ValueError("insecure_artifact_redirect")
        if (original.hostname, original.port) != (destination.hostname, destination.port):
            redirected.remove_header("Authorization")
        return redirected


def classify(blob: bytes) -> list[str]:
    # Search raw bytes even in opaque inputs. A NUL prefix must never erase
    # visible signature matches; inspectability is tracked separately.
    # Avoid false alarms for public GitHub Actions secret variable references.
    material = re.sub(rb"\$\{\{\s*secrets\.[^}]+\}\}", b"SECRET_PLACEHOLDER", blob)
    return sorted(name for name, rule in RULES.items() if rule.search(material))

def opaque_reason(blob: bytes, name: str = "") -> str | None:
    """Recognize payloads that a one-level byte-pattern audit cannot clear.

    The caller still scans raw bytes for recognizable credential patterns.
    Missing a pattern within an opaque payload must never imply clean scope.
    """
    lower_name = name.lower()
    if blob.startswith((b"PK\x03\x04", b"PK\x05\x06",
                       b"\x1f\x8b", b"\x28\xb5\x2f\xfd",
                       b"SQLite format 3\x00")):
        return "nested_or_opaque_magic"
    if lower_name.endswith((".zip", ".gz", ".gzip", ".zst", ".sqlite",
                            ".sqlite3", ".db")):
        return "opaque_extension"
    if b"\x00" in blob:
        return "binary_nul"
    return None


def inspect_bounded_nested(blob: bytes, name: str = "") -> tuple[list[str], str | None]:
    """Scan a small ZIP/gzip tree without treating unknown binary as text.

    No extracted entry is written to disk. Findings only include rule names;
    an uninspected child remains INCOMPLETE even when siblings are readable.
    """
    findings = set(classify(blob))
    expanded_total = 0
    entries_seen = 0

    def visit(data: bytes, label: str, depth: int) -> str | None:
        nonlocal expanded_total, entries_seen
        reason = opaque_reason(data, label)
        if reason is None:
            try:
                data.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                return "nested_nontext"
            return None
        if depth >= MAX_NESTED_DEPTH:
            return "nested_depth_budget"
        lower = label.lower()
        is_zip = data.startswith((b"PK\x03\x04", b"PK\x05\x06")) or lower.endswith(".zip")
        is_gzip = data.startswith(b"\x1f\x8b") or lower.endswith((".gz", ".gzip"))
        if is_zip and is_gzip:
            return "nested_type_mismatch"
        if not (is_zip or is_gzip):
            return reason

        def consume(data: bytes, label: str) -> str | None:
            nonlocal expanded_total, entries_seen
            entries_seen += 1
            expanded_total += len(data)
            if entries_seen > MAX_NESTED_ENTRIES or expanded_total > MAX_NESTED_TOTAL_BYTES:
                return "nested_budget"
            findings.update(classify(data))
            return visit(data, label, depth + 1)

        try:
            if is_gzip and not is_zip:
                with gzip.GzipFile(fileobj=io.BytesIO(data)) as source:
                    extracted = source.read(MAX_NESTED_BYTES + 1)
                if len(extracted) > MAX_NESTED_BYTES or len(extracted) > max(1, len(data)) * MAX_NESTED_COMPRESSION_RATIO:
                    return "nested_budget"
                suffix = ".gzip" if lower.endswith(".gzip") else ".gz"
                return consume(extracted, label[:-len(suffix)] if lower.endswith(suffix) else "gzip-content")
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) + entries_seen > MAX_NESTED_ENTRIES:
                    return "nested_budget"
                filenames = [info.filename for info in infos]
                if len(set(filenames)) != len(filenames):
                    return "nested_unsafe_entry"
                first_unattested = None
                for info in infos:
                    member = PurePosixPath(info.filename)
                    mode = info.external_attr >> 16
                    if (not info.filename or member.is_absolute()
                            or ".." in member.parts or "\\" in info.filename
                            or ":" in info.filename
                            or info.flag_bits & 1 or stat.S_ISLNK(mode)
                            or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                        return "nested_unsafe_entry"
                    if info.is_dir():
                        continue
                    if (info.file_size > MAX_NESTED_BYTES
                            or info.file_size > max(1, info.compress_size) * MAX_NESTED_COMPRESSION_RATIO
                            or expanded_total + info.file_size > MAX_NESTED_TOTAL_BYTES):
                        return "nested_budget"
                    with archive.open(info) as handle:
                        inner = handle.read(MAX_NESTED_BYTES + 1)
                    if len(inner) != info.file_size:
                        return "nested_unreadable"
                    child_reason = consume(inner, info.filename)
                    if child_reason is not None and first_unattested is None:
                        first_unattested = child_reason
            return first_unattested
        except (OSError, EOFError, ValueError, RuntimeError, NotImplementedError,
                zipfile.BadZipFile, zlib.error):
            return "nested_unreadable"

    return sorted(findings), visit(blob, name, 0)


def scan_streamed_blob(oid: str, size: int, path: str) -> tuple[list[str], str | None]:
    """Inspect one bounded Git blob without materializing its full payload.

    Overlapping windows cover token signatures that straddle read boundaries.
    The helper never logs or returns matched secret bytes.
    """
    found: set[str] = set()
    carry = b""
    header = b""
    saw_nul = False
    whitespace_tail = 0
    uncertain_pattern_window = False
    read_bytes = 0
    with subprocess.Popen(
        ["git", "cat-file", "blob", oid],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) as process:
        if process.stdout is None:
            raise OSError("git_blob_stream_unavailable")
        while read_bytes < size:
            chunk = process.stdout.read(min(STREAM_CHUNK_BYTES, size - read_bytes))
            if not chunk:
                raise ValueError("git_blob_truncated")
            read_bytes += len(chunk)
            header = (header + chunk)[:128]
            saw_nul = saw_nul or b"\x00" in chunk
            # Regexes include multiple unbounded whitespace groups.
            # If a run approaches a quarter of the carry window, matching
            # across the streaming boundary can no longer be proven.
            for match in re.finditer(rb"\s+", chunk):
                length = len(match.group()) + (whitespace_tail if match.start() == 0 else 0)
                if length >= max(1, STREAM_PATTERN_OVERLAP // 4):
                    uncertain_pattern_window = True
            trailing = re.search(rb"\s+$", chunk)
            whitespace_tail = (whitespace_tail + len(chunk)
                               if trailing and trailing.start() == 0 else
                               len(trailing.group()) if trailing else 0)
            window = carry + chunk
            found.update(classify(window))
            carry = window[-STREAM_PATTERN_OVERLAP:]
        if process.wait(timeout=60) != 0:
            raise subprocess.CalledProcessError(process.returncode, "git cat-file blob")
    reason = opaque_reason(header, path)
    if reason is None and saw_nul:
        reason = "binary_nul"
    if reason is None and uncertain_pattern_window:
        reason = "stream_regex_window_unattested"
    return sorted(found), reason


def scan_git() -> dict:
    if not Path(".git").exists():
        return {"status": "INCOMPLETE", "error": "git_checkout_unavailable"}
    objects = subprocess.check_output(["git", "rev-list", "--objects", "--all"], text=True)
    scanned = 0
    skipped = 0
    streamed = 0
    streamed_bytes = 0
    skip_reasons: dict[str, int] = {}
    opaque = 0
    opaque_reasons: dict[str, int] = {}
    findings = []
    visited = set()
    for line in objects.splitlines():
        oid, _, path = line.partition(" ")
        if oid in visited:
            continue
        visited.add(oid)
        typ = subprocess.check_output(["git", "cat-file", "-t", oid], text=True).strip()
        if typ != "blob":
            continue
        size = int(subprocess.check_output(["git", "cat-file", "-s", oid], text=True))
        if size > MAX_BLOB_BYTES:
            if (size > MAX_STREAM_BLOB_BYTES or
                    streamed_bytes + size > MAX_TOTAL_STREAM_BLOB_BYTES):
                skipped += 1
                reason = ("object_size_budget" if size > MAX_STREAM_BLOB_BYTES
                          else "aggregate_stream_budget")
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                continue
            try:
                rules, reason = scan_streamed_blob(oid, size, path)
            except (OSError, ValueError, subprocess.SubprocessError):
                skipped += 1
                skip_reasons["stream_unreadable"] = skip_reasons.get("stream_unreadable", 0) + 1
                continue
            streamed += 1
            streamed_bytes += size
        else:
            data = subprocess.check_output(["git", "cat-file", "blob", oid])
            rules, reason = inspect_bounded_nested(data, path)
        scanned += 1
        for rule in rules:
            findings.append({"blob_id": oid, "path": path or "(unnamed)", "rule": rule})
        if reason is not None:
            opaque += 1
            opaque_reasons[reason] = opaque_reasons.get(reason, 0) + 1
    return {"status": "INCOMPLETE" if skipped or opaque else "COMPLETE",
            "scanned_blobs": scanned, "streamed_blobs": streamed,
            "streamed_bytes": streamed_bytes,
            "skipped_large_blobs": skipped, "skip_reasons": skip_reasons,
            "opaque_blobs": opaque, "opaque_reasons": opaque_reasons,
            "findings": findings}

def api_json(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)

def scan_artifacts(repository: str, token: str) -> dict:
    result = {"status": "COMPLETE", "scanned_archives": 0,
              "skipped_archives": 0, "scanned_entries": 0,
              "skipped_entries": 0, "skip_reasons": {},
              "opaque_entries": 0, "opaque_reasons": {}, "findings": []}
    if not token:
        result.update(status="INCOMPLETE", error="actions_read_token_unavailable")
        return result
    def skip_archive(reason: str) -> None:
        result["skipped_archives"] += 1
        result["skip_reasons"][reason] = result["skip_reasons"].get(reason, 0) + 1
        result["status"] = "INCOMPLETE"

    opener = urllib.request.build_opener(ArtifactRedirectPolicy())
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repository}/actions/artifacts?per_page=100&page={page}"
        try:
            response = api_json(url, token)
        except (urllib.error.URLError, ValueError) as exc:
            result.update(status="INCOMPLETE", error="artifact_inventory_unavailable")
            break
        artifacts = response.get("artifacts", [])
        if not artifacts:
            break
        for artifact in artifacts:
            artifact_id = artifact["id"]
            if artifact.get("expired"):
                skip_archive("expired")
                continue
            if artifact.get("size_in_bytes", 0) > MAX_ARCHIVE_BYTES:
                skip_archive("compressed_size_budget")
                continue
            location = f"https://api.github.com/repos/{repository}/actions/artifacts/{artifact_id}/zip"
            request = urllib.request.Request(location, headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
            })
            try:
                with opener.open(request, timeout=90) as download:
                    payload = download.read(MAX_ARCHIVE_BYTES + 1)
                if len(payload) > MAX_ARCHIVE_BYTES:
                    raise ValueError("archive_size_budget")
                with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                    entries = archive.infolist()
                    if len(entries) > MAX_ARCHIVE_ENTRIES:
                        raise ValueError("entry_count_budget")
                    if sum(i.file_size for i in entries if not i.is_dir()) > MAX_TOTAL_EXPANDED_BYTES:
                        raise ValueError("expanded_size_budget")
                    for info in entries:
                        if info.is_dir():
                            continue
                        if info.file_size > MAX_ENTRY_BYTES:
                            result["skipped_entries"] += 1
                            result["status"] = "INCOMPLETE"
                            continue
                        with archive.open(info) as handle:
                            data = handle.read(MAX_ENTRY_BYTES + 1)
                        if len(data) > MAX_ENTRY_BYTES:
                            result["skipped_entries"] += 1
                            result["status"] = "INCOMPLETE"
                            continue
                        result["scanned_entries"] += 1
                        rules, reason = inspect_bounded_nested(data, info.filename)
                        for rule in rules:
                            result["findings"].append({
                                "artifact_id": artifact_id,
                                "entry_name": info.filename,
                                "rule": rule,
                            })
                        if reason is not None:
                            result["opaque_entries"] += 1
                            counts = result["opaque_reasons"]
                            counts[reason] = counts.get(reason, 0) + 1
                            result["status"] = "INCOMPLETE"
                result["scanned_archives"] += 1
            except ValueError as exc:
                reason = str(exc)
                if reason not in {"entry_count_budget", "expanded_size_budget", "insecure_artifact_redirect", "archive_size_budget"}:
                    reason = "unreadable_archive"
                skip_archive(reason)
            except (urllib.error.URLError, OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError):
                skip_archive("unreadable_archive")
        if len(artifacts) < 100:
            break
        page += 1
    return result

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    result = {"schema_version": "rhombus-credential-audit-v1",
              "scope": "all locally reachable git objects and accessible non-expired Actions artifact ZIPs"}
    try:
        result["git_history"] = scan_git()
    except (OSError, subprocess.SubprocessError):
        result["git_history"] = {"status": "INCOMPLETE", "error": "git_history_unreadable"}
    result["actions_artifacts"] = scan_artifacts(args.repository, os.getenv("GH_TOKEN", ""))
    findings = sum(len(result[x].get("findings", [])) for x in ("git_history", "actions_artifacts"))
    incomplete = any(result[x]["status"] != "COMPLETE" for x in ("git_history", "actions_artifacts"))
    result["overall_status"] = "FINDINGS" if findings else "INCOMPLETE" if incomplete else "NO_MATCHES_IN_SCANNED_SCOPE"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SECRET_AUDIT_STATUS=" + result["overall_status"])
    print("SECRET_AUDIT_FINDING_COUNT=" + str(findings))
    return 1 if findings or incomplete else 0

if __name__ == "__main__":
    sys.exit(main())
