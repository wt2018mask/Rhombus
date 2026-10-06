#!/usr/bin/env python3
"""Materialize the visible B4 blind execution package from sealed external identity state.

The sealed legacy-to-opaque mapping is an input only. It is never echoed, embedded in
the visible package, or written into repository data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Mapping

from rudeus.science.known_material_artifact_curation import (
    load_registry,
    load_retention_index,
)
from rudeus.science.known_material_b2_coverage import (
    load_cataloged_truth_bundles,
    load_truth_bundle_catalog,
)
from rudeus.science.known_material_b3_split import (
    B3SplitFreeze,
    load_b3_split_freeze,
)
from rudeus.science.known_material_b4_blind_package import (
    B4BlindExecutionPackage,
    build_b4_blind_execution_package,
)
from rudeus.science.known_material_b4_blinding_amendment import (
    build_b4_blind_identity_amendment,
)
from rudeus.science.known_material_representation_policy import (
    load_representation_evidence_ledger,
    load_representation_policy_registry,
)
from rudeus.science.known_material_structure_resolution import (
    load_structure_resolution_manifest,
    resolve_structure_manifest,
)


SEALED_OPAQUE_MAP_VERSION = "known-material-b4-sealed-opaque-map-v1"
VISIBLE_DOCUMENT_VERSION = "known-material-b4-visible-package-v1"
DATA_RELATIVE_ROOT = Path("data/benchmarks/known_material")


def load_sealed_opaque_id_map(path: Path) -> Mapping[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {
        "mapping_version",
        "opaque_ids_by_legacy_id",
    }:
        raise ValueError("sealed opaque map has unexpected schema")
    if payload["mapping_version"] != SEALED_OPAQUE_MAP_VERSION:
        raise ValueError("unsupported sealed opaque map version")
    mapping = payload["opaque_ids_by_legacy_id"]
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("sealed opaque map requires a non-empty mapping")
    if any(
        not isinstance(key, str)
        or not key
        or not isinstance(value, str)
        or not value
        for key, value in mapping.items()
    ):
        raise ValueError("sealed opaque map ids must be non-empty strings")
    return dict(mapping)


def build_canonical_blind_package(
    *,
    repo_root: Path,
    sealed_mapping_path: Path,
) -> tuple[B3SplitFreeze, B4BlindExecutionPackage]:
    data_root = repo_root / DATA_RELATIVE_ROOT
    split_freeze = load_b3_split_freeze(data_root / "b3_split_freeze_v1.json")
    catalog = load_truth_bundle_catalog(data_root / "truth_bundle_catalog_v1.json")
    bundles = load_cataloged_truth_bundles(catalog, repo_root=repo_root)
    protocol_hash_by_truth_bundle_hash = {
        bundle.content_hash: bundle.benchmark_protocol_hash
        for bundle in bundles.values()
    }
    amendment = build_b4_blind_identity_amendment(
        split_freeze,
        opaque_ids_by_legacy_id=load_sealed_opaque_id_map(sealed_mapping_path),
        protocol_hash_by_truth_bundle_hash=protocol_hash_by_truth_bundle_hash,
    )
    structure_ledger = resolve_structure_manifest(
        load_structure_resolution_manifest(
            data_root / "structure_resolution_manifest_v1.json"
        ),
        load_registry(data_root / "artifact_registry_v1.json"),
        load_retention_index(data_root / "artifact_retention_index_v1.json"),
        policy_registry=load_representation_policy_registry(
            data_root / "representation_policy_registry_v1.json"
        ),
        policy_evidence_ledger=load_representation_evidence_ledger(
            data_root / "representation_evidence_ledger_v1.json"
        ),
    )
    return (
        split_freeze,
        build_b4_blind_execution_package(
            split_freeze,
            amendment,
            structure_ledger,
        ),
    )


def render_visible_document(
    split_freeze: B3SplitFreeze,
    package: B4BlindExecutionPackage,
) -> str:
    document = {
        "document_version": VISIBLE_DOCUMENT_VERSION,
        "package_version": package.package_version,
        "payloads": [dict(payload) for payload in package.execution_payloads],
    }
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    for member in split_freeze.members:
        if member.benchmark_id in encoded or member.truth_bundle_hash in encoded:
            raise ValueError("visible B4 package leaks frozen scientific identity")
    return encoded + "\n"


def write_visible_document(
    document: str,
    *,
    output_path: Path | None,
    repo_root: Path,
) -> None:
    if output_path is None:
        sys.stdout.write(document)
        return
    resolved_output = output_path.resolve()
    if resolved_output.is_relative_to(repo_root.resolve()):
        raise ValueError("blind package output must remain outside the repository")
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the visible B4 blind package from an externally sealed opaque-id map."
        )
    )
    parser.add_argument(
        "sealed_mapping",
        type=Path,
        help="external JSON mapping; never commit this file to the repository",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Rhombus repository root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="optional output path outside the repository; defaults to stdout",
    )
    args = parser.parse_args()

    split_freeze, package = build_canonical_blind_package(
        repo_root=args.repo_root,
        sealed_mapping_path=args.sealed_mapping,
    )
    write_visible_document(
        render_visible_document(split_freeze, package),
        output_path=args.output,
        repo_root=args.repo_root,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"B4_BLIND_PACKAGE_MATERIALIZATION_FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
