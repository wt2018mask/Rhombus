"""Persisted B4 blind-package materialization tests."""
import hashlib
import json
from pathlib import Path

import pytest

from rudeus.science.known_material_b3_split import load_b3_split_freeze
from rudeus.science.known_material_b4_ingress import VISIBLE_FIELDS
from rudeus.science.known_material_b4_materialization import (
    materialize_visible_b4_execution_payloads,
)


ROOT = Path("data/benchmarks/known_material")


def _sealed_test_map():
    freeze = load_b3_split_freeze(ROOT / "b3_split_freeze_v1.json")
    return {
        member.benchmark_id: f"km-out{index:05d}"
        for index, member in enumerate(freeze.members)
    }


def test_materialization_is_deterministic_identity_clean_and_non_overwriting(tmp_path):
    sealed_map = tmp_path / "sealed-map.json"
    sealed_map.write_text(json.dumps(_sealed_test_map()), encoding="utf-8")
    first = tmp_path / "blind-package-a.json"
    second = tmp_path / "blind-package-b.json"

    first_hash, first_count = materialize_visible_b4_execution_payloads(
        repo_root=Path("."),
        opaque_id_map_path=sealed_map,
        output_path=first,
    )
    second_hash, second_count = materialize_visible_b4_execution_payloads(
        repo_root=Path("."),
        opaque_id_map_path=sealed_map,
        output_path=second,
    )

    first_bytes = first.read_bytes()
    assert first_bytes == second.read_bytes()
    assert first_hash == second_hash == hashlib.sha256(first_bytes).hexdigest()
    assert first_count == second_count == 6

    payloads = json.loads(first_bytes)
    assert len(payloads) == 6
    assert all(set(payload) == set(VISIBLE_FIELDS) for payload in payloads)
    assert [payload["benchmark_id"] for payload in payloads] == sorted(
        payload["benchmark_id"] for payload in payloads
    )

    freeze = load_b3_split_freeze(ROOT / "b3_split_freeze_v1.json")
    serialized = first_bytes.decode("utf-8")
    assert all(member.benchmark_id not in serialized for member in freeze.members)
    assert all(member.truth_bundle_hash not in serialized for member in freeze.members)

    with pytest.raises(FileExistsError):
        materialize_visible_b4_execution_payloads(
            repo_root=Path("."),
            opaque_id_map_path=sealed_map,
            output_path=first,
        )


def test_materialization_fails_closed_on_incomplete_sealed_mapping(tmp_path):
    mapping = _sealed_test_map()
    mapping.pop(next(iter(mapping)))
    sealed_map = tmp_path / "incomplete-map.json"
    sealed_map.write_text(json.dumps(mapping), encoding="utf-8")

    with pytest.raises(ValueError, match="cover exactly"):
        materialize_visible_b4_execution_payloads(
            repo_root=Path("."),
            opaque_id_map_path=sealed_map,
            output_path=tmp_path / "should-not-exist.json",
        )

    assert not (tmp_path / "should-not-exist.json").exists()
