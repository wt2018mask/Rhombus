"""Host-selected, hash-verified, bounded task-status snapshot lookup.

NOT a live provider status or remote API. The AI cannot choose the input path
or modify job state. A status of SUCCEEDED never authorizes scientific PASS.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

STATUS_SCHEMA = "rhombus-ai-task-status-snapshot-v1"
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_LINE_BYTES = 16 * 1024
MAX_RECORDS = 10000
ID_PATTERN = re.compile(r"^task-proposal:sha256:[a-f0-9]{64}$")
RECORD_PATTERN = re.compile(r"^task-status:sha256:[a-f0-9]{64}$")
ALLOWED_STATES = frozenset({
    "PROPOSED", "PENDING_APPROVAL", "AUTHORIZED", "QUEUED", "RUNNING",
    "SUCCEEDED", "ERROR", "CANCELLED",
})
BACKENDS = frozenset({"LOCAL_CPU", "KAGGLE_CPU"})

_SPEC = {
    "type": "function",
    "function": {
        "name": "get_task_status",
        "description": (
            "Query the last host-attested, hash-verified task status snapshot. "
            "Not a live Kaggle/CPU probe; no execution or scientific qualification."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "pattern": "^task-proposal:sha256:[a-f0-9]{64}$",
                },
            },
            "required": ["proposal_id"],
            "additionalProperties": False,
        },
    },
}


def task_status_tool_spec() -> dict[str, Any]:
    return json.loads(json.dumps(_SPEC))


def _canonical(record: Mapping[str, Any]) -> bytes:
    return json.dumps(
        record, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _verify(row: Any, line: int) -> dict[str, Any]:
    expected = {"schema_version", "proposal_id", "task_state", "backend_identity",
                "observed_at_utc", "provider_run_id", "record_id"}
    if not isinstance(row, dict) or set(row) != expected:
        raise ValueError(f"invalid task-status fields at line {line}")
    if row["schema_version"] != STATUS_SCHEMA:
        raise ValueError(f"unknown task-status schema at line {line}")
    if not isinstance(row["proposal_id"], str) or not ID_PATTERN.fullmatch(row["proposal_id"]):
        raise ValueError(f"invalid proposal identity at line {line}")
    if not isinstance(row["task_state"], str) or row["task_state"] not in ALLOWED_STATES:
        raise ValueError(f"invalid task state at line {line}")
    if not isinstance(row["backend_identity"], str) or row["backend_identity"] not in BACKENDS:
        raise ValueError(f"invalid backend identity at line {line}")
    when = row["observed_at_utc"]
    if not isinstance(when, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", when):
        raise ValueError(f"invalid UTC observation timestamp at line {line}")
    try:
        datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"invalid observation calendar date at line {line}") from exc
    run_id = row["provider_run_id"]
    if run_id is not None and (
        not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", run_id)
    ):
        raise ValueError(f"invalid provider run identity at line {line}")
    rid = row["record_id"]
    if not isinstance(rid, str) or not RECORD_PATTERN.fullmatch(rid):
        raise ValueError(f"invalid status record identity at line {line}")
    expected_id = "task-status:sha256:" + hashlib.sha256(
        _canonical({k:v for k,v in row.items() if k != "record_id"})
    ).hexdigest()
    if rid != expected_id:
        raise ValueError(f"status record SHA256 mismatch at line {line}")
    return row


class ReadOnlyTaskStatusTools:
    """Host selects the immutable status JSONL. AI supplies only proposal_id."""

    def __init__(self, status_jsonl: Path | None = None):
        self._snapshot = Path(status_jsonl) if status_jsonl is not None else None

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if name != "get_task_status":
            raise ValueError("unavailable task status tool")
        if not isinstance(arguments, Mapping) or set(arguments) != {"proposal_id"}:
            raise ValueError("task status requires only proposal_id")
        proposal_id = arguments["proposal_id"]
        if not isinstance(proposal_id, str) or not ID_PATTERN.fullmatch(proposal_id):
            raise ValueError("invalid task proposal ID")
        if self._snapshot is None or not self._snapshot.is_file():
            raise ValueError("trusted task-status snapshot is not configured")
        if self._snapshot.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("task-status snapshot exceeds size budget")
        selected = None
        ids = set()
        source_hash = hashlib.sha256()
        with self._snapshot.open("rb") as stream:
            for index, raw in enumerate(stream, 1):
                if index > MAX_RECORDS or len(raw) > MAX_LINE_BYTES:
                    raise ValueError("task-status snapshot exceeds record budget")
                source_hash.update(raw)
                try:
                    row = _verify(json.loads(raw), index)
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise ValueError(f"invalid task-status JSON at line {index}") from exc
                if row["proposal_id"] in ids:
                    raise ValueError(f"duplicate proposal_id at line {index}")
                ids.add(row["proposal_id"])
                if row["proposal_id"] == proposal_id:
                    selected = row
        return {
            "schema_version": "rhombus-ai-tool-result-v1",
            "tool_name": name,
            "proposal_id": proposal_id,
            "operational_status": "SUCCEEDED",
            "task_state": selected["task_state"] if selected else "UNKNOWN",
            "last_observed_at_utc": selected["observed_at_utc"] if selected else None,
            "backend_identity": selected["backend_identity"] if selected else None,
            "provider_run_id": selected["provider_run_id"] if selected else None,
            "status_record_id": selected["record_id"] if selected else None,
            "snapshot_sha256": source_hash.hexdigest(),
            "snapshot_record_count": len(ids),
            "status_freshness": "HOST_SNAPSHOT_ONLY_NOT_LIVE",
            "scientific_verdict": "UNKNOWN",
            "domain_status": "UNQUALIFIED",
            "claim_authorized": False,
            "limitations": [
                "STATUS_SNAPSHOT_NOT_LIVE_PROVIDER_AVAILABILITY",
                "STATUS_RECORD_HASH_NOT_EXTERNAL_PROVIDER_AUTHENTICATION",
                "OPERATIONAL_SUCCESS_NEVER_IMPLIES_SCIENTIFIC_PASS",
                "NO_DISPATCH_APPROVAL_OR_CANCELLATION_TOOL",
            ],
        }


__all__ = ["ReadOnlyTaskStatusTools", "task_status_tool_spec", "STATUS_SCHEMA"]
