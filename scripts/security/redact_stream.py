"""Redact untrusted provider diagnostics before any GitHub Actions artifact."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import subprocess

RULES = (
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer|token)\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|secret|password|kaggle_api_token)\s*[:=]\s*['\"]?)[^'\s\",;]+"),
    re.compile(r"(?:ghp_|gho_|ghu_|ghs_|github_pat_)[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)(https?://)[^/\s:@]+:[^@/\s]+@"),
)

def redact(text: str) -> str:
    for name in ("KAGGLE_API_TOKEN", "KAGGLE_KEY", "GH_TOKEN"):
        token = os.environ.get(name, "")
        if len(token) >= 6:
            text = text.replace(token, "[REDACTED]")
    for rule in RULES:
        text = rule.sub(
            lambda match: match.group(1) + "[REDACTED]" if match.lastindex else "[REDACTED]",
            text,
        )
    return text

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not command:
        parser.error("missing provider command")
    try:
        job = subprocess.run(command, capture_output=True, timeout=120, check=False)
        body = (job.stdout + b"\n" + job.stderr)[:2 * 1024 * 1024]
    except (OSError, subprocess.TimeoutExpired):
        body = b"[provider logs unavailable]"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(redact(body.decode("utf-8", errors="replace")), encoding="utf-8")
    print("PROVIDER_LOG_REDACTED")

if __name__ == "__main__":
    main()
