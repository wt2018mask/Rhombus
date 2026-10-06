"""Persist the canonical B4 blind execution payload from sealed identity state.

This module intentionally keeps the legacy↔opaque identity mapping outside the
repository.  The persisted output contains only the four B0-visible ingress
fields and is rendered deterministically for content-addressed handling.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from rudeus.science.contracts import canonical_bytes
from rudeus.science.known_material_artifact_curation import (
    load_registry,
    load_retention_index,
)
from rudeus.science.known_material_b2_coverage import (
    load_cataloged_truth_bundles,
    load_truth_bundle_catalog,
)
from rudeus.science.known_material_b3_split import load_b3_split_freeze
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


def load_opaque_id_map(path: Path) -> Mapping[str, str]:
    """Load a sealed legacy-id→opaque-id mapping without retaining its path."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value:
        raise ValueError("opaque-id map must be a non-empty JSON object")
    if any(not isinstance(key, str) or not isinstance(item, str) for key, item in value.items()):
        raise ValueError("opaque-id map keys and values must be strings")
    return dict(value)


def build_canonical_b4_blind_execution_package(
    *,
    repo_root: Path,
    opaque_ids_by_legacy_id: Mapping[str, str],
) -> B4BlindExecutionPackage:
    """Build the B4 package from persisted canonical state plus sealed ids."""
    data_root = repo_root / "data/benchmarks/known_material"

    split_freeze = load_b3_split_freeze(data_root / "b3_split_freeze_v1.json")
    catalog = load_truth_bundle_catalog(data_root / "truth_bundle_catalog_v1.json")
    truth_bundles = load_cataloged_truth_bundles(catalog, repo_root=repo_root)
    protocol_hash_by_truth_bundle_hash = {
        bundle.content_hash: bundle.benchmark_protocol_hash
        for bundle in truth_bundles.values()
    }
    amendment = build_b4_blind_identity_amendment(
        split_freeze,
        opaque_ids_by_legacy_id=opaque_ids_by_legacy_id,
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
    return build_b4_blind_execution_package(
        split_freeze,
        amendment,
        structure_ledger,
    )


def render_visible_b4_execution_payloads(
    package: B4BlindExecutionPackage,
) -> bytes:
    """Render only the public execution payloads as deterministic JSON bytes."""
    return canonical_bytes(package.execution_payloads) + b"\n"


def materialize_visible_b4_execution_payloads(
    *,
    repo_root: Path,
    opaque_id_map_path: Path,
    output_path: Path,
) -> tuple[str, int]:
    """Create a new identity-clean package file and return (sha256, count).

    Existing files are never overwritten.  The sealed mapping is only read as
    input and is not copied, hashed into a public receipt, or persisted beside
    the visible package.
    """
    opaque_ids = load_opaque_id_map(opaque_id_map_path)
    package = build_canonical_b4_blind_execution_package(
        repo_root=repo_root,
        opaque_ids_by_legacy_id=opaque_ids,
    )
    rendered = render_visible_b4_execution_payloads(package)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as handle:
        handle.write(rendered)
    return hashlib.sha256(rendered).hexdigest(), len(package.execution_payloads)
