"""Read-only, no-network guard for the legacy scheduled discovery placeholder.

The scheduled workflow is NOT a production discovery, calibration or WBM/MPTrj
source download. Its historical job failed to collect tests because its
requirements installation omitted Phase 3 runtime imports and MCP optional deps.
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/cron.yml"


def _workflow():
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_existing_schedule_preserved_but_no_automated_science_write_authority():
    workflow = _workflow()
    assert set(workflow["on"]) == {"schedule", "workflow_dispatch"}
    assert workflow["on"]["schedule"] == [{"cron": "0 4,16 * * *"}]
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["readiness-smoke"]["timeout-minutes"] == "10"
    checkout = workflow["jobs"]["readiness-smoke"]["steps"][0]
    assert checkout["with"]["persist-credentials"] == "false"
    assert checkout["with"]["ref"] == "${{ github.sha }}"


def test_scheduled_imports_and_test_scope_are_bounded_and_reproducible():
    steps = _workflow()["jobs"]["readiness-smoke"]["steps"]
    install = next(step["run"] for step in steps if "Install bounded" in step["name"])
    assert "scripts/ci/constraints.txt" in install
    assert "ijson==3.5.1" in install
    assert "pymatgen" in install
    assert "python -m pip install --no-deps -e ." in install
    assert "-r requirements.txt" not in install

    verify = next(step["run"] for step in steps if "Verify selected" in step["name"])
    assert "python -m pytest -q" in verify
    assert "pytest tests/" not in verify
    assert "tests/test_phase3_wbm_v2_github_profile_review.py" in verify
    assert "tests/test_phase3_wbm_v2_archived_profile_replay.py" in verify
    assert "tests/test_phase3_scheduled_readiness_contract.py" in verify
    assert "python scripts/development/continuity.py check" in "\n".join(
        s.get("run", "") for s in steps
    )


def test_scheduled_workflow_cannot_run_original_source_or_publish_state():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "Scheduled Read-only Readiness" in source
    assert "RHOMBUS_SCHEDULED_OFFLINE_READINESS_PASS_NO_DISCOVERY_NO_SOURCE_GET" in source
    assert "contents: write" not in source
    assert "secrets." not in source
    for forbidden in ("git push", "git commit", "kaggle kernels", "curl --", "wget ",
                      "execute-full-download", "upload-artifact@", "actions/cache/save"):
        assert forbidden not in source
