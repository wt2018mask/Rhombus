#!/usr/bin/env python3
"""Extract and retain model-domain snapshots from registry-selected checkpoints."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rudeus.science.known_material_model_domain import (
    extract_model_domain_snapshot,
    load_model_domain_index,
    load_model_domain_registry,
    download_checkpoint,
    persist_model_domain_index,
    plan_model_domain_entries,
    retain_model_domain_snapshot,
)


ROOT = Path("data/benchmarks/known_material")
REGISTRY_PATH = ROOT / "model_domain_registry_v1.json"
INDEX_PATH = ROOT / "model_domain_snapshot_index_v1.json"
CACHE_ROOT = Path(".cache/known-material/model-domain")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--scope",
        choices=("unresolved", "all", "domain"),
        default="unresolved",
    )
    p.add_argument("--selector")
    return p


def main() -> None:
    args = parser().parse_args()
    registry = load_model_domain_registry(REGISTRY_PATH)
    index = load_model_domain_index(INDEX_PATH)
    selected = plan_model_domain_entries(
        registry,
        index,
        scope=args.scope,
        selector=args.selector,
    )

    snapshots = []
    current_index = index
    for entry in selected:
        checkpoint_path = CACHE_ROOT / f"{entry.model_id}.model"
        download_checkpoint(entry, checkpoint_path)
        snapshot = extract_model_domain_snapshot(
            entry,
            checkpoint_path=checkpoint_path,
        )
        current_index = retain_model_domain_snapshot(
            entry=entry,
            snapshot=snapshot,
            index=current_index,
            repo_root=Path("."),
        )
        snapshots.append(
            {
                "domain_key": entry.domain_key,
                "model_id": entry.model_id,
                "checkpoint_sha256": snapshot.checkpoint_sha256,
                "element_count": snapshot.element_count,
                "snapshot_path": entry.snapshot_path,
                "snapshot_content_hash": snapshot.content_hash,
                "unsupported_count_1_to_118": len(
                    snapshot.unsupported_atomic_numbers_1_to_118
                ),
            }
        )

    persist_model_domain_index(current_index, INDEX_PATH)
    print(
        json.dumps(
            {
                "scope": args.scope,
                "selector": args.selector,
                "planned_count": len(selected),
                "retained_count": len(snapshots),
                "snapshots": snapshots,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"MODEL_DOMAIN_SNAPSHOT_FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
