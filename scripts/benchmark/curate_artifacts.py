#!/usr/bin/env python3
"""Generic known-material artifact curation entry point."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rudeus.science.known_material_artifact_curation import (
    CurationScope,
    adapter_for,
    apply_retention_receipt,
    build_curation_plan,
    load_registry,
    load_retention_index,
)


REGISTRY = Path("data/benchmarks/known_material/artifact_registry_v1.json")
INDEX = Path("data/benchmarks/known_material/artifact_retention_index_v1.json")


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(path)


def curate(
    repo_root: Path,
    *,
    scope: str,
    selector: str | None,
):
    registry = load_registry(repo_root / REGISTRY)
    index_path = repo_root / INDEX
    index = load_retention_index(index_path)

    plan = build_curation_plan(
        registry,
        index,
        scope=scope,
        selector=selector,
    )
    entries = {entry.artifact_key: entry for entry in registry.entries}

    receipts = []
    for artifact_key in plan.artifact_keys:
        entry = entries[artifact_key]
        adapter = adapter_for(entry.source_adapter)
        receipt = adapter.retain(entry, repo_root=repo_root)
        index = apply_retention_receipt(index, receipt)
        _write_json(repo_root / entry.receipt_path, receipt.to_dict())
        receipts.append(receipt)

    if receipts:
        _write_json(index_path, index.to_dict())

    summary = {
        "scope": plan.scope,
        "selector": plan.selector,
        "planned_count": len(plan.artifact_keys),
        "retained_count": len(receipts),
        "artifact_keys": list(plan.artifact_keys),
        "receipts": [
            {
                "artifact_key": receipt.artifact_key,
                "material_key": receipt.material_key,
                "source_adapter": receipt.source_adapter,
                "source_id": receipt.source_id,
                "artifact_sha256": receipt.artifact_sha256,
                "byte_count": receipt.byte_count,
                "retained_path": receipt.retained_path,
            }
            for receipt in receipts
        ],
    }
    print(json.dumps(summary, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope",
        choices=[scope.value for scope in CurationScope],
        default=CurationScope.UNRESOLVED.value,
    )
    parser.add_argument(
        "--selector",
        default=None,
        help="Required only for material/family/source scopes.",
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[2],
        type=Path,
    )
    args = parser.parse_args(argv)
    selector = args.selector.strip() if args.selector else None
    curate(
        args.repo_root.resolve(),
        scope=args.scope,
        selector=selector,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"ARTIFACT_CURATION_FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
