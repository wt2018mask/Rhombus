"""Replay a previously saved WBM v2 GitHub review receipt and ZIP offline.

This checks two caller-supplied local files against one another, NOT the
authenticity of a GitHub run, independent WBM source bytes or model training.
No network, workflow dispatch, file writes, or expensive original-source work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from rhombus.domain.mptrj_source_overlap import WBM_COUNT, WBM_SHA256
from scripts.development.review_wbm_v2_github_profile import (
    SHA40, SHA256, WBMProfileReviewError, _json_pairs, _positive_int,
    verify_report_zip,
)

MAX_RECEIPT_BYTES = 32 * 1024
SCIENTIFIC_FALSE_FIELDS = (
    "github_signed_attestation_present",
    "source_recomputed_independently",
    "full_mptrj_source_verified",
    "exact_mace_mpa0_training_selection_attested",
    "unseen_generalization_authorized",
    "empirical_calibration_authorized",
)
PROFILE_METRIC_FIELDS = (
    "v2_largest_composition_bucket_targets",
    "v1_largest_composition_sitecount_subbucket_targets",
    "v2_index_only_pair_proxy",
    "v1_index_only_pair_proxy",
)
RECEIPT_FIELDS = {
    "schema_version", "status", "run_id", "run_attempt", "artifact_id",
    "head_sha", "artifact_zip_sha256", "profile_report_sha256",
    "wbm_original_gzip_sha256", "wbm_initial_structure_count",
    *SCIENTIFIC_FALSE_FIELDS, *PROFILE_METRIC_FIELDS,
}


def replay_archived_profile(*, receipt_path: Path, artifact_zip: Path,
                            run_id: int, expected_head_sha: str) -> dict:
    """Fail closed on local receipt/ZIP disagreement, preserve claim limits."""
    if not _positive_int(run_id, maximum=2**63 - 1):
        raise WBMProfileReviewError("positive pinned workflow run ID required")
    if not isinstance(expected_head_sha, str) or not SHA40.fullmatch(expected_head_sha):
        raise WBMProfileReviewError("exact 40-hex pinned main SHA required")
    receipt_path = Path(receipt_path)
    if (receipt_path.is_symlink() or not receipt_path.is_file()
            or not _positive_int(receipt_path.stat().st_size,
                                 maximum=MAX_RECEIPT_BYTES)):
        raise WBMProfileReviewError("bounded nonsymlink archived receipt required")

    raw_receipt = receipt_path.read_bytes()
    if len(raw_receipt) > MAX_RECEIPT_BYTES:
        raise WBMProfileReviewError("oversized archived receipt")
    receipt = json.loads(
        raw_receipt.decode("utf-8"), object_pairs_hook=_json_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(
            WBMProfileReviewError("nonfinite archived receipt JSON rejected")
        ),
    )
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
        raise WBMProfileReviewError("unexpected archived review receipt schema")
    if (receipt["schema_version"] != "rhombus-phase3-wbm-v2-github-profile-rest-review-v1"
            or receipt["status"]
            != "SOURCE_ONLY_PUBLIC_GITHUB_RUN_AND_LOCAL_ZIP_CONSISTENCY_VERIFIED"
            or type(receipt["run_id"]) is not int or receipt["run_id"] != run_id
            or not _positive_int(receipt["run_attempt"], maximum=1000)
            or not _positive_int(receipt["artifact_id"])
            or receipt["head_sha"] != expected_head_sha
            or receipt["wbm_original_gzip_sha256"] != WBM_SHA256
            or type(receipt["wbm_initial_structure_count"]) is not int
            or receipt["wbm_initial_structure_count"] != WBM_COUNT
            or not isinstance(receipt["artifact_zip_sha256"], str)
            or not SHA256.fullmatch(receipt["artifact_zip_sha256"])
            or not isinstance(receipt["profile_report_sha256"], str)
            or not SHA256.fullmatch(receipt["profile_report_sha256"])
            or any(receipt[field] is not False for field in SCIENTIFIC_FALSE_FIELDS)):
        raise WBMProfileReviewError("archived receipt identity or scope invalid")

    proof = verify_report_zip(
        Path(artifact_zip), expected_digest="sha256:" + receipt["artifact_zip_sha256"]
    )
    if (proof["profile_report_sha256"] != receipt["profile_report_sha256"]
            or any(type(receipt[field]) is not int
                   or receipt[field] != proof["profile"][field]
                   for field in PROFILE_METRIC_FIELDS)):
        raise WBMProfileReviewError("archived WBM profile differs from reviewed receipt")

    return {
        "schema_version": "rhombus-phase3-wbm-v2-offline-review-replay-v1",
        "status": "LOCAL_ARCHIVED_RECEIPT_AND_ZIP_CONSISTENCY_VERIFIED",
        "run_id": run_id,
        "run_attempt": receipt["run_attempt"],
        "artifact_id": receipt["artifact_id"],
        "head_sha": expected_head_sha,
        "archived_receipt_sha256": hashlib.sha256(raw_receipt).hexdigest(),
        "artifact_zip_sha256": proof["artifact_zip_sha256"],
        "profile_report_sha256": proof["profile_report_sha256"],
        "wbm_original_gzip_sha256": WBM_SHA256,
        "wbm_initial_structure_count": WBM_COUNT,
        **{field: proof["profile"][field] for field in PROFILE_METRIC_FIELDS},
        "github_run_reauthenticated_offline": False,
        "original_wbm_recomputed_offline": False,
        "exact_mace_mpa0_training_selection_attested": False,
        "unseen_generalization_authorized": False,
        "empirical_calibration_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-receipt", type=Path, required=True)
    parser.add_argument("--artifact-zip", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--expected-head-sha", required=True)
    args = parser.parse_args(argv)
    try:
        output = replay_archived_profile(
            receipt_path=args.review_receipt, artifact_zip=args.artifact_zip,
            run_id=args.run_id, expected_head_sha=args.expected_head_sha,
        )
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(f"WBM_V2_ARCHIVED_EVIDENCE_REPLAY_FAIL_CLOSED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
