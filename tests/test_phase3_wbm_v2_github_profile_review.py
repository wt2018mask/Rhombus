"""Offline fake-HTTPS tests for manually approved WBM v2 profile evidence."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.development import review_wbm_v2_github_profile as module

RUN_ID = 1789
HEAD_SHA = "a" * 40
ART_ID = 42


class Response:
    def __init__(self, url, data):
        self.status = 200
        self.url = url
        self.data = data
        self.headers = {
            "Content-Type": "application/json",
            "Content-Encoding": "identity",
            "Content-Length": str(len(data)),
        }
    def geturl(self): return self.url
    def read(self, n): return self.data[:n]
    def __enter__(self): return self
    def __exit__(self, *_): return False


def _evidence(tmp_path: Path):
    report = {
        "schema_version": "rhombus-phase3-original-wbm-v2-direct-candidate-profile-v2",
        "status": "ORIGINAL_WBM_BYTES_VERIFIED_INDEX_FREE_RESOURCE_PROXY_ONLY",
        "wbm_original_gzip_sha256": module.WBM_SHA256,
        "wbm_original_gzip_bytes": 123,
        "wbm_decompressed_jsonl_bytes": 999,
        "wbm_initial_structure_count": module.WBM_COUNT,
        "candidate_fingerprint_protocol_id": module.CANDIDATE_FINGERPRINT_PROTOCOL_ID,
        "v2_composition_bucket_count": 2,
        "v1_composition_sitecount_subbucket_count": 3,
        "v2_buckets_with_multiple_sitecounts": 1,
        "v2_largest_composition_bucket_targets": module.WBM_COUNT - 2,
        "v1_largest_composition_sitecount_subbucket_targets": module.WBM_COUNT - 2,
        "v2_index_only_pair_proxy": (module.WBM_COUNT - 2)**2 + 4,
        "v1_index_only_pair_proxy": (module.WBM_COUNT - 2)**2 + 2,
        "v2_composition_bucket_size_histogram": {
            "2": 1, str(module.WBM_COUNT - 2): 1,
        },
        "v1_composition_sitecount_subbucket_size_histogram": {
            "1": 2, str(module.WBM_COUNT - 2): 1,
        },
        "mptrj_runtime_estimate_authorized": False,
        "salex_full_runtime_estimate_authorized": False,
        "full_source_transfer_authorized": False,
        "exact_mace_mpa0_training_selection_attested": False,
        "unseen_generalization_authorized": False,
    }
    # one composition bucket has N-2; other has two targets with different
    # original site counts: v2 = (N-2)^2+4, legacy v1=(N-2)^2+1+1.
    zip_path = tmp_path / "profile.zip"
    with ZipFile(zip_path, "w") as zf:
        zf.writestr(module.REPORT_FILE_NAME, json.dumps(report))
    raw = zip_path.read_bytes()
    run = {
        "id": RUN_ID, "run_attempt": 1, "event": "workflow_dispatch",
        "name": module.WORKFLOW_NAME, "path": module.WORKFLOW_PATH,
        "head_branch": "main", "head_sha": HEAD_SHA,
        "status": "completed", "conclusion": "success",
        "html_url": "https://github.com/wt2018mask/Rhombus/actions/runs/" + str(RUN_ID),
        "repository": {"full_name": "wt2018mask/Rhombus"},
    }
    art = {
        "total_count": 1,
        "artifacts": [{
            "id": ART_ID, "name": module.ARTIFACT_NAME, "expired": False,
            "size_in_bytes": len(raw), "digest": "sha256:" + sha256(raw).hexdigest(),
            "archive_download_url": module.API_ROOT + "/actions/artifacts/" + str(ART_ID) + "/zip",
            "workflow_run": {"id": RUN_ID, "head_sha": HEAD_SHA},
        }],
    }
    return zip_path, report, run, art


def _get(run, artifacts):
    run_url = module.API_ROOT + "/actions/runs/" + str(RUN_ID)
    arts_url = run_url + "/artifacts?name=" + module.ARTIFACT_NAME + "&per_page=100"
    docs = {run_url: json.dumps(run).encode(), arts_url: json.dumps(artifacts).encode()}
    touched = []
    def opener(req, timeout):
        assert req.get_method() == "GET"
        assert timeout == 15
        assert req.full_url in docs
        touched.append(req.full_url)
        return Response(req.full_url, docs[req.full_url])
    return opener, touched


def test_pinned_two_get_run_and_artifact_complete():
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as dirname:
        zip_path, report, run, arts = _evidence(Path(dirname))
        opener, calls = _get(run, arts)
        result = module.review_wbm_v2_manual_run(
            run_id=RUN_ID, expected_head_sha=HEAD_SHA,
            artifact_zip=zip_path, open_url=opener)
        assert len(calls) == 2
        assert result["artifact_zip_sha256"] == sha256(zip_path.read_bytes()).hexdigest()
        assert result["v2_largest_composition_bucket_targets"] == module.WBM_COUNT - 2
        assert result["v2_index_only_pair_proxy"] > result["v1_index_only_pair_proxy"]
        assert all(v is False for k,v in result.items() if k in (
            "github_signed_attestation_present", "source_recomputed_independently",
            "exact_mace_mpa0_training_selection_attested",
            "unseen_generalization_authorized", "empirical_calibration_authorized",
        ))


@pytest.mark.parametrize(("field", "bad"), [
    ("event", "push"), ("head_branch", "worker/other"),
    ("head_sha", "f"*40), ("conclusion", "failure"),
    ("status", "in_progress"), ("path", ".github/workflows/other.yml"),
    ("name", "some other job"),
])
def test_reject_incorrect_run_metadata(tmp_path, field, bad):
    zip_path, _, run, arts = _evidence(tmp_path)
    run[field] = bad
    opener, _ = _get(run, arts)
    with pytest.raises(module.WBMProfileReviewError):
        module.review_wbm_v2_manual_run(
            run_id=RUN_ID, expected_head_sha=HEAD_SHA,
            artifact_zip=zip_path, open_url=opener)


def test_reject_zip_hash_swap_before_admitting_source_counts(tmp_path):
    zip_path, _, run, arts = _evidence(tmp_path)
    arts["artifacts"][0]["digest"] = "sha256:" + "0"*64
    opener, _ = _get(run, arts)
    with pytest.raises(module.WBMProfileReviewError, match="SHA256 mismatch"):
        module.review_wbm_v2_manual_run(
            run_id=RUN_ID, expected_head_sha=HEAD_SHA,
            artifact_zip=zip_path, open_url=opener)


def test_reject_extra_zip_member_even_with_matching_github_digest(tmp_path):
    zip_path, _, run, arts = _evidence(tmp_path)
    with ZipFile(zip_path, "a") as zf: zf.writestr("source-structures.jsonl.gz", b"forbidden")
    new_bytes = zip_path.read_bytes()
    arts["artifacts"][0]["digest"] = "sha256:" + sha256(new_bytes).hexdigest()
    arts["artifacts"][0]["size_in_bytes"] = len(new_bytes)
    opener, _ = _get(run, arts)
    with pytest.raises(module.WBMProfileReviewError, match="exactly"):
        module.review_wbm_v2_manual_run(
            run_id=RUN_ID, expected_head_sha=HEAD_SHA,
            artifact_zip=zip_path, open_url=opener)


def test_reject_source_only_claim_promotion_and_impossible_cost_numbers(tmp_path):
    zip_path, report, _, _ = _evidence(tmp_path)
    report["unseen_generalization_authorized"] = True
    with pytest.raises(module.WBMProfileReviewError, match="promotes"):
        module.validate_profile_report(report)
    report["unseen_generalization_authorized"] = False
    report["v2_index_only_pair_proxy"] = 1
    with pytest.raises(module.WBMProfileReviewError, match="arithmetic"):
        module.validate_profile_report(report)


def test_reject_boolean_count_or_duplicate_json_key_even_with_matching_zip_sha(tmp_path):
    zip_path, report, run, arts = _evidence(tmp_path)
    report["v2_composition_bucket_count"] = True
    with pytest.raises(module.WBMProfileReviewError, match="positive bounded"):
        module.validate_profile_report(report)
    payload = json.dumps(report).replace('"wbm_initial_structure_count": ',
                                          '"wbm_initial_structure_count": 256963, "wbm_initial_structure_count": ',1)
    with ZipFile(zip_path, "w") as zf: zf.writestr(module.REPORT_FILE_NAME,payload)
    new = zip_path.read_bytes()
    arts["artifacts"][0]["digest"] = "sha256:" + sha256(new).hexdigest()
    arts["artifacts"][0]["size_in_bytes"] = len(new)
    opener, _ = _get(run, arts)
    with pytest.raises(module.WBMProfileReviewError, match="duplicate"):
        module.review_wbm_v2_manual_run(
            run_id=RUN_ID, expected_head_sha=HEAD_SHA,
            artifact_zip=zip_path, open_url=opener)


def test_refuse_live_rest_without_explicit_cli_flag(tmp_path,capsys):
    path, *_ = _evidence(tmp_path)
    assert module.main([
        "--run-id", str(RUN_ID), "--expected-head-sha", HEAD_SHA,
        "--artifact-zip", str(path),
    ]) == 1
    assert "explicit --live-review" in capsys.readouterr().err


def test_reject_ambiguous_artifact_counts_without_unsafe_claim(tmp_path):
    zip_path, _, run, arts = _evidence(tmp_path)
    arts["total_count"] = 2
    opener, _ = _get(run, arts)
    with pytest.raises(module.WBMProfileReviewError, match="unique"):
        module.review_wbm_v2_manual_run(run_id=RUN_ID,expected_head_sha=HEAD_SHA,
                                        artifact_zip=zip_path,open_url=opener)



@pytest.mark.parametrize("field,changed", [
    ("v2_composition_bucket_size_histogram", {"1": module.WBM_COUNT}),
    ("v1_composition_sitecount_subbucket_size_histogram", {"1": module.WBM_COUNT}),
    ("v2_composition_bucket_size_histogram", {"01": module.WBM_COUNT}),
    ("v2_composition_bucket_size_histogram", {"1": True}),
    ("v2_composition_bucket_size_histogram", {}),
])
def test_reject_histogram_inconsistent_with_source_bucket_arithmetic(tmp_path, field, changed):
    zip_path, report, run, arts = _evidence(tmp_path)
    report[field] = changed
    with ZipFile(zip_path, "w") as zf:
        zf.writestr(module.REPORT_FILE_NAME, json.dumps(report))
    payload = zip_path.read_bytes()
    arts["artifacts"][0]["digest"] = "sha256:" + sha256(payload).hexdigest()
    arts["artifacts"][0]["size_in_bytes"] = len(payload)
    opener, _ = _get(run, arts)
    with pytest.raises(module.WBMProfileReviewError, match="histogram"):
        module.review_wbm_v2_manual_run(
            run_id=RUN_ID, expected_head_sha=HEAD_SHA,
            artifact_zip=zip_path, open_url=opener,
        )


def test_reject_missing_histogram_even_when_other_scalars_are_plausible(tmp_path):
    _, report, _, _ = _evidence(tmp_path)
    report.pop("v2_composition_bucket_size_histogram")
    with pytest.raises(module.WBMProfileReviewError, match="histogram"):
        module.validate_profile_report(report)



def test_zip_path_swap_after_digest_read_never_changes_verified_json(tmp_path, monkeypatch):
    """A new pathname target must not replace the JSON in the hashed ZIP bytes."""
    zip_path, report, _, _ = _evidence(tmp_path)
    original_bytes = zip_path.read_bytes()
    expected_digest = "sha256:" + sha256(original_bytes).hexdigest()

    # Both payloads are valid original-WBM *metadata*; only one is hashed.
    replacement = dict(report)
    replacement["wbm_decompressed_jsonl_bytes"] += 17
    alternate = tmp_path / "swapped.zip"
    with ZipFile(alternate, "w") as archive:
        archive.writestr(module.REPORT_FILE_NAME, json.dumps(replacement))
    actual_read = Path.read_bytes
    replaced = False

    def swap_after_read(path):
        nonlocal replaced
        original = actual_read(path)
        if path == zip_path and not replaced:
            alternate.replace(zip_path)
            replaced = True
        return original

    monkeypatch.setattr(Path, "read_bytes", swap_after_read)
    proof = module.verify_report_zip(zip_path, expected_digest=expected_digest)
    assert replaced
    assert proof["artifact_zip_sha256"] == sha256(original_bytes).hexdigest()
    assert proof["profile"]["wbm_decompressed_jsonl_bytes"] == report["wbm_decompressed_jsonl_bytes"]
    assert proof["profile"]["wbm_decompressed_jsonl_bytes"] != replacement["wbm_decompressed_jsonl_bytes"]


def test_zip_path_swap_to_invalid_archive_still_parses_hashed_snapshot(tmp_path, monkeypatch):
    zip_path, report, _, _ = _evidence(tmp_path)
    original_bytes = zip_path.read_bytes()
    expected_digest = "sha256:" + sha256(original_bytes).hexdigest()
    actual_read = Path.read_bytes
    exchanged = False

    def swap_to_corrupt(path):
        nonlocal exchanged
        original = actual_read(path)
        if path == zip_path and not exchanged:
            zip_path.write_bytes(b"not a valid ZIP")
            exchanged = True
        return original

    monkeypatch.setattr(Path, "read_bytes", swap_to_corrupt)
    proof = module.verify_report_zip(zip_path, expected_digest=expected_digest)
    assert exchanged
    assert proof["profile"]["wbm_initial_structure_count"] == module.WBM_COUNT
    assert proof["profile_report_sha256"] == sha256(
        json.dumps(report).encode("utf-8")
    ).hexdigest()
