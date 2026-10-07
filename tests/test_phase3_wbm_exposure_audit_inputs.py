from __future__ import annotations

import pytest

from rhombus.domain import (
    ExposureAuditTarget,
    TrainingExposureReference,
    assess_exposure_audit_input_readiness,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


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


def test_exposure_audit_inputs_require_both_training_lineages_and_protocols() -> None:
    result = assess_exposure_audit_input_readiness(
        (_target(),),
        (_training("MPTrj", "1"),),
        structure_fingerprint_protocol_id="fingerprint:v1",
        near_duplicate_protocol_id="near-duplicate:v1",
    )

    assert result.ready is False
    assert "required training dataset missing: sAlex" in result.blockers


def test_exposure_audit_inputs_are_ready_only_with_explicit_basis() -> None:
    result = assess_exposure_audit_input_readiness(
        (_target(),),
        (_training("MPTrj", "1"), _training("sAlex", "1")),
        structure_fingerprint_protocol_id="fingerprint:v1",
        near_duplicate_protocol_id="near-duplicate:v1",
    )

    assert result.ready is True
    assert result.target_count == 1
    assert result.training_reference_count == 2
    assert result.training_dataset_count == 2
    assert result.blockers == ()


def test_exposure_audit_inputs_fail_closed_without_protocol_identity() -> None:
    result = assess_exposure_audit_input_readiness(
        (_target(),),
        (_training("MPTrj", "1"), _training("sAlex", "1")),
        structure_fingerprint_protocol_id="",
        near_duplicate_protocol_id="",
    )

    assert result.ready is False
    assert "structure fingerprint protocol identity is missing" in result.blockers
    assert "near-duplicate protocol identity is missing" in result.blockers


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
