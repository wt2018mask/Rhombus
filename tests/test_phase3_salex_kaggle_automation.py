from __future__ import annotations

import json
from pathlib import Path

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
    assert "python -m kaggle kernels push" in workflow
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
    assert plan["status"] == "MERGE_TRIGGER_LAUNCH_ARMED_FULL_RUN_PENDING_DISPATCH"
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
