"""One-pass WBM↔sAlex overlap-audit primitives for Rhombus Phase 3."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import json
from pathlib import Path
import sqlite3
from typing import Callable, Iterable, Iterator

from ase import Atoms
from pymatgen.core import Structure

from .membership import MembershipIndexRecord
from .structure_protocols import (
    CANDIDATE_FINGERPRINT_PROTOCOL_ID,
    PROTOTYPE_GROUP_PROTOCOL_ID,
    matbench_prototype_group,
    near_duplicate_structure,
    strict_structure_equivalent,
    structure_candidate_fingerprint_sha256,
)
from .wbm_audit import MaterialExposureRecord, ExposureAuditSummary, summarize_exposure_audit


@dataclass(frozen=True)
class WBMTargetRecord:
    material_id: str
    structure: Structure

    def __post_init__(self) -> None:
        if not self.material_id.strip():
            raise ValueError("material_id must be non-empty")


@dataclass(frozen=True)
class WBMTargetIndexSummary:
    row_count: int
    source_file_sha256: str
    index_path: str


def _validate_sha256(value: str) -> None:
    if len(value) != 64:
        raise ValueError("source_file_sha256 must be a 64-character SHA256 digest")
    int(value, 16)


def iter_wbm_initial_structure_jsonl(path: str | Path) -> Iterator[WBMTargetRecord]:
    """Stream canonical WBM initial-structure JSONL(.gz) records."""

    source = Path(path)
    opener = gzip.open if source.suffix == ".gz" else open
    with opener(source, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            try:
                material_id = str(payload["material_id"])
                structure = Structure.from_dict(payload["initial_structure"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid WBM initial-structure record at line {line_number}"
                ) from exc
            yield WBMTargetRecord(material_id=material_id, structure=structure)


def build_wbm_target_index(
    records: Iterable[WBMTargetRecord],
    db_path: str | Path,
    *,
    source_file_sha256: str,
    batch_size: int = 500,
    fingerprint: Callable[[Structure], str] = structure_candidate_fingerprint_sha256,
    prototype_group: Callable[[Structure], str] = matbench_prototype_group,
) -> WBMTargetIndexSummary:
    """Build a memory-bounded WBM target index with frozen structure semantics."""

    _validate_sha256(source_file_sha256)
    # A caller-provided callback is not evidence that the frozen Phase 3
    # implementation ran. Record an explicit non-authoritative sentinel.
    candidate_protocol_id = (
        CANDIDATE_FINGERPRINT_PROTOCOL_ID
        if fingerprint is structure_candidate_fingerprint_sha256
        else "CUSTOM_UNATTESTED"
    )
    prototype_protocol_id = (
        PROTOTYPE_GROUP_PROTOCOL_ID
        if prototype_group is matbench_prototype_group
        else "CUSTOM_UNATTESTED"
    )
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"WBM target index already exists: {path}")

    connection = sqlite3.connect(path)
    row_count = 0
    pending: list[tuple[str, str, int, str, str, str]] = []
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
            CREATE TABLE targets (
                material_id TEXT PRIMARY KEY,
                composition_key TEXT NOT NULL,
                site_count INTEGER NOT NULL,
                candidate_fingerprint_sha256 TEXT NOT NULL,
                prototype_group TEXT NOT NULL,
                structure_json TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            (
                ("source_file_sha256", source_file_sha256),
                ("comparison_scope", "WBM_INITIAL_STRUCTURES"),
                ("candidate_fingerprint_protocol_id", candidate_protocol_id),
                ("prototype_group_protocol_id", prototype_protocol_id),
            ),
        )

        insert_sql = """
            INSERT INTO targets(
                material_id, composition_key, site_count,
                candidate_fingerprint_sha256, prototype_group, structure_json
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        for record in records:
            structure = record.structure
            composition_key = structure.composition.element_composition.reduced_formula
            pending.append(
                (
                    record.material_id,
                    composition_key,
                    len(structure),
                    fingerprint(structure),
                    prototype_group(structure),
                    json.dumps(
                        structure.as_dict(),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                )
            )
            if len(pending) >= batch_size:
                connection.executemany(insert_sql, pending)
                row_count += len(pending)
                pending.clear()
                connection.commit()

        if pending:
            connection.executemany(insert_sql, pending)
            row_count += len(pending)
            connection.commit()

        connection.execute(
            "CREATE INDEX idx_wbm_target_fingerprint "
            "ON targets(candidate_fingerprint_sha256)"
        )
        connection.execute(
            "CREATE INDEX idx_wbm_target_prototype ON targets(prototype_group)"
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
        connection.close()

    return WBMTargetIndexSummary(
        row_count=row_count,
        source_file_sha256=source_file_sha256,
        index_path=str(path),
    )


class WBMStreamingOverlapAuditor:
    """Observe sAlex structures while they are materialized and record WBM overlap."""

    def __init__(
        self,
        target_db_path: str | Path,
        *,
        strict_match: Callable[[Structure, Atoms], bool] = strict_structure_equivalent,
        near_match: Callable[[Structure, Atoms], bool] = near_duplicate_structure,
    ) -> None:
        self._path = Path(target_db_path)
        self._connection = sqlite3.connect(self._path)
        self._strict_match = strict_match
        self._near_match = near_match
        self._candidate_fingerprints = {
            str(row[0])
            for row in self._connection.execute(
                "SELECT DISTINCT candidate_fingerprint_sha256 FROM targets"
            )
        }
        self._target_prototypes = {
            str(row[0])
            for row in self._connection.execute(
                "SELECT DISTINCT prototype_group FROM targets"
            )
        }
        self._exact_material_ids: set[str] = set()
        self._near_material_ids: set[str] = set()
        self._prototype_groups_seen: set[str] = set()
        self.observed_training_structures = 0
        self.candidate_training_structures = 0

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "WBMStreamingOverlapAuditor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def observe(self, record: MembershipIndexRecord, atoms: Atoms) -> None:
        self.observed_training_structures += 1
        if record.prototype_group in self._target_prototypes:
            self._prototype_groups_seen.add(record.prototype_group)

        if record.structure_fingerprint_sha256 not in self._candidate_fingerprints:
            return
        self.candidate_training_structures += 1

        rows = self._connection.execute(
            "SELECT material_id, structure_json FROM targets "
            "WHERE candidate_fingerprint_sha256 = ?",
            (record.structure_fingerprint_sha256,),
        ).fetchall()
        for material_id_raw, structure_json in rows:
            material_id = str(material_id_raw)
            if (
                material_id in self._exact_material_ids
                and material_id in self._near_material_ids
            ):
                continue
            target = Structure.from_dict(json.loads(str(structure_json)))
            if material_id not in self._exact_material_ids:
                if self._strict_match(target, atoms):
                    self._exact_material_ids.add(material_id)
            if material_id not in self._near_material_ids:
                if self._near_match(target, atoms):
                    self._near_material_ids.add(material_id)

    def material_records(self) -> tuple[MaterialExposureRecord, ...]:
        rows = self._connection.execute(
            "SELECT material_id, prototype_group FROM targets ORDER BY material_id"
        ).fetchall()
        return tuple(
            MaterialExposureRecord(
                material_id=str(material_id),
                exact_training_match=str(material_id) in self._exact_material_ids,
                near_duplicate_match=str(material_id) in self._near_material_ids,
                prototype_overlap=str(prototype_group) in self._prototype_groups_seen,
                audit_basis_ids=(),
            )
            for material_id, prototype_group in rows
        )

    def summary(self) -> ExposureAuditSummary:
        """Summarize sAlex overlap without authorizing unseen eligibility.

        audit_basis_ids remain empty because MPTrj is still unresolved. Therefore
        every WBM material remains unresolved for full training-lineage claims.
        """

        return summarize_exposure_audit(self.material_records())
