"""Fail-closed review readiness for exact MACE-MPA-0 training provenance.

Dataset name declarations, source-file hashes, or a model release asset are
NOT sufficient evidence that source frames/labels were used in a checkpoint.
This module checks whether an externally reviewed evidence *package* is
complete. It NEVER authorizes generalization, training exposure, or empirical
calibration; that needs a separate scientific qualification protocol.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


REQUIRED_SOURCES = ("MPTrj", "sAlex")


def _digest(value: str | None) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class TrainingDatasetLineageEvidence:
    dataset_id: str
    exact_source_sha256: str | None = None
    selected_frame_manifest_sha256: str | None = None
    preprocessing_manifest_sha256: str | None = None
    energy_label_selection_manifest_sha256: str | None = None
    checkpoint_binding_evidence_id: str | None = None


@dataclass(frozen=True)
class MaceMPA0LineageReview:
    """Completeness for independent review, NEVER training verification."""

    ready_for_independent_review: bool
    blockers: tuple[str, ...]
    model_asset_name: str
    required_sources: tuple[str, ...] = REQUIRED_SOURCES
    exact_training_frames_attested: bool = False
    exposure_audit_authorized: bool = False
    unseen_generalization_authorized: bool = False
    empirical_calibration_authorized: bool = False


def assess_mace_mpa0_training_lineage_review(
    sources: Iterable[TrainingDatasetLineageEvidence],
    *,
    checkpoint_sha256: str | None,
    checkpoint_release_url: str,
    checkpoint_asset_name: str = "mace-mpa-0-medium.model",
) -> MaceMPA0LineageReview:
    """Check required proof locations before a later *independent* audit.

    Requiring all fields does not prove that they are authentic, independently
    sourced, or actually bind the model. Readiness here is only a checklist.
    """
    blockers: list[str] = []
    source_rows = tuple(sources)
    if checkpoint_asset_name != "mace-mpa-0-medium.model":
        blockers.append("model checkpoint asset is not the frozen MACE-MPA-0 medium checkpoint")
    if not checkpoint_release_url.startswith(
        "https://github.com/ACEsuit/mace-foundations/releases/"
    ):
        blockers.append("model checkpoint release URL is not an official frozen repository path")
    if not _digest(checkpoint_sha256):
        blockers.append("checkpoint full-file SHA256 not independently frozen")
    seen: set[str] = set()
    for record in source_rows:
        if record.dataset_id in seen:
            blockers.append(f"duplicate training evidence dataset: {record.dataset_id}")
        seen.add(record.dataset_id)
        if record.dataset_id not in REQUIRED_SOURCES:
            blockers.append(f"unsupported declared training evidence dataset: {record.dataset_id}")
    by_dataset = {record.dataset_id: record for record in source_rows}
    requirements = (
        ("exact_source_sha256", "canonical source SHA256"),
        ("selected_frame_manifest_sha256", "checkpoint-selected frame manifest SHA256"),
        ("preprocessing_manifest_sha256", "checkpoint-bound preprocessing manifest SHA256"),
        ("energy_label_selection_manifest_sha256", "training energy-label selection SHA256"),
    )
    for dataset_id in REQUIRED_SOURCES:
        record = by_dataset.get(dataset_id)
        if record is None:
            blockers.append(f"missing required training lineage: {dataset_id}")
            continue
        for field, label in requirements:
            if not _digest(getattr(record, field)):
                blockers.append(f"{dataset_id}: missing {label}")
        if not (record.checkpoint_binding_evidence_id or "").strip():
            blockers.append(f"{dataset_id}: missing checkpoint-binding evidence ID")
    return MaceMPA0LineageReview(
        ready_for_independent_review=not blockers,
        blockers=tuple(blockers),
        model_asset_name=checkpoint_asset_name,
    )
