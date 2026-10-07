from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhombus.domain import (
    ExposureAuditTarget,
    ExposureComparisonProtocol,
    TrainingAuditBasis,
    TrainingExposureReference,
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


def test_training_audit_basis_records_source_ambiguity_and_salex_filter() -> None:
    plan = json.loads(
        (ROOT / "data/development/phase3_training_exposure_audit_basis_v1.json")
        .read_text(encoding="utf-8")
    )

    assert plan["status"] == "NOT_READY"
    assert plan["comparison_protocol"]["protocol_id"] == "wbm-exposure-comparison-v1"
    rows = {row["dataset_id"]: row for row in plan["training_audit_bases"]}
    assert rows["MPTrj"]["coverage_status"] == "SOURCE_IDENTIFIED_ONLY"
    assert rows["MPTrj"]["dataset_registry_download_url"] != rows["MPTrj"]["data_file_registry_url"]
    assert rows["sAlex"]["coverage_status"] == "DECLARED_WBM_PROTOTYPE_FILTER"
    assert plan["authorization"]["execute_exposure_audit"] is False
    assert plan["authorization"]["unseen_generalization_claim"] is False
