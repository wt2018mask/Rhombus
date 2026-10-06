"""B4 blind-identity amendment tests over the immutable canonical B3 split."""
import json
from pathlib import Path

import pytest

from rudeus.science.known_material_b3_split import authorize_b3_split, freeze_b3_split
from rudeus.science.known_material_b4_blinding_amendment import (
    build_b4_blind_identity_amendment,
)
from rudeus.science.known_material_sample_size import load_sample_size_assessment
from rudeus.science.known_material_truth import KnownMaterialTruthBundle
from tests.test_known_material_b2_coverage import canonical_audit
from tests.test_known_material_b3_split_freeze import ROLE_HASHES


ROOT = Path("data/benchmarks/known_material")
PROTOCOL_HASH = "6cb6579cdddaaf4d4fb93ca71828832eb741e31c749fbcff54bce9ab85351369"


def _test_only_opaque_ids(freeze):
    """Generate non-canonical IDs for contract tests only.

    Real B4 opaque IDs must be supplied from a sealed external mapping and must
    never be committed in source or test data.
    """
    return {
        member.benchmark_id: f"km-test{index:04d}"
        for index, member in enumerate(freeze.members)
    }


TRUTH_FILES = (
    "li2s-microcrystalline-v1.json",
    "li3n-crystalline-v1.json",
    "lialo2-gamma-v1.json",
    "libh4-phase-transition-pair-v1.json",
    "llzo-cubic-al-stabilized-v1.json",
    "llzo-tetragonal-undoped-v1.json",
)


def _freeze():
    authorization = authorize_b3_split(
        canonical_audit(),
        load_sample_size_assessment(ROOT / "sample_size_assessment_v1.json"),
    )
    return freeze_b3_split(authorization, ROLE_HASHES)


def _protocol_map():
    result = {}
    for name in TRUTH_FILES:
        bundle = KnownMaterialTruthBundle.from_dict(
            json.loads((ROOT / "truth_bundles" / name).read_text(encoding="utf-8"))
        )
        result[bundle.content_hash] = bundle.benchmark_protocol_hash
    return result


def test_blind_identity_amendment_preserves_split_and_binds_common_protocol():
    freeze = _freeze()
    amendment = build_b4_blind_identity_amendment(
        freeze,
        opaque_ids_by_legacy_id=_test_only_opaque_ids(freeze),
        protocol_hash_by_truth_bundle_hash=_protocol_map(),
    )

    assert amendment.split_freeze_hash == freeze.content_hash
    assert amendment.benchmark_protocol_hash == PROTOCOL_HASH
    assert len(amendment.bindings) == 6
    assert {item.legacy_benchmark_id: item.split for item in amendment.bindings} == {
        item.benchmark_id: item.split for item in freeze.members
    }
    assert {item.opaque_benchmark_id for item in amendment.bindings} == set(
        _test_only_opaque_ids(freeze).values()
    )


def test_opaque_ids_do_not_embed_frozen_material_keys():
    freeze = _freeze()
    amendment = build_b4_blind_identity_amendment(
        freeze,
        opaque_ids_by_legacy_id=_test_only_opaque_ids(freeze),
        protocol_hash_by_truth_bundle_hash=_protocol_map(),
    )
    for item in amendment.bindings:
        assert item.legacy_benchmark_id not in item.opaque_benchmark_id


def test_blind_identity_amendment_rejects_membership_or_protocol_drift():
    opaque = dict(_test_only_opaque_ids(_freeze()))
    opaque.pop("li3n-crystalline")
    with pytest.raises(ValueError, match="cover exactly"):
        build_b4_blind_identity_amendment(
            _freeze(),
            opaque_ids_by_legacy_id=opaque,
            protocol_hash_by_truth_bundle_hash=_protocol_map(),
        )

    protocols = _protocol_map()
    first_hash = next(iter(protocols))
    protocols[first_hash] = "0" * 64
    freeze = _freeze()
    with pytest.raises(ValueError, match="share one benchmark protocol hash"):
        build_b4_blind_identity_amendment(
            freeze,
            opaque_ids_by_legacy_id=_test_only_opaque_ids(freeze),
            protocol_hash_by_truth_bundle_hash=protocols,
        )
