from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import BinaryIO


def stream_copy_and_hash(source: BinaryIO, destination: BinaryIO) -> tuple[int, str, str]:
    md5_hasher = hashlib.md5()  # noqa: S324 - source-registry compatibility
    sha256_hasher = hashlib.sha256()
    size = 0

    while True:
        chunk = source.read(1024 * 1024)
        if not chunk:
            break
        destination.write(chunk)
        md5_hasher.update(chunk)
        sha256_hasher.update(chunk)
        size += len(chunk)

    return size, md5_hasher.hexdigest(), sha256_hasher.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--file-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    row = next(item for item in manifest["files"] if item["file_id"] == args.file_id)
    url = row["url"].replace(
        "https://figshare.com/files/",
        "https://figshare.com/ndownloader/files/",
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, out.open("wb") as handle:
        size, md5_hex, sha256_hex = stream_copy_and_hash(response, handle)

    if md5_hex != row["expected_md5"]:
        out.unlink(missing_ok=True)
        raise SystemExit(
            f"MD5_MISMATCH file_id={args.file_id} expected={row['expected_md5']} actual={md5_hex}"
        )

    expected_size = row.get("expected_size")
    if expected_size is not None and size != expected_size:
        out.unlink(missing_ok=True)
        raise SystemExit(
            f"SIZE_MISMATCH file_id={args.file_id} expected={expected_size} actual={size}"
        )

    print(
        f"WBM_FILE_VERIFIED file_id={args.file_id} size={size} "
        f"md5={md5_hex} sha256={sha256_hex}"
    )


if __name__ == "__main__":
    main()
