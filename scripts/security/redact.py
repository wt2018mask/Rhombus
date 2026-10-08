"""Redact secrets in Kaggle diagnostics; block unsafe artifact publication."""
import os
import re
import sys
from pathlib import Path

PATTERN = re.compile(r"(?i)(?:github_pat_[A-Za-z0-9_]{12,}|gh[pousr]_[A-Za-z0-9_]{16,}|KGAT_[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._~+/=-]{12,})")
KEY = re.compile(r"(?i)((?:api[_-]?key|api[_-]?token|access[_-]?token|password|secret)\s*[:=]\s*)([^\s,'\"}]{8,})")
DIAGNOSTIC = {"kaggle-error.log","kernel-submit-error.json","rhombus_phase3_wbm_source_diagnostics.json"}

def scrub(value):
    value, n = PATTERN.subn("[REDACTED]", value)
    value, k = KEY.subn(lambda m: m.group(1)+"[REDACTED]", value)
    n += k
    for name in ("KAGGLE_API_TOKEN","KAGGLE_KEY","GH_TOKEN","GITHUB_TOKEN"):
        token = os.environ.get(name,"")
        if len(token) >= 8 and token in value:
            n += 1
            value = value.replace(token,"[REDACTED]")
    return value, n

def audit(root):
    total = 0
    if not root.exists():
        return total
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.stat().st_size > 256*1024*1024:
            raise ValueError("unsafe artifact too large")
        if path.suffix in {".json",".log",".txt"}:
            source = path.read_text(encoding="utf-8",errors="replace")
            clean, n = scrub(source)
            if n:
                if path.name not in DIAGNOSTIC:
                    raise ValueError("sensitive non-diagnostic artifact: upload blocked")
                path.write_text(clean,encoding="utf-8")
        else:
            raw = path.read_bytes()
            for key in ("KAGGLE_API_TOKEN","KAGGLE_KEY","GH_TOKEN","GITHUB_TOKEN"):
                token = os.environ.get(key,"")
                if len(token)>=8 and token.encode() in raw:
                    raise ValueError("secret in binary artifact: upload blocked")
        total+=1
    return total

def main():
    if len(sys.argv)==3 and sys.argv[1]=="--audit":
        count=audit(Path(sys.argv[2]))
        print("ARTIFACT_SECURITY_VERIFIED",count)
    elif len(sys.argv)==3:
        source=Path(sys.argv[1])
        if source.stat().st_size>8*1024*1024:
            raise ValueError("diagnostic too large")
        safe,n=scrub(source.read_text(encoding="utf-8",errors="replace"))
        target=Path(sys.argv[2]);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(safe,encoding="utf-8")
        print("DIAGNOSTIC_SCRUBBED",n)
    else:
        raise SystemExit("usage: redact.py INPUT OUTPUT | --audit PATH")

if __name__=="__main__":
    main()
