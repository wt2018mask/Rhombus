"""Pure offline resume planning for trusted, independently verified shard receipts.

This module does not read external files, select arbitrary file paths, access
Kaggle, submit work, or infer scientific qualification. The host must first
verify each artifact's bytes, SQLite integrity and receipt-to-source lineage.
"""
from __future__ import annotations

from typing import Any, Mapping

from .shard_contract import assess_shard_coverage


def plan_verified_shard_resume(
    *, shard_plan: Mapping[str, Any], verified_receipts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return uncompleted shard ranges; trust only host-attested verification.

    Each receipt must carry the exact shard contract's six metadata fields plus
    two true host-owned attestation flags. Metadata completeness alone is never
    treated as byte or source provenance verification.
    """
    if not isinstance(verified_receipts, list):
        raise ValueError("verified_receipts must be a list")
    plain: list[dict[str, Any]] = []
    for receipt in verified_receipts:
        if not isinstance(receipt, Mapping) or set(receipt) != {
            "plan_sha256", "shard_index", "start_row", "end_row_exclusive",
            "output_sha256", "row_count", "artifact_bytes_verified",
            "source_lineage_verified",
        }:
            raise ValueError("unexpected verified receipt schema")
        if receipt["artifact_bytes_verified"] is not True or receipt["source_lineage_verified"] is not True:
            raise ValueError("checkpoint has not been independently verified")
        plain.append({k: receipt[k] for k in (
            "plan_sha256", "shard_index", "start_row", "end_row_exclusive",
            "output_sha256", "row_count",
        )})
    assessment = assess_shard_coverage(shard_plan, plain)
    missing_ids = assessment["missing_shard_indices"]
    pending = [dict(shard_plan["shards"][i]) for i in missing_ids]
    return {
        "schema_version": "rhombus-phase3-verified-resume-plan-v1",
        "plan_sha256": assessment["plan_sha256"],
        "verified_completed_shards": assessment["received_shards"],
        "expected_shards": assessment["expected_shards"],
        "pending_shards": pending,
        "all_shard_artifacts_verified": not pending,
        "source_stream_complete_attested": False,
        "merged_output_verified": False,
        "scientific_verdict": "UNKNOWN",
        "claim_authorized": False,
        "execution_authorized": False,
        "limitations": [
            "HOST_OWNED_RECEIPT_ATTESTATION_REQUIRED",
            "VERIFIED_SHARDS_NOT_A_MERGED_INDEX",
            "SOURCE_STREAM_COMPLETENESS_UNATTESTED",
            "NO_KAGGLE_OR_SCHEDULER_SIDE_EFFECTS",
        ],
    }


__all__ = ["plan_verified_shard_resume"]
