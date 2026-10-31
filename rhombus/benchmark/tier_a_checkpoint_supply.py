"""Checkpoint supply-chain evidence without downloads, deserialization or execution.

This module intentionally distinguishes:
 - upstream RELEASE METADATA (file name, size, asset ID, *no publisher hash*),
 - an independent educational source reporting a SHA-256 for MACE-MP-0a small,
 - an actual local byte-for-byte match (only when a file is explicitly supplied),
 - the historical Rhombus MPA-0 medium digest (not reverified unless supplied).

A matching checksum is not proof of training-set independence, scientific
accuracy, signed publication provenance, or permission to run a model.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .tier_a_budget_contract import (
    MACE_MEDIUM_SHA256, REQUIRED_MODEL_IDS, inspect_budget_draft,
)
from .tier_a_model_neb_preflight import verify_local_binary_bytes

SCHEMA = "rhombus-0204-tier-a-checkpoint-supply-review-v1"
SMALL_ID = "MACE_MP_0_SMALL_PUBLISHER_EXAMPLE"
MEDIUM_ID = "MACE_MPA_0_MEDIUM_RHOMBUS"
UPSTREAM_REPO = "ACEsuit/mace-foundations"
SOURCE_OF_THIRD_PARTY_CHECKSUM = (
    "https://enccs.github.io/mlip-hands-on/episodes/01-model.html"
)
SMALL_THIRD_PARTY_SHA256 = (
    "2ddb079cee0e131eaaf6912ba581b394551ead283e95c99cfe78c605d10b5736"
)
ASSET_INVENTORY = {
    SMALL_ID: {
        "tag": "mace_mp_0",
        "release_id": 136640972,
        "asset_id": 145021750,
        "filename": "2023-12-10-mace-128-L0_energy_epoch-249.model",
        "size_bytes": 32_581_838,
        "sha256_source": "THIRD_PARTY_ENCCS_TUTORIAL_NOT_UPSTREAM_SIGNATURE",
        "reference_sha256": SMALL_THIRD_PARTY_SHA256,
        "release_asset_sha256": None,
        "source_url": (
            "https://github.com/ACEsuit/mace-foundations/releases/download/"
            "mace_mp_0/2023-12-10-mace-128-L0_energy_epoch-249.model"
        ),
    },
    MEDIUM_ID: {
        "tag": "mace_mpa_0",
        "release_id": 191152959,
        "asset_id": 213937064,
        "filename": "mace-mpa-0-medium.model",
        "size_bytes": 79_462_305,
        "sha256_source": "HISTORICAL_RHOMBUS_0200_NOT_UPSTREAM_SIGNATURE",
        "reference_sha256": MACE_MEDIUM_SHA256,
        "release_asset_sha256": None,
        "source_url": (
            "https://github.com/ACEsuit/mace-foundations/releases/download/"
            "mace_mpa_0/mace-mpa-0-medium.model"
        ),
    },
}


def _canonical_hash(obj: Any) -> str:
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def inspect_supply(
    draft: Mapping[str, Any],
    *,
    provided_files: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    """Review exactly two roles, with strict size/hash and no silent auto-pinning.

    A locally verified small file is eligible for owner review, NOT frozen.
    The input draft is never modified and may already contain an owner-declared
    candidate digest; this function does not treat that as owner authorization.
    """
    contract = inspect_budget_draft(draft)
    models = {row["arm_id"]: row for row in draft["model_arms"]}
    supplied = {} if provided_files is None else provided_files
    if type(supplied) is not dict or not set(supplied).issubset(REQUIRED_MODEL_IDS):
        raise ValueError("UNKNOWN_MODEL_ROLE")
    records: dict[str, Any] = {}
    blockers: set[str] = set()
    for role in sorted(REQUIRED_MODEL_IDS):
        expected = ASSET_INVENTORY[role]
        source_digest = expected["reference_sha256"]
        draft_digest = models[role]["checkpoint_sha256"]
        status: dict[str, Any] = {
            "upstream_repository": UPSTREAM_REPO,
            "role": role,
            "release_tag": expected["tag"],
            "release_id": expected["release_id"],
            "asset_id": expected["asset_id"],
            "filename": expected["filename"],
            "release_reported_size_bytes": expected["size_bytes"],
            "release_reported_sha256": None,
            "source_url": expected["source_url"],
            "reference_digest_source": expected["sha256_source"],
            "reference_sha256": source_digest,
            "draft_sha256": draft_digest,
            "local_file_status": "NOT_PROVIDED",
            "local_observation": None,
        }
        if draft_digest is not None and draft_digest != source_digest:
            blockers.add(f"{role}:DRAFT_DIGEST_CONFLICTS_WITH_REFERENCE")
        if role not in supplied:
            blockers.add(f"{role}:LOCAL_FILE_NOT_VERIFIED")
        else:
            try:
                observed = verify_local_binary_bytes(
                    Path(supplied[role]), expected_sha256=source_digest,
                    expected_size_bytes=expected["size_bytes"],
                )
            except (OSError, ValueError) as exc:
                status["local_file_status"] = "REJECTED"
                status["rejection_code"] = str(exc)
                blockers.add(f"{role}:LOCAL_BYTES_REJECTED")
            else:
                status["local_file_status"] = "MATCHED_REFERENCE_BYTES_NOT_PUBLISHER_SIGNATURE"
                status["local_observation"] = {
                    "sha256": observed["sha256"],
                    "size_bytes": observed["size_bytes"],
                    "deserialization": False,
                    "inference": False,
                }
                if role == SMALL_ID:
                    blockers.add("SMALL:OWNER_DRAFT_PIN_REVIEW_PENDING")
        records[role] = status

    return {
        "schema_version": SCHEMA,
        "science_status": "SCIENTIFIC_NO_GO_ABSTAIN",
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "execution_authorized": False,
        "task": draft["scope"],
        "draft_sha256": contract["draft_sha256"],
        "reference_catalog_sha256": _canonical_hash(ASSET_INVENTORY),
        "small_third_party_hash_source_url": SOURCE_OF_THIRD_PARTY_CHECKSUM,
        "source_statement": "GITHUB_RELEASE_METADATA_NO_SHA256; THIRD_PARTY_SMALL_SHA256_NOT_PUBLISHER_ATTESTED",
        "model_arms": records,
        "supply_blockers": sorted(blockers),
        "owner_review_required": True,
        "file_downloads": False,
        "model_loads": False,
        "model_evaluations": 0,
        "heldout_targets_read": False,
    }


def make_small_digest_candidate(draft: Mapping[str, Any], review: Mapping[str, Any],
                                *, small_model_file: Path) -> dict[str, Any]:
    """Return a *non-executable* candidate only after actual small bytes match.

    Never auto-enable execution or write to CURRENT; the owner must separately
    inspect provenance and approve any authoritative freeze.
    """
    inspect_budget_draft(draft)
    if (review.get("schema_version") != SCHEMA
            or review.get("draft_sha256") != _canonical_hash(draft)
            or review.get("execution_authorized") is not False
            or review.get("file_downloads") is not False
            or review.get("model_loads") is not False):
        raise ValueError("SUPPLY_REPORT_CONTEXT_MISMATCH")
    status = review.get("model_arms", {}).get(SMALL_ID, {})
    if (status.get("local_file_status") != "MATCHED_REFERENCE_BYTES_NOT_PUBLISHER_SIGNATURE"
            or status.get("local_observation", {}).get("sha256") != SMALL_THIRD_PARTY_SHA256
            or status.get("local_observation", {}).get("size_bytes") != 32_581_838):
        raise ValueError("SMALL_MODEL_BYTES_MUST_BE_VERIFIED_BEFORE_CANDIDATE_PIN")
    # The JSON review can be forged or become stale: rehash exact bytes at the
    # moment this non-executable candidate is constructed.
    verify_local_binary_bytes(
        Path(small_model_file), expected_sha256=SMALL_THIRD_PARTY_SHA256,
        expected_size_bytes=ASSET_INVENTORY[SMALL_ID]["size_bytes"],
    )
    candidate = deepcopy(draft)
    arms = {a["arm_id"]: a for a in candidate["model_arms"]}
    if arms[SMALL_ID]["checkpoint_sha256"] not in (None, SMALL_THIRD_PARTY_SHA256):
        raise ValueError("SMALL_MODEL_OWNER_PIN_CONFLICT")
    arms[SMALL_ID]["checkpoint_sha256"] = SMALL_THIRD_PARTY_SHA256
    result = inspect_budget_draft(candidate)
    if result["execution_authorized"] is not False or candidate["execution_authorized"] is not False:
        raise ValueError("UNAUTHORIZED_MODEL_EXECUTION_PROMOTION")
    return candidate
