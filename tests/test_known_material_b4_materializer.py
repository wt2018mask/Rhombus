"""Production B4 blind-package materializer tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rudeus.science.known_material_artifact_curation import (
    load_registry,
    load_retention_index,
)
from rudeus.science.known_material_b2_coverage import (
    load_cataloged_truth_bundles,
    load_truth_bundle_catalog,
)
from rudeus.science.known_material_b3_split import load_b3_split_freeze
from rudeus.science.known_material_b4_blinding_integrity import (
    PUBLIC_FROZEN_MATERIAL_IDENTITIES,
    PUBLIC_TRUTH_BUNDLE_BINDINGS,
    PUBLIC_VISIBLE_STRUCTURE_HASH_BINDINGS,
    audit_b4_blinding_integrity,
)
from rudeus.science.known_material_representation_policy import (
    load_representation_evidence_ledger,
    load_representation_policy_registry,
)
from rudeus.science.known_material_structure_resolution import (
    load_structure_resolution_manifest,
    resolve_structure_manifest,
)
from scripts.benchmark.materialize_b4_blind_package import (
    SEALED_OPAQUE_MAP_VERSION,
    build_canonical_blind_package,
    load_sealed_opaque_id_map,
    write_visible_document,
)


ROOT = Path(".")
DATA_ROOT = Path("data/benchmarks/known_material")


def _sealed_map(tmp_path: Path) -> Path:
    from rudeus.science.known_material_b3_split import load_b3_split_freeze

    freeze = load_b3_split_freeze(DATA_ROOT / "b3_split_freeze_v1.json")
    payload = {
        "mapping_version": SEALED_OPAQUE_MAP_VERSION,
        "opaque_ids_by_legacy_id": {
            member.benchmark_id: f"km-mat{index:05d}"
            for index, member in enumerate(freeze.members)
        },
    }
    path = tmp_path / "sealed-map.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _canonical_blinding_audit():
    freeze = load_b3_split_freeze(DATA_ROOT / "b3_split_freeze_v1.json")
    catalog = load_truth_bundle_catalog(DATA_ROOT / "truth_bundle_catalog_v1.json")
    bundles = load_cataloged_truth_bundles(catalog, repo_root=ROOT)
    ledger = resolve_structure_manifest(
        load_structure_resolution_manifest(
            DATA_ROOT / "structure_resolution_manifest_v1.json"
        ),
        load_registry(DATA_ROOT / "artifact_registry_v1.json"),
        load_retention_index(DATA_ROOT / "artifact_retention_index_v1.json"),
        policy_registry=load_representation_policy_registry(
            DATA_ROOT / "representation_policy_registry_v1.json"
        ),
        policy_evidence_ledger=load_representation_evidence_ledger(
            DATA_ROOT / "representation_evidence_ledger_v1.json"
        ),
    )
    return audit_b4_blinding_integrity(freeze, bundles, ledger)


def test_canonical_b4_blinding_integrity_fails_closed_on_public_exposure():
    audit = _canonical_blinding_audit()

    assert audit.contamination_codes == (
        PUBLIC_FROZEN_MATERIAL_IDENTITIES,
        PUBLIC_TRUTH_BUNDLE_BINDINGS,
        PUBLIC_VISIBLE_STRUCTURE_HASH_BINDINGS,
    )
    assert len(audit.public_frozen_material_keys) == 6
    assert len(audit.public_truth_material_keys) == 6
    assert len(audit.public_structure_bindings) == 6
    assert {
        item.material_key for item in audit.public_structure_bindings
    } == set(audit.public_frozen_material_keys)
    assert audit.strong_blind_qualification_authorized is False
    assert audit.production_blind_package_authorized is False


def test_production_materializer_refuses_contaminated_canonical_cohort(tmp_path):
    sealed = _sealed_map(tmp_path)
    with pytest.raises(ValueError, match="blinding integrity is contaminated"):
        build_canonical_blind_package(
            repo_root=ROOT,
            sealed_mapping_path=sealed,
        )

def test_materializer_rejects_repository_sealed_map():
    with pytest.raises(ValueError, match="sealed opaque map must remain outside"):
        build_canonical_blind_package(
            repo_root=ROOT,
            sealed_mapping_path=DATA_ROOT / "must-not-store-sealed-map.json",
        )


def test_sealed_map_schema_fails_closed(tmp_path):
    path = tmp_path / "sealed-map.json"
    path.write_text(
        json.dumps(
            {
                "mapping_version": SEALED_OPAQUE_MAP_VERSION,
                "opaque_ids_by_legacy_id": {"legacy": "km-deadbeef"},
                "unexpected": "must-not-be-accepted",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unexpected schema"):
        load_sealed_opaque_id_map(path)


def test_materializer_rejects_repository_output_path():
    with pytest.raises(ValueError, match="outside the repository"):
        write_visible_document(
            "{}\n",
            output_path=DATA_ROOT / "must-not-write-blind-package.json",
            repo_root=ROOT,
        )
