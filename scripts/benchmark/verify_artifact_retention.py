#!/usr/bin/env python3
"""Verify persisted known-material artifact curation state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rudeus.science.known_material_artifact_curation import (
    load_registry,
    load_retention_index,
    verify_retention_repository_state,
)


REGISTRY = Path("data/benchmarks/known_material/artifact_registry_v1.json")
INDEX = Path("data/benchmarks/known_material/artifact_retention_index_v1.json")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[2],
        type=Path,
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()

    report = verify_retention_repository_state(
        load_registry(repo_root / REGISTRY),
        load_retention_index(repo_root / INDEX),
        repo_root=repo_root,
    )
    print(
        json.dumps(
            {
                "verification_version": report.verification_version,
                "checked_count": len(report.checked_artifact_keys),
                "checked_artifact_keys": list(report.checked_artifact_keys),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"ARTIFACT_RETENTION_VERIFY_FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
