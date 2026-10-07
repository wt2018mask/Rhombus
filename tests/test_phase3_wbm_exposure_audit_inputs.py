from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhombus.domain import (
    ExposureAuditTarget,
    ExposureComparisonProtocol,
    TrainingAuditBasis,
    TrainingExposureReference,
    TrainingSnapshotResolution,
    assess_exposure_audit_input_readiness,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
ROOT = Path(__file__).resolve().parents[1]


def _target() -> ExposureAuditTarget:
    return ExposureAuditTarget(
        material_id="wbm-1",
        source_record_id="wbm:1",
        structure_fingerprint_sha256=SHA_A,
        prototype_group="proto:alpha",
        source_file_sha256=SHA_B,
        verification_evidence_id="evidence:wbm-source",
    )


def _training(dataset_id: str, suffix: str) -> TrainingExposureReference:
    return TrainingExposureReference(
        reference_id=f"{dataset_id}:{suffix}",
        dataset_id=dataset_id,
        structure_fingerprint_sha256=SHA_C if dataset_id == "MPTrj" else SHA_D,
        prototype_group=f"proto:{suffix}",
        source_file_sha256=SHA_B,
        verification_evidence_id=f"evidence:{dataset_id}",
    )


def _protocol() -> ExposureComparisonProtocol:
    return ExposureComparisonProtocol(
        protocol_id="wbm-exposure-comparison-v1",
        structure_fingerprint_protocol_id="pymatgen-structure-equivalence-v1",
        exact_match_rule="source identity or strict structure equivalence",
        near_duplicate_protocol_id="pymatgen-structure-near-duplicate-v1",
        prototype_group_protocol_id="matbench-protostructure-label-v1",
    )


def _basis(dataset_id: str, status: str = "COMPLETE_STRUCTURE_MEMBERSHIP") -> TrainingAuditBasis:
    return TrainingAuditBasis(
        dataset_id=dataset_id,
        source_snapshot_id=f"{dataset_id}:snapshot",
        source_url=f"https://example.invalid/{dataset_id}",
        coverage_status=status,
        verification_evidence_ids=(f"evidence:{dataset_id}:snapshot",),
        source_file_sha256=SHA_B if status == "COMPLETE_STRUCTURE_MEMBERSHIP" else None,
    )


def test_exposure_audit_inputs_require_both_training_lineages() -> None:
    result = assess_exposure_audit_input_readiness(
        (_target(),),
        (_training("MPTrj", "1"),),
        (_basis("MPTrj"),),
        comparison_protocol=_protocol(),
    )

    assert result.ready is False
    assert "required training dataset missing: sAlex" in result.blockers
    assert "required training audit basis missing: sAlex" in result.blockers


def test_exposure_audit_inputs_require_complete_membership_basis() -> None:
    result = assess_exposure_audit_input_readiness(
        (_target(),),
        (_training("MPTrj", "1"), _training("sAlex", "1")),
        (
            _basis("MPTrj", "SOURCE_IDENTIFIED_ONLY"),
            _basis("sAlex", "DECLARED_WBM_PROTOTYPE_FILTER"),
        ),
        comparison_protocol=_protocol(),
    )

    assert result.ready is False
    assert (
        "training audit basis incomplete for MPTrj: SOURCE_IDENTIFIED_ONLY"
        in result.blockers
    )
    assert (
        "training audit basis incomplete for sAlex: DECLARED_WBM_PROTOTYPE_FILTER"
        in result.blockers
    )


def test_exposure_audit_inputs_ready_only_with_complete_hash_bound_basis() -> None:
    result = assess_exposure_audit_input_readiness(
        (_target(),),
        (_training("MPTrj", "1"), _training("sAlex", "1")),
        (_basis("MPTrj"), _basis("sAlex")),
        comparison_protocol=_protocol(),
    )

    assert result.ready is True
    assert result.target_count == 1
    assert result.training_reference_count == 2
    assert result.training_dataset_count == 2
    assert result.blockers == ()


def test_complete_training_basis_requires_source_sha256() -> None:
    with pytest.raises(ValueError, match="requires frozen source_file_sha256"):
        TrainingAuditBasis(
            dataset_id="MPTrj",
            source_snapshot_id="snapshot",
            source_url="https://example.invalid/mptrj",
            coverage_status="COMPLETE_STRUCTURE_MEMBERSHIP",
            verification_evidence_ids=("evidence:mptrj",),
        )


def test_exposure_audit_target_requires_real_sha256_shape() -> None:
    with pytest.raises(ValueError, match="64-character SHA256"):
        ExposureAuditTarget(
            material_id="wbm-1",
            source_record_id="wbm:1",
            structure_fingerprint_sha256="not-a-hash",
            prototype_group="proto:alpha",
            source_file_sha256=SHA_B,
            verification_evidence_id="evidence:wbm-source",
        )


def test_exposure_audit_input_plan_remains_fail_closed() -> None:
    plan = json.loads(
        (ROOT / "data/development/phase3_wbm_exposure_audit_input_plan_v1.json")
        .read_text(encoding="utf-8")
    )

    assert plan["status"] == "NOT_READY"
    assert plan["authorization"]["execute_exposure_audit"] is False
    assert plan["authorization"]["empirical_calibration_use"] is False
    assert plan["authorization"]["unseen_generalization_claim"] is False


def test_training_snapshot_resolution_distinguishes_dataset_from_training_representation() -> None:
    resolution = TrainingSnapshotResolution(
        dataset_id="MPTrj",
        canonical_source_id="figshare:23713842:v2:file:41619375",
        canonical_source_url="https://figshare.com/files/41619375",
        resolution_status="CANONICAL_SOURCE_RESOLVED",
        evidence_ids=("figshare-api:23713842:v2",),
        canonical_source_md5="50ead5f27f9a4f6beb7564c4188f1e9f",
        canonical_source_size=12188168685,
        limitations=("training representation is unattested",),
    )

    assert resolution.exact_training_representation_resolved is False


def test_attested_training_representation_requires_identity() -> None:
    with pytest.raises(ValueError, match="requires training_representation_id"):
        TrainingSnapshotResolution(
            dataset_id="MPTrj",
            canonical_source_id="figshare:23713842:v2:file:41619375",
            canonical_source_url="https://figshare.com/files/41619375",
            resolution_status="TRAINING_REPRESENTATION_ATTESTED",
            evidence_ids=("evidence:model-release",),
        )


def test_training_audit_basis_resolves_canonical_mptrj_but_keeps_training_unattested() -> None:
    plan = json.loads(
        (ROOT / "data/development/phase3_training_exposure_audit_basis_v1.json")
        .read_text(encoding="utf-8")
    )

    assert plan["status"] == "NOT_READY"
    assert plan["comparison_protocol"]["protocol_id"] == "wbm-exposure-comparison-v1"
    rows = {row["dataset_id"]: row for row in plan["training_audit_bases"]}
    mptrj = rows["MPTrj"]
    assert mptrj["coverage_status"] == "SOURCE_IDENTIFIED_ONLY"
    assert mptrj["canonical_dataset_resolution_status"] == "CANONICAL_SOURCE_RESOLVED"
    assert mptrj["canonical_dataset"]["file_id"] == 41619375
    assert mptrj["canonical_dataset"]["md5"] == "50ead5f27f9a4f6beb7564c4188f1e9f"
    assert mptrj["converted_representation"]["file_id"] == 43302033
    assert mptrj["training_representation_status"] == "UNATTESTED"
    assert rows["sAlex"]["coverage_status"] == "DECLARED_WBM_PROTOTYPE_FILTER"
    assert plan["authorization"]["execute_exposure_audit"] is False
    assert plan["authorization"]["unseen_generalization_claim"] is False


def test_training_snapshot_resolution_evidence_remains_fail_closed() -> None:
    evidence = json.loads(
        (ROOT / "data/development/phase3_training_snapshot_resolution_v1.json")
        .read_text(encoding="utf-8")
    )

    assert evidence["mptrj"]["canonical_source"]["file_id"] == 41619375
    assert evidence["mptrj"]["canonical_source"]["md5"] == "50ead5f27f9a4f6beb7564c4188f1e9f"
    assert evidence["mptrj"]["training_representation"]["status"] == "UNATTESTED"
    assert evidence["salex"]["status"] == "SOURCE_BYTE_IDENTITY_VERIFIED"
    assert evidence["salex"]["source_file_sha256"] == "48eb3664d95331e7fd84bfe1f04f5e741600bffcfb1253334c82dae92cebf1ef"
    assert evidence["authorization"]["execute_exposure_audit"] is False
    assert evidence["authorization"]["unseen_generalization_claim"] is False
