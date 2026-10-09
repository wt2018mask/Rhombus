"""Opt-in WBM v2 GitHub run↔ZIP evidence consistency review, no original WBM GET.

Only two exact public GitHub REST GETs (run + named artifact metadata).
The artifact ZIP is a caller-supplied local file, never downloaded here.
Public GitHub API metadata and a matching ZIP digest are not cryptographic
signed attestations or independent re-performance of scientific calculations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import io
import re
import sys
from zipfile import ZipFile, BadZipFile

from rhombus.domain.mptrj_source_overlap import WBM_COUNT, WBM_SHA256
from rhombus.domain.structure_protocols import CANDIDATE_FINGERPRINT_PROTOCOL_ID
from scripts.development.review_mptrj_live_github_run import (
    API_ROOT, _fetch_json, NoRedirect,
)

ARTIFACT_NAME = "phase3-wbm-v2-original-source-profile"
REPORT_FILE_NAME = "wbm-v2-original-source-profile.json"
WORKFLOW_PATH = ".github/workflows/phase3-wbm-v2-original-profile-manual.yml"
WORKFLOW_NAME = "Phase 3 WBM v2 Original Source Profile (Manual)"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_ZIP_BYTES = 512 * 1024
MAX_REPORT_BYTES = 64 * 1024


class WBMProfileReviewError(ValueError):
    """Invalid source identity, scientific scope, or run↔artifact evidence."""


def _json_pairs(pairs):
    record = {}
    for key, val in pairs:
        if key in record:
            raise WBMProfileReviewError("duplicate JSON field in profile evidence")
        record[key] = val
    return record


def _positive_int(value, *, maximum=10**18):
    return type(value) is int and 1 <= value <= maximum


def _histogram_moments(payload: dict, field: str) -> tuple[int, int, int, int]:
    """Reconstruct bucket count, total rows, largest size, and sum of squares.

    This is bounded summary validation, not original structure recomputation.
    """
    hist = payload.get(field)
    if not isinstance(hist, dict) or not 1 <= len(hist) <= 1024:
        raise WBMProfileReviewError("bounded WBM bucket histogram required")
    n_buckets = n_rows = pair_proxy = largest = 0
    for text_size, frequency in hist.items():
        if (not isinstance(text_size, str)
                or not text_size.isascii()
                or not text_size.isdecimal()
                or len(text_size) > len(str(WBM_COUNT))
                or not _positive_int(frequency, maximum=WBM_COUNT)):
            raise WBMProfileReviewError("invalid WBM bucket histogram entry")
        size = int(text_size)
        if not 1 <= size <= WBM_COUNT or str(size) != text_size:
            raise WBMProfileReviewError("noncanonical WBM histogram size")
        n_buckets += frequency
        n_rows += size * frequency
        pair_proxy += size * size * frequency
        largest = max(largest, size)
        if n_buckets > WBM_COUNT or n_rows > WBM_COUNT:
            raise WBMProfileReviewError("WBM bucket histogram exceeds frozen rows")
    return n_buckets, n_rows, largest, pair_proxy


def validate_profile_report(payload: dict) -> dict:
    """All measured numbers are source-bound *bucket proxies*, never model proof."""
    if not isinstance(payload, dict):
        raise WBMProfileReviewError("WBM v2 profile JSON object required")
    if (payload.get("schema_version")
            != "rhombus-phase3-original-wbm-v2-direct-candidate-profile-v2"
            or payload.get("status")
            != "ORIGINAL_WBM_BYTES_VERIFIED_INDEX_FREE_RESOURCE_PROXY_ONLY"
            or payload.get("wbm_original_gzip_sha256") != WBM_SHA256
            or payload.get("wbm_initial_structure_count") != WBM_COUNT
            or payload.get("candidate_fingerprint_protocol_id")
            != CANDIDATE_FINGERPRINT_PROTOCOL_ID):
        raise WBMProfileReviewError("original WBM source identity/protocol invalid")
    if not all(payload.get(key) is False for key in (
        "mptrj_runtime_estimate_authorized",
        "salex_full_runtime_estimate_authorized",
        "full_source_transfer_authorized",
        "exact_mace_mpa0_training_selection_attested",
        "unseen_generalization_authorized",
    )):
        raise WBMProfileReviewError("WBM source-only profile promotes scientific claims")
    fields = (
        "wbm_original_gzip_bytes", "wbm_decompressed_jsonl_bytes",
        "v2_composition_bucket_count",
        "v1_composition_sitecount_subbucket_count",
        "v2_largest_composition_bucket_targets",
        "v1_largest_composition_sitecount_subbucket_targets",
        "v2_index_only_pair_proxy", "v1_index_only_pair_proxy",
    )
    if not all(_positive_int(payload.get(k), maximum=10**15) for k in fields):
        raise WBMProfileReviewError("positive bounded integer WBM bucket counts required")
    mixed = payload.get("v2_buckets_with_multiple_sitecounts")
    if type(mixed) is not int or mixed < 0 or mixed > WBM_COUNT:
        raise WBMProfileReviewError("invalid mixed-sitecount composition buckets")
    n2 = payload["v2_composition_bucket_count"]
    n1 = payload["v1_composition_sitecount_subbucket_count"]
    m2 = payload["v2_largest_composition_bucket_targets"]
    m1 = payload["v1_largest_composition_sitecount_subbucket_targets"]
    proxy2 = payload["v2_index_only_pair_proxy"]
    proxy1 = payload["v1_index_only_pair_proxy"]
    if not (1 <= n2 <= n1 <= WBM_COUNT
            and 1 <= m1 <= m2 <= WBM_COUNT
            and 1 <= proxy1 <= proxy2 <= WBM_COUNT**2
            and proxy1 >= WBM_COUNT and proxy2 >= WBM_COUNT
            and mixed <= n2 and n1 >= n2 + mixed
            and proxy2 >= m2 * m2 + (WBM_COUNT - m2)
            and proxy1 >= m1 * m1 + (WBM_COUNT - m1)
            and n2 * m2 >= WBM_COUNT
            and n1 * m1 >= WBM_COUNT):
        raise WBMProfileReviewError("WBM profile arithmetic is impossible")
    if _histogram_moments(
        payload, "v2_composition_bucket_size_histogram"
    ) != (n2, WBM_COUNT, m2, proxy2):
        raise WBMProfileReviewError("v2 bucket histogram contradicts aggregate profile")
    if _histogram_moments(
        payload, "v1_composition_sitecount_subbucket_size_histogram"
    ) != (n1, WBM_COUNT, m1, proxy1):
        raise WBMProfileReviewError("v1 bucket histogram contradicts aggregate profile")
    if not isinstance(payload.get("wbm_original_gzip_bytes"), int):
        raise WBMProfileReviewError("WBM source byte count absent")
    return payload


def _read_bounded_zip_snapshot(path: Path) -> bytes:
    """Bound the actual read even if the file grows after its stat preflight.

    Digest and ZipFile later consume exactly this one in-memory byte snapshot.
    This avoids a Path.read_bytes() allocation proportional to a concurrently
    replaced or enlarged file. Preflight alone is not a memory budget.
    """
    with path.open("rb") as handle:
        data = handle.read(MAX_ZIP_BYTES + 1)
    if not 1 <= len(data) <= MAX_ZIP_BYTES:
        raise WBMProfileReviewError("artifact ZIP changed or exceeds bounded byte budget")
    return data


def verify_report_zip(path: Path, *, expected_digest: str) -> dict:
    """ZIP is bounded and must contain exactly one metadata-only JSON file."""
    path = Path(path)
    if (path.is_symlink() or not path.is_file()
            or not _positive_int(path.stat().st_size, maximum=MAX_ZIP_BYTES)
            or not isinstance(expected_digest, str)
            or not expected_digest.startswith("sha256:")
            or not SHA256.fullmatch(expected_digest[7:])):
        raise WBMProfileReviewError("bounded nonsymlink artifact ZIP + SHA256 required")
    zip_bytes = _read_bounded_zip_snapshot(path)
    archive_hash = hashlib.sha256(zip_bytes).hexdigest()
    if "sha256:" + archive_hash != expected_digest:
        raise WBMProfileReviewError("GitHub artifact archive SHA256 mismatch")
    try:
        # Parse exactly the bounded bytes we hashed; never reopen this pathname.
        with ZipFile(io.BytesIO(zip_bytes)) as zf:
            infos = zf.infolist()
            if len(infos) != 1 or infos[0].filename != REPORT_FILE_NAME:
                raise WBMProfileReviewError("ZIP must contain exactly original WBM profile JSON")
            item = infos[0]
            if (item.is_dir() or item.file_size <= 0 or item.file_size > MAX_REPORT_BYTES
                    or (item.external_attr >> 16) & 0o170000 == 0o120000):
                raise WBMProfileReviewError("unsafe WBM ZIP member or inflated length")
            with zf.open(item) as fh:
                raw = fh.read(MAX_REPORT_BYTES + 1)
            if len(raw) != item.file_size or len(raw) > MAX_REPORT_BYTES:
                raise WBMProfileReviewError("WBM ZIP report exceeds bounded length")
    except (BadZipFile, EOFError, OSError, RuntimeError) as exc:
        raise WBMProfileReviewError("corrupted WBM profile artifact ZIP") from exc
    report = json.loads(
        raw.decode("utf-8"), object_pairs_hook=_json_pairs,
        parse_constant=lambda c: (_ for _ in ()).throw(
            WBMProfileReviewError("nonfinite JSON number rejected")
        ),
    )
    validate_profile_report(report)
    return {
        "artifact_zip_sha256": archive_hash,
        "profile_report_sha256": hashlib.sha256(raw).hexdigest(),
        "profile": report,
    }


def review_wbm_v2_manual_run(*, run_id: int, expected_head_sha: str,
                             artifact_zip: Path, open_url=None) -> dict:
    """Validate one exact manually dispatched run, artifact identity and report."""
    if not _positive_int(run_id, maximum=2**63 - 1):
        raise WBMProfileReviewError("bounded positive run ID required")
    if not isinstance(expected_head_sha, str) or not SHA40.fullmatch(expected_head_sha):
        raise WBMProfileReviewError("pinned 40-hex HEAD SHA required")
    if open_url is None:
        import urllib.request
        open_url = urllib.request.build_opener(NoRedirect()).open
    run_url = f"{API_ROOT}/actions/runs/{run_id}"
    artifact_url = f"{run_url}/artifacts?name={ARTIFACT_NAME}&per_page=100"
    run = _fetch_json(run_url, open_url=open_url)
    artifact_list = _fetch_json(artifact_url, open_url=open_url)
    if (not isinstance(run, dict)
            or run.get("id") != run_id or type(run.get("id")) is not int
            or run.get("repository", {}).get("full_name") != "wt2018mask/Rhombus"
            or run.get("name") != WORKFLOW_NAME or run.get("path") != WORKFLOW_PATH
            or run.get("event") != "workflow_dispatch"
            or run.get("head_branch") != "main"
            or run.get("head_sha") != expected_head_sha
            or run.get("status") != "completed"
            or run.get("conclusion") != "success"
            or not _positive_int(run.get("run_attempt"), maximum=1000)
            or run.get("html_url") != f"https://github.com/wt2018mask/Rhombus/actions/runs/{run_id}"):
        raise WBMProfileReviewError("not an exact successful manually approved main run")
    if (not isinstance(artifact_list, dict)
            or type(artifact_list.get("total_count")) is not int
            or artifact_list["total_count"] != 1
            or not isinstance(artifact_list.get("artifacts"), list)
            or len(artifact_list["artifacts"]) != 1):
        raise WBMProfileReviewError("one unique named WBM profile artifact required")
    art = artifact_list["artifacts"][0]
    if (not isinstance(art, dict)
            or art.get("name") != ARTIFACT_NAME
            or art.get("expired") is not False
            or not _positive_int(art.get("id"))
            or type(art.get("size_in_bytes")) is not int
            or art["size_in_bytes"] != artifact_zip.stat().st_size
            or art.get("archive_download_url") != (
                f"{API_ROOT}/actions/artifacts/{art.get('id')}/zip"
            )
            or not isinstance(art.get("workflow_run"), dict)
            or art["workflow_run"].get("id") != run_id
            or art["workflow_run"].get("head_sha") != expected_head_sha):
        raise WBMProfileReviewError("artifact identity/size not bound to selected run")
    proof = verify_report_zip(artifact_zip, expected_digest=art.get("digest"))
    profile = proof["profile"]
    return {
        "schema_version": "rhombus-phase3-wbm-v2-github-profile-rest-review-v1",
        "status": "SOURCE_ONLY_PUBLIC_GITHUB_RUN_AND_LOCAL_ZIP_CONSISTENCY_VERIFIED",
        "run_id": run_id,
        "run_attempt": run["run_attempt"],
        "artifact_id": art["id"],
        "head_sha": expected_head_sha,
        "artifact_zip_sha256": proof["artifact_zip_sha256"],
        "profile_report_sha256": proof["profile_report_sha256"],
        "wbm_original_gzip_sha256": WBM_SHA256,
        "wbm_initial_structure_count": WBM_COUNT,
        "v2_largest_composition_bucket_targets": profile["v2_largest_composition_bucket_targets"],
        "v1_largest_composition_sitecount_subbucket_targets": profile["v1_largest_composition_sitecount_subbucket_targets"],
        "v2_index_only_pair_proxy": profile["v2_index_only_pair_proxy"],
        "v1_index_only_pair_proxy": profile["v1_index_only_pair_proxy"],
        "github_signed_attestation_present": False,
        "source_recomputed_independently": False,
        "full_mptrj_source_verified": False,
        "exact_mace_mpa0_training_selection_attested": False,
        "unseen_generalization_authorized": False,
        "empirical_calibration_authorized": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-review", action="store_true")
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--expected-head-sha", required=True)
    parser.add_argument("--artifact-zip", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if not args.live_review:
            raise WBMProfileReviewError("explicit --live-review required for GitHub GET")
        result = review_wbm_v2_manual_run(
            run_id=args.run_id, expected_head_sha=args.expected_head_sha,
            artifact_zip=args.artifact_zip,
        )
    except (OSError, ValueError, UnicodeError, TypeError, BadZipFile) as exc:
        print(f"WBM_V2_PROFILE_EVIDENCE_FAIL_CLOSED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
