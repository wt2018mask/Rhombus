"""MACE-MPA-0 checkpoint training lineage: checklist is NOT scientific authorization."""
from __future__ import annotations

import json
from pathlib import Path

from rhombus.domain.mpa0_training_lineage import (
    TrainingDatasetLineageEvidence,
    assess_mace_mpa0_training_lineage_review,
)

OFFICIAL_RELEASE = "https://github.com/ACEsuit/mace-foundations/releases/tag/mace_mpa_0"
SHA = "a" * 64


def _source(dataset_id, *, missing=None):
    arguments = {
        "dataset_id": dataset_id,
        "exact_source_sha256": SHA,
        "selected_frame_manifest_sha256": SHA,
        "preprocessing_manifest_sha256": SHA,
        "energy_label_selection_manifest_sha256": SHA,
        "checkpoint_binding_evidence_id": "synthetic:checkpoint",
    }
    if missing is not None:
        arguments[missing] = None
    return TrainingDatasetLineageEvidence(**arguments)


def _review(sources=(), checkpoint_sha256=None, release=OFFICIAL_RELEASE):
    return assess_mace_mpa0_training_lineage_review(
        sources,
        checkpoint_sha256=checkpoint_sha256,
        checkpoint_release_url=release,
    )


def test_public_training_datasets_and_release_are_not_lineage_attestation():
    report = _review((), checkpoint_sha256=None)
    assert report.ready_for_independent_review is False
    assert "checkpoint full-file SHA256 not independently frozen" in report.blockers
    assert "missing required training lineage: MPTrj" in report.blockers
    assert "missing required training lineage: sAlex" in report.blockers
    assert report.exposure_audit_authorized is False
    assert report.unseen_generalization_authorized is False


def test_source_sha_only_does_not_prove_training_selected_frames():
    result = _review(
        (
            TrainingDatasetLineageEvidence("MPTrj", exact_source_sha256=SHA),
            TrainingDatasetLineageEvidence("sAlex", exact_source_sha256=SHA),
        ),
        checkpoint_sha256=SHA,
    )
    assert result.ready_for_independent_review is False
    assert "MPTrj: missing checkpoint-selected frame manifest SHA256" in result.blockers
    assert "sAlex: missing checkpoint-binding evidence ID" in result.blockers


def test_empty_or_bad_manifest_digest_fails_closed():
    for field in (
        "exact_source_sha256",
        "selected_frame_manifest_sha256",
        "preprocessing_manifest_sha256",
        "energy_label_selection_manifest_sha256",
    ):
        report = _review(
            (_source("MPTrj", missing=field), _source("sAlex")),
            checkpoint_sha256=SHA,
        )
        assert not report.ready_for_independent_review
        assert any(block.startswith("MPTrj:") for block in report.blockers)


def test_wrong_model_release_and_unknown_source_rejected():
    report = _review(
        (_source("MPTrj"), _source("sAlex"), _source("fake")),
        checkpoint_sha256=SHA,
        release="https://example.com/model",
    )
    assert report.ready_for_independent_review is False
    assert any("official frozen repository" in b for b in report.blockers)
    assert any("unsupported declared" in b for b in report.blockers)


def test_duplicate_source_evidence_rejected():
    report = _review(
        (_source("MPTrj"), _source("MPTrj"), _source("sAlex")),
        checkpoint_sha256=SHA,
    )
    assert not report.ready_for_independent_review
    assert "duplicate training evidence dataset: MPTrj" in report.blockers


def test_even_synthetic_complete_package_does_not_attest_scientific_claims():
    report = _review(
        (_source("MPTrj"), _source("sAlex")),
        checkpoint_sha256=SHA,
    )
    assert report.ready_for_independent_review is True
    assert report.blockers == ()
    assert report.exact_training_frames_attested is False
    assert report.exposure_audit_authorized is False
    assert report.unseen_generalization_authorized is False
    assert report.empirical_calibration_authorized is False


def test_current_public_evidence_is_explicitly_insufficient():
    root = Path(__file__).resolve().parents[1]
    data = json.loads(
        (root / "data/development/phase3_mpa0_checkpoint_lineage_evidence_v1.json").read_text()
    )
    assert data["model_release"]["asset_name"] == "mace-mpa-0-medium.model"
    assert data["model_release"]["asset_size_bytes"] == 79462305
    assert data["public_declaration"]["training_datasets"] == ["MPTrj", "sAlex"]
    assert data["public_evidence_limitations"]["exact_training_frame_manifest_found"] is False
    assert data["public_evidence_limitations"]["checkpoint_bound_preprocessing_found"] is False
    assert data["authorization"]["execute_exposure_audit"] is False
    assert data["authorization"]["unseen_generalization_claim"] is False
