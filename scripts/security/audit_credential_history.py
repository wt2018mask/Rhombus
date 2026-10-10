"""Read-only secret-pattern audit of Git blobs and GitHub Actions artifacts.

Never prints secret values or source excerpts. Receipt is metadata-only.
A partial audit is explicitly INCOMPLETE, not a clean bill of health.
"""
from __future__ import annotations
import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import zipfile

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
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_ENTRY_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2048
MAX_TOTAL_EXPANDED_BYTES = 64 * 1024 * 1024


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
    if b"\x00" in blob[:1024]:
        return []
    # Avoid false alarms for public GitHub Actions secret variable references.
    material = re.sub(rb"\$\{\{\s*secrets\.[^}]+\}\}", b"SECRET_PLACEHOLDER", blob)
    return sorted(name for name, rule in RULES.items() if rule.search(material))

def scan_git() -> dict:
    if not Path(".git").exists():
        return {"status": "INCOMPLETE", "error": "git_checkout_unavailable"}
    objects = subprocess.check_output(["git", "rev-list", "--objects", "--all"], text=True)
    scanned = 0
    skipped = 0
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
            skipped += 1
            continue
        data = subprocess.check_output(["git", "cat-file", "blob", oid])
        scanned += 1
        for rule in classify(data):
            findings.append({"blob_id": oid, "path": path or "(unnamed)", "rule": rule})
    return {"status": "INCOMPLETE" if skipped else "COMPLETE",
            "scanned_blobs": scanned, "skipped_large_blobs": skipped,
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
              "skipped_entries": 0, "skip_reasons": {}, "findings": []}
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
                        for rule in classify(data):
                            result["findings"].append({
                                "artifact_id": artifact_id,
                                "entry_name": info.filename,
                                "rule": rule,
                            })
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
