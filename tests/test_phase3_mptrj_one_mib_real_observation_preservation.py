"""Offline real MPTrj 1MiB 16-frame archival evidence; no network/source GET.

Real GitHub Actions 37937653254 JSON-only ZIP is committed byte-exact.
The 1MiB prefix is NOT retained; frozen-256KiB matching and 16 frames
cannot establish full 12.2GB SHA or MACE-MPA-0 model training selection.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.development.review_mptrj_1mib_github_run import (
    OneMiBReviewError, verify_1mib_zip,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data/development/observations/mptrj-1mib-run-37937653254"
ARCHIVE_SHA = "5413d90c1f5087b831ceec1ad4707b21f3281db3bd84f98fa100766fc3f5678d"
MEMBER_SHA = "21545e8f7ff867868bfa6b99ed81d2ec7ba4f76b1b6860e892bda693413e539b"


def _saved():
    archive = EVIDENCE / "diagnostic.zip"
    manifest = json.loads((EVIDENCE / "manifest.json").read_text(encoding="utf-8"))
    receipt = json.loads((EVIDENCE / "review-receipt.json").read_text(encoding="utf-8"))
    return archive, manifest, receipt


def test_real_mptrj_one_mib_zip_source_only_and_histograms_replay_offline():
    archive, manifest, receipt = _saved()
    run = manifest["github_run"]
    art = manifest["github_artifact"]
    obs = manifest["observation"]
    scopes = manifest["scope"]
    assert (run["repository"], run["run_id"], run["run_attempt"]) == (
        "wt2018mask/Rhombus", 37937653254, 1
    )
    assert run["event"] == "workflow_dispatch"
    assert run["conclusion"] == "success"
    assert run["head_branch"] == "main"
    assert run["head_sha"] == "c5ccf2da207f9dc4874c436e46d32b4a31a1ad8f"
    assert art["id"] == 11619042244
    assert art["archive_path"] == str(archive.relative_to(ROOT))
    assert art["archive_size_bytes"] == archive.stat().st_size == 1120
    assert art["archive_sha256"] == ARCHIVE_SHA == sha256(archive.read_bytes()).hexdigest()
    assert art["api_digest"] == "sha256:" + ARCHIVE_SHA
    result = verify_1mib_zip(archive, expected_digest=art["api_digest"])
    report = result["report"]
    assert result["report_sha256"] == MEMBER_SHA == art["member_sha256"]
    with ZipFile(archive) as z:
        assert z.namelist() == [art["member_name"]]
        assert z.getinfo(art["member_name"]).file_size == art["member_size_bytes"] == 7246
        assert sha256(z.read(art["member_name"])).hexdigest() == MEMBER_SHA
    assert report["prefix_bytes"] == obs["prefix_bytes"] == 1048576
    assert report["prefix_1mib_sha256"] == obs["prefix_1mib_sha256"]
    assert report["first_256k_sha256"] == obs["frozen_first_256k_sha256"]
    assert report["source_total_bytes_declared"] == obs["source_total_bytes_declared"]
    assert report["complete_frame_count"] == obs["complete_frame_count"] == 16
    assert Counter(x["material_id"] for x in report["complete_frames"]) == obs["material_frame_counts"]
    for frame in report["complete_frames"]:
        assert frame["site_count"] == obs["site_count_by_material"][frame["material_id"]]
        assert all(frame["energy_fields_present"].values())
    assert report["tail_status"] == obs["tail_status"] == "FRAME_CAP_REACHED_TAIL_NOT_INSPECTED"
    assert report["runtime_observation"]["range_operation_elapsed_ms"] == obs["range_operation_elapsed_ms"] == 1862
    assert report["runtime_observation"]["frame_inspection_elapsed_ms"] == obs["frame_inspection_elapsed_ms"] == 11
    assert receipt["artifact_zip_sha256"] == ARCHIVE_SHA
    assert receipt["report_sha256"] == MEMBER_SHA
    assert receipt["head_sha"] == run["head_sha"]
    assert receipt["run_id"] == run["run_id"] and receipt["artifact_id"] == art["id"]
    assert receipt["complete_frame_count"] == report["complete_frame_count"]
    assert receipt["first_256k_sha256"] == report["first_256k_sha256"]
    assert scopes["github_api_run_and_archive_metadata_consistent"] is True
    assert scopes["archived_zip_digest_matches_api"] is True
    assert scopes["frozen_256k_prefix_sha_matches_real_record"] is True
    for name, flag in scopes.items():
        if name in (
            "github_api_run_and_archive_metadata_consistent",
            "archived_zip_digest_matches_api", "frozen_256k_prefix_sha_matches_real_record",
            "complete_frames_within_capped_prefix",
        ):
            continue
        assert flag is False, name
    for key in (
        "github_signed_attestation_present", "full_mptrj_original_source_verified",
        "mace_mpa0_training_frames_attested", "full_runtime_estimate_authorized",
        "exposure_audit_authorized", "unseen_generalization_authorized",
    ):
        assert receipt[key] is False
    assert not list(EVIDENCE.glob("*.bin")) and not list(EVIDENCE.glob("*.gz"))


def test_real_mptrj_one_mib_archived_zip_corruption_fails_closed(tmp_path):
    archive, manifest, _ = _saved()
    original = archive.read_bytes()
    damaged = tmp_path / "damaged.zip"
    damaged.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(OneMiBReviewError, match="SHA256"):
        verify_1mib_zip(damaged, expected_digest=manifest["github_artifact"]["api_digest"])


def test_real_mptrj_one_mib_manifest_claims_cannot_be_promoted():
    _, manifest, receipt = _saved()
    assert manifest["scope"]["full_mptrj_frame_population_verified"] is False
    assert manifest["scope"]["mace_mpa0_checkpoint_training_membership_attested"] is False
    assert receipt["full_runtime_estimate_authorized"] is False
    assert manifest["observation"]["source_total_bytes_declared"] > (
        manifest["observation"]["prefix_bytes"] * 1000
    )
