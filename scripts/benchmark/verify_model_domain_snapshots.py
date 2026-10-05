#!/usr/bin/env python3
"""Verify all retained model-domain snapshots against the registry and index."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from rudeus.science.known_material_model_domain import (
    load_model_domain_index,
    load_model_domain_registry,
    verify_model_domain_repository_state,
)


ROOT = Path("data/benchmarks/known_material")


def main() -> None:
    checked = verify_model_domain_repository_state(
        load_model_domain_registry(ROOT / "model_domain_registry_v1.json"),
        load_model_domain_index(ROOT / "model_domain_snapshot_index_v1.json"),
        repo_root=Path("."),
    )
    print(
        json.dumps(
            {
                "verification_version": "known-material-model-domain-verification-v1",
                "checked_domain_keys": checked,
                "checked_count": len(checked),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"MODEL_DOMAIN_VERIFY_FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
