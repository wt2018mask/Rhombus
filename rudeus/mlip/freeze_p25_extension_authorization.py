"""Freeze the canonical P2.5 evidence-sufficiency transition authorization."""

from __future__ import annotations

import argparse
import json

from rudeus.mlip.p25_extension import write_extension_manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--p1-dir", required=True)
    ap.add_argument("--p2-dir", required=True)
    ap.add_argument("--p25-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    m = write_extension_manifest(
        args.p1_dir, args.p2_dir, args.p25_dir, args.out
    )
    print(json.dumps(m, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
