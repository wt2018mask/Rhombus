"""Host-bound task status lookup: exact row hash, no provider dispatch."""
import hashlib
import json
from pathlib import Path

import pytest

from rhombus.tools.task_status import ReadOnlyTaskStatusTools, STATUS_SCHEMA, task_status_tool_spec


TASK = "task-proposal:sha256:" + "a" * 64
OTHER = "task-proposal:sha256:" + "b" * 64


def row(task=TASK, status="RUNNING"):
    record = {
        "schema_version": STATUS_SCHEMA,
        "proposal_id": task,
        "task_state": status,
        "backend_identity": "KAGGLE_CPU",
        "observed_at_utc": "2026-10-08T01:00:00Z",
        "provider_run_id": "37713197144",
    }
    body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    record["record_id"] = "task-status:sha256:" + hashlib.sha256(body).hexdigest()
    return record


def snapshot(tmp_path, records):
    path = tmp_path / "statuses.jsonl"
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))
    return path


def test_status_is_snapshot_not_live_or_science(tmp_path):
    path = snapshot(tmp_path, [row(TASK), row(OTHER, "SUCCEEDED")])
    before = path.read_bytes()
    gateway = ReadOnlyTaskStatusTools(path)
    result = gateway.call_tool("get_task_status", {"proposal_id": OTHER})
    assert result["task_state"] == "SUCCEEDED"
    assert result["operational_status"] == "SUCCEEDED"
    assert result["scientific_verdict"] == "UNKNOWN"
    assert result["claim_authorized"] is False
    assert result["status_freshness"] == "HOST_SNAPSHOT_ONLY_NOT_LIVE"
    assert result["snapshot_sha256"] == hashlib.sha256(before).hexdigest()
    assert result["status_record_id"] == row(OTHER,"SUCCEEDED")["record_id"]
    assert result["snapshot_record_count"] == 2
    assert before == path.read_bytes()
    missing = gateway.call_tool("get_task_status", {
        "proposal_id": "task-proposal:sha256:" + "0" * 64
    })
    assert missing["task_state"] == "UNKNOWN"
    assert missing["claim_authorized"] is False


def test_untrusted_or_corrupt_snapshot_fails_closed(tmp_path):
    valid = row()
    for mutation, match in [
        ({"task_state": "PASS"}, "invalid task state"),
        ({"provider_run_id": "https://user:token@example.com"}, "invalid provider run identity"),
        ({"observed_at_utc": "2026-02-30T00:00:00Z"}, "invalid observation calendar date"),
        ({"record_id": "task-status:sha256:" + "0"*64}, "SHA256 mismatch"),
    ]:
        invalid = {**valid, **mutation}
        path = snapshot(tmp_path, [invalid])
        with pytest.raises(ValueError, match=match):
            ReadOnlyTaskStatusTools(path).call_tool("get_task_status", {"proposal_id": TASK})
    path = snapshot(tmp_path, [valid,valid])
    with pytest.raises(ValueError, match="duplicate proposal_id"):
        ReadOnlyTaskStatusTools(path).call_tool("get_task_status", {"proposal_id": TASK})
    path.write_text("not-json\n")
    with pytest.raises(ValueError, match="invalid task-status JSON"):
        ReadOnlyTaskStatusTools(path).call_tool("get_task_status", {"proposal_id": TASK})
    path.write_bytes(b" " * (16*1024+1) + b"\n")
    with pytest.raises(ValueError, match="budget"):
        ReadOnlyTaskStatusTools(path).call_tool("get_task_status", {"proposal_id": TASK})


def test_fail_closed_when_unconfigured_or_invalid_argument(tmp_path):
    with pytest.raises(ValueError, match="not configured"):
        ReadOnlyTaskStatusTools().call_tool("get_task_status", {"proposal_id": TASK})
    path = snapshot(tmp_path,[row()])
    for args in ({}, {"proposal_id": "../../secret"}, {"proposal_id": TASK,"path":"/etc/passwd"}):
        with pytest.raises(ValueError):
            ReadOnlyTaskStatusTools(path).call_tool("get_task_status", args)
    with pytest.raises(ValueError):
        ReadOnlyTaskStatusTools(path).call_tool("cancel_task", {"proposal_id": TASK})
    params = task_status_tool_spec()["function"]["parameters"]
    assert set(params["properties"]) == {"proposal_id"}
    assert params["additionalProperties"] is False
