from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_kaggle_full_run_request_authorizes_only_salex_component() -> None:
    request = json.loads(
        (ROOT / "data/development/phase3_salex_kaggle_full_run_request_v1.json")
        .read_text(encoding="utf-8")
    )
    assert request["enabled"] is True
    assert request["run_once"] is True
    assert request["backend"] == "KAGGLE_CPU"
    assert request["frozen_sources"]["salex"]["expected_records"] == 10447765
    assert request["frozen_sources"]["wbm_initial_structures"]["expected_records"] == 256963
    assert request["authorization"]["full_run_authorized"] is True
    assert request["authorization"]["build_production_salex_membership_index"] is True
    assert request["authorization"]["execute_salex_wbm_overlap_component"] is True
    assert request["authorization"]["complete_training_lineage_audit"] is False
    assert request["authorization"]["unseen_generalization_claim"] is False


def test_kaggle_kernel_driver_is_cpu_exact_commit_and_chunked() -> None:
    path = ROOT / "scripts/kaggle/salex_phase3_full_run.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    assert 'checkout_exact(REPO_URL, repo_root, source_commit)' in source
    assert 'verify_matbench_blobs(matbench_root, matbench["git_blobs"])' in source
    assert '"run_salex_wbm_overlap.py"' in source
    assert '"salex_membership_row_count"] != salex["expected_records"]' in source
    assert "CHUNK_SIZE = 128 * 1024 * 1024" in source
    assert "unseen_generalization_claim_authorized" in source


def test_kaggle_controller_self_continues_and_retrieves_with_hash_verification() -> None:
    workflow = (
        ROOT / ".github/workflows/r2-phase3-salex-kaggle-full-run.yml"
    ).read_text(encoding="utf-8")
    assert '"enable_gpu": false' in workflow
    assert 'api.kernels_push("kaggle-stage/kernel")' in workflow
    assert "KAGGLE_KERNEL_PUSH_REJECTED" in workflow
    assert "KAGGLE_EXACT_COMMIT_REQUEST_EMBEDDED" in workflow
    assert 'source.count(marker) == 1' in workflow
    assert "rhombus-salexcpu-$short" in workflow
    assert '"title": "$KERNEL_TITLE"' in workflow
    assert "python -m kaggle kernels status" in workflow
    assert "operation=resume" in workflow
    assert "operation=retrieve" in workflow
    assert "python -m kaggle kernels output" in workflow
    assert "ZstdDecompressor().stream_reader" in workflow
    assert "compressed.hexdigest() == spec[\"compressed_sha256\"]" in workflow
    assert "raw.hexdigest() == expected_raw == spec[\"raw_sha256\"]" in workflow
    assert "actions/upload-artifact@v4" in workflow


def test_kaggle_full_run_plan_keeps_full_training_lineage_closed() -> None:
    plan = json.loads(
        (ROOT / "data/development/phase3_salex_kaggle_full_run_plan_v1.json")
        .read_text(encoding="utf-8")
    )
    assert plan["status"] == "KAGGLE_KERNEL_RUNTIME_REQUEST_MOUNT_RECOVERY_ARMED"
    assert plan["trigger"]["gpu_enabled"] is False
    assert plan["continuation"]["user_reentry_required"] is False
    assert plan["scientific_scope"]["salex_component_may_be_completed"] is True
    assert plan["scientific_scope"]["full_training_lineage_resolved"] is False
    assert plan["scientific_scope"]["unseen_generalization_claim_authorized"] is False


def test_merge_launcher_dispatches_exact_main_push_once() -> None:
    root = ROOT
    launch = json.loads(
        (root / "data/development/phase3_salex_kaggle_launch_v1.json")
        .read_text(encoding="utf-8")
    )
    workflow = (
        root / ".github/workflows/r2-phase3-salex-kaggle-launch.yml"
    ).read_text(encoding="utf-8")

    assert launch["armed"] is True
    assert launch["launch_once"] is True
    assert launch["target_operation"] == "submit"
    assert launch["authorization"]["unseen_generalization_claim"] is False
    assert "push:" in workflow
    assert "- main" in workflow
    assert "phase3_salex_kaggle_launch_v1.json" in workflow
    assert "gh workflow run r2-phase3-salex-kaggle-full-run.yml" in workflow
    assert "-f operation=submit" in workflow
    assert '-f expected_commit="$GITHUB_SHA"' in workflow


def test_kaggle_dispatch_blocker_records_zero_remote_side_effects() -> None:
    evidence = json.loads(
        (ROOT / "data/development/phase3_salex_kaggle_dispatch_blocker_v1.json")
        .read_text(encoding="utf-8")
    )
    assert evidence["status"] == "REMOTE_CREDENTIAL_NOT_CONFIGURED"
    assert evidence["source_commit"] == "ca8f44d3aabdf7680c6b8f970b302ef058e507a4"
    assert evidence["launch"]["conclusion"] == "success"
    assert evidence["controller"]["production_authorization_check"] == "success"
    assert evidence["controller"]["credential_gate"] == "failure"
    assert evidence["controller"]["kaggle_dataset_created"] is False
    assert evidence["controller"]["kaggle_kernel_submitted"] is False
    assert evidence["controller"]["scientific_computation_started"] is False
    assert evidence["recovery"]["required_repository_actions_secret"] == "KAGGLE_API_TOKEN"
    assert evidence["scientific_authorization"]["unseen_generalization_claim"] is False


def test_kaggle_conflict_recovery_keeps_earlier_failure_provenance() -> None:
    recovery = json.loads(
        (ROOT / "data/development/phase3_salex_kaggle_kernel_conflict_v1.json")
        .read_text(encoding="utf-8")
    )
    assert recovery["controller_run_id"] == 37704726464
    assert recovery["controller_attempt"] == 2
    assert recovery["kaggle_credential_gate"] == "PASS"
    assert recovery["private_dataset_created"] is True
    assert recovery["kernel_push_http_status"] == 409
    assert recovery["production_computation_started"] is False
    assert recovery["recovery"]["fresh_kernel_slug_namespace"] == "rhombus-salexcpu-<short>"
    assert recovery["scientific_authorization"]["unseen_generalization_claim"] is False


def _request_fixture() -> dict:
    request = json.loads(
        (ROOT / "data/development/phase3_salex_kaggle_full_run_request_v1.json")
        .read_text(encoding="utf-8")
    )
    request["source_commit"] = "e5b13b6aab57947013d54044b6263943a011c3d3"
    request["controller"] = {"repository": "wt2018mask/Rhombus", "workflow_run_id": 37708908104}
    return request


def _request_loader(tmp_path, embedded: dict | None):
    namespace = runpy.run_path(str(ROOT / "scripts/kaggle/salex_phase3_full_run.py"))
    finder = namespace["find_request"]
    finder.__globals__["REQUEST_ROOT"] = tmp_path / "input"
    finder.__globals__["EMBEDDED_REQUEST_JSON"] = (
        json.dumps(embedded, sort_keys=True) if embedded is not None else None
    )
    return finder


def test_kaggle_request_nested_owner_qualified_mount(tmp_path) -> None:
    request = _request_fixture()
    path = tmp_path / "input" / "datasets" / "wt2018mask" / "rhombus-phase3-salex" / "request.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(request), encoding="utf-8")
    found_path, found_request = _request_loader(tmp_path, request)()
    assert found_path == path
    assert found_request == request


def test_kaggle_request_empty_mount_uses_exact_bound_embedded_request(tmp_path) -> None:
    request = _request_fixture()
    found_path, found_request = _request_loader(tmp_path, request)()
    assert found_path is None
    assert found_request == request


def test_kaggle_request_detects_mount_vs_embedded_drift(tmp_path) -> None:
    request = _request_fixture()
    altered = json.loads(json.dumps(request))
    altered["frozen_sources"]["salex"]["expected_records"] = 1
    path = tmp_path / "input" / "rhombus-phase3-salex-test" / "request.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(RuntimeError, match="differs from exact-commit"):
        _request_loader(tmp_path, request)()


def test_kaggle_request_rejects_missing_mount_and_missing_embedded(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="missing from both"):
        _request_loader(tmp_path, None)()


def test_kaggle_runtime_failure_evidence() -> None:
    evidence = json.loads(
        (ROOT / "data/development/phase3_salex_kaggle_input_failure_v1.json")
        .read_text(encoding="utf-8")
    )
    assert evidence["controller_run_id"] == 37708908104
    assert evidence["launch_run_id"] == 37708897867
    assert evidence["kaggle_kernel_push"] == "PASS"
    assert evidence["kaggle_kernel_terminal_state"] == "ERROR"
    assert evidence["failure"]["exception_class"] == "RuntimeError"
    assert evidence["failure"]["expected_matches"] == 1
    assert evidence["failure"]["observed_matches"] == 0
    assert evidence["scientific_authorization"]["unseen_generalization_claim"] is False
