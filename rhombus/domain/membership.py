"""Memory-bounded training-set membership index primitives for Rhombus 2.0."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterable, Iterator


def _validate_sha256(name: str, value: str) -> None:
    if len(value) != 64:
        raise ValueError(f"{name} must be a 64-character SHA256 digest")
    int(value, 16)


@dataclass(frozen=True)
class MembershipIndexRecord:
    dataset_id: str
    record_id: str
    source_locator: str
    composition_key: str
    site_count: int
    structure_fingerprint_sha256: str
    prototype_group: str

    def __post_init__(self) -> None:
        for name, value in (
            ("dataset_id", self.dataset_id),
            ("record_id", self.record_id),
            ("source_locator", self.source_locator),
            ("composition_key", self.composition_key),
            ("prototype_group", self.prototype_group),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.site_count <= 0:
            raise ValueError("site_count must be positive")
        _validate_sha256(
            "structure_fingerprint_sha256",
            self.structure_fingerprint_sha256,
        )


@dataclass(frozen=True)
class MembershipIndexSummary:
    dataset_id: str
    row_count: int
    source_file_sha256: str
    fingerprint_protocol_id: str
    prototype_group_protocol_id: str
    index_path: str


def _batched(
    records: Iterable[MembershipIndexRecord],
    batch_size: int,
) -> Iterator[list[MembershipIndexRecord]]:
    batch: list[MembershipIndexRecord] = []
    for record in records:
        batch.append(record)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def build_membership_index(
    records: Iterable[MembershipIndexRecord],
    db_path: str | Path,
    *,
    dataset_id: str,
    source_file_sha256: str,
    fingerprint_protocol_id: str,
    prototype_group_protocol_id: str,
    batch_size: int = 1000,
) -> MembershipIndexSummary:
    """Build a SQLite membership index without materializing the record stream."""

    if not dataset_id.strip():
        raise ValueError("dataset_id must be non-empty")
    _validate_sha256("source_file_sha256", source_file_sha256)
    if not fingerprint_protocol_id.strip():
        raise ValueError("fingerprint_protocol_id must be non-empty")
    if not prototype_group_protocol_id.strip():
        raise ValueError("prototype_group_protocol_id must be non-empty")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"membership index already exists: {path}")

    row_count = 0
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE membership (
                dataset_id TEXT NOT NULL,
                record_id TEXT NOT NULL,
                source_locator TEXT NOT NULL,
                composition_key TEXT NOT NULL,
                site_count INTEGER NOT NULL,
                structure_fingerprint_sha256 TEXT NOT NULL,
                prototype_group TEXT NOT NULL,
                PRIMARY KEY (dataset_id, record_id)
            )
            """
        )
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            (
                ("dataset_id", dataset_id),
                ("source_file_sha256", source_file_sha256),
                ("fingerprint_protocol_id", fingerprint_protocol_id),
                ("prototype_group_protocol_id", prototype_group_protocol_id),
            ),
        )

        insert_sql = """
            INSERT INTO membership(
                dataset_id,
                record_id,
                source_locator,
                composition_key,
                site_count,
                structure_fingerprint_sha256,
                prototype_group
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        for batch in _batched(records, batch_size):
            rows = []
            for record in batch:
                if record.dataset_id != dataset_id:
                    raise ValueError(
                        "membership record dataset_id does not match index dataset_id"
                    )
                rows.append(
                    (
                        record.dataset_id,
                        record.record_id,
                        record.source_locator,
                        record.composition_key,
                        record.site_count,
                        record.structure_fingerprint_sha256,
                        record.prototype_group,
                    )
                )
            connection.executemany(insert_sql, rows)
            row_count += len(rows)
            connection.commit()

        connection.execute(
            "CREATE INDEX idx_membership_fingerprint "
            "ON membership(structure_fingerprint_sha256)"
        )
        connection.execute(
            "CREATE INDEX idx_membership_composition_sites "
            "ON membership(composition_key, site_count)"
        )
        connection.execute(
            "CREATE INDEX idx_membership_prototype "
            "ON membership(prototype_group)"
        )
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            ("row_count", str(row_count)),
        )
        connection.commit()
    except Exception:
        connection.close()
        path.unlink(missing_ok=True)
        Path(f"{path}-wal").unlink(missing_ok=True)
        Path(f"{path}-shm").unlink(missing_ok=True)
        raise
    finally:
        if connection:
            connection.close()

    return MembershipIndexSummary(
        dataset_id=dataset_id,
        row_count=row_count,
        source_file_sha256=source_file_sha256,
        fingerprint_protocol_id=fingerprint_protocol_id,
        prototype_group_protocol_id=prototype_group_protocol_id,
        index_path=str(path),
    )


def fingerprint_candidate_count(
    db_path: str | Path,
    structure_fingerprint_sha256: str,
) -> int:
    """Count fingerprint-bucket candidates, not authoritative exact matches."""

    _validate_sha256(
        "structure_fingerprint_sha256",
        structure_fingerprint_sha256,
    )
    with sqlite3.connect(Path(db_path)) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM membership "
            "WHERE structure_fingerprint_sha256 = ?",
            (structure_fingerprint_sha256,),
        ).fetchone()
    return int(row[0])


def candidate_locators_for_near_duplicate(
    db_path: str | Path,
    *,
    composition_key: str,
    site_count: int,
) -> tuple[str, ...]:
    if not composition_key.strip():
        raise ValueError("composition_key must be non-empty")
    if site_count <= 0:
        raise ValueError("site_count must be positive")

    with sqlite3.connect(Path(db_path)) as connection:
        rows = connection.execute(
            "SELECT source_locator FROM membership "
            "WHERE composition_key = ? AND site_count = ? "
            "ORDER BY source_locator",
            (composition_key, site_count),
        ).fetchall()
    return tuple(str(row[0]) for row in rows)
