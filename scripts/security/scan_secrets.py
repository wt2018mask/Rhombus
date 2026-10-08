"""Conservative offline scanner for tracked files and GitHub Actions outputs.

Do not print matching secret text. Exits nonzero if high-confidence exposures
are found; additional unknown formats require external/manual inspection.
"""
import argparse
import os
from pathlib import Path
import re
import sys

PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
ASSIGNMENT = re.compile(rb"(?i)(?:KAGGLE_API_TOKEN|KAGGLE_KEY|GH_TOKEN|GITHUB_TOKEN|OPENAI_API_KEY|ANTHROPIC_API_KEY)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{24,})")
MAX_BYTES=32*1024*1024

def scan_path(path: Path):
    if not path.exists():
        return []
    files=[path] if path.is_file() else (p for p in path.rglob("*") if p.is_file())
    findings=[]
    for item in files:
        if item.is_symlink() or item.stat().st_size>MAX_BYTES:
            findings.append((str(item),"UNSCANNED_LARGE_OR_LINK"))
            continue
        data=item.read_bytes()
        if PRIVATE_KEY.search(data):
            findings.append((str(item),"PRIVATE_KEY_BLOCK"))
        if ASSIGNMENT.search(data):
            findings.append((str(item),"POSSIBLE_LITERAL_API_SECRET"))
    return findings

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("paths",nargs="+",type=Path)
    parser.add_argument("--quiet",action="store_true")
    args=parser.parse_args()
    found=[item for path in args.paths for item in scan_path(path)]
    for path,code in found:
        print(f"SECRET_AUDIT_FLAG {code} at {path}",file=sys.stderr)
    if not args.quiet: print(f"SECRET_AUDIT_SCANNED_PATHS={len(args.paths)} FLAGS={len(found)}")
    return 1 if found else 0

if __name__=="__main__":
    raise SystemExit(main())
