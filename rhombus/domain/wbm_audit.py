"""WBM file-freeze and exposure/dedup audit contracts for Rhombus 2.0."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5, sha256
from typing import Iterable


@dataclass(frozen=True)
class FrozenRemoteFile:
    file_id: str
    url: str
    relative_path: str
    expected_md5: str
    expected_size: int | None = None

    def __post_init__(self) -> None:
        if not self.file_id.strip() or not self.url.strip() or not self.relative_path.strip():
            raise ValueError("file identity fields must be non-empty")
        if len(self.expected_md5) != 32:
            raise ValueError("expected_md5 must be a 32-character hex digest")
        int(self.expected_md5, 16)
        if self.expected_size is not None and self.expected_size <= 0:
            raise ValueError("expected_size must be positive when supplied")


@dataclass(frozen=True)
class MaterialExposureRecord:
    material_id: str
    exact_training_match: bool
    near_duplicate_match: bool
    prototype_overlap: bool
    audit_basis_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.material_id.strip():
            raise ValueError("material_id must be non-empty")


@dataclass(frozen=True)
class ExposureAuditSummary:
    material_count: int
    exact_match_count: int
    near_duplicate_count: int
    prototype_overlap_count: int
    unseen_generalization_eligible_count: int
    unresolved_count: int


def verify_frozen_bytes(data: bytes, spec: FrozenRemoteFile) -> tuple[str, str]:
    actual_md5 = md5(data).hexdigest()  # noqa: S324 - compatibility with source registry
    if actual_md5 != spec.expected_md5:
        raise ValueError(
            f"MD5 mismatch for {spec.file_id}: expected {spec.expected_md5}, got {actual_md5}"
        )
    if spec.expected_size is not None and len(data) != spec.expected_size:
        raise ValueError(
            f"size mismatch for {spec.file_id}: expected {spec.expected_size}, got {len(data)}"
        )
    return actual_md5, sha256(data).hexdigest()


def summarize_exposure_audit(
    rows: Iterable[MaterialExposureRecord],
) -> ExposureAuditSummary:
    records = tuple(rows)
    if len({row.material_id for row in records}) != len(records):
        raise ValueError("material_id values must be unique")

    exact = sum(row.exact_training_match for row in records)
    near = sum(row.near_duplicate_match for row in records)
    proto = sum(row.prototype_overlap for row in records)
    eligible = 0
    unresolved = 0

    for row in records:
        if not row.audit_basis_ids:
            unresolved += 1
            continue
        if not (row.exact_training_match or row.near_duplicate_match or row.prototype_overlap):
            eligible += 1

    return ExposureAuditSummary(
        material_count=len(records),
        exact_match_count=exact,
        near_duplicate_count=near,
        prototype_overlap_count=proto,
        unseen_generalization_eligible_count=eligible,
        unresolved_count=unresolved,
    )
