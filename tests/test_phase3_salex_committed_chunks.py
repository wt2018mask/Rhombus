"""Offline interruption coverage for committed sAlex Kaggle diagnostic chunks.

No real original source, network access, Kaggle token, or heavy computation.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from rhombus.domain.membership import MembershipIndexRecord, build_membership_index
from scripts.development.salex_committed_chunks import (
    CommittedSalexChunkWriter, verify_committed_chunk,
)


def _records(count):
    return [
        MembershipIndexRecord(
            dataset_id="sAlex", record_id=f"shard#row-{i:03d}",
            source_locator=f"shard.aselmdb#{i}",
            composition_key="Li2O", site_count=3,
            structure_fingerprint_sha256=f"{i:064x}",
            prototype_group="fixture-only",
        )
        for i in range(count)
    ]


def _index(tmp_path, records, observer, *, batch_size=2):
    return build_membership_index(
        records, tmp_path / "index.sqlite",
        dataset_id="sAlex",
        source_file_sha256="a" * 64,
        fingerprint_protocol_id="fixture-fingerprint-v2",
        prototype_group_protocol_id="fixture-prototype-v2",
        batch_size=batch_size, on_committed_batch=observer,
    )


def test_multiple_source_partial_chunks_are_committed_and_replayable(tmp_path, capsys):
    observer = CommittedSalexChunkWriter(tmp_path / "partial", chunk_records=2)
    result = _index(tmp_path, _records(5), observer, batch_size=2)
    assert result.row_count == 5
    manifest_paths = sorted(observer.root.glob("*.json"))
    assert len(manifest_paths) == 2
    assert observer.committed == 5
    assert observer.last_complete == 4
    assert (observer.root / "salex-committed-0002.jsonl.gz.inflight").exists()
    previous = None
    for i, receipt in enumerate(manifest_paths):
        z = receipt.with_suffix(".jsonl.gz")
        assert z.exists()
        info = verify_committed_chunk(z, receipt)
        assert info["chunk_index"] == i
        assert info["first_record_ordinal"] == i * 2
        assert info["last_record_ordinal_exclusive"] == (i + 1) * 2
        assert info["prior_chunk_sha256"] == previous
        previous = info["sha256"]
        for name in (
            "full_salex_archive_sha256_verified", "source_complete",
            "training_membership_attested", "unseen_generalization_authorized",
        ):
            assert info[name] is False
    assert capsys.readouterr().out.count("SALEX_COMMITTED_DIAGNOSTIC_CHUNK ") == 2


def test_abort_during_next_batch_preserves_previous_full_chunk(tmp_path):
    observer = CommittedSalexChunkWriter(tmp_path / "partial", chunk_records=2)

    def incomplete_stream():
        yield from _records(3)
        raise RuntimeError("synthetic source interruption")

    with pytest.raises(RuntimeError, match="source interruption"):
        _index(tmp_path, incomplete_stream(), observer, batch_size=1)
    assert not (tmp_path / "index.sqlite").exists()  # Scientific DB aborted.
    done = observer.root / "salex-committed-0000.json"
    assert verify_committed_chunk(observer.root / "salex-committed-0000.jsonl.gz", done)[
        "committed_records_in_chunk"
    ] == 2
    assert not (observer.root / "salex-committed-0001.json").exists()
    assert (observer.root / "salex-committed-0001.jsonl.gz.inflight").exists()


def test_reject_hash_corruption_and_scientific_claim_escalation(tmp_path):
    writer = CommittedSalexChunkWriter(tmp_path / "partial", chunk_records=2)
    _index(tmp_path, _records(2), writer)
    archive = writer.root / "salex-committed-0000.jsonl.gz"
    receipt = writer.root / "salex-committed-0000.json"
    assert verify_committed_chunk(archive, receipt)["committed_records_in_chunk"] == 2
    changed = archive.read_bytes()
    archive.write_bytes(changed + b"changed")
    with pytest.raises(ValueError, match="tampered"):
        verify_committed_chunk(archive, receipt)
    archive.write_bytes(changed)
    record = json.loads(receipt.read_text())
    record["source_complete"] = True
    receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="tampered"):
        verify_committed_chunk(archive, receipt)


def test_no_reuse_of_checkpoint_directory_and_nonmonotonic_batches(tmp_path):
    root = tmp_path / "partials"
    writer = CommittedSalexChunkWriter(root, chunk_records=2)
    with pytest.raises(FileExistsError):
        CommittedSalexChunkWriter(root)
    records = _records(2)
    with pytest.raises(ValueError, match="nonmonotonic"):
        writer(records, 1)
    assert not list(root.iterdir())
    with pytest.raises(ValueError, match="invalid partial"):
        CommittedSalexChunkWriter(tmp_path / "other", chunk_records=0)


def test_production_kaggle_driver_writes_chunk_evidence_to_working_not_temp():
    root = Path(__file__).resolve().parents[1]
    code = (root / "scripts/kaggle/salex_phase3_full_run.py").read_text()
    cli = (root / "scripts/development/run_salex_wbm_overlap.py").read_text()
    assert 'str(OUTPUT / "rhombus_salex_partial_chunks")' in code
    assert '"--partial-output-dir"' in code and cli
    assert 'on_committed_batch=checkpoint' in cli
    assert "CommittedSalexChunkWriter" in cli
    assert 'OUTPUT = Path("/kaggle/working")' in code
    assert '"source_complete": False' in (
        root / "scripts/development/salex_committed_chunks.py"
    ).read_text()
    assert "training_membership_attested" in (
        root / "scripts/development/salex_committed_chunks.py"
    ).read_text()
