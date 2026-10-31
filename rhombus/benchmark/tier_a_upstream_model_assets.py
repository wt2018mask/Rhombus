"""Recorded official MACE release asset metadata, not signed model bytes.

Observation: ACEsuit/mace-foundations GitHub Releases, 2026-10-31.
No network calls, binary deserialization, model execution or performance claims.
GitHub API release digest fields were null. Asset size is NOT authentication.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

SCHEMA = "rhombus-0205-tier-a-release-asset-candidate-v1"
EXPECTED_ASSETS = {
    "MACE_MP_0_SMALL_PUBLISHER_EXAMPLE": {
        "repository": "ACEsuit/mace-foundations", "release_tag": "mace_mp_0",
        "release_id": 136640972, "asset_id": 145021750,
        "asset_name": "2023-12-10-mace-128-L0_energy_epoch-249.model",
        "size_bytes": 32581838,
    },
    "MACE_MPA_0_MEDIUM_RHOMBUS": {
        "repository": "ACEsuit/mace-foundations", "release_tag": "mace_mpa_0",
        "release_id": 191152959, "asset_id": 213937064,
        "asset_name": "mace-mpa-0-medium.model",
        "size_bytes": 79462305,
    },
}


def create_candidate_asset_manifest():
    rows = []
    for role, expected in sorted(EXPECTED_ASSETS.items()):
        row = deepcopy(expected)
        row["arm_id"] = role
        row["github_asset_digest"] = None
        row["model_bytes_verified"] = False
        rows.append(row)
    return {
        "schema_version": SCHEMA,
        "source": "GITHUB_FIRST_PARTY_RELEASE_METADATA_OBSERVED_2026_10_31",
        "assets": rows,
        "publisher_signature_verified": False,
        "execution_authorized": False,
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "scientific_status": "SCIENTIFIC_NO_GO_ABSTAIN",
    }


def verify_candidate_asset_manifest(document):
    expected = create_candidate_asset_manifest()
    if type(document) is not dict or document != expected:
        raise ValueError("RELEASE_ASSET_IDENTITY_OR_AUTHORIZATION_TAMPERED")
    encoded = (json.dumps(expected, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
    return {
        "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        "matched_assets": 2,
        "binary_authenticated": False,
        "execution_authorized": False,
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "blockers": ["MODEL_FILE_BYTES_NOT_VERIFIED", "MODEL_CHECKPOINT_OWNER_PIN_REQUIRED"],
    }
