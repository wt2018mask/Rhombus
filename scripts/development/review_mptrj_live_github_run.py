"""Opt-in public GitHub REST review of a manually dispatched MPTrj diagnostic.

Only two pinned public read-only GET requests. No credentials, dispatch,
artifact download, MPTrj source download, or scientific claim promotion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import urllib.request

from rhombus.domain.mptrj_artifact_zip import verify_mptrj_diagnostic_zip_binding
from rhombus.domain.mptrj_run_metadata import validate_mptrj_manual_run_metadata
from scripts.development.verify_mptrj_probe_receipt import read_and_validate_receipt

API_ROOT = "https://api.github.com/repos/wt2018mask/Rhombus"
ARTIFACT_NAME = "mptrj-first-frame-observation"
MAX_API_BYTES = 128 * 1024
SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")


class MPTrjLiveReviewError(ValueError):
    """Unsafe or inconsistent public GitHub REST evidence."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _unique_pairs(pairs):
    record = {}
    for key, value in pairs:
        if key in record:
            raise MPTrjLiveReviewError("duplicate JSON key from GitHub REST")
        record[key] = value
    return record


def _fetch_json(url: str, *, open_url) -> object:
    if not url.startswith(API_ROOT + "/actions/runs/"):
        raise MPTrjLiveReviewError("unapproved GitHub REST endpoint")
    request = urllib.request.Request(
        url, method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Accept-Encoding": "identity",
            "User-Agent": "Rhombus-MPTrj-public-diagnostic-review/1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with open_url(request, timeout=15) as response:
        if getattr(response, "status", None) != 200 or response.geturl() != url:
            raise MPTrjLiveReviewError("GitHub API requires exact HTTP 200 without redirect")
        if response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip() != "application/json":
            raise MPTrjLiveReviewError("GitHub API returned non-JSON")
        if response.headers.get("Content-Encoding", "identity").lower() not in ("", "identity"):
            raise MPTrjLiveReviewError("compressed API response is forbidden")
        declared = response.headers.get("Content-Length")
        if declared is not None:
            try:
                length = int(declared)
            except ValueError as exc:
                raise MPTrjLiveReviewError("invalid API Content-Length") from exc
            if not 1 <= length <= MAX_API_BYTES:
                raise MPTrjLiveReviewError("API Content-Length exceeds 128KiB limit")
        data = response.read(MAX_API_BYTES + 1)
        if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_API_BYTES:
            raise MPTrjLiveReviewError("API JSON exceeds 128KiB read limit")
        if declared is not None and len(data) != length:
            raise MPTrjLiveReviewError("API JSON header/body length mismatch")
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)


def review_mptrj_live_run(
    *,
    run_id: int,
    expected_head_sha: str,
    artifact_zip: Path,
    receipt: Path,
    open_url=None,
) -> dict:
    """Review one explicitly identified run with two public HTTPS GETs only.

    API transport and local archive integrity are NOT signed scientific lineage.
    """
    if type(run_id) is not int or not 1 <= run_id < 2**63:
        raise MPTrjLiveReviewError("run ID must be a bounded positive integer")
    if not isinstance(expected_head_sha, str) or not SHA_PATTERN.fullmatch(expected_head_sha):
        raise MPTrjLiveReviewError("expected main SHA must be 40 lowercase hex digits")
    if open_url is None:
        open_url = urllib.request.build_opener(NoRedirect()).open

    run_url = f"{API_ROOT}/actions/runs/{run_id}"
    artifact_url = (
        f"{run_url}/artifacts?name={ARTIFACT_NAME}&per_page=100"
    )
    run_json = _fetch_json(run_url, open_url=open_url)
    artifacts_json = _fetch_json(artifact_url, open_url=open_url)
    if (
        not isinstance(artifacts_json, dict)
        or type(artifacts_json.get("total_count")) is not int
        or artifacts_json["total_count"] != 1
    ):
        raise MPTrjLiveReviewError("live named-artifact total_count must equal one")
    metadata = validate_mptrj_manual_run_metadata(
        run_json, artifacts_json, expected_head_sha=expected_head_sha,
        require_artifact_digest=True,
    )
    receipt_info = read_and_validate_receipt(receipt, expected_bytes=262144)
    archive_info = verify_mptrj_diagnostic_zip_binding(
        artifact_zip, receipt,
        expected_artifact_digest=metadata["artifact_digest_claim"],
    )
    if receipt_info["report_metadata_sha256"] != archive_info["receipt_metadata_sha256"]:
        raise MPTrjLiveReviewError("ZIP/local receipt metadata fingerprints disagree")
    return {
        "status": "LIVE_PUBLIC_GITHUB_REST_LOCAL_ARTIFACT_CONSISTENCY_ONLY",
        "run_id": metadata["run_id"],
        "artifact_id": metadata["artifact_id"],
        "head_sha": metadata["head_sha"],
        "artifact_zip_sha256": archive_info["artifact_zip_sha256"],
        "receipt_byte_sha256": archive_info["receipt_byte_sha256"],
        "github_signed_attestation_present": False,
        "mptrj_full_source_verified": False,
        "mace_mpa0_training_frames_attested": False,
        "exposure_audit_authorized": False,
        "empirical_calibration_authorized": False,
        "unseen_generalization_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-review", action="store_true")
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--expected-head-sha", required=True)
    parser.add_argument("--artifact-zip", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if not args.live_review:
            raise MPTrjLiveReviewError("explicit --live-review required for public GET")
        result = review_mptrj_live_run(
            run_id=args.run_id, expected_head_sha=args.expected_head_sha,
            artifact_zip=args.artifact_zip, receipt=args.receipt,
        )
    except (ValueError, OSError, UnicodeError, TypeError) as exc:
        print(f"MPTRJ_LIVE_REVIEW_REJECTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("MPTRJ_LIVE_REST_LOCAL_ARTIFACT_CONSISTENCY_PASS")
    print(f"RUN_ID={result['run_id']}; ARTIFACT_ID={result['artifact_id']}")
    print(f"ZIP_SHA256={result['artifact_zip_sha256']}")
    print("NO_SIGNED_GITHUB_PROVENANCE; NO_FULL_MPTRJ_OR_MACE_TRAINING_ATTESTATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
