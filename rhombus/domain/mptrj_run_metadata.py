"""Offline consistency review of an explicitly dispatched MPTrj GitHub run.

Caller-supplied API JSON can be edited. This check is not a GitHub signature,
proof that a receipt came from an artifact, or any scientific attestation.
"""
from __future__ import annotations

import re


class MPTrjRunMetadataError(ValueError):
    """Missing, inconsistent, or disallowed workflow metadata."""


REPOSITORY = "wt2018mask/Rhombus"
WORKFLOW_NAME = "Phase 3 MPTrj Capped Source Prefix"
WORKFLOW_PATH = ".github/workflows/phase3-mptrj-first-frame-manual.yml"
ARTIFACT_NAME = "mptrj-first-frame-observation"
ARTIFACT_DIGEST_PATTERN = re.compile(r"sha256:([0-9a-f]{64})\Z")
SHA_PATTERN = re.compile(r"[a-f0-9]{40}\Z")


def _positive_integer(value: object, name: str, maximum: int = 2**63 - 1) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise MPTrjRunMetadataError(f"{name} must be a bounded positive integer")
    return value


def _mapping(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise MPTrjRunMetadataError(f"{name} must be a JSON object")
    return value


def validate_mptrj_manual_run_metadata(
    run_record: object,
    artifacts_record: object,
    *,
    expected_head_sha: str,
    require_artifact_digest: bool = False,
) -> dict:
    """Check metadata *consistency* only; inputs must be independently sourced.

    Does not bind arbitrary local receipt bytes to an actual GitHub artifact.
    It does not authorize exposure, calibration, or unseen-generalization.
    """
    if not isinstance(expected_head_sha, str) or not SHA_PATTERN.fullmatch(expected_head_sha):
        raise MPTrjRunMetadataError("expected head SHA must be an exact lowercase Git commit SHA")
    run = _mapping(run_record, "run")
    run_id = _positive_integer(run.get("id"), "run.id")
    _positive_integer(run.get("run_attempt"), "run.run_attempt")
    if run.get("event") != "workflow_dispatch" or run.get("name") != WORKFLOW_NAME:
        raise MPTrjRunMetadataError("not the specifically named manual MPTrj workflow")
    if run.get("path") not in (WORKFLOW_PATH, WORKFLOW_PATH + "@refs/heads/main"):
        raise MPTrjRunMetadataError("manual workflow path/ref does not match")
    if run.get("head_branch") != "main" or run.get("head_sha") != expected_head_sha:
        raise MPTrjRunMetadataError("run does not match the explicitly reviewed main SHA")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise MPTrjRunMetadataError("run is not completed successfully")
    if run.get("html_url") != f"https://github.com/{REPOSITORY}/actions/runs/{run_id}":
        raise MPTrjRunMetadataError("run HTML URL does not match its ID")
    repo = _mapping(run.get("repository"), "run.repository")
    if repo.get("full_name") != REPOSITORY:
        raise MPTrjRunMetadataError("workflow run belongs to a different repository")

    collection = _mapping(artifacts_record, "artifact response")
    artifacts = collection.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) > 100:
        raise MPTrjRunMetadataError("artifact collection missing or exceeds review limit")
    named = [a for a in artifacts if isinstance(a, dict) and a.get("name") == ARTIFACT_NAME]
    if len(named) != 1:
        raise MPTrjRunMetadataError("expected exactly one bounded diagnostic artifact")
    artifact = named[0]
    artifact_id = _positive_integer(artifact.get("id"), "artifact.id")
    _positive_integer(artifact.get("size_in_bytes"), "artifact.size_in_bytes", maximum=65536)
    if artifact.get("expired") is not False:
        raise MPTrjRunMetadataError("diagnostic artifact is expired or missing expiry state")
    if artifact.get("archive_download_url") != (
        f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip"
    ):
        raise MPTrjRunMetadataError("artifact API URL does not match its ID")
    # SHA256 of entire ZIP archive. Caller-supplied JSON is not signed.
    claimed_digest = artifact.get("digest")
    if claimed_digest is None:
        if require_artifact_digest:
            raise MPTrjRunMetadataError("strict archive review requires artifact sha256 digest")
    elif not isinstance(claimed_digest, str) or not ARTIFACT_DIGEST_PATTERN.fullmatch(claimed_digest):
        raise MPTrjRunMetadataError("artifact digest must be canonical sha256:lowercase-hex")
    bound_run = _mapping(artifact.get("workflow_run"), "artifact.workflow_run")
    if bound_run.get("id") != run_id or bound_run.get("head_sha") != expected_head_sha:
        raise MPTrjRunMetadataError("artifact metadata does not match the reviewed run")

    return {
        "status": "CALLER_SUPPLIED_GITHUB_API_METADATA_CONSISTENT_ONLY",
        "run_id": run_id,
        "run_attempt": run["run_attempt"],
        "head_sha": expected_head_sha,
        "artifact_id": artifact_id,
        "artifact_digest_claim": claimed_digest,
        "github_api_response_authenticated": False,
        "receipt_bytes_bound_to_artifact": False,
        "full_source_byte_identity_verified": False,
        "mace_mpa0_training_membership_attested": False,
        "execute_exposure_audit": False,
        "empirical_calibration_use": False,
        "unseen_generalization_claim": False,
    }
