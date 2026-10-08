"""Cheap isolated Phase 3 shard coverage contract tests (no Kaggle network)."""
import copy
import pytest
from rhombus.domain.shard_contract import plan_record_shards, assess_shard_coverage


S = "a" * 64


def plan():
    return plan_record_shards(source_sha256=S, protocol_id="frozen-phase3", total_rows=11, rows_per_shard=4)


def receipt(p, i):
    row = p["shards"][i]
    return {**row, "plan_sha256": p["plan_sha256"],
            "row_count": row["end_row_exclusive"] - row["start_row"],
            "output_sha256": "b" * 64}


def test_deterministic_disjoint_partition_and_tail():
    p = plan()
    assert [(s["start_row"], s["end_row_exclusive"]) for s in p["shards"]] == [(0, 4), (4, 8), (8, 11)]
    assert plan() == p
    assert p["coverage_state"] == "PLANNED_NOT_EXECUTED"
    assert p["claim_authorized"] is False


def test_coverage_never_grants_scientific_pass():
    p = plan()
    partial = assess_shard_coverage(p, [receipt(p, 1)])
    assert partial["missing_shard_indices"] == [0, 2]
    done = assess_shard_coverage(p, [receipt(p, i) for i in (2, 0, 1)])
    assert done["coverage_state"] == "METADATA_COVERAGE_COMPLETE_UNATTESTED"
    assert done["missing_shard_indices"] == []
    assert done["output_bytes_verified"] is False
    assert done["source_byte_identity_verified"] is False
    assert done["scientific_verdict"] == "UNKNOWN"
    assert done["claim_authorized"] is False


@pytest.mark.parametrize("mutation", [
    lambda x: x.__setitem__("row_count", 99),
    lambda x: x.__setitem__("shard_index", True),
    lambda x: x.__setitem__("start_row", -1),
    lambda x: x.__setitem__("output_sha256", "not-a-digest"),
    lambda x: x.__setitem__("plan_sha256", "f"*64),
    lambda x: x.__setitem__("injected_path", "/etc/passwd"),
])
def test_poisoned_receipt_fails_closed(mutation):
    p = plan()
    r = receipt(p, 0)
    mutation(r)
    with pytest.raises(ValueError):
        assess_shard_coverage(p, [r])


def test_duplicate_and_tampered_plan_rejected():
    p = plan()
    with pytest.raises(ValueError, match="duplicate"):
        assess_shard_coverage(p, [receipt(p, 0), receipt(p, 0)])
    corrupt = copy.deepcopy(p)
    corrupt["shards"][1]["start_row"] = 3
    with pytest.raises(ValueError):
        assess_shard_coverage(corrupt, [])


@pytest.mark.parametrize("kwargs", [
    {"source_sha256": "a" * 63},
    {"rows_per_shard": 0},
    {"total_rows": True},
    {"total_rows": 100_000_001},
    {"rows_per_shard": 1, "total_rows": 4097},
    {"protocol_id": ""},
])
def test_invalid_plan_rejected(kwargs):
    args = {"source_sha256": S, "protocol_id": "frozen-phase3", "total_rows": 11, "rows_per_shard": 4}
    args.update(kwargs)
    with pytest.raises(ValueError):
        plan_record_shards(**args)
