"""Local-only replay of archived WBM v2 run-review evidence."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.development import replay_wbm_v2_archived_profile as replay

HEAD_SHA = "a" * 40
RUN_ID = 1789


def _fixture(tmp_path: Path):
    n = replay.WBM_COUNT
    report = {
        "schema_version": "rhombus-phase3-original-wbm-v2-direct-candidate-profile-v1",
        "status": "ORIGINAL_WBM_BYTES_VERIFIED_INDEX_FREE_RESOURCE_PROXY_ONLY",
        "wbm_original_gzip_sha256": replay.WBM_SHA256,
        "wbm_original_gzip_bytes": 123,
        "wbm_decompressed_jsonl_bytes": 999,
        "wbm_initial_structure_count": n,
        "candidate_fingerprint_protocol_id":
            "rhombus-reduced-composition-candidate-fingerprint-v2",
        "v2_composition_bucket_count": 2,
        "v1_composition_sitecount_subbucket_count": 3,
        "v2_buckets_with_multiple_sitecounts": 1,
        "v2_largest_composition_bucket_targets": n - 2,
        "v1_largest_composition_sitecount_subbucket_targets": n - 2,
        "v2_index_only_pair_proxy": (n - 2)**2 + 4,
        "v1_index_only_pair_proxy": (n - 2)**2 + 2,
        "mptrj_runtime_estimate_authorized": False,
        "salex_full_runtime_estimate_authorized": False,
        "full_source_transfer_authorized": False,
        "exact_mace_mpa0_training_selection_attested": False,
        "unseen_generalization_authorized": False,
    }
    zip_path = tmp_path / "saved-archive.zip"
    raw_report = json.dumps(report, sort_keys=True).encode("utf-8")
    with ZipFile(zip_path, "w") as zf:
        zf.writestr("wbm-v2-original-source-profile.json", raw_report)
    receipt = {
        "schema_version": "rhombus-phase3-wbm-v2-github-profile-rest-review-v1",
        "status": "SOURCE_ONLY_PUBLIC_GITHUB_RUN_AND_LOCAL_ZIP_CONSISTENCY_VERIFIED",
        "run_id": RUN_ID,
        "run_attempt": 1,
        "artifact_id": 42,
        "head_sha": HEAD_SHA,
        "artifact_zip_sha256": sha256(zip_path.read_bytes()).hexdigest(),
        "profile_report_sha256": sha256(raw_report).hexdigest(),
        "wbm_original_gzip_sha256": replay.WBM_SHA256,
        "wbm_initial_structure_count": n,
        **{k: report[k] for k in replay.PROFILE_METRIC_FIELDS},
        **{k: False for k in replay.SCIENTIFIC_FALSE_FIELDS},
    }
    receipt_path = tmp_path / "saved-review.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return receipt_path, zip_path, receipt


def _verify(receipt_path, zip_path, *, run_id=RUN_ID, head_sha=HEAD_SHA):
    return replay.replay_archived_profile(
        receipt_path=receipt_path, artifact_zip=zip_path,
        run_id=run_id, expected_head_sha=head_sha,
    )


def test_valid_offline_replay_preserves_exact_bytes_and_scientific_limits(tmp_path):
    receipt_path, zip_path, receipt = _fixture(tmp_path)
    output = _verify(receipt_path, zip_path)
    assert output["status"] == "LOCAL_ARCHIVED_RECEIPT_AND_ZIP_CONSISTENCY_VERIFIED"
    assert output["archived_receipt_sha256"] == sha256(receipt_path.read_bytes()).hexdigest()
    assert output["artifact_zip_sha256"] == receipt["artifact_zip_sha256"]
    assert output["profile_report_sha256"] == receipt["profile_report_sha256"]
    assert output["v2_index_only_pair_proxy"] > output["v1_index_only_pair_proxy"]
    assert output["github_run_reauthenticated_offline"] is False
    assert output["original_wbm_recomputed_offline"] is False
    assert output["unseen_generalization_authorized"] is False


@pytest.mark.parametrize("field,replacement", [
    ("run_id", RUN_ID + 1),
    ("head_sha", "b" * 40),
    ("artifact_id", True),
    ("run_attempt", 0),
    ("wbm_initial_structure_count", True),
    ("wbm_original_gzip_sha256", "0" * 64),
    ("v2_index_only_pair_proxy", 1),
    ("profile_report_sha256", "0" * 64),
    ("github_signed_attestation_present", True),
    ("exact_mace_mpa0_training_selection_attested", True),
    ("schema_version", "forged"),
])
def test_fails_closed_on_swapped_or_promoted_receipt(tmp_path, field, replacement):
    receipt_path, zip_path, receipt = _fixture(tmp_path)
    receipt[field] = replacement
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(replay.WBMProfileReviewError):
        _verify(receipt_path, zip_path)


def test_wrong_expected_id_or_head_is_rejected(tmp_path):
    receipt_path, zip_path, _ = _fixture(tmp_path)
    with pytest.raises(replay.WBMProfileReviewError):
        _verify(receipt_path, zip_path, run_id=RUN_ID + 1)
    with pytest.raises(replay.WBMProfileReviewError):
        _verify(receipt_path, zip_path, head_sha="b" * 40)


def test_zip_change_after_saved_receipt_is_rejected(tmp_path):
    receipt_path, zip_path, _ = _fixture(tmp_path)
    with zip_path.open("ab") as fh:
        fh.write(b"change")
    with pytest.raises(replay.WBMProfileReviewError, match="SHA256 mismatch"):
        _verify(receipt_path, zip_path)


def test_unapproved_zip_member_is_rejected_even_if_receipt_digest_matches(tmp_path):
    receipt_path, zip_path, receipt = _fixture(tmp_path)
    with ZipFile(zip_path, "a") as zf:
        zf.writestr("original-data.jsonl", "should not be retained")
    receipt["artifact_zip_sha256"] = sha256(zip_path.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(replay.WBMProfileReviewError, match="exactly original"):
        _verify(receipt_path, zip_path)


@pytest.mark.parametrize("replacement", [
    '{"schema_version":"a","schema_version":"b"}',
    '{"run_id":NaN}',
    '[]',
    '{"unseen_generalization_authorized":true}',
])
def test_invalid_receipt_json_is_rejected(tmp_path, replacement):
    receipt_path, zip_path, _ = _fixture(tmp_path)
    receipt_path.write_text(replacement, encoding="utf-8")
    with pytest.raises((ValueError, TypeError)):
        _verify(receipt_path, zip_path)


def test_receipt_unknown_fields_and_oversize_are_rejected(tmp_path):
    receipt_path, zip_path, receipt = _fixture(tmp_path)
    receipt["new_model_truth"] = True
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(replay.WBMProfileReviewError, match="schema"):
        _verify(receipt_path, zip_path)
    receipt_path.write_bytes(b" " * (replay.MAX_RECEIPT_BYTES + 1))
    with pytest.raises(replay.WBMProfileReviewError, match="bounded"):
        _verify(receipt_path, zip_path)


def test_symlink_receipt_and_zip_are_rejected(tmp_path):
    receipt_path, zip_path, _ = _fixture(tmp_path)
    receipt_link = tmp_path / "receipt-link"
    zip_link = tmp_path / "zip-link"
    receipt_link.symlink_to(receipt_path)
    zip_link.symlink_to(zip_path)
    with pytest.raises(replay.WBMProfileReviewError, match="nonsymlink"):
        _verify(receipt_link, zip_path)
    with pytest.raises(replay.WBMProfileReviewError, match="nonsymlink"):
        _verify(receipt_path, zip_link)


def test_cli_failure_does_not_print_success_receipt(tmp_path, capsys):
    receipt_path, zip_path, _ = _fixture(tmp_path)
    args = [
        "--review-receipt", str(receipt_path), "--artifact-zip", str(zip_path),
        "--run-id", str(RUN_ID), "--expected-head-sha", HEAD_SHA,
    ]
    assert replay.main(args) == 0
    assert json.loads(capsys.readouterr().out)["run_id"] == RUN_ID
    assert replay.main(args[:-1] + ["b" * 40]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "FAIL_CLOSED" in captured.err
