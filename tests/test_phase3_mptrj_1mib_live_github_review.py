"""Offline fake GitHub REST contract for real MPTrj 1MiB evidence review."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.development import review_mptrj_1mib_github_run as m
from scripts.development.reobserve_mptrj_frozen_prefix import read_frozen_first_frame

RUN_ID = 456789
HEAD = "e" * 40


class Response:
    status = 200

    def __init__(self, url, raw):
        self.url = url
        self.raw = raw
        self.headers = {
            "Content-Type": "application/json",
            "Content-Encoding": "identity",
            "Content-Length": str(len(raw)),
        }

    def geturl(self):
        return self.url

    def read(self, maximum):
        return self.raw[:maximum]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def evidence(tmp_path: Path):
    first = read_frozen_first_frame()["observation"]
    frame = dict(first["first_frame_structure"])
    frame["source_locator"] = "/" + frame["material_id"] + "/" + frame["frame_id"]
    # Fixture intentionally describes only the one previously proven real frame.
    report = {
        "schema_version": "rhombus-phase3-mptrj-real-1mib-manual-frames-v2",
        "status": "ONE_MIB_FIRST_N_FRAMES_DIAGNOSTIC_ONLY",
        "source_file_id": 41619375,
        "source_total_bytes_declared": 12188168685,
        "prefix_bytes": 1048576,
        "first_256k_sha256": first["prefix_sha256"],
        "prefix_1mib_sha256": "b" * 64,
        "redirect_host": "cdn.example.org",
        "complete_frame_count": 1,
        "complete_frames": [frame],
        "tail_status": "TAIL_UNVERIFIED_TRUNCATED_OR_MALFORMED",
        "runtime_observation": {
            "range_operation_elapsed_ms": 1234,
            "frame_inspection_elapsed_ms": 567,
            "scope": "ONE_1MIB_PREFIX_ON_CURRENT_RUNNER_ONLY",
            "full_corpus_runtime_estimate_authorized": False,
        },
        **{k: False for k in (
            "raw_source_saved", "full_source_verified",
            "mace_mpa0_training_frames_attested", "execute_exposure_audit",
            "empirical_calibration_use", "unseen_generalization_claim",
        )},
    }
    archive = tmp_path / "sample.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr(m.REPORT_FILE, json.dumps(report, separators=(",", ":")))
    raw = archive.read_bytes()
    run = {
        "id": RUN_ID, "run_attempt": 1, "event": "workflow_dispatch",
        "name": m.WORKFLOW_NAME, "path": m.WORKFLOW_PATH,
        "head_branch": "main", "head_sha": HEAD, "status": "completed",
        "conclusion": "success",
        "html_url": f"https://github.com/wt2018mask/Rhombus/actions/runs/{RUN_ID}",
        "repository": {"full_name": "wt2018mask/Rhombus"},
    }
    artifact = {
        "total_count": 1, "artifacts": [{
            "id": 987, "name": m.ARTIFACT_NAME, "expired": False,
            "size_in_bytes": len(raw), "digest": "sha256:" + sha256(raw).hexdigest(),
            "archive_download_url": m.API_ROOT + "/actions/artifacts/987/zip",
            "workflow_run": {"id": RUN_ID, "head_sha": HEAD},
        }],
    }
    return archive, report, run, artifact


def openers(run, artifacts):
    urls = [
        f"{m.API_ROOT}/actions/runs/{RUN_ID}",
        f"{m.API_ROOT}/actions/runs/{RUN_ID}/artifacts?name={m.ARTIFACT_NAME}&per_page=100",
    ]
    raw = [json.dumps(run).encode(), json.dumps(artifacts).encode()]
    seen = []

    def get(req, timeout):
        assert req.get_method() == "GET" and timeout == 15
        assert req.full_url in urls
        seen.append(req.full_url)
        k = urls.index(req.full_url)
        return Response(req.full_url, raw[k])

    return get, seen


def check(archive, run, artifacts):
    opener, seen = openers(run, artifacts)
    result = m.review_1mib_manual_run(
        run_id=RUN_ID, expected_head_sha=HEAD,
        artifact_zip=archive, open_url=opener,
    )
    return result, seen


def test_exact_two_readonly_requests_and_frozen_first_prefix(tmp_path):
    archive, report, run, arts = evidence(tmp_path)
    before = sorted(tmp_path.iterdir())
    result, seen = check(archive, run, arts)
    assert len(seen) == 2
    assert result["complete_frame_count"] == 1
    assert result["first_256k_sha256"] == report["first_256k_sha256"]
    assert result["prefix_1mib_sha256"] == "b" * 64
    assert result["artifact_zip_sha256"] == sha256(archive.read_bytes()).hexdigest()
    assert result["range_operation_elapsed_ms"] == 1234
    assert result["frame_inspection_elapsed_ms"] == 567
    assert all(value is False for key, value in result.items() if key in (
        "github_signed_attestation_present", "full_mptrj_original_source_verified",
        "mace_mpa0_training_frames_attested", "full_runtime_estimate_authorized",
        "exposure_audit_authorized", "unseen_generalization_authorized",
    ))
    assert sorted(tmp_path.iterdir()) == before


@pytest.mark.parametrize("field,bad", [
    ("id", RUN_ID + 1),
    ("event", "push"), ("name", "wrong"),
    ("path", ".github/workflows/untrusted.yml"),
    ("head_branch", "worker/other"), ("head_sha", "a"*40),
    ("status", "in_progress"), ("conclusion", "failure"),
    ("run_attempt", True),
])
def test_wrong_run_identity_never_qualifies(tmp_path, field, bad):
    archive, _, run, arts = evidence(tmp_path)
    run[field] = bad
    with pytest.raises(m.OneMiBReviewError):
        check(archive, run, arts)


@pytest.mark.parametrize("field,bad", [
    ("total_count", 2),
    ("total_count", True),
])
def test_ambiguous_artifact_never_qualifies(tmp_path, field, bad):
    archive, _, run, arts = evidence(tmp_path)
    arts[field] = bad
    with pytest.raises(m.OneMiBReviewError):
        check(archive, run, arts)


def test_swapped_zip_checksum_fails(tmp_path):
    archive, _, run, arts = evidence(tmp_path)
    arts["artifacts"][0]["digest"] = "sha256:" + "0"*64
    with pytest.raises(m.OneMiBReviewError, match="SHA256"):
        check(archive, run, arts)


def test_extra_raw_source_zip_member_even_with_matching_artifact_digest_rejected(tmp_path):
    archive, _, run, arts = evidence(tmp_path)
    with ZipFile(archive, "a") as zf:
        zf.writestr("full-mptrj-original.bin", b"forbidden")
    raw = archive.read_bytes()
    arts["artifacts"][0]["size_in_bytes"] = len(raw)
    arts["artifacts"][0]["digest"] = "sha256:" + sha256(raw).hexdigest()
    with pytest.raises(m.OneMiBReviewError, match="exactly one"):
        check(archive, run, arts)


def test_promoted_training_claim_in_original_report_rejected(tmp_path):
    archive, report, run, arts = evidence(tmp_path)
    report["mace_mpa0_training_frames_attested"] = True
    with ZipFile(archive, "w") as zf:
        zf.writestr(m.REPORT_FILE, json.dumps(report))
    raw = archive.read_bytes()
    arts["artifacts"][0]["digest"] = "sha256:" + sha256(raw).hexdigest()
    arts["artifacts"][0]["size_in_bytes"] = len(raw)
    with pytest.raises(ValueError, match="unsupported"):
        check(archive, run, arts)


def test_misreported_complete_frame_count_rejected(tmp_path):
    archive, report, run, arts = evidence(tmp_path)
    report["complete_frame_count"] = 20
    with ZipFile(archive, "w") as zf:
        zf.writestr(m.REPORT_FILE, json.dumps(report))
    raw = archive.read_bytes()
    arts["artifacts"][0]["digest"] = "sha256:" + sha256(raw).hexdigest()
    arts["artifacts"][0]["size_in_bytes"] = len(raw)
    with pytest.raises(ValueError, match="count"):
        check(archive, run, arts)


def test_duplicate_json_keys_and_nonfinite_rejected(tmp_path):
    archive, report, run, arts = evidence(tmp_path)
    raw_report = json.dumps(report).replace(
        '"prefix_bytes": 1048576', '"prefix_bytes": 1048576, "prefix_bytes": 1048576', 1
    )
    with ZipFile(archive, "w") as zf:
        zf.writestr(m.REPORT_FILE, raw_report)
    data = archive.read_bytes()
    arts["artifacts"][0]["digest"] = "sha256:" + sha256(data).hexdigest()
    arts["artifacts"][0]["size_in_bytes"] = len(data)
    with pytest.raises(ValueError, match="duplicate"):
        check(archive, run, arts)


def test_default_cli_refuses_any_remote_get(tmp_path, capsys):
    archive, *_ = evidence(tmp_path)
    assert m.main([
        "--run-id", str(RUN_ID),
        "--expected-head-sha", HEAD,
        "--artifact-zip", str(archive),
    ]) == 1
    assert "explicit --live-review" in capsys.readouterr().err


def test_large_zip_preflight_rejects_before_api(tmp_path):
    zip_path = tmp_path / "large.zip"
    zip_path.write_bytes(b"x" * (m.MAX_ZIP_BYTES + 1))
    with pytest.raises(m.OneMiBReviewError, match="bounded"):
        m.verify_1mib_zip(zip_path, expected_digest="sha256:"+"0"*64)
