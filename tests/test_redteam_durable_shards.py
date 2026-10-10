from rhombus.domain.durable_shards import plan_durable_shard_resume


def test_self_reported_persistence_is_not_verified():
    import pytest

    with pytest.raises(ValueError):
        plan_durable_shard_resume(
            shard_plan={},
            checkpoints=[{"persisted": True}],
            artifacts={},
            trusted_issuers={},
            protocol_sha256="a" * 64,
            storage_epoch="synthetic-v1",
            trusted_root=None,
        )


import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import sqlite3
import pytest

from rhombus.domain.durable_shards import verify_completed_shard_merge
from rhombus.domain.checkpoint_staging import stage_verified_checkpoint
from rhombus.domain.checkpoint_bundle import (
    pack_checkpoint_parts,
    verify_checkpoint_parts,
)
from rhombus.evidence.receipts import evidence_sha256
from tests.redteam_batch_b_fixtures import shard_fixture, sqlite_records


def test_interruptions_before_finalization_and_before_persistence_remain_pending(
    tmp_path,
):
    args = shard_fixture(tmp_path)
    all_checkpoints = args["checkpoints"]
    args["checkpoints"] = []
    assert len(plan_durable_shard_resume(**args)["pending_shards"]) == 3
    local = copy.deepcopy(all_checkpoints[0])
    local["identity"]["persistence_state"] = "LOCAL_ONLY"
    local["storage_receipt"] = None
    args["checkpoints"] = [local]
    assert len(plan_durable_shard_resume(**args)["pending_shards"]) == 3
    args["checkpoints"] = [all_checkpoints[1]]
    report = plan_durable_shard_resume(**args)
    assert report["verified_completed_shards"] == [1]
    assert [row["shard_index"] for row in report["pending_shards"]] == [0, 2]
    assert report["verified_rows"] == 3
    assert not report["execution_authorized"]


def test_persistence_retrieval_and_continuation_are_deterministic_without_double_counting(
    tmp_path,
):
    args = shard_fixture(tmp_path)
    original = plan_durable_shard_resume(**args)
    args["checkpoints"].reverse()
    assert plan_durable_shard_resume(**args) == original
    assert original["all_shards_verified"]
    assert original["verified_rows"] == 8
    assert not original["external_assertions_authenticated"]
    assert not original["real_kaggle_crash_recovery_verified"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert (
            list(pool.map(lambda _: plan_durable_shard_resume(**args), range(2)))
            == [original] * 2
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_remote",
        "corrupted_remote",
        "stale_epoch",
        "duplicate",
        "conflicting",
        "missing_receipt",
        "forged_receipt",
        "wrong_source",
        "wrong_protocol",
        "wrong_range",
        "wrong_count",
        "wrong_total",
        "unfinalized",
        "wrong_namespace",
        "wrong_length",
        "source_record_commitment",
        "path_traversal",
        "wal",
        "early_persistence",
    ],
)
def test_shard_adversarial_rejection(tmp_path, mutation):
    args = shard_fixture(tmp_path)
    cp = args["checkpoints"][0]
    identity = cp["identity"]
    path = args["artifacts"][identity["artifact_sha256"]]
    if mutation == "missing_remote":
        path.unlink()
    elif mutation == "corrupted_remote":
        path.write_bytes(b"broken")
    elif mutation == "stale_epoch":
        args["storage_epoch"] = "synthetic-new-epoch"
    elif mutation == "duplicate":
        args["checkpoints"][1] = copy.deepcopy(cp)
    elif mutation == "conflicting":
        args["checkpoints"][1]["identity"]["shard_index"] = 0
    elif mutation == "missing_receipt":
        cp["storage_receipt"] = None
    elif mutation == "forged_receipt":
        cp["storage_receipt"]["signature"] = "b" * 128
    elif mutation == "wrong_source":
        identity["source_sha256"] = "b" * 64
    elif mutation == "wrong_protocol":
        identity["protocol_sha256"] = "b" * 64
    elif mutation == "wrong_range":
        identity["start_row"] = 1
    elif mutation == "wrong_count":
        identity["row_count"] = 2
    elif mutation == "wrong_total":
        identity["shard_count"] = 100
    elif mutation == "unfinalized":
        identity["completion_state"] = "WRITING"
    elif mutation == "wrong_namespace":
        args["storage_namespace"] = "unverified-receiver"
    elif mutation == "wrong_length":
        identity["artifact_bytes"] += 1
    elif mutation == "source_record_commitment":
        identity["records_sha256"] = "b" * 64
    elif mutation == "path_traversal":
        args["trusted_root"] = tmp_path / "different-root"
    elif mutation == "wal":
        path.with_name(path.name + "-wal").write_bytes(b"unfinalized")
    elif mutation == "early_persistence":
        cp["storage_receipt"], cp["source_receipt"] = (
            cp["source_receipt"],
            cp["storage_receipt"],
        )
    with pytest.raises(ValueError):
        plan_durable_shard_resume(**args)


def test_sqlite_duplicate_coverage_rejected_even_with_valid_hash_and_signed_receipts(
    tmp_path,
):
    args = shard_fixture(tmp_path)
    cp = args["checkpoints"][0]
    identity = cp["identity"]
    path = args["artifacts"][identity["artifact_sha256"]]
    with sqlite3.connect(path) as db:
        db.execute("UPDATE records SET ordinal=0")
    rebind_shard(args, cp, path)
    with pytest.raises(ValueError, match="record coverage"):
        plan_durable_shard_resume(**args)


def rebind_shard(args, cp, path):
    from tests.redteam_batch_b_fixtures import receipt

    identity = cp["identity"]
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    args["artifacts"][sha] = path
    identity["artifact_sha256"] = sha
    identity["artifact_bytes"] = path.stat().st_size
    context = args["shard_plan"]["plan_sha256"]
    subject = evidence_sha256(identity)
    cp["source_receipt"] = receipt("source", "shard_source_audited", subject, context)
    cp["storage_receipt"] = receipt(
        "receiver",
        "shard_persisted",
        subject,
        context,
        sequence=2,
        previous=evidence_sha256(cp["source_receipt"]),
    )


def test_duplicate_source_records_across_ranges_are_rejected(tmp_path):
    args = shard_fixture(tmp_path)
    cp = args["checkpoints"][1]
    identity = cp["identity"]
    path = args["artifacts"][identity["artifact_sha256"]]
    with sqlite3.connect(path) as db:
        db.execute("UPDATE records SET record_id='synthetic-record-0' WHERE ordinal=3")
        rows = [
            list(row)
            for row in db.execute(
                "SELECT ordinal,record_id,payload_sha256 FROM records ORDER BY ordinal"
            )
        ]
    identity["records_sha256"] = evidence_sha256(rows)
    rebind_shard(args, cp, path)
    with pytest.raises(ValueError, match="across shards"):
        plan_durable_shard_resume(**args)


def test_multipart_corruption_and_missing_part_are_rejected(tmp_path):
    args = shard_fixture(tmp_path)
    source = next(iter(args["artifacts"].values()))
    parts = tmp_path / "parts"
    parts.mkdir()
    pack_checkpoint_parts(
        source=source, output_dir=parts, bundle_id="synthetic", part_bytes=1024
    )
    checked = verify_checkpoint_parts(output_dir=parts, bundle_id="synthetic")
    assert checked["verified_parts"] > 1
    part = parts / "synthetic.part-00000"
    original = part.read_bytes()
    part.write_bytes(b"!" + original[1:])
    with pytest.raises(ValueError, match="checksum"):
        verify_checkpoint_parts(output_dir=parts, bundle_id="synthetic")
    part.write_bytes(original)
    part.unlink()
    with pytest.raises(ValueError, match="missing"):
        verify_checkpoint_parts(output_dir=parts, bundle_id="synthetic")


def test_concurrent_local_staging_never_overwrites_completed_pair(tmp_path):
    args = shard_fixture(tmp_path)
    source = next(iter(args["artifacts"].values()))
    root = tmp_path / "stage"
    root.mkdir()

    def stage(_):
        try:
            return stage_verified_checkpoint(
                finalized_source=source,
                trusted_directory=root,
                checkpoint_id="synthetic",
                expected_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                source_sha256=args["shard_plan"]["source_sha256"],
                row_count=3,
            )
        except FileExistsError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(stage, range(2)))
    assert sum(result is not None for result in results) == 1
    assert (root / "synthetic.sqlite").read_bytes() == source.read_bytes()
    assert (root / "synthetic.manifest.json").is_file()


def test_final_merge_requires_complete_coverage_and_exact_retained_rows(tmp_path):
    args = shard_fixture(tmp_path)
    rows = []
    for cp in args["checkpoints"]:
        with sqlite3.connect(
            args["artifacts"][cp["identity"]["artifact_sha256"]]
        ) as db:
            rows.extend(
                db.execute(
                    "SELECT ordinal,record_id,payload_sha256 FROM records ORDER BY ordinal"
                )
            )
    path = sqlite_records(
        tmp_path / "merged.sqlite",
        rows,
        args["shard_plan"]["source_sha256"],
        args["protocol_sha256"],
    )
    merge = {
        "merged_path": path,
        "merged_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "merged_bytes": path.stat().st_size,
    }
    assert verify_completed_shard_merge(**args, **merge)["verified_rows"] == 8
    args["checkpoints"].pop()
    with pytest.raises(ValueError, match="incomplete final merge"):
        verify_completed_shard_merge(**args, **merge)


def test_valid_sqlite_merge_cannot_silently_replace_verified_records(tmp_path):
    args = shard_fixture(tmp_path)
    rows = []
    for cp in args["checkpoints"]:
        with sqlite3.connect(
            args["artifacts"][cp["identity"]["artifact_sha256"]]
        ) as db:
            rows.extend(
                db.execute(
                    "SELECT ordinal,record_id,payload_sha256 FROM records ORDER BY ordinal"
                )
            )
    path = sqlite_records(
        tmp_path / "altered-merge.sqlite",
        rows,
        args["shard_plan"]["source_sha256"],
        args["protocol_sha256"],
    )
    with sqlite3.connect(path) as db:
        db.execute("UPDATE records SET payload_sha256=? WHERE ordinal=0", ("b" * 64,))
    with pytest.raises(ValueError, match="differs from verified"):
        verify_completed_shard_merge(
            **args,
            merged_path=path,
            merged_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            merged_bytes=path.stat().st_size,
        )


@pytest.mark.parametrize("budget", ["MAX_ROWS", "MAX_TOTAL_BYTES"])
def test_recovery_assessment_has_aggregate_resource_bounds(
    tmp_path, monkeypatch, budget
):
    import rhombus.domain.durable_shards as implementation

    args = shard_fixture(tmp_path)
    monkeypatch.setattr(implementation, budget, 1)
    with pytest.raises(ValueError, match="budget"):
        plan_durable_shard_resume(**args)
