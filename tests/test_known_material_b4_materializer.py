"""Production B4 blind-package materializer tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rudeus.science.known_material_b4_ingress import VISIBLE_FIELDS
from scripts.benchmark.materialize_b4_blind_package import (
    SEALED_OPAQUE_MAP_VERSION,
    VISIBLE_DOCUMENT_VERSION,
    build_canonical_blind_package,
    load_sealed_opaque_id_map,
    render_visible_document,
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


def test_materializer_emits_only_identity_clean_visible_payloads(tmp_path):
    sealed = _sealed_map(tmp_path)
    freeze, package = build_canonical_blind_package(
        repo_root=ROOT,
        sealed_mapping_path=sealed,
    )
    document = json.loads(render_visible_document(freeze, package))

    assert document["document_version"] == VISIBLE_DOCUMENT_VERSION
    assert len(document["payloads"]) == 6
    assert all(tuple(payload) == VISIBLE_FIELDS for payload in document["payloads"])
    serialized = json.dumps(document, sort_keys=True)
    assert all(member.benchmark_id not in serialized for member in freeze.members)
    assert all(member.truth_bundle_hash not in serialized for member in freeze.members)
    assert sum(payload["split"] == "DEV" for payload in document["payloads"]) == 3
    assert sum(payload["split"] == "HELD_OUT" for payload in document["payloads"]) == 3


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


def test_materializer_rejects_repository_output_path(tmp_path):
    sealed = _sealed_map(tmp_path)
    freeze, package = build_canonical_blind_package(
        repo_root=ROOT,
        sealed_mapping_path=sealed,
    )
    document = render_visible_document(freeze, package)

    with pytest.raises(ValueError, match="outside the repository"):
        write_visible_document(
            document,
            output_path=DATA_ROOT / "must-not-write-blind-package.json",
            repo_root=ROOT,
        )
