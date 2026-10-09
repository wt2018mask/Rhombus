"""Streaming sAlex source adapter for Rhombus 2.0 training exposure audits."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
from typing import BinaryIO, Callable, Iterator

from ase import Atoms
from ase.db import connect
from pymatgen.core import Composition

from .membership import MembershipIndexRecord, MembershipIndexSummary, build_membership_index


FingerprintFunction = Callable[[Atoms], str]
PrototypeGroupFunction = Callable[[Atoms], str]
StructureObserver = Callable[[MembershipIndexRecord, Atoms], None]


@dataclass(frozen=True)
class SalexSourceIdentity:
    size_bytes: int
    md5: str
    sha256: str

    def __post_init__(self) -> None:
        if self.size_bytes <= 0:
            raise ValueError("size_bytes must be positive")
        _validate_digest("md5", self.md5, 32)
        _validate_digest("sha256", self.sha256, 64)


class _HashingReader:
    def __init__(self, source: BinaryIO) -> None:
        self._source = source
        self._md5 = hashlib.md5()  # noqa: S324 - source identity compatibility
        self._sha256 = hashlib.sha256()
        self._size = 0

    def read(self, size: int = -1) -> bytes:
        data = self._source.read(size)
        if data:
            self._md5.update(data)
            self._sha256.update(data)
            self._size += len(data)
        return data

    def drain(self, chunk_size: int = 8 * 1024 * 1024) -> None:
        while self.read(chunk_size):
            pass

    @property
    def identity(self) -> SalexSourceIdentity:
        return SalexSourceIdentity(
            size_bytes=self._size,
            md5=self._md5.hexdigest(),
            sha256=self._sha256.hexdigest(),
        )


def _validate_digest(name: str, value: str, length: int) -> None:
    if len(value) != length:
        raise ValueError(f"{name} must be a {length}-character hexadecimal digest")
    int(value, 16)


def _validate_member_name(name: str) -> str:
    member = PurePosixPath(name)
    if member.is_absolute() or ".." in member.parts:
        raise ValueError(f"unsafe archive member path: {name}")
    return member.as_posix()


def _composition_key(atoms: Atoms) -> str:
    return Composition(atoms.get_chemical_formula()).reduced_formula


def _iter_aselmdb_atoms(path: Path) -> Iterator[Atoms]:
    with connect(str(path), readonly=True, use_lock_file=False) as database:
        for index in range(database.count()):
            yield database._get_row_by_index(index).toatoms()


def _verify_source_identity(
    observed: SalexSourceIdentity,
    expected: SalexSourceIdentity,
) -> None:
    if observed.size_bytes != expected.size_bytes:
        raise ValueError(
            "sAlex source size mismatch: "
            f"expected={expected.size_bytes} observed={observed.size_bytes}"
        )
    if observed.md5.lower() != expected.md5.lower():
        raise ValueError(
            f"sAlex source MD5 mismatch: expected={expected.md5} observed={observed.md5}"
        )
    if observed.sha256.lower() != expected.sha256.lower():
        raise ValueError(
            "sAlex source SHA256 mismatch: "
            f"expected={expected.sha256} observed={observed.sha256}"
        )


def iter_salex_membership_records(
    source: BinaryIO,
    *,
    expected_source_identity: SalexSourceIdentity,
    fingerprint: FingerprintFunction,
    prototype_group: PrototypeGroupFunction,
    expected_record_count: int | None = None,
    scratch_dir: str | Path | None = None,
    on_structure: StructureObserver | None = None,
    max_records: int | None = None,
) -> Iterator[MembershipIndexRecord]:
    """Stream a sAlex tar.gz archive and yield membership records.

    The compressed archive is never persisted. Each .aselmdb member is copied
    to one temporary shard because ASE LMDB requires a filesystem path. The
    shard is deleted before the next archive member is processed. Source byte
    identity is verified only after the stream is fully consumed; mismatch
    raises so the enclosing membership builder deletes its partial index. A
    max_records limit is reserved for non-authoritative throughput pilots; an
    early return intentionally skips complete-source identity/count checks.
    """

    if expected_record_count is not None and expected_record_count <= 0:
        raise ValueError("expected_record_count must be positive")
    if max_records is not None and max_records <= 0:
        raise ValueError("max_records must be positive when supplied")

    hashing_source = _HashingReader(source)
    shard_count = 0
    record_count = 0

    with tempfile.TemporaryDirectory(dir=scratch_dir) as temporary:
        temp_root = Path(temporary)
        with tarfile.open(fileobj=hashing_source, mode="r|gz") as archive:
            for member in archive:
                if not member.isfile() or not member.name.endswith(".aselmdb"):
                    continue

                member_name = _validate_member_name(member.name)
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError(f"unable to read archive member: {member_name}")

                shard_path = temp_root / f"salex-{shard_count:06d}.aselmdb"
                try:
                    with shard_path.open("wb") as handle:
                        shutil.copyfileobj(extracted, handle, length=8 * 1024 * 1024)

                    for row_index, atoms in enumerate(_iter_aselmdb_atoms(shard_path)):
                        locator = f"{member_name}#{row_index}"
                        record = MembershipIndexRecord(
                            dataset_id="sAlex",
                            record_id=locator,
                            source_locator=locator,
                            composition_key=_composition_key(atoms),
                            site_count=len(atoms),
                            structure_fingerprint_sha256=fingerprint(atoms),
                            prototype_group=prototype_group(atoms),
                        )
                        if on_structure is not None:
                            on_structure(record, atoms)
                        yield record
                        record_count += 1
                        if max_records is not None and record_count >= max_records:
                            return
                finally:
                    extracted.close()
                    shard_path.unlink(missing_ok=True)

                shard_count += 1

        hashing_source.drain()

    if shard_count == 0:
        raise ValueError("sAlex archive contains no .aselmdb members")

    observed = hashing_source.identity
    _verify_source_identity(observed, expected_source_identity)

    if expected_record_count is not None and record_count != expected_record_count:
        raise ValueError(
            "sAlex record-count mismatch: "
            f"expected={expected_record_count} observed={record_count}"
        )


def build_salex_membership_index(
    source: BinaryIO,
    db_path: str | Path,
    *,
    expected_source_identity: SalexSourceIdentity,
    fingerprint: FingerprintFunction,
    prototype_group: PrototypeGroupFunction,
    fingerprint_protocol_id: str,
    prototype_group_protocol_id: str,
    expected_record_count: int | None = None,
    scratch_dir: str | Path | None = None,
    batch_size: int = 1000,
    on_structure: StructureObserver | None = None,
    on_committed_batch: Callable[[list[MembershipIndexRecord], int], None] | None = None,
) -> MembershipIndexSummary:
    """Build a source-hash-bound sAlex membership index from a tar.gz stream."""

    records = iter_salex_membership_records(
        source,
        expected_source_identity=expected_source_identity,
        fingerprint=fingerprint,
        prototype_group=prototype_group,
        expected_record_count=expected_record_count,
        scratch_dir=scratch_dir,
        on_structure=on_structure,
        on_committed_batch=on_committed_batch,
    )
    return build_membership_index(
        records,
        db_path,
        dataset_id="sAlex",
        source_file_sha256=expected_source_identity.sha256,
        fingerprint_protocol_id=fingerprint_protocol_id,
        prototype_group_protocol_id=prototype_group_protocol_id,
        batch_size=batch_size,
        on_committed_batch=on_committed_batch,
    )


def build_salex_membership_index_with_frozen_protocols(
    source: BinaryIO,
    db_path: str | Path,
    *,
    expected_source_identity: SalexSourceIdentity,
    expected_record_count: int | None = None,
    scratch_dir: str | Path | None = None,
    batch_size: int = 1000,
    on_structure: StructureObserver | None = None,
    on_committed_batch: Callable[[list[MembershipIndexRecord], int], None] | None = None,
) -> MembershipIndexSummary:
    """Build sAlex index using the frozen Phase 3 candidate/prototype executors."""

    from .structure_protocols import (
        CANDIDATE_FINGERPRINT_PROTOCOL_ID,
        PROTOTYPE_GROUP_PROTOCOL_ID,
        matbench_prototype_group,
        structure_candidate_fingerprint_sha256,
    )

    return build_salex_membership_index(
        source,
        db_path,
        expected_source_identity=expected_source_identity,
        fingerprint=structure_candidate_fingerprint_sha256,
        prototype_group=matbench_prototype_group,
        fingerprint_protocol_id=CANDIDATE_FINGERPRINT_PROTOCOL_ID,
        prototype_group_protocol_id=PROTOTYPE_GROUP_PROTOCOL_ID,
        expected_record_count=expected_record_count,
        scratch_dir=scratch_dir,
        batch_size=batch_size,
        on_structure=on_structure,
        on_committed_batch=on_committed_batch,
    )
