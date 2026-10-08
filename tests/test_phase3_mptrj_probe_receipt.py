"""Offline receipt admission regression: no upstream MPTrj bytes or network."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from rhombus.domain.mptrj_probe_receipt import (
    MPTrjProbeReceiptError,
    validate_mptrj_first_frame_receipt,
)
from scripts.development.verify_mptrj_probe_receipt import (
    MAX_REPORT_BYTES,
    main,
    read_and_validate_receipt,
)


def receipt():
    return {
        "schema_version": "rhombus-phase3-mptrj-range-prefix-probe-v1",
        "source_metadata": {
            "figshare_file_id": 41619375,
            "expected_total_size_bytes_from_registry": 12_188_168_685,
            "server_content_range_total_declared": 12_188_168_685,
            "redirect_host": "cdn.figshare.example",
        },
        "observation": {
            "prefix_size_bytes": 262144,
            "prefix_sha256": "a" * 64,
            "first_material_id": "mp-1000",
            "first_frame_id": "task-0-0",
            "first_frame_structure_object_start_seen": True,
            "complete_frame_parsed": True,
            "first_frame_structure": {
                "material_id": "mp-1000",
                "frame_id": "task-0-0",
                "site_count": 2,
                "reduced_formula": "LiO",
                "energy_fields_present": {
                    "energy_per_atom": True,
                    "corrected_total_energy": True,
                    "uncorrected_total_energy": False,
                },
                "complete_frame_parsed": True,
            },
            "complete_original_source_hashed": False,
        },
        "training_lineage": {
            "mace_mpa0_exact_training_bytes_attested": False,
            "training_frame_selection_attested": False,
        },
        "authorization": {
            "execute_exposure_audit": False,
            "empirical_calibration_use": False,
            "unseen_generalization_claim": False,
        },
    }


def test_valid_first_frame_metadata_only_gets_diagnostic_admission():
    r = validate_mptrj_first_frame_receipt(receipt())
    assert r["status"] == "DIAGNOSTIC_REPORT_SCHEMA_VALID_ONLY"
    assert len(r["report_metadata_sha256"]) == 64
    assert r["first_frame_site_count"] == 2
    assert r["full_source_byte_identity_verified"] is False
    assert r["github_workflow_origin_attested"] is False
    assert r["model_training_frame_membership_attested"] is False
    assert r["execute_exposure_audit"] is False
    assert r["unseen_generalization_claim"] is False


@pytest.mark.parametrize(("path", "bad"), [
    (("source_metadata", "figshare_file_id"), 41619374),
    (("source_metadata", "server_content_range_total_declared"), 123),
    (("observation", "prefix_size_bytes"), 1048576),
    (("observation", "prefix_sha256"), "bad"),
    (("observation", "first_frame_id"), "wrong"),
    (("observation", "complete_frame_parsed"), False),
    (("observation", "first_frame_structure_object_start_seen"), False),
    (("observation", "complete_original_source_hashed"), True),
    (("observation", "first_frame_structure", "site_count"), 0),
    (("observation", "first_frame_structure", "complete_frame_parsed"), False),
    (("observation", "first_frame_structure", "energy_fields_present", "energy_per_atom"), "True"),
    (("training_lineage", "mace_mpa0_exact_training_bytes_attested"), True),
    (("training_lineage", "training_frame_selection_attested"), True),
    (("authorization", "execute_exposure_audit"), True),
    (("authorization", "empirical_calibration_use"), True),
    (("authorization", "unseen_generalization_claim"), True),
])
def test_inconsistent_or_promoted_report_fails_closed(path, bad):
    value = deepcopy(receipt())
    node = value
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = bad
    with pytest.raises(MPTrjProbeReceiptError):
        validate_mptrj_first_frame_receipt(value)


def test_missing_and_extra_fields_are_rejected():
    incomplete = receipt()
    del incomplete["observation"]["first_frame_structure"]
    with pytest.raises(MPTrjProbeReceiptError, match="missing or unexpected"):
        validate_mptrj_first_frame_receipt(incomplete)
    extraneous = receipt()
    extraneous["observation"]["raw_source_frame"] = {"secret": "should-not-be-here"}
    with pytest.raises(MPTrjProbeReceiptError):
        validate_mptrj_first_frame_receipt(extraneous)


def test_report_fingerprint_does_not_depend_on_json_object_key_order():
    a = receipt()
    b = dict(reversed(list(a.items())))
    assert validate_mptrj_first_frame_receipt(a)["report_metadata_sha256"] == (
        validate_mptrj_first_frame_receipt(b)["report_metadata_sha256"]
    )


def test_cli_validates_small_offline_report_without_writing_success_artifacts(tmp_path, capsys):
    report = tmp_path / "observation.json"
    report.write_text(json.dumps(receipt()), encoding="utf-8")
    before = sorted(x.name for x in tmp_path.iterdir())
    assert main(["--receipt", str(report), "--expected-prefix-bytes", "262144"]) == 0
    stdout = capsys.readouterr().out
    assert "MPTRJ_DIAGNOSTIC_REPORT_SCHEMA_PASS" in stdout
    assert "FULL_SOURCE_NOT_ATTESTED" in stdout
    assert sorted(x.name for x in tmp_path.iterdir()) == before


def test_report_is_binary_bounded_and_duplicate_json_keys_are_rejected(tmp_path):
    too_big = tmp_path / "too-big.json"
    too_big.write_bytes(b"x" * (MAX_REPORT_BYTES + 1))
    with pytest.raises(MPTrjProbeReceiptError, match="larger"):
        read_and_validate_receipt(too_big)

    duplicate = tmp_path / "duplicate.json"
    data = json.dumps(receipt())
    data = data.replace('"figshare_file_id": 41619375', '"figshare_file_id": 41619375, "figshare_file_id": 41619375')
    duplicate.write_text(data, encoding="utf-8")
    with pytest.raises(MPTrjProbeReceiptError, match="duplicate"):
        read_and_validate_receipt(duplicate)


def test_symlink_receipt_refused(tmp_path):
    report = tmp_path / "observation.json"
    report.write_text(json.dumps(receipt()), encoding="utf-8")
    alias = tmp_path / "alias.json"
    alias.symlink_to(report)
    with pytest.raises(MPTrjProbeReceiptError, match="non-symlink"):
        read_and_validate_receipt(alias)


def test_manual_workflow_verifies_report_before_upload():
    from pathlib import Path
    import yaml

    root = Path(__file__).resolve().parents[1]
    workflow = yaml.load(
        (root / ".github/workflows/phase3-mptrj-first-frame-manual.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    steps = workflow["jobs"]["first-frame"]["steps"]
    verification = [i for i, step in enumerate(steps) if "verify_mptrj_probe_receipt" in step.get("run", "")]
    probe = [i for i, step in enumerate(steps) if "probe_mptrj_source_prefix" in step.get("run", "")]
    upload = [i for i, step in enumerate(steps) if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(verification) == len(probe) == len(upload) == 1
    assert probe[0] < verification[0] < upload[0]
    assert "--expected-prefix-bytes 262144" in steps[verification[0]]["run"]
    assert set(workflow["on"]) == {"workflow_dispatch"}
