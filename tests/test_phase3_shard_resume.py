"""Resume planning rejects unverified, duplicate or forged shard coverage."""
import copy

import pytest

from rhombus.domain.shard_contract import plan_record_shards
from rhombus.domain.shard_resume import plan_verified_shard_resume


def plan():
    return plan_record_shards(
        source_sha256="a"*64, protocol_id="phase3-frozen-v1",
        total_rows=10, rows_per_shard=4,
    )


def receipt(p, i):
    shard = p["shards"][i]
    return {
        **shard, "plan_sha256": p["plan_sha256"],
        "row_count": shard["end_row_exclusive"] - shard["start_row"],
        "output_sha256": "b"*64,
        "artifact_bytes_verified": True,
        "source_lineage_verified": True,
    }


def test_missing_shards_are_deterministic_and_do_not_authorize_execution():
    p = plan()
    result = plan_verified_shard_resume(shard_plan=p, verified_receipts=[receipt(p, 2)])
    assert [s["shard_index"] for s in result["pending_shards"]] == [0, 1]
    assert result["verified_completed_shards"] == 1
    assert result["execution_authorized"] is False
    assert result["claim_authorized"] is False
    assert result["scientific_verdict"] == "UNKNOWN"


def test_all_shards_still_does_not_claim_stream_or_merge_completion():
    p = plan()
    result = plan_verified_shard_resume(
        shard_plan=p, verified_receipts=[receipt(p, i) for i in [2, 0, 1]],
    )
    assert result["all_shard_artifacts_verified"] is True
    assert result["pending_shards"] == []
    assert result["source_stream_complete_attested"] is False
    assert result["merged_output_verified"] is False


@pytest.mark.parametrize("key,value", [
    ("artifact_bytes_verified", False),
    ("artifact_bytes_verified", 1),
    ("source_lineage_verified", False),
    ("source_lineage_verified", "true"),
    ("plan_sha256", "f"*64),
    ("row_count", 99),
    ("shard_index", True),
])
def test_unverified_or_corrupt_receipts_fail_closed(key, value):
    p = plan()
    r = receipt(p, 0)
    r[key] = value
    with pytest.raises(ValueError):
        plan_verified_shard_resume(shard_plan=p, verified_receipts=[r])


def test_duplicate_receipts_rejected():
    p = plan()
    with pytest.raises(ValueError, match="duplicate"):
        plan_verified_shard_resume(shard_plan=p, verified_receipts=[receipt(p, 0), receipt(p, 0)])


def test_tampered_plan_rejected():
    p = plan()
    bad = copy.deepcopy(p)
    bad["shards"][0]["start_row"] = 1
    with pytest.raises(ValueError):
        plan_verified_shard_resume(shard_plan=bad, verified_receipts=[])


def test_unexpected_fields_rejected():
    p = plan()
    bad = receipt(p, 0)
    bad["checkpoint_url"] = "https://untrusted.example"
    with pytest.raises(ValueError):
        plan_verified_shard_resume(shard_plan=p, verified_receipts=[bad])
