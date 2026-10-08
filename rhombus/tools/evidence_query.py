"""Bounded, read-only, AI-callable evidence queries.

A trusted host binds the path to a v2 EvidenceRecord JSONL snapshot. AI tool
arguments cannot select filesystem paths, execute code, or run simulations.
Every delivered record is content-hash checked; missing evidence never
authorizes a scientific PASS or model generalization claim.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from rhombus.evidence.schema import EVIDENCE_SCHEMA_VERSION

TOOL_SCHEMA_VERSION = "rhombus-ai-tool-result-v1"
MAX_RECORDS = 25
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024

_GET_CANDIDATE_EVIDENCE_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_candidate_evidence",
        "description": (
            "Read verified Rhombus v2 EvidenceRecord entries for a candidate "
            "from a host-bound, read-only snapshot. Does not assess, qualify, "
            "simulate, or authorize any scientific claim. An empty result "
            "means missing evidence, not PASS."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "candidate_id": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 256,
                    "description": "Exact candidate identifier, never a chemical-name guess",
                },
                "max_records": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_RECORDS,
                    "default": 10,
                    "description": "Maximum evidence records returned (bounded)",
                },
            },
            "required": ["candidate_id"],
            "additionalProperties": False,
        },
    },
}


def list_tool_specs() -> list[dict[str, Any]]:
    """Expose a small function-calling-compatible catalog, without side effects."""
    # Clone so the caller cannot mutate future advertised schemas.
    from .read_only_analysis import list_analysis_tool_specs
    from .evidence_manifest import manifest_tool_spec
    from .task_proposal import plan_task_tool_spec
    from .task_status import task_status_tool_spec
    return json.loads(json.dumps([
        _GET_CANDIDATE_EVIDENCE_SPEC, *list_analysis_tool_specs(), manifest_tool_spec(), plan_task_tool_spec(), task_status_tool_spec(),
    ]))


def _verify_evidence_row(row: Any, *, lineno: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(f"evidence JSONL line {lineno} is not an object")
    if row.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        raise ValueError(f"unsupported evidence schema at line {lineno}")
    candidate = row.get("candidate_id")
    if not isinstance(candidate, str) or not candidate.strip():
        raise ValueError(f"missing evidence candidate_id at line {lineno}")
    expected_id = row.get("evidence_id")
    if not isinstance(expected_id, str) or not expected_id.startswith("evidence:sha256:"):
        raise ValueError(f"invalid evidence_id at line {lineno}")
    body = {key: value for key, value in row.items() if key != "evidence_id"}
    try:
        canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid evidence body at line {lineno}") from exc
    actual = "evidence:sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if expected_id != actual:
        raise ValueError(f"evidence hash mismatch at line {lineno}")
    for key, allowed in (
        ("operational_status", {"PENDING", "RUNNING", "SUCCEEDED", "ERROR", "CANCELLED"}),
        ("scientific_verdict", {"PASS", "FAIL", "UNKNOWN", "INDETERMINATE", "NOT_APPLICABLE"}),
    ):
        if row.get(key) not in allowed:
            raise ValueError(f"invalid {key} at line {lineno}")
    applicability = row.get("applicability")
    if not isinstance(applicability, dict) or applicability.get("domain_status") not in {
        "IN_DOMAIN", "NEAR_OOD", "FAR_OOD", "UNQUALIFIED"
    }:
        raise ValueError(f"invalid applicability at line {lineno}")
    if not isinstance(row.get("uncertainty"), dict):
        raise ValueError(f"missing uncertainty at line {lineno}")
    if not isinstance(row.get("limitations"), list) or not isinstance(row.get("artifact_ids"), list):
        raise ValueError(f"missing limitations/artifact references at line {lineno}")
    return row


def _compact_record(row: Mapping[str, Any]) -> dict[str, Any]:
    # Deliberately omit arbitrary large payload, while exposing exact IDs and
    # scientific qualifications needed by downstream AI tool invocations.
    return {
        "evidence_id": row["evidence_id"],
        "evidence_kind": row["evidence_kind"],
        "capability": row["capability"],
        "operational_status": row["operational_status"],
        "scientific_verdict": row["scientific_verdict"],
        "applicability": row["applicability"],
        "uncertainty": row["uncertainty"],
        "limitations": row["limitations"],
        "artifact_ids": row["artifact_ids"],
        "protocol_id": row.get("protocol_id"),
        "model_identity": row.get("model_identity"),
        "source_bindings": row.get("source_bindings", []),
        "legacy_stage": row.get("legacy_stage"),
    }


class ReadOnlyEvidenceTools:
    """Trusted host configures the snapshot; an AI controls only tool arguments."""

    def __init__(self, evidence_jsonl: Path):
        self._snapshot = Path(evidence_jsonl)

    def call_tool(self, tool_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if tool_name != "get_candidate_evidence":
            raise ValueError(f"unavailable Rhombus tool: {tool_name}")
        if not isinstance(arguments, Mapping):
            raise ValueError("tool arguments must be a JSON object")
        if set(arguments) - {"candidate_id", "max_records"}:
            raise ValueError("unexpected AI tool arguments")
        candidate_id = arguments.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip() or len(candidate_id) > 256:
            raise ValueError("candidate_id must be 1..256 non-whitespace characters")
        requested_limit = arguments.get("max_records", 10)
        if type(requested_limit) is not int or not 1 <= requested_limit <= MAX_RECORDS:
            raise ValueError("max_records must be an integer from 1 to 25")
        if not self._snapshot.is_file():
            raise FileNotFoundError("trusted EvidenceRecord snapshot not present")
        if self._snapshot.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("evidence snapshot exceeds read-only tool size budget")
        matched: list[dict[str, Any]] = []
        count = 0
        seen_ids: set[str] = set()
        with self._snapshot.open("rb") as stream:
            for lineno, raw in enumerate(stream, start=1):
                if len(raw) > MAX_LINE_BYTES:
                    raise ValueError(f"evidence record exceeds size budget at line {lineno}")
                try:
                    row = _verify_evidence_row(json.loads(raw), lineno=lineno)
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise ValueError(f"invalid evidence JSONL at line {lineno}") from exc
                if row["evidence_id"] in seen_ids:
                    raise ValueError(f"duplicate evidence_id at line {lineno}")
                seen_ids.add(row["evidence_id"])
                if row["candidate_id"] == candidate_id:
                    count += 1
                    if len(matched) < requested_limit:
                        matched.append(_compact_record(row))
        matched.sort(key=lambda row: row["evidence_id"])
        # A candidate's aggregate verdict cannot be inferred just by finding
        # evidence, even if an individual evidence record reports PASS.
        return {
            "schema_version": TOOL_SCHEMA_VERSION,
            "tool_name": tool_name,
            "candidate_id": candidate_id,
            "operational_status": "SUCCEEDED",
            "scientific_verdict": "UNKNOWN",
            "domain_status": "UNQUALIFIED",
            "claim_authorized": False,
            "evidence_count": count,
            "returned_count": len(matched),
            "truncated": count > len(matched),
            "evidence_records": matched,
            "limitations": [
                "READ_ONLY_EVIDENCE_LOOKUP_NOT_SCIENTIFIC_QUALIFICATION",
                "MISSING_EVIDENCE_NEVER_IMPLIES_PASS",
                "FOUND_EVIDENCE_DOES_NOT_AUTHORIZE_UNSEEN_GENERALIZATION",
            ],
        }


__all__ = ["ReadOnlyEvidenceTools", "list_tool_specs"]
