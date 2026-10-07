from __future__ import annotations

import argparse
import hashlib
import urllib.request
from typing import BinaryIO


def stream_hash(source: BinaryIO, *, chunk_size: int = 8 * 1024 * 1024) -> tuple[int, str, str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    md5_hasher = hashlib.md5()  # noqa: S324 - source registry compatibility
    sha256_hasher = hashlib.sha256()
    size = 0

    while True:
        chunk = source.read(chunk_size)
        if not chunk:
            break
        md5_hasher.update(chunk)
        sha256_hasher.update(chunk)
        size += len(chunk)

    return size, md5_hasher.hexdigest(), sha256_hasher.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--expected-size", type=int)
    parser.add_argument("--expected-md5")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--chunk-size-mib", type=int, default=8)
    args = parser.parse_args()

    if not args.label.strip():
        raise SystemExit("label must be non-empty")
    if args.expected_size is not None and args.expected_size <= 0:
        raise SystemExit("expected-size must be positive")
    if args.chunk_size_mib <= 0:
        raise SystemExit("chunk-size-mib must be positive")

    request = urllib.request.Request(
        args.url,
        headers={"User-Agent": "Rhombus-source-hash/1"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        size, md5_hex, sha256_hex = stream_hash(
            response,
            chunk_size=args.chunk_size_mib * 1024 * 1024,
        )

    if args.expected_size is not None and size != args.expected_size:
        raise SystemExit(
            f"SIZE_MISMATCH label={args.label} "
            f"expected={args.expected_size} actual={size}"
        )
    if args.expected_md5 is not None and md5_hex != args.expected_md5.lower():
        raise SystemExit(
            f"MD5_MISMATCH label={args.label} "
            f"expected={args.expected_md5.lower()} actual={md5_hex}"
        )
    if (
        args.expected_sha256 is not None
        and sha256_hex != args.expected_sha256.lower()
    ):
        raise SystemExit(
            f"SHA256_MISMATCH label={args.label} "
            f"expected={args.expected_sha256.lower()} actual={sha256_hex}"
        )

    print(
        f"REMOTE_FILE_HASHED label={args.label} "
        f"size={size} md5={md5_hex} sha256={sha256_hex}"
    )


if __name__ == "__main__":
    main()
