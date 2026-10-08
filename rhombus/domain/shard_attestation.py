"""Join host-attested checkpoint provenance to a bounded, offline resume plan.

No file paths, provider access, dispatch, scientific qualification or automatic
trust in a self-reported receipt. The host must supply independently verified
byte/source/ordinal coverage attestations before calling this function.
"""
from __future__ import annotations

from typing import Any, Mapping

from .shard_contract import _sha
from .shard_resume import plan_verified_shard_resume


def assess_attested_resume(
    *, shard_plan: Mapping[str, Any], attestations: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Accept only exact-range, SHA-bound host attestations and plan missing work."""
    if not isinstance(attestations, list):
        raise ValueError("attestations must be a bounded list")
    receipts: list[dict[str, Any]] = []
    for a in attestations:
        if not isinstance(a, Mapping) or set(a) != {
            "plan_sha256", "shard_index", "start_row", "end_row_exclusive",
            "row_count", "output_sha256", "artifact_sha256",
            "artifact_bytes_verified", "source_lineage_verified",
            "sqlite_integrity_verified",
        }:
            raise ValueError("unexpected attestation schema")
        if a["artifact_bytes_verified"] is not True or a["source_lineage_verified"] is not True or a["sqlite_integrity_verified"] is not True:
            raise ValueError("host attestation incomplete")
        if _sha(a["output_sha256"], "output_sha256") != _sha(a["artifact_sha256"], "artifact_sha256"):
            raise ValueError("artifact and shard digest mismatch")
        receipts.append({k: a[k] for k in (
            "plan_sha256", "shard_index", "start_row", "end_row_exclusive",
            "row_count", "output_sha256",
        )} | {"artifact_bytes_verified": True, "source_lineage_verified": True})
    plan = plan_verified_shard_resume(shard_plan=shard_plan, verified_receipts=receipts)
    return {
        **plan,
        "schema_version": "rhombus-phase3-attested-resume-v1",
        "sqlite_verified_shards": len(receipts),
        "external_checkpoint_durability_attested": False,
        "recovery_execution_authorized": False,
        "limitations": plan["limitations"] + [
            "ATTESTATIONS_MUST_BE_GENERATED_BY_TRUSTED_HOST_NOT_AGENT",
            "NO_EXTERNAL_DURABILITY_OR_SOURCE_STREAM_COMPLETION_INFERENCE",
        ],
    }


__all__ = ["assess_attested_resume"]
