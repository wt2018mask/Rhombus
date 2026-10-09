"""Validate *reported* upstream MACE-MPA-0 checkpoint bytes identity, offline.

A known SHA256 in upstream code is useful for future binary verification, but
we have not independently hashed the release asset and it carries no training
frame selection/preprocessing provenance. This contract cannot authorize an
exposure audit or any generalization claim.
"""
from __future__ import annotations

from typing import Mapping, Any

PUBLIC_SHA256 = "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"
MACE_REPO_COMMIT = "0f5de4b15d9c7f86d4e50996533ecf6c0f48a51b"
SOURCE_PATH = "tests/golden/foundation_artifacts.py"
REFERENCE_PATH = "tests/golden/references/mpa0_medium_e3nn_cpu_fp64.json"
RELEASE_URL = "https://github.com/ACEsuit/mace-foundations/releases/tag/mace_mpa_0"
MODEL = "mace-mpa-0-medium.model"
SCHEMA = "rhombus-phase3-mpa0-publisher-reported-digest-v1"
NEVER_AUTHORIZED = (
    "binary_independently_rehashed",
    "mptrj_full_source_sha256_verified",
    "exact_mptrj_training_frames_attested",
    "exact_salex_training_frames_attested",
    "checkpoint_bound_preprocessing_attested",
    "training_energy_label_selection_attested",
    "exposure_audit_authorized",
    "empirical_calibration_authorized",
    "unseen_generalization_authorized",
)


def review_reported_mpa0_checkpoint_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    """Accept only an exact bounded source inventory, never a training audit.

    The two fixed upstream repository files are intentionally a *reported*
    checkpoint digest. They do not constitute a local binary rehash. This
    function does not contact GitHub or take a downloaded model path.
    """
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "status", "publisher", "release",
        "declared_training_families", "limits_and_claims",
    } or value["schema_version"] != SCHEMA or value["status"] != (
        "UPSTREAM_REPORTED_CHECKPOINT_SHA256_NOT_INDEPENDENTLY_VERIFIED"
    ):
        raise ValueError("unexpected upstream checkpoint inventory schema")
    publisher = value["publisher"]
    release = value["release"]
    limits = value["limits_and_claims"]
    if (not isinstance(publisher, dict) or set(publisher) != {
        "repository", "commit_sha", "source_file", "reference_file",
        "tracked_checkpoint_file", "reported_model_sha256",
        "release_same_digest_asserted_by_upstream",
    } or publisher != {
        "repository": "ACEsuit/mace",
        "commit_sha": MACE_REPO_COMMIT,
        "source_file": SOURCE_PATH,
        "reference_file": REFERENCE_PATH,
        "tracked_checkpoint_file": "mace/calculators/foundations_models/" + MODEL,
        "reported_model_sha256": PUBLIC_SHA256,
        "release_same_digest_asserted_by_upstream": True,
    }):
        raise ValueError("upstream SHA256 and source revision not pinned")
    if not isinstance(release, dict) or release != {
        "url": RELEASE_URL,
        "asset_name": MODEL,
        "asset_size_bytes": 79_462_305,
        "github_release_digest_independently_verified": False,
    }:
        raise ValueError("upstream release asset identity or verification scope changed")
    if value["declared_training_families"] != ["MPTrj", "sAlex"]:
        raise ValueError("wrong training dataset family declaration")
    if not isinstance(limits, dict) or set(limits) != set(NEVER_AUTHORIZED) or any(
        limits[key] is not False for key in NEVER_AUTHORIZED
    ):
        raise ValueError("unverified scientific provenance promoted to PASS")
    return {
        "schema_version": "rhombus-phase3-mpa0-source-inventory-readiness-v1",
        "checkpoint_reported_sha256": PUBLIC_SHA256,
        "checkpoint_publisher_sha256_found": True,
        "checkpoint_independently_verified": False,
        "exact_training_frames_attested": False,
        "mptrj_full_source_verified": False,
        "exposure_audit_authorized": False,
        "empirical_calibration_authorized": False,
        "unseen_generalization_authorized": False,
        "next_evidence_needed": [
            "independently hash exact 79462305-byte upstream checkpoint if resource-approved",
            "independent original MPTrj complete-source identity",
            "checkpoint-selected MPTrj and sAlex frame manifests",
            "checkpoint-bound preprocessing and energy-label selection",
        ],
    }
