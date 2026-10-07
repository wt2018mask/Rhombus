from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--file-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    row = next(item for item in manifest["files"] if item["file_id"] == args.file_id)
    url = row["url"].replace("https://figshare.com/files/", "https://figshare.com/ndownloader/files/")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, out.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)

    data = out.read_bytes()
    md5_hex = hashlib.md5(data).hexdigest()  # noqa: S324 - source-registry compatibility
    sha256_hex = hashlib.sha256(data).hexdigest()

    if md5_hex != row["expected_md5"]:
        raise SystemExit(
            f"MD5_MISMATCH file_id={args.file_id} expected={row['expected_md5']} actual={md5_hex}"
        )
    expected_size = row.get("expected_size")
    if expected_size is not None and len(data) != expected_size:
        raise SystemExit(
            f"SIZE_MISMATCH file_id={args.file_id} expected={expected_size} actual={len(data)}"
        )

    print(f"WBM_FILE_VERIFIED file_id={args.file_id} size={len(data)} md5={md5_hex} sha256={sha256_hex}")


if __name__ == "__main__":
    main()
