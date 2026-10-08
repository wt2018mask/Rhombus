"""Deterministic, bounded, read-only manifest of SHA256-verified evidence IDs.

An evidence manifest is a traceable index, not a verdict. The caller controls
only candidate_id and max_evidence_ids; host binds the trusted JSONL bytes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .evidence_query import (
    MAX_LINE_BYTES, MAX_RECORDS, MAX_SOURCE_BYTES, TOOL_SCHEMA_VERSION,
    _verify_evidence_row,
)

MANIFEST_VERSION = "rhombus-ai-evidence-manifest-v1"

_MANIFEST_SPEC = {
    "type": "function",
    "function": {
        "name": "build_evidence_manifest",
        "description": (
            "Return a deterministic digest and bounded verified evidence IDs "
            "for a single candidate. This is a read-only index; it never "
            "qualifies scientific PASS, model domain or unseen generalization."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "candidate_id": {
                    "type": "string", "minLength": 1, "maxLength": 256,
                },
                "max_evidence_ids": {
                    "type": "integer", "minimum": 1, "maximum": MAX_RECORDS,
                    "default": 10,
                },
            },
            "required": ["candidate_id"],
            "additionalProperties": False,
        },
    },
}


def manifest_tool_spec() -> dict[str, Any]:
    """Return a safe cloned function-calling schema."""
    return json.loads(json.dumps(_MANIFEST_SPEC))


class ReadOnlyEvidenceManifestTools:
    """Host-selected snapshot is fully validated before any manifest is returned."""

    def __init__(self, evidence_jsonl: Path):
        self._snapshot = Path(evidence_jsonl)

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if name != "build_evidence_manifest":
            raise ValueError("unavailable evidence manifest tool")
        if not isinstance(arguments, Mapping):
            raise ValueError("tool arguments must be an object")
        if set(arguments) - {"candidate_id", "max_evidence_ids"}:
            raise ValueError("unexpected tool arguments")
        candidate_id = arguments.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip() or len(candidate_id) > 256:
            raise ValueError("candidate_id must be a nonempty bounded identifier")
        limit = arguments.get("max_evidence_ids", 10)
        if type(limit) is not int or not 1 <= limit <= MAX_RECORDS:
            raise ValueError("max_evidence_ids must be an integer in [1, 25]")
        if not self._snapshot.is_file():
            raise FileNotFoundError("trusted evidence snapshot not present")
        if self._snapshot.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("evidence snapshot exceeds size budget")

        source_digest = hashlib.sha256()
        seen: set[str] = set()
        matched: list[str] = []
        with self._snapshot.open("rb") as stream:
            for lineno, raw in enumerate(stream, 1):
                if len(raw) > MAX_LINE_BYTES:
                    raise ValueError(f"evidence record exceeds size budget at line {lineno}")
                source_digest.update(raw)
                try:
                    row = _verify_evidence_row(json.loads(raw), lineno=lineno)
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise ValueError(f"invalid evidence JSONL at line {lineno}") from exc
                evidence_id = row["evidence_id"]
                if evidence_id in seen:
                    raise ValueError(f"duplicate evidence_id at line {lineno}")
                seen.add(evidence_id)
                if row["candidate_id"] == candidate_id:
                    matched.append(evidence_id)

        ordered = sorted(matched)
        snapshot_sha256 = source_digest.hexdigest()
        # Covers *all* matching evidence IDs even when the visible list is truncated.
        # Also ties the manifest to the exact complete input snapshot file bytes.
        canonical = json.dumps(
            {
                "schema_version": MANIFEST_VERSION,
                "candidate_id": candidate_id,
                "snapshot_sha256": snapshot_sha256,
                "evidence_ids": ordered,
            },
            ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
        manifest_id = "manifest:sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return {
            "schema_version": TOOL_SCHEMA_VERSION,
            "manifest_schema_version": MANIFEST_VERSION,
            "tool_name": name,
            "candidate_id": candidate_id,
            "operational_status": "SUCCEEDED",
            "scientific_verdict": "UNKNOWN",
            "domain_status": "UNQUALIFIED",
            "claim_authorized": False,
            "manifest_id": manifest_id,
            "snapshot_sha256": snapshot_sha256,
            "evidence_count": len(ordered),
            "returned_count": min(len(ordered), limit),
            "truncated": len(ordered) > limit,
            "evidence_ids": ordered[:limit],
            "limitations": [
                "MANIFEST_INDEX_NOT_A_SCIENTIFIC_VERDICT",
                "RECORD_HASH_VALIDATION_NOT_SOURCE_INDEPENDENCE",
                "MISSING_EVIDENCE_DOES_NOT_AUTHORIZE_PASS",
                "TRUNCATED_LIST_MUST_NOT_BE_TREATED_AS_COMPLETE",
            ],
        }


__all__ = ["ReadOnlyEvidenceManifestTools", "manifest_tool_spec"]
