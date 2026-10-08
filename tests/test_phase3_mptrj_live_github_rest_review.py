"""Offline fake HTTPS tests for the opt-in pinned two-request reviewer."""
import json
from hashlib import sha256
import zipfile

import pytest

from scripts.development.review_mptrj_live_github_run import (
    API_ROOT, ARTIFACT_NAME, MPTrjLiveReviewError, main, review_mptrj_live_run,
)

SHA = "b" * 40
RUN_ID = 12345


class Response:
    def __init__(self, url, data, *, status=200, final_url=None, content_type="application/json", encoding="identity", declared=None):
        self.status = status
        self.url = final_url or url
        self.data = data
        self.headers = {"Content-Type": content_type, "Content-Encoding": encoding}
        if declared is not None:
            self.headers["Content-Length"] = str(declared)
    def geturl(self):
        return self.url
    def read(self, size):
        return self.data[:size]
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


def evidence(tmp_path):
    report = {
        "schema_version": "rhombus-phase3-mptrj-range-prefix-probe-v1",
        "source_metadata": {
            "figshare_file_id": 41619375,
            "expected_total_size_bytes_from_registry": 12_188_168_685,
            "server_content_range_total_declared": 12_188_168_685,
            "redirect_host": "cdn.figshare.example",
        },
        "observation": {
            "prefix_size_bytes": 262144, "prefix_sha256": "a" * 64,
            "first_material_id": "mp-1", "first_frame_id": "task-1",
            "first_frame_structure_object_start_seen": True, "complete_frame_parsed": True,
            "complete_original_source_hashed": False,
            "first_frame_structure": {
                "material_id": "mp-1", "frame_id": "task-1",
                "site_count": 3, "reduced_formula": "LiO", "complete_frame_parsed": True,
                "energy_fields_present": {
                    "uncorrected_total_energy": False, "corrected_total_energy": True,
                    "energy_per_atom": False,
                },
            },
        },
        "training_lineage": {
            "mace_mpa0_exact_training_bytes_attested": False,
            "training_frame_selection_attested": False,
        },
        "authorization": {
            "execute_exposure_audit": False,
            "empirical_calibration_use": False,
            "unseen_generalization_claim": False,
        },
    }
    receipt = tmp_path / "mptrj-first-frame-observation.json"
    receipt.write_text(json.dumps(report), encoding="utf-8")
    archive = tmp_path / "artifact.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("mptrj-first-frame-observation.json", receipt.read_bytes())
    run = {
        "id": RUN_ID, "run_attempt": 1, "event": "workflow_dispatch",
        "name": "Phase 3 MPTrj Capped Source Prefix",
        "path": ".github/workflows/phase3-mptrj-first-frame-manual.yml",
        "head_branch": "main", "head_sha": SHA, "status": "completed", "conclusion": "success",
        "html_url": f"https://github.com/wt2018mask/Rhombus/actions/runs/{RUN_ID}",
        "repository": {"full_name": "wt2018mask/Rhombus"},
    }
    arts = {"total_count": 1, "artifacts": [{
        "id": 987, "name": ARTIFACT_NAME, "expired": False,
        "size_in_bytes": len(archive.read_bytes()),
        "digest": "sha256:" + sha256(archive.read_bytes()).hexdigest(),
        "archive_download_url": "https://api.github.com/repos/wt2018mask/Rhombus/actions/artifacts/987/zip",
        "workflow_run": {"id": RUN_ID, "head_sha": SHA},
    }]}
    return archive, receipt, run, arts


def opener_for(run, arts, mutate=None):
    urls = [
        f"{API_ROOT}/actions/runs/{RUN_ID}",
        f"{API_ROOT}/actions/runs/{RUN_ID}/artifacts?name={ARTIFACT_NAME}&per_page=100",
    ]
    bodies = [json.dumps(run).encode(), json.dumps(arts).encode()]
    seen = []
    def open_url(req, timeout):
        assert req.get_method() == "GET" and timeout == 15
        assert req.full_url in urls
        seen.append(req.full_url)
        i = urls.index(req.full_url)
        if mutate:
            return mutate(req.full_url, bodies[i])
        return Response(req.full_url, bodies[i], declared=len(bodies[i]))
    return open_url, seen


def test_two_pinned_https_requests_and_no_artifact_download_or_writes(tmp_path):
    archive, receipt, run, arts = evidence(tmp_path)
    opener, seen = opener_for(run, arts)
    names_before = sorted(p.name for p in tmp_path.iterdir())
    result = review_mptrj_live_run(
        run_id=RUN_ID, expected_head_sha=SHA, artifact_zip=archive,
        receipt=receipt, open_url=opener,
    )
    assert seen == [
        f"{API_ROOT}/actions/runs/{RUN_ID}",
        f"{API_ROOT}/actions/runs/{RUN_ID}/artifacts?name={ARTIFACT_NAME}&per_page=100",
    ]
    assert result["artifact_zip_sha256"] == sha256(archive.read_bytes()).hexdigest()
    assert all(result[k] is False for k in (
        "github_signed_attestation_present", "mptrj_full_source_verified",
        "mace_mpa0_training_frames_attested", "exposure_audit_authorized",
        "empirical_calibration_authorized", "unseen_generalization_authorized",
    ))
    assert sorted(p.name for p in tmp_path.iterdir()) == names_before


@pytest.mark.parametrize(("k", "v"), [
    ("status", 206), ("content_type", "text/html"), ("encoding", "gzip"),
    ("final_url", "https://attacker.example/redirect"), ("declared", 131073),
])
def test_api_response_safety_rejections(tmp_path, k, v):
    archive, receipt, run, arts = evidence(tmp_path)
    opener, _ = opener_for(run, arts, mutate=lambda u, b: Response(u, b, **{k: v}))
    with pytest.raises(MPTrjLiveReviewError):
        review_mptrj_live_run(
            run_id=RUN_ID, expected_head_sha=SHA,
            artifact_zip=archive, receipt=receipt, open_url=opener,
        )


def test_oversize_duplicate_and_missing_artifact_rejected(tmp_path):
    archive, receipt, run, arts = evidence(tmp_path)
    opener, _ = opener_for(run, arts, mutate=lambda u, b: Response(u, b + b"x" * 131073))
    with pytest.raises(MPTrjLiveReviewError, match="limit"):
        review_mptrj_live_run(run_id=RUN_ID, expected_head_sha=SHA, artifact_zip=archive, receipt=receipt, open_url=opener)
    def dup(u, b):
        if u.endswith(str(RUN_ID)):
            b = b.replace(b'"id": 12345', b'"id": 12345, "id": 12345')
        return Response(u, b)
    opener, _ = opener_for(run, arts, mutate=dup)
    with pytest.raises(MPTrjLiveReviewError, match="duplicate"):
        review_mptrj_live_run(run_id=RUN_ID, expected_head_sha=SHA, artifact_zip=archive, receipt=receipt, open_url=opener)
    arts["total_count"] = 2
    opener, _ = opener_for(run, arts)
    with pytest.raises(MPTrjLiveReviewError, match="total_count"):
        review_mptrj_live_run(run_id=RUN_ID, expected_head_sha=SHA, artifact_zip=archive, receipt=receipt, open_url=opener)


def test_sha_and_zip_tampering_rejected(tmp_path):
    archive, receipt, run, arts = evidence(tmp_path)
    opener, _ = opener_for(run, arts)
    with pytest.raises(ValueError):
        review_mptrj_live_run(run_id=RUN_ID, expected_head_sha="c" * 40, artifact_zip=archive, receipt=receipt, open_url=opener)
    arts["artifacts"][0]["digest"] = "sha256:" + "0" * 64
    opener, _ = opener_for(run, arts)
    with pytest.raises(ValueError, match="SHA256|digest"):
        review_mptrj_live_run(run_id=RUN_ID, expected_head_sha=SHA, artifact_zip=archive, receipt=receipt, open_url=opener)


def test_no_network_without_explicit_cli_opt_in(tmp_path, capsys):
    archive, receipt, run, arts = evidence(tmp_path)
    assert main([
        "--run-id", str(RUN_ID), "--expected-head-sha", SHA,
        "--artifact-zip", str(archive), "--receipt", str(receipt),
    ]) == 1
    assert "explicit --live-review" in capsys.readouterr().err


def test_invalid_run_id_rejected_without_any_get(tmp_path):
    archive, receipt, run, arts = evidence(tmp_path)
    opener, seen = opener_for(run, arts)
    with pytest.raises(MPTrjLiveReviewError):
        review_mptrj_live_run(run_id=0, expected_head_sha=SHA, artifact_zip=archive, receipt=receipt, open_url=opener)
    assert seen == []

def test_versioned_readonly_evidence_is_machine_readable_without_sci_claim(tmp_path):
    archive, receipt, run, arts = evidence(tmp_path)
    opener, calls = opener_for(run, arts)
    review = review_mptrj_live_run(
        run_id=RUN_ID, expected_head_sha=SHA,
        artifact_zip=archive, receipt=receipt, open_url=opener,
    )
    assert review["schema_version"] == "rhombus-phase3-mptrj-live-rest-review-v1"
    assert review["run_id"] == RUN_ID
    assert review["run_attempt"] == 1
    assert review["api_get_count"] == 2
    assert len(review["receipt_metadata_sha256"]) == 64
    assert review["receipt_byte_sha256"] == sha256(receipt.read_bytes()).hexdigest()
    assert review["artifact_zip_sha256"] == sha256(archive.read_bytes()).hexdigest()
    for key in (
        "github_signed_attestation_present", "mptrj_full_source_verified",
        "mace_mpa0_training_frames_attested", "exposure_audit_authorized",
        "empirical_calibration_authorized", "unseen_generalization_authorized",
    ):
        assert review[key] is False
    assert len(calls) == 2


def test_json_cli_machine_contract_only_outputs_json_on_success(tmp_path, monkeypatch, capsys):
    import scripts.development.review_mptrj_live_github_run as module
    archive, receipt, run, arts = evidence(tmp_path)
    opener, calls = opener_for(run, arts)
    original_review = module.review_mptrj_live_run
    def fake_review(**kwargs):
        return original_review(
            run_id=kwargs["run_id"],
            expected_head_sha=kwargs["expected_head_sha"],
            artifact_zip=kwargs["artifact_zip"],
            receipt=kwargs["receipt"], open_url=opener,
        )
    monkeypatch.setattr(module, "review_mptrj_live_run", fake_review)
    assert main([
        "--live-review", "--output-format", "json",
        "--run-id", str(RUN_ID), "--expected-head-sha", SHA,
        "--artifact-zip", str(archive), "--receipt", str(receipt),
    ]) == 0
    stdout = capsys.readouterr().out
    report = json.loads(stdout)
    assert report["schema_version"] == "rhombus-phase3-mptrj-live-rest-review-v1"
    assert report["status"].endswith("CONSISTENCY_ONLY")
    assert report["github_signed_attestation_present"] is False
    assert len(calls) == 2
    assert stdout.strip().startswith("{") and stdout.strip().endswith("}")


def test_nonfinite_rest_json_is_rejected_even_if_other_fields_appear_valid(tmp_path):
    archive, receipt, run, arts = evidence(tmp_path)
    def inject_nan(url, body):
        if url.endswith(str(RUN_ID)):
            body = body.replace(b'"run_attempt": 1', b'"run_attempt": NaN')
        return Response(url, body)
    opener, _ = opener_for(run, arts, mutate=inject_nan)
    with pytest.raises(MPTrjLiveReviewError, match="non-finite"):
        review_mptrj_live_run(
            run_id=RUN_ID, expected_head_sha=SHA,
            artifact_zip=archive, receipt=receipt, open_url=opener,
        )


def test_failed_cli_never_prints_success_json(tmp_path, capsys):
    archive, receipt, run, arts = evidence(tmp_path)
    assert main([
        "--output-format", "json",
        "--run-id", str(RUN_ID), "--expected-head-sha", SHA,
        "--artifact-zip", str(archive), "--receipt", str(receipt),
    ]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "explicit --live-review" in output.err
