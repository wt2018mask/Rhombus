"""Verify a successfully dispatched 1MiB MPTrj GitHub run and metadata ZIP.

Exactly two public read-only GitHub REST GETs, only when --live-review is set.
The report ZIP is supplied locally: this script NEVER downloads the MPTrj
source, the artifact, or triggers Actions/Kaggle. GitHub API and digest
consistency are not signed provenance or full-source/training attestation.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
from zipfile import BadZipFile, ZipFile

from scripts.development.observe_mptrj_multiframe_manual import (
    MAX_REPORT_BYTES, validate_manual_multiframe_summary,
)
from scripts.development.review_mptrj_live_github_run import (
    API_ROOT, NoRedirect, _fetch_json, _unique_pairs,
)

WORKFLOW_NAME = "Phase 3 MPTrj 1MiB Multi-Frame Manual"
WORKFLOW_PATH = ".github/workflows/phase3-mptrj-multiframe-1mib-manual.yml"
ARTIFACT_NAME = "mptrj-multiframe-1mib-observation"
REPORT_FILE = "mptrj-multiframe-1mib.json"
MAX_ZIP_BYTES = 256 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class OneMiBReviewError(ValueError):
    """Run identity, bounded ZIP, original-prefix or science scope invalid."""


def _positive(value: object, maximum: int = 2**63 - 1) -> bool:
    return type(value) is int and 1 <= value <= maximum


def verify_1mib_zip(path: Path, *, expected_digest: str) -> dict:
    """Hash and inspect exactly the same bounded original ZIP byte snapshot."""
    path = Path(path)
    if (path.is_symlink() or not path.is_file()
            or not _positive(path.stat().st_size, MAX_ZIP_BYTES)
            or not isinstance(expected_digest, str)
            or not expected_digest.startswith("sha256:")
            or not SHA256.fullmatch(expected_digest[7:])):
        raise OneMiBReviewError("bounded nonsymlink ZIP and valid SHA256 required")
    with path.open("rb") as handle:
        raw_zip = handle.read(MAX_ZIP_BYTES + 1)
    if not 1 <= len(raw_zip) <= MAX_ZIP_BYTES:
        raise OneMiBReviewError("artifact ZIP grew or exceeds byte budget")
    zip_sha = sha256(raw_zip).hexdigest()
    if expected_digest != "sha256:" + zip_sha:
        raise OneMiBReviewError("GitHub artifact ZIP SHA256 mismatch")
    try:
        with ZipFile(io.BytesIO(raw_zip)) as archive:
            members = archive.infolist()
            if len(members) != 1 or members[0].filename != REPORT_FILE:
                raise OneMiBReviewError("exactly one approved metadata-only member required")
            member = members[0]
            if (member.is_dir()
                    or not _positive(member.file_size, MAX_REPORT_BYTES)
                    or (member.external_attr >> 16) & 0o170000 == 0o120000):
                raise OneMiBReviewError("unsafe or inflated report ZIP member")
            with archive.open(member) as fp:
                report_raw = fp.read(MAX_REPORT_BYTES + 1)
            if len(report_raw) != member.file_size or len(report_raw) > MAX_REPORT_BYTES:
                raise OneMiBReviewError("ZIP report exceeds fixed bytes")
    except (BadZipFile, EOFError, OSError, RuntimeError) as exc:
        raise OneMiBReviewError("corrupt or unsafe report ZIP") from exc
    report = json.loads(
        report_raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(
            OneMiBReviewError("nonfinite JSON number rejected")
        ),
    )
    validate_manual_multiframe_summary(report)
    return {
        "artifact_zip_sha256": zip_sha,
        "report_sha256": sha256(report_raw).hexdigest(),
        "report": report,
    }


def review_1mib_manual_run(*, run_id: int, expected_head_sha: str,
                           artifact_zip: Path, open_url=None) -> dict:
    """Check GitHub run, unique named artifact and saved ZIP with two pinned GETs."""
    if not _positive(run_id):
        raise OneMiBReviewError("positive bounded exact run ID required")
    if not isinstance(expected_head_sha, str) or not SHA40.fullmatch(expected_head_sha):
        raise OneMiBReviewError("exact lowercase 40-hex main SHA required")
    if open_url is None:
        import urllib.request
        open_url = urllib.request.build_opener(NoRedirect()).open
    run_url = f"{API_ROOT}/actions/runs/{run_id}"
    art_url = f"{run_url}/artifacts?name={ARTIFACT_NAME}&per_page=100"
    run = _fetch_json(run_url, open_url=open_url)
    arts = _fetch_json(art_url, open_url=open_url)
    if (not isinstance(run, dict)
            or type(run.get("id")) is not int or run["id"] != run_id
            or not isinstance(run.get("repository"), dict)
            or run["repository"].get("full_name") != "wt2018mask/Rhombus"
            or run.get("name") != WORKFLOW_NAME or run.get("path") != WORKFLOW_PATH
            or run.get("event") != "workflow_dispatch"
            or run.get("head_branch") != "main" or run.get("head_sha") != expected_head_sha
            or run.get("status") != "completed" or run.get("conclusion") != "success"
            or not _positive(run.get("run_attempt"), 1000)
            or run.get("html_url") != f"https://github.com/wt2018mask/Rhombus/actions/runs/{run_id}"):
        raise OneMiBReviewError("not exact successful operator-dispatched main workflow")
    if (not isinstance(arts, dict)
            or type(arts.get("total_count")) is not int or arts["total_count"] != 1
            or not isinstance(arts.get("artifacts"), list)
            or len(arts["artifacts"]) != 1):
        raise OneMiBReviewError("one uniquely named source-only artifact required")
    art = arts["artifacts"][0]
    if (not isinstance(art, dict) or art.get("name") != ARTIFACT_NAME
            or art.get("expired") is not False or not _positive(art.get("id"))
            or type(art.get("size_in_bytes")) is not int
            or art["size_in_bytes"] != Path(artifact_zip).stat().st_size
            or art.get("archive_download_url") != (
                f"{API_ROOT}/actions/artifacts/{art.get('id')}/zip")
            or not isinstance(art.get("workflow_run"), dict)
            or art["workflow_run"].get("id") != run_id
            or art["workflow_run"].get("head_sha") != expected_head_sha):
        raise OneMiBReviewError("artifact run identity, size or provenance mismatch")
    proof = verify_1mib_zip(artifact_zip, expected_digest=art.get("digest"))
    report = proof["report"]
    return {
        "schema_version": "rhombus-phase3-mptrj-1mib-github-live-review-v1",
        "status": "PUBLIC_RUN_AND_LOCAL_BOUNDED_PREFIX_METADATA_CONSISTENT_ONLY",
        "run_id": run_id,
        "run_attempt": run["run_attempt"],
        "artifact_id": art["id"],
        "head_sha": expected_head_sha,
        "artifact_zip_sha256": proof["artifact_zip_sha256"],
        "report_sha256": proof["report_sha256"],
        "first_256k_sha256": report["first_256k_sha256"],
        "prefix_1mib_sha256": report["prefix_1mib_sha256"],
        "complete_frame_count": report["complete_frame_count"],
        "range_operation_elapsed_ms": report["runtime_observation"]["range_operation_elapsed_ms"],
        "frame_inspection_elapsed_ms": report["runtime_observation"]["frame_inspection_elapsed_ms"],
        "api_get_count": 2,
        "github_signed_attestation_present": False,
        "full_mptrj_original_source_verified": False,
        "mace_mpa0_training_frames_attested": False,
        "full_runtime_estimate_authorized": False,
        "exposure_audit_authorized": False,
        "unseen_generalization_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-review", action="store_true")
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--expected-head-sha", required=True)
    parser.add_argument("--artifact-zip", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if not args.live_review:
            raise OneMiBReviewError("explicit --live-review required")
        record = review_1mib_manual_run(
            run_id=args.run_id, expected_head_sha=args.expected_head_sha,
            artifact_zip=args.artifact_zip,
        )
    except (OSError, ValueError, UnicodeError, TypeError, BadZipFile) as exc:
        print(f"MPTRJ_1MIB_REVIEW_FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(record, separators=(",", ":"), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
