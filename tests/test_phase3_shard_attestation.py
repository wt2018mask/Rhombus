"""No provider calls: provenance and shard coverage stay fail-closed."""
import pytest
from rhombus.domain.shard_contract import plan_record_shards
from rhombus.domain.shard_attestation import assess_attested_resume


def plan():
    return plan_record_shards(source_sha256="a"*64, protocol_id="frozen-v1", total_rows=9, rows_per_shard=4)


def attestation(p, i):
    x = p["shards"][i]
    return {**x, "row_count": x["end_row_exclusive"]-x["start_row"],
            "plan_sha256": p["plan_sha256"], "output_sha256": "b"*64,
            "artifact_sha256": "b"*64, "artifact_bytes_verified": True,
            "source_lineage_verified": True, "sqlite_integrity_verified": True}


def test_subset_requires_missing_work_and_never_dispatches():
    p = plan()
    result = assess_attested_resume(shard_plan=p, attestations=[attestation(p, 1)])
    assert [r["shard_index"] for r in result["pending_shards"]] == [0, 2]
    assert result["sqlite_verified_shards"] == 1
    assert result["external_checkpoint_durability_attested"] is False
    assert result["recovery_execution_authorized"] is False
    assert result["claim_authorized"] is False


def test_all_metadata_complete_is_not_scientific_completion():
    p = plan()
    result = assess_attested_resume(shard_plan=p, attestations=[attestation(p, i) for i in (2, 0, 1)])
    assert result["all_shard_artifacts_verified"]
    assert not result["source_stream_complete_attested"]
    assert result["scientific_verdict"] == "UNKNOWN"


@pytest.mark.parametrize("key,value", [
    ("artifact_bytes_verified", False), ("source_lineage_verified", False),
    ("sqlite_integrity_verified", 1), ("artifact_sha256", "c"*64),
    ("plan_sha256", "d"*64), ("shard_index", True), ("row_count", 100),
])
def test_bad_attestation_rejected(key, value):
    p = plan()
    receipt = attestation(p, 0)
    receipt[key] = value
    with pytest.raises(ValueError):
        assess_attested_resume(shard_plan=p, attestations=[receipt])


def test_duplicate_attestation_and_extra_fields_rejected():
    p = plan()
    a = attestation(p, 0)
    with pytest.raises(ValueError, match="duplicate"):
        assess_attested_resume(shard_plan=p, attestations=[a, a])
    a["file_path"] = "/secret"
    with pytest.raises(ValueError, match="schema"):
        assess_attested_resume(shard_plan=p, attestations=[a])
