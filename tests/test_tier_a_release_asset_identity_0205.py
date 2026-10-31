"""Adversarial supply provenance checks, without model files."""
from copy import deepcopy
import pytest
from rhombus.benchmark.tier_a_upstream_model_assets import (
    create_candidate_asset_manifest, verify_candidate_asset_manifest,
)


def test_github_release_assets_are_not_checkpoint_attestation():
    p = create_candidate_asset_manifest()
    summary = verify_candidate_asset_manifest(p)
    assert summary["matched_assets"] == 2
    assert summary["binary_authenticated"] is False
    assert summary["execution_authorized"] is False
    assert {r["arm_id"]: r["size_bytes"] for r in p["assets"]} == {"MACE_MP_0_SMALL_PUBLISHER_EXAMPLE": 32581838, "MACE_MPA_0_MEDIUM_RHOMBUS": 79462305}
    assert all(r["github_asset_digest"] is None for r in p["assets"])


@pytest.mark.parametrize("key,value", [
    ("execution_authorized", True),
    ("benchmark_status", "FROZEN"),
    ("publisher_signature_verified", True),
])
def test_release_manifest_promotion_is_rejected(key, value):
    p = create_candidate_asset_manifest()
    p[key] = value
    with pytest.raises(ValueError, match="TAMPERED"):
        verify_candidate_asset_manifest(p)


def test_replaced_asset_id_is_rejected():
    p = create_candidate_asset_manifest()
    p["assets"][0]["asset_id"] = -1
    with pytest.raises(ValueError, match="TAMPERED"):
        verify_candidate_asset_manifest(p)
