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


def _validate_sha256(name: str, value: str) -> None:
    if len(value) != 64:
        raise ValueError(f"{name} must be a 64-character SHA256 digest")
    int(value, 16)


@dataclass(frozen=True)
class ExposureAuditTarget:
    material_id: str
    source_record_id: str
    structure_fingerprint_sha256: str
    prototype_group: str
    source_file_sha256: str
    verification_evidence_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("material_id", self.material_id),
            ("source_record_id", self.source_record_id),
            ("prototype_group", self.prototype_group),
            ("verification_evidence_id", self.verification_evidence_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        _validate_sha256("structure_fingerprint_sha256", self.structure_fingerprint_sha256)
        _validate_sha256("source_file_sha256", self.source_file_sha256)


@dataclass(frozen=True)
class TrainingExposureReference:
    reference_id: str
    dataset_id: str
    structure_fingerprint_sha256: str
    prototype_group: str
    source_file_sha256: str
    verification_evidence_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("reference_id", self.reference_id),
            ("dataset_id", self.dataset_id),
            ("prototype_group", self.prototype_group),
            ("verification_evidence_id", self.verification_evidence_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        _validate_sha256("structure_fingerprint_sha256", self.structure_fingerprint_sha256)
        _validate_sha256("source_file_sha256", self.source_file_sha256)


@dataclass(frozen=True)
class ExposureAuditInputReadiness:
    ready: bool
    target_count: int
    training_reference_count: int
    training_dataset_count: int
    blockers: tuple[str, ...]


def assess_exposure_audit_input_readiness(
    targets: Iterable[ExposureAuditTarget],
    training_references: Iterable[TrainingExposureReference],
    *,
    required_training_datasets: tuple[str, ...] = ("MPTrj", "sAlex"),
    structure_fingerprint_protocol_id: str,
    near_duplicate_protocol_id: str,
) -> ExposureAuditInputReadiness:
    target_rows = tuple(targets)
    reference_rows = tuple(training_references)
    blockers: list[str] = []

    if not structure_fingerprint_protocol_id.strip():
        blockers.append("structure fingerprint protocol identity is missing")
    if not near_duplicate_protocol_id.strip():
        blockers.append("near-duplicate protocol identity is missing")
    if not target_rows:
        blockers.append("no WBM target structures supplied")
    if not reference_rows:
        blockers.append("no training-reference structures supplied")

    if len({row.material_id for row in target_rows}) != len(target_rows):
        blockers.append("duplicate WBM target material IDs")
    if len({row.reference_id for row in reference_rows}) != len(reference_rows):
        blockers.append("duplicate training reference IDs")

    present_datasets = {row.dataset_id for row in reference_rows}
    for dataset_id in required_training_datasets:
        if dataset_id not in present_datasets:
            blockers.append(f"required training dataset missing: {dataset_id}")

    return ExposureAuditInputReadiness(
        ready=not blockers,
        target_count=len(target_rows),
        training_reference_count=len(reference_rows),
        training_dataset_count=len(present_datasets),
        blockers=tuple(blockers),
    )
