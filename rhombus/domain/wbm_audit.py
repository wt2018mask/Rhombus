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


AUDIT_BASIS_STATUSES = {
    "SOURCE_IDENTIFIED_ONLY",
    "DECLARED_WBM_PROTOTYPE_FILTER",
    "COMPLETE_STRUCTURE_MEMBERSHIP",
}

TRAINING_SNAPSHOT_RESOLUTION_STATUSES = {
    "CANONICAL_SOURCE_RESOLVED",
    "SOURCE_IDENTIFIED_HASH_UNFROZEN",
    "TRAINING_REPRESENTATION_ATTESTED",
}


@dataclass(frozen=True)
class TrainingSnapshotResolution:
    dataset_id: str
    canonical_source_id: str
    canonical_source_url: str
    resolution_status: str
    evidence_ids: tuple[str, ...]
    canonical_source_md5: str | None = None
    canonical_source_size: int | None = None
    training_representation_id: str | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("dataset_id", self.dataset_id),
            ("canonical_source_id", self.canonical_source_id),
            ("canonical_source_url", self.canonical_source_url),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.resolution_status not in TRAINING_SNAPSHOT_RESOLUTION_STATUSES:
            raise ValueError(
                f"unsupported training snapshot resolution status: {self.resolution_status}"
            )
        if not self.evidence_ids:
            raise ValueError("evidence_ids must be non-empty")
        if self.canonical_source_md5 is not None:
            if len(self.canonical_source_md5) != 32:
                raise ValueError("canonical_source_md5 must be a 32-character MD5 digest")
            int(self.canonical_source_md5, 16)
        if self.canonical_source_size is not None and self.canonical_source_size <= 0:
            raise ValueError("canonical_source_size must be positive when supplied")
        if (
            self.resolution_status == "TRAINING_REPRESENTATION_ATTESTED"
            and not (self.training_representation_id or "").strip()
        ):
            raise ValueError(
                "attested training representation requires training_representation_id"
            )

    @property
    def exact_training_representation_resolved(self) -> bool:
        return self.resolution_status == "TRAINING_REPRESENTATION_ATTESTED"


@dataclass(frozen=True)
class TrainingAuditBasis:
    dataset_id: str
    source_snapshot_id: str
    source_url: str
    coverage_status: str
    verification_evidence_ids: tuple[str, ...]
    source_file_sha256: str | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("dataset_id", self.dataset_id),
            ("source_snapshot_id", self.source_snapshot_id),
            ("source_url", self.source_url),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.coverage_status not in AUDIT_BASIS_STATUSES:
            raise ValueError(f"unsupported coverage_status: {self.coverage_status}")
        if not self.verification_evidence_ids:
            raise ValueError("verification_evidence_ids must be non-empty")
        if self.source_file_sha256 is not None:
            _validate_sha256("source_file_sha256", self.source_file_sha256)
        if (
            self.coverage_status == "COMPLETE_STRUCTURE_MEMBERSHIP"
            and self.source_file_sha256 is None
        ):
            raise ValueError(
                "complete structure membership requires frozen source_file_sha256"
            )


@dataclass(frozen=True)
class ExposureComparisonProtocol:
    protocol_id: str
    structure_fingerprint_protocol_id: str
    exact_match_rule: str
    near_duplicate_protocol_id: str
    prototype_group_protocol_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("protocol_id", self.protocol_id),
            ("structure_fingerprint_protocol_id", self.structure_fingerprint_protocol_id),
            ("exact_match_rule", self.exact_match_rule),
            ("near_duplicate_protocol_id", self.near_duplicate_protocol_id),
            ("prototype_group_protocol_id", self.prototype_group_protocol_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")


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
    audit_bases: Iterable[TrainingAuditBasis],
    *,
    required_training_datasets: tuple[str, ...] = ("MPTrj", "sAlex"),
    comparison_protocol: ExposureComparisonProtocol,
) -> ExposureAuditInputReadiness:
    target_rows = tuple(targets)
    reference_rows = tuple(training_references)
    basis_rows = tuple(audit_bases)
    blockers: list[str] = []

    if not target_rows:
        blockers.append("no WBM target structures supplied")
    if not reference_rows:
        blockers.append("no training-reference structures supplied")

    if len({row.material_id for row in target_rows}) != len(target_rows):
        blockers.append("duplicate WBM target material IDs")
    if len({row.reference_id for row in reference_rows}) != len(reference_rows):
        blockers.append("duplicate training reference IDs")
    if len({row.dataset_id for row in basis_rows}) != len(basis_rows):
        blockers.append("duplicate training audit basis dataset IDs")

    present_datasets = {row.dataset_id for row in reference_rows}
    basis_by_dataset = {row.dataset_id: row for row in basis_rows}

    for dataset_id in required_training_datasets:
        if dataset_id not in present_datasets:
            blockers.append(f"required training dataset missing: {dataset_id}")
        basis = basis_by_dataset.get(dataset_id)
        if basis is None:
            blockers.append(f"required training audit basis missing: {dataset_id}")
        elif basis.coverage_status != "COMPLETE_STRUCTURE_MEMBERSHIP":
            blockers.append(
                f"training audit basis incomplete for {dataset_id}: "
                f"{basis.coverage_status}"
            )

    if not comparison_protocol.structure_fingerprint_protocol_id.strip():
        blockers.append("structure fingerprint protocol identity is missing")
    if not comparison_protocol.near_duplicate_protocol_id.strip():
        blockers.append("near-duplicate protocol identity is missing")
    if not comparison_protocol.prototype_group_protocol_id.strip():
        blockers.append("prototype-group protocol identity is missing")

    return ExposureAuditInputReadiness(
        ready=not blockers,
        target_count=len(target_rows),
        training_reference_count=len(reference_rows),
        training_dataset_count=len(present_datasets),
        blockers=tuple(blockers),
    )
