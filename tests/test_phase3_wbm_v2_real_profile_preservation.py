"""Replay real, byte-exact WBM v2 original-source profile without network.

The 882-byte GitHub artifact ZIP, its 1,608-byte JSON member and locally
reviewed run/archive metadata are retained. No original WBM gzip, Figshare
request, model training audit or expensive Kaggle work is performed here.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest

from scripts.development.review_wbm_v2_github_profile import (
    WBMProfileReviewError, validate_profile_report, verify_report_zip,
)
from scripts.development.replay_wbm_v2_archived_profile import replay_archived_profile

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data/development/observations/wbm-v2-run-37929699171"
RUN_ID = 37929699171
RUN_SHA = "65376c8825afc4b4cb0b4a7958ad09f6bd3218fb"
ZIP_SHA = "2736020aeb21c3a99158aca2bafc3305cae487c8fded00528eb3308f292003a1"
REPORT_SHA = "26cf2141004f3e012d963c510b49a18e3f1965809b8cc4a2fa577b387418cc34"


def _paths():
    return (
        EVIDENCE / "manifest.json", EVIDENCE / "profile.zip",
        EVIDENCE / "wbm-v2-original-source-profile.json",
        EVIDENCE / "review-receipt.json",
    )


def test_real_wbm_v2_profile_archive_byte_identity_and_run_scope():
    manifest_path, archive, report_path, receipt_path = _paths()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    recorded = manifest["github_run"]
    artifact = manifest["github_artifact"]
    measured = manifest["measured_original_WBM_index_only_proxy"]
    scope = manifest["scope"]
    assert manifest["status"] == "REAL_WBM_V2_ORIGINAL_SOURCE_BUCKET_PROXY_VERIFIED_SOURCE_ONLY"
    assert recorded["repository"] == "wt2018mask/Rhombus"
    assert recorded["run_id"] == RUN_ID and recorded["run_attempt"] == 1
    assert recorded["head_sha"] == RUN_SHA and recorded["head_branch"] == "main"
    assert recorded["event"] == "workflow_dispatch" and recorded["conclusion"] == "success"
    assert artifact["id"] == 11615418696
    assert artifact["archive_path"] == str(archive.relative_to(ROOT))
    assert artifact["member_path"] == str(report_path.relative_to(ROOT))
    assert artifact["review_receipt_path"] == str(receipt_path.relative_to(ROOT))
    assert artifact["archive_size_bytes"] == archive.stat().st_size == 882
    assert artifact["member_size_bytes"] == report_path.stat().st_size == 1608
    assert artifact["archive_sha256"] == ZIP_SHA == sha256(archive.read_bytes()).hexdigest()
    assert artifact["api_digest"] == "sha256:" + ZIP_SHA
    assert artifact["member_sha256"] == REPORT_SHA == sha256(report_path.read_bytes()).hexdigest()
    assert artifact["member_name"] == "wbm-v2-original-source-profile.json"

    import zipfile
    with zipfile.ZipFile(archive) as zip_file:
        assert zip_file.namelist() == [artifact["member_name"]]
        assert zip_file.read(artifact["member_name"]) == report_path.read_bytes()
    proof = verify_report_zip(archive, expected_digest=artifact["api_digest"])
    report = validate_profile_report(json.loads(report_path.read_text(encoding="utf-8")))
    assert proof["profile"] == report
    assert proof["profile_report_sha256"] == REPORT_SHA
    for key, expected in (
        ("v1_composition_sitecount_subbucket_count", 195549),
        ("v2_composition_bucket_count", 168150),
        ("v2_buckets_with_multiple_sitecounts", 21700),
        ("v1_largest_composition_sitecount_subbucket_targets", 14),
        ("v2_largest_composition_bucket_targets", 22),
        ("v1_index_only_pair_proxy", 433549),
        ("v2_index_only_pair_proxy", 596225),
        ("wbm_initial_structure_count", 256963),
    ):
        assert report[key] == expected
    assert measured["v2_index_only_pair_proxy"] == report["v2_index_only_pair_proxy"]
    assert measured["v1_index_only_pair_proxy"] == report["v1_index_only_pair_proxy"]
    assert measured["v2_largest_composition_bucket"] == report["v2_largest_composition_bucket_targets"]
    assert measured["total_wbm_original_initial_structures"] == report["wbm_initial_structure_count"]
    assert scope["github_run_and_archive_metadata_verified"] is True
    assert scope["source_only_original_wbm_hash_count_measured_by_workflow"] is True
    assert scope["original_WBM_raw_source_preserved"] is False
    for key, value in scope.items():
        if key not in ("github_run_and_archive_metadata_verified",
                       "source_only_original_wbm_hash_count_measured_by_workflow"):
            assert value is False, key
    assert not any(EVIDENCE.glob("*.gz"))


def test_real_wbm_v2_source_only_receipt_replays_against_archived_zip():
    _, archive, _, receipt_path = _paths()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["run_id"] == RUN_ID and receipt["head_sha"] == RUN_SHA
    assert receipt["artifact_id"] == 11615418696
    assert receipt["artifact_zip_sha256"] == ZIP_SHA
    assert receipt["profile_report_sha256"] == REPORT_SHA
    replay = replay_archived_profile(
        receipt_path=receipt_path, artifact_zip=archive,
        run_id=RUN_ID, expected_head_sha=RUN_SHA,
    )
    assert replay["status"] == "LOCAL_ARCHIVED_RECEIPT_AND_ZIP_CONSISTENCY_VERIFIED"
    assert replay["v2_index_only_pair_proxy"] == 596225
    assert replay["v1_index_only_pair_proxy"] == 433549
    assert replay["original_wbm_recomputed_offline"] is False
    assert replay["github_run_reauthenticated_offline"] is False
    assert replay["unseen_generalization_authorized"] is False


def test_real_wbm_v2_archived_artifact_tampering_fails_closed(tmp_path):
    _, archive, _, receipt = _paths()
    copy = tmp_path / "tampered.zip"
    raw = archive.read_bytes()
    copy.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    with pytest.raises(WBMProfileReviewError, match="SHA256 mismatch"):
        replay_archived_profile(
            receipt_path=receipt, artifact_zip=copy,
            run_id=RUN_ID, expected_head_sha=RUN_SHA,
        )
    copied = tmp_path / "verified.zip"
    shutil.copy2(archive, copied)
    altered_receipt = tmp_path / "altered-review.json"
    values = json.loads(receipt.read_text(encoding="utf-8"))
    values["unseen_generalization_authorized"] = True
    altered_receipt.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(WBMProfileReviewError, match="scope"):
        replay_archived_profile(
            receipt_path=altered_receipt, artifact_zip=copied,
            run_id=RUN_ID, expected_head_sha=RUN_SHA,
        )
