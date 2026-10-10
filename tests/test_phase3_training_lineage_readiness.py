"""Science A: training-lineage acquisition readiness, never synthetic promotion."""
from __future__ import annotations

import copy
import json

import pytest

from rhombus.domain.lineage_readiness import (
    READINESS_SCHEMA,
    assess_training_lineage_readiness,
    main,
)
from tests.redteam_batch_b_fixtures import lineage_fixture


def trusted_rules(fixture):
    return {
        row["dataset_id"]: {
            "preprocessing_sha256": row["preprocessing_sha256"],
            "energy_labels_sha256": row["energy_labels_sha256"],
        }
        for row in fixture["manifest"]["sources"]
    }


def test_no_evidence_produces_actionable_nonpromoting_report():
    result = assess_training_lineage_readiness()
    assert result["schema_version"] == READINESS_SCHEMA
    assert result["status"] == "BLOCKED"
    assert result["ready_for_membership_audit"] is False
    assert result["scientific_qualification_authorized"] is False
    assert result["unseen_generalization_authorized"] is False
    assert "INDEPENDENT_MODEL_BINARY_FULL_SHA256" in result["missing_requirements"]
    assert "MPTRJ_ORIGINAL_SOURCE_FULL_SHA256" in result["missing_requirements"]
    assert "SALEX_ENERGY_LABEL_MAPPING_BYTES_SHA256" in result["missing_requirements"]
    assert len(result["missing_requirements"]) > 8


def test_declared_artifact_hashes_are_not_independently_verified():
    f = lineage_fixture()
    result = assess_training_lineage_readiness(manifest=f["manifest"])
    assert result["status"] == "BLOCKED"
    assert result["requirements"]
    assert any(row["declaration_status"] == "DECLARED_UNVERIFIED" for row in result["requirements"])
    assert "MPTRJ_SELECTED_FRAME_LIST_BYTES_SHA256" in result["missing_requirements"]
    assert "HOST_PROVISIONED_TRUST_ANCHORS" in result["missing_requirements"]
    assert result["exact_training_frames_attested"] is False


def test_synthetic_signed_complete_package_cannot_authorize_training_claim():
    f = lineage_fixture()
    result = assess_training_lineage_readiness(
        **f, trusted_rule_bindings=trusted_rules(f),
    )
    assert result["scope"] == "SYNTHETIC"
    assert result["status"] == "BLOCKED"
    assert result["ready_for_membership_audit"] is False
    assert result["independently_authenticated"] is False
    assert result["exact_training_frames_attested"] is False
    assert result["scientific_verdict"] == "INDETERMINATE"
    assert result["missing_requirements"] == []
    assert "INDEPENDENT_TRAINING_PROVENANCE_NOT_ATTESTED" in result["blockers"]


def test_missing_host_rule_bindings_remains_explicit_even_with_signed_fixture():
    f = lineage_fixture()
    result = assess_training_lineage_readiness(**f)
    assert "HOST_APPROVED_SOURCE_PREPROCESSING_RULES" in result["missing_requirements"]
    assert result["ready_for_membership_audit"] is False


def test_tampered_signed_manifest_is_not_passed_as_valid():
    f = lineage_fixture()
    f["manifest"]["checkpoint"]["independent_observation"]["sha256"] = "a" * 64
    result = assess_training_lineage_readiness(
        **f, trusted_rule_bindings=trusted_rules(f),
    )
    assert result["status"] == "BLOCKED"
    assert "INDEPENDENT_MODEL_BINARY_FULL_SHA256" in result["missing_requirements"]
    assert result["ready_for_membership_audit"] is False


def test_forged_receipt_with_semantically_valid_manifest_fails_strict_authentication():
    f = lineage_fixture()
    f["receipts"][0]["signature"] = "a" * 128
    result = assess_training_lineage_readiness(
        **f, trusted_rule_bindings=trusted_rules(f),
    )
    assert result["status"] == "BLOCKED"
    assert "STRICT_TRAINING_LINEAGE_AUTHENTICATION_REJECTED" in result["blockers"]
    assert result["ready_for_membership_audit"] is False


def test_duplicate_source_is_rejected_without_exposing_material_tokens():
    f = lineage_fixture()
    f["manifest"]["sources"][1] = copy.deepcopy(f["manifest"]["sources"][0])
    result = assess_training_lineage_readiness(
        manifest=f["manifest"], artifacts=f["artifacts"],
    )
    assert "DUPLICATE_SOURCE_FAMILY" in result["blockers"]
    assert "synthetic-training-material-0" not in json.dumps(result)
    assert result["exact_training_frames_attested"] is False


def test_unknown_schema_or_source_fails_closed():
    f = lineage_fixture()
    f["manifest"]["schema_version"] = "bogus"
    f["manifest"]["sources"][0]["dataset_id"] = "unrecognized"
    result = assess_training_lineage_readiness(manifest=f["manifest"])
    assert "MANIFEST_SCHEMA_SCOPE_OR_IDENTITY_INVALID" in result["blockers"]
    assert "UNKNOWN_SOURCE_FAMILY" in result["blockers"]


def test_bad_input_types_rejected():
    with pytest.raises(ValueError):
        assess_training_lineage_readiness(manifest=[])
    with pytest.raises(ValueError):
        assess_training_lineage_readiness(manifest=42)


def test_cli_unconfigured_plan_json_is_machine_readable(capsys):
    assert main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["scope"] == "NOT_SUBMITTED"
    assert report["status"] == "BLOCKED"
    assert report["missing_requirements"]


def test_cli_declared_manifest_never_becomes_external_evidence(tmp_path, capsys):
    f = lineage_fixture()
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(f["manifest"]), encoding="utf-8")
    assert main(["--manifest-json", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["scope"] == "SYNTHETIC"
    assert not report["ready_for_membership_audit"]
    assert "synthetic-training-material" not in json.dumps(report)


def test_cli_duplicate_and_nan_rejected(tmp_path):
    for body in ('{"scope":"SYNTHETIC","scope":"EXTERNAL"}', '{"x":NaN}'):
        path = tmp_path / "invalid.json"
        path.write_text(body, encoding="utf-8")
        with pytest.raises(SystemExit):
            main(["--manifest-json", str(path)])
