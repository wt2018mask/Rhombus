"""Deterministic *planning* and coverage validation for future sAlex shards.

Pure local functions: no Kaggle, files, network, execution or scientific PASS.
The in-flight monolithic production kernel is intentionally unaffected.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

MAX_SHARDS = 4096
MAX_TOTAL_ROWS = 100_000_000
SCHEMA = "rhombus-phase3-shard-coverage-v1"


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} outside supported integer range")
    return value


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be exact lowercase SHA256")
    if any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{name} must be exact lowercase SHA256")
    return value


def plan_record_shards(
    *, source_sha256: str, protocol_id: str, total_rows: int, rows_per_shard: int,
) -> dict[str, Any]:
    """Record-ordinal partition plan, NOT a resumable byte/source checkpoint.

    Counting rows is insufficient to establish a valid LMDB member boundary,
    recover an interrupted tar.gz stream, or prove full source identity.
    """
    source_sha256 = _sha(source_sha256, "source_sha256")
    if not isinstance(protocol_id, str) or not 1 <= len(protocol_id) <= 256 or not protocol_id.strip():
        raise ValueError("protocol_id must be bounded nonempty text")
    total_rows = _integer(total_rows, "total_rows", 1, MAX_TOTAL_ROWS)
    rows_per_shard = _integer(rows_per_shard, "rows_per_shard", 1, MAX_TOTAL_ROWS)
    shard_count = (total_rows + rows_per_shard - 1) // rows_per_shard
    if shard_count > MAX_SHARDS:
        raise ValueError("shard count exceeds safe bound")
    specs = [
        {"shard_index": i, "start_row": i * rows_per_shard,
         "end_row_exclusive": min(total_rows, (i + 1) * rows_per_shard)}
        for i in range(shard_count)
    ]
    identity = {"schema_version": SCHEMA, "source_sha256": source_sha256,
                "protocol_id": protocol_id, "total_rows": total_rows,
                "shards": specs}
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        **identity, "plan_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "coverage_state": "PLANNED_NOT_EXECUTED",
        "source_byte_identity_verified": False,
        "scientific_verdict": "UNKNOWN",
        "claim_authorized": False,
    }


def assess_shard_coverage(plan: Mapping[str, Any], receipts: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Fail-closed validation of untrusted receipt *metadata*, not artifact bytes.

    Caller must independently check receipt signatures, file bytes, WAL-safe DB
    snapshots, exact source-member alignment and whole-stream hashes.
    """
    if not isinstance(plan, Mapping) or set(plan) != {
        "schema_version", "source_sha256", "protocol_id", "total_rows",
        "shards", "plan_sha256", "coverage_state", "source_byte_identity_verified",
        "scientific_verdict", "claim_authorized",
    }:
        raise ValueError("unexpected plan schema")
    shards = plan["shards"]
    if not isinstance(shards, list) or not 1 <= len(shards) <= MAX_SHARDS:
        raise ValueError("invalid shard array")
    expected = plan_record_shards(
        source_sha256=plan["source_sha256"], protocol_id=plan["protocol_id"],
        total_rows=plan["total_rows"],
        rows_per_shard=shards[0]["end_row_exclusive"],
    )
    if expected != plan:
        raise ValueError("plan identity or coverage mismatch")
    if not isinstance(receipts, list) or len(receipts) > len(shards):
        raise ValueError("receipt count exceeds bounded shard plan")
    seen: set[int] = set()
    for receipt in receipts:
        if not isinstance(receipt, Mapping) or set(receipt) != {
            "plan_sha256", "shard_index", "start_row", "end_row_exclusive",
            "output_sha256", "row_count",
        }:
            raise ValueError("unexpected receipt schema")
        if receipt["plan_sha256"] != plan["plan_sha256"]:
            raise ValueError("receipt plan binding mismatch")
        i = _integer(receipt["shard_index"], "shard_index", 0, len(shards) - 1)
        if i in seen:
            raise ValueError("duplicate shard receipt")
        seen.add(i)
        spec = shards[i]
        for k in ("start_row", "end_row_exclusive"):
            if type(receipt[k]) is not int or receipt[k] != spec[k]:
                raise ValueError("receipt range mismatch")
        if type(receipt["row_count"]) is not int or receipt["row_count"] != spec["end_row_exclusive"] - spec["start_row"]:
            raise ValueError("receipt row count mismatch")
        _sha(receipt["output_sha256"], "output_sha256")
    missing = [spec["shard_index"] for spec in shards if spec["shard_index"] not in seen]
    return {
        "schema_version": SCHEMA,
        "plan_sha256": plan["plan_sha256"],
        "received_shards": len(seen),
        "expected_shards": len(shards),
        "missing_shard_indices": missing,
        "coverage_state": "METADATA_COVERAGE_COMPLETE_UNATTESTED" if not missing else "INCOMPLETE",
        "source_byte_identity_verified": False,
        "output_bytes_verified": False,
        "scientific_verdict": "UNKNOWN",
        "claim_authorized": False,
        "limitations": [
            "ORDINAL_PARTITION_NOT_STREAM_RESUME",
            "UNTRUSTED_RECEIPTS_REQUIRE_HOST_BYTE_VALIDATION",
            "METADATA_COVERAGE_NOT_SCIENTIFIC_PASS",
        ],
    }


__all__ = ["plan_record_shards", "assess_shard_coverage"]
