from __future__ import annotations

import hashlib
import io
from pathlib import Path
import tarfile

from ase import Atoms
from ase.db import connect

from rhombus.domain import (
    SalexSourceIdentity,
    build_salex_membership_index,
    fingerprint_candidate_count,
)


def _write_aselmdb(path: Path, atoms_list: list[Atoms]) -> None:
    with connect(str(path)) as database:
        for atoms in atoms_list:
            database.write(atoms)


def _make_archive(tmp_path: Path) -> bytes:
    shard_a = tmp_path / "a.aselmdb"
    shard_b = tmp_path / "b.aselmdb"
    _write_aselmdb(
        shard_a,
        [
            Atoms("Li2O", positions=[[0, 0, 0], [1, 0, 0], [0, 1, 0]]),
            Atoms("Li3N", positions=[[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]]),
        ],
    )
    _write_aselmdb(
        shard_b,
        [Atoms("Li2O", positions=[[0, 0, 0], [1, 0, 0], [0, 1, 0]])],
    )

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        archive.add(shard_a, arcname="train/part-a.aselmdb")
        archive.add(shard_b, arcname="train/part-b.aselmdb")
    return buffer.getvalue()


def _identity(payload: bytes) -> SalexSourceIdentity:
    return SalexSourceIdentity(
        size_bytes=len(payload),
        md5=hashlib.md5(payload).hexdigest(),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def _fingerprint(atoms: Atoms) -> str:
    payload = atoms.get_chemical_formula(mode="reduce").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _prototype(atoms: Atoms) -> str:
    return f"fixture:{atoms.get_chemical_formula(mode='reduce')}"


def test_salex_adapter_builds_hash_bound_index_from_streamed_aselmdb_tar(
    tmp_path: Path,
) -> None:
    payload = _make_archive(tmp_path)
    output = tmp_path / "salex.sqlite"

    summary = build_salex_membership_index(
        io.BytesIO(payload),
        output,
        expected_source_identity=_identity(payload),
        fingerprint=_fingerprint,
        prototype_group=_prototype,
        fingerprint_protocol_id="fixture-fingerprint-v1",
        prototype_group_protocol_id="fixture-prototype-v1",
        expected_record_count=3,
        scratch_dir=tmp_path,
        batch_size=1,
    )

    assert summary.dataset_id == "sAlex"
    assert summary.row_count == 3
    assert summary.source_file_sha256 == hashlib.sha256(payload).hexdigest()
    li2o = hashlib.sha256(b"Li2O").hexdigest()
    assert fingerprint_candidate_count(output, li2o) == 2
    assert list(tmp_path.glob("tmp*/salex-*.aselmdb")) == []


def test_salex_adapter_fails_closed_on_source_hash_mismatch(tmp_path: Path) -> None:
    payload = _make_archive(tmp_path)
    output = tmp_path / "salex.sqlite"
    observed = _identity(payload)
    wrong = SalexSourceIdentity(
        size_bytes=observed.size_bytes,
        md5=observed.md5,
        sha256="0" * 64,
    )

    try:
        build_salex_membership_index(
            io.BytesIO(payload),
            output,
            expected_source_identity=wrong,
            fingerprint=_fingerprint,
            prototype_group=_prototype,
            fingerprint_protocol_id="fixture-fingerprint-v1",
            prototype_group_protocol_id="fixture-prototype-v1",
            expected_record_count=3,
            scratch_dir=tmp_path,
            batch_size=1,
        )
    except ValueError as exc:
        assert "SHA256 mismatch" in str(exc)
    else:
        raise AssertionError("source mismatch must fail closed")

    assert output.exists() is False
    assert Path(f"{output}-wal").exists() is False
    assert Path(f"{output}-shm").exists() is False


def test_salex_adapter_fails_closed_on_record_count_mismatch(tmp_path: Path) -> None:
    payload = _make_archive(tmp_path)
    output = tmp_path / "salex.sqlite"

    try:
        build_salex_membership_index(
            io.BytesIO(payload),
            output,
            expected_source_identity=_identity(payload),
            fingerprint=_fingerprint,
            prototype_group=_prototype,
            fingerprint_protocol_id="fixture-fingerprint-v1",
            prototype_group_protocol_id="fixture-prototype-v1",
            expected_record_count=4,
            scratch_dir=tmp_path,
            batch_size=1,
        )
    except ValueError as exc:
        assert "record-count mismatch" in str(exc)
    else:
        raise AssertionError("record-count mismatch must fail closed")

    assert output.exists() is False
