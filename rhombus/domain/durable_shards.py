"""Read-only deterministic recovery from authenticated persisted shard evidence.

Only host-selected retrieved files are opened. Signatures bind immutable shard
identity to a separately provisioned source observer and storage receiver. No
Kaggle, upload, scheduling or scientific qualification is performed here.
"""

from __future__ import annotations

import hashlib
from contextlib import closing
from pathlib import Path
import sqlite3

from rhombus.evidence.receipts import (
    bounded_text,
    digest,
    evidence_sha256,
    exact_fields,
    integer,
    verify_evidence_receipt,
)
from .shard_contract import assess_shard_coverage

SCHEMA = "rhombus-persisted-source-shard-v1"
MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 100_000
MAX_TOTAL_BYTES = 64 * 1024 * 1024


def _file_bytes(path, root, expected_sha256, expected_length):
    if (
        not isinstance(path, Path)
        or not isinstance(root, Path)
        or root.is_symlink()
        or not root.is_dir()
    ):
        raise ValueError("host-bound artifact path and root required")
    if (
        path.is_symlink()
        or not path.resolve().is_relative_to(root.resolve())
        or not path.is_file()
    ):
        raise ValueError("missing/unconfined artifact")
    if Path(str(path) + "-wal").exists() or Path(str(path) + "-shm").exists():
        raise ValueError("artifact not finalized: WAL/SHM present")
    integer(expected_length, high=MAX_BYTES)
    if path.stat().st_size != expected_length:
        raise ValueError("artifact length mismatch")
    raw = path.read_bytes()
    if len(raw) != expected_length or hashlib.sha256(raw).hexdigest() != digest(
        expected_sha256
    ):
        raise ValueError("artifact SHA256 mismatch")
    return raw


def _read_records(
    path,
    root,
    expected_sha256,
    expected_length,
    source_sha256,
    protocol_sha256,
    start,
    end,
):
    before = _file_bytes(path, root, expected_sha256, expected_length)
    try:
        with closing(sqlite3.connect(":memory:")) as db:
            db.deserialize(before)  # Query exactly the bytes whose hash was checked.
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite integrity failure")
            objects = db.execute(
                "SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            ).fetchall()
            if sorted(objects) != [("metadata", "table"), ("records", "table")]:
                raise ValueError("unexpected SQLite tables/views/triggers")
            if db.execute("SELECT COUNT(*) FROM metadata").fetchone()[0] != 2:
                raise ValueError("unexpected SQLite metadata coverage")
            metadata_rows = db.execute("SELECT key,value FROM metadata").fetchall()
            metadata = dict(metadata_rows)
            if len(metadata_rows) != len(metadata) or metadata != {
                "source_sha256": source_sha256,
                "protocol_sha256": protocol_sha256,
            }:
                raise ValueError("SQLite source/protocol identity mismatch")
            if db.execute("SELECT COUNT(*) FROM records").fetchone()[0] != end - start:
                raise ValueError("missing/duplicate shard records")
            rows = db.execute(
                "SELECT ordinal,record_id,payload_sha256 FROM records ORDER BY ordinal"
            ).fetchall()
    except sqlite3.Error as exc:
        raise ValueError("invalid SQLite shard") from exc
    record_ids = set()
    for expected, row in enumerate(rows, start):
        ordinal, record_id, payload_sha256 = row
        if type(ordinal) is not int or ordinal != expected or record_id in record_ids:
            raise ValueError("duplicate/missing/overlapping record coverage")
        bounded_text(record_id)
        digest(payload_sha256)
        record_ids.add(record_id)
    after = _file_bytes(path, root, expected_sha256, expected_length)
    if after != before:
        raise ValueError("artifact changed during verification")
    return [list(row) for row in rows]


def _validate_identity(identity, plan, protocol_sha256, storage_epoch):
    exact_fields(
        identity,
        (
            "schema_version",
            "scope",
            "plan_sha256",
            "source_sha256",
            "protocol_sha256",
            "shard_index",
            "shard_count",
            "start_row",
            "end_row_exclusive",
            "row_count",
            "artifact_sha256",
            "artifact_bytes",
            "records_sha256",
            "storage_epoch",
            "storage_namespace",
            "completion_state",
            "persistence_state",
        ),
        "durable shard",
    )
    if identity["schema_version"] != SCHEMA or identity["scope"] not in (
        "SYNTHETIC",
        "EXTERNAL",
    ):
        raise ValueError("unsupported durable shard schema")
    index = integer(identity["shard_index"], low=0, high=len(plan["shards"]) - 1)
    expected = plan["shards"][index]
    if (
        identity["plan_sha256"] != plan["plan_sha256"]
        or identity["source_sha256"] != plan["source_sha256"]
        or identity["protocol_sha256"] != digest(protocol_sha256)
        or plan["protocol_id"] != "sha256:" + protocol_sha256
    ):
        raise ValueError("shard source/protocol/plan mismatch")
    if type(identity["shard_count"]) is not int or identity["shard_count"] != len(
        plan["shards"]
    ):
        raise ValueError("shard ordinal/total count mismatch")
    for field in ("start_row", "end_row_exclusive"):
        if type(identity[field]) is not int or identity[field] != expected[field]:
            raise ValueError("missing/overlapping shard range")
    if (
        type(identity["row_count"]) is not int
        or identity["row_count"]
        != expected["end_row_exclusive"] - expected["start_row"]
    ):
        raise ValueError("shard row count mismatch")
    integer(identity["row_count"], high=MAX_ROWS)
    integer(identity["artifact_bytes"], high=MAX_BYTES)
    for field in ("artifact_sha256", "records_sha256"):
        digest(identity[field])
    bounded_text(identity["storage_namespace"])
    if identity["storage_epoch"] != bounded_text(storage_epoch):
        raise ValueError("stale/replayed persistence epoch")
    if identity["completion_state"] != "COMPLETED" or identity[
        "persistence_state"
    ] not in ("LOCAL_ONLY", "PERSISTED"):
        raise ValueError("unfinalized checkpoint cannot be resumed")
    return index


def _verified_shards(
    *,
    shard_plan,
    checkpoints,
    artifacts,
    trusted_issuers,
    protocol_sha256,
    storage_epoch,
    trusted_root,
    storage_namespace,
    development_group,
):
    assess_shard_coverage(
        shard_plan, []
    )  # Recompute exact existing partition identity.
    if shard_plan["total_rows"] > MAX_ROWS:
        raise ValueError("recovery assessment exceeds bounded total row budget")
    digest(protocol_sha256)
    bounded_text(storage_namespace)
    bounded_text(development_group)
    if not isinstance(checkpoints, list) or len(checkpoints) > len(
        shard_plan["shards"]
    ):
        raise ValueError("duplicate/excess shard candidates")
    completed = {}
    seen = set()
    receipt_seen = set()
    record_ids = set()
    total_bytes = 0
    for checkpoint in checkpoints:
        exact_fields(
            checkpoint,
            ("identity", "source_receipt", "storage_receipt"),
            "checkpoint proof",
        )
        identity = checkpoint["identity"]
        index = _validate_identity(identity, shard_plan, protocol_sha256, storage_epoch)
        if index in seen:
            raise ValueError("duplicate/conflicting shard versions")
        seen.add(index)
        if identity["storage_namespace"] != storage_namespace:
            raise ValueError("unverified storage receiver namespace")
        if identity["persistence_state"] == "LOCAL_ONLY":
            if checkpoint["storage_receipt"] is not None:
                raise ValueError("local-only checkpoint carries fabricated persistence")
            continue  # Local finalization never removes pending work.
        total_bytes += identity["artifact_bytes"]
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("recovery assessment exceeds aggregate byte budget")
        subject = evidence_sha256(identity)
        authorities = []
        for key, role, event in (
            ("source_receipt", "source_observer", "shard_source_audited"),
            ("storage_receipt", "storage_receiver", "shard_persisted"),
        ):
            receipt = checkpoint[key]
            authority = verify_evidence_receipt(
                receipt,
                trusted_issuers=trusted_issuers,
                role=role,
                event=event,
                subject_sha256=subject,
                context_sha256=shard_plan["plan_sha256"],
                scope=identity["scope"],
            )
            if authority.independence_group == development_group:
                raise ValueError(
                    "producer assertion is not independent persistence/source evidence"
                )
            receipt_id = evidence_sha256(receipt)
            if receipt_id in receipt_seen:
                raise ValueError("duplicated persistence/source receipt")
            receipt_seen.add(receipt_id)
            authorities.append(authority)
        if authorities[0].independence_group == authorities[1].independence_group:
            raise ValueError("storage and source observation must be independent")
        if (
            checkpoint["storage_receipt"]["previous_receipt_sha256"]
            != evidence_sha256(checkpoint["source_receipt"])
            or checkpoint["storage_receipt"]["sequence"]
            <= checkpoint["source_receipt"]["sequence"]
        ):
            raise ValueError("persistence predates source audit")
        path = artifacts.get(identity["artifact_sha256"])
        rows = _read_records(
            path,
            trusted_root,
            identity["artifact_sha256"],
            identity["artifact_bytes"],
            identity["source_sha256"],
            protocol_sha256,
            identity["start_row"],
            identity["end_row_exclusive"],
        )
        if evidence_sha256(rows) != identity["records_sha256"]:
            raise ValueError(
                "record coverage differs from independent source observation"
            )
        ids = {row[1] for row in rows}
        if ids & record_ids:
            raise ValueError("duplicate source records across shards")
        record_ids.update(ids)
        completed[index] = (identity, rows)
    return completed


def plan_durable_shard_resume(
    *,
    shard_plan,
    checkpoints,
    artifacts,
    trusted_issuers,
    protocol_sha256,
    storage_epoch,
    trusted_root,
    storage_namespace="synthetic-fixtures",
    development_group="development",
):
    completed = _verified_shards(
        shard_plan=shard_plan,
        checkpoints=checkpoints,
        artifacts=artifacts,
        trusted_issuers=trusted_issuers,
        protocol_sha256=protocol_sha256,
        storage_epoch=storage_epoch,
        trusted_root=trusted_root,
        storage_namespace=storage_namespace,
        development_group=development_group,
    )
    pending = [
        dict(row) for row in shard_plan["shards"] if row["shard_index"] not in completed
    ]
    return {
        "schema_version": "rhombus-durable-shard-resume-v1",
        "plan_sha256": shard_plan["plan_sha256"],
        "verified_completed_shards": sorted(completed),
        "pending_shards": pending,
        "verified_rows": sum(len(rows) for _, rows in completed.values()),
        "all_shards_verified": not pending,
        "external_assertions_authenticated": bool(completed)
        and all(v[0]["scope"] == "EXTERNAL" for v in completed.values()),
        "merged_output_verified": False,
        "real_kaggle_crash_recovery_verified": False,
        "execution_authorized": False,
        "scientific_verdict": "UNKNOWN",
        "claim_authorized": False,
        "limitations": [
            "SIGNED_ASSERTIONS_REQUIRE_EXTERNAL_TRUST_GOVERNANCE",
            "SOURCE_RECORD_AUDIT_NOT_FULL_STREAM_RESTART_PROOF",
            "NO_SCHEDULING_OR_PRODUCTION_KAGGLE",
        ],
    }


def verify_completed_shard_merge(
    *, merged_path, merged_sha256, merged_bytes, **arguments
):
    completed = _verified_shards(**arguments)
    plan = arguments["shard_plan"]
    if len(completed) != len(plan["shards"]):
        raise ValueError("incomplete final merge: persisted shards missing")
    if plan["total_rows"] > MAX_ROWS:
        raise ValueError("merge exceeds bounded verification budget")
    expected = [row for index in sorted(completed) for row in completed[index][1]]
    rows = _read_records(
        merged_path,
        arguments["trusted_root"],
        merged_sha256,
        merged_bytes,
        plan["source_sha256"],
        arguments["protocol_sha256"],
        0,
        plan["total_rows"],
    )
    if rows != expected:
        raise ValueError("final merge differs from verified shard records")
    return {
        "merged_output_verified": True,
        "verified_rows": len(rows),
        "merged_sha256": merged_sha256,
        "real_kaggle_crash_recovery_verified": False,
        "scientific_verdict": "UNKNOWN",
        "claim_authorized": False,
        "execution_authorized": False,
    }
