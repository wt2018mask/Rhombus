"""Workflow-dispatch only MPTrj source prefix control contract; NO network."""
from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/phase3-mptrj-first-frame-manual.yml"


def _workflow():
    # YAML BaseLoader keeps 'on' as a string across PyYAML 1.1 parsers.
    data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(data, dict)
    return data


def test_only_explicit_workflow_dispatch_can_trigger_source_probe():
    data = _workflow()
    assert set(data["on"]) == {"workflow_dispatch"}
    assert set(data["permissions"]) == {"contents"}
    assert data["permissions"]["contents"] == "read"
    assert len(data["jobs"]) == 1
    job = data["jobs"]["first-frame"]
    assert int(job["timeout-minutes"]) <= 10


def test_never_falls_back_to_full_corpus_and_only_posts_receipt():
    steps = _workflow()["jobs"]["first-frame"]["steps"]
    scripts = "\n".join(str(step.get("run", "")) for step in steps)
    assert "--probe --require-complete-frame --prefix-bytes 262144" in scripts
    assert "--report" in scripts
    assert "curl " not in scripts
    assert "wget " not in scripts
    assert "kaggle " not in scripts
    assert "figshare.com/files/" not in scripts
    assert "pip install --no-deps -e ." in scripts

    upload = next(step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["with"]["path"].endswith("/mptrj-first-frame-observation.json")
    assert int(upload["with"]["retention-days"]) <= 7
    assert upload["with"]["if-no-files-found"] == "error"


def test_action_permits_no_write_token_or_persisted_checkout_credential():
    data = _workflow()
    assert data["jobs"]["first-frame"]["steps"][0]["with"]["persist-credentials"] == "false"
    serialized = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in serialized
    assert "contents: write" not in serialized
    assert "pull_request:" not in serialized
    assert "schedule:" not in serialized
    assert "repository_dispatch:" not in serialized


def test_frozen_observation_contract_unchanged():
    from scripts.development import probe_mptrj_source_prefix as probe
    assert probe.CANONICAL_DOWNLOAD_URL == "https://ndownloader.figshare.com/files/41619375"
    assert probe.DEFAULT_PREFIX_BYTES == 262144
    assert probe.MAX_PREFIX_BYTES == 1048576
