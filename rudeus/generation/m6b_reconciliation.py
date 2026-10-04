"""Append-only M6-B selection-provenance reconciliation; no report repair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _run_ancestry(report: dict, panel_raw: bytes, prereg_raw: bytes,
                  evidence_directory: Path) -> dict:
    """Bind retained pass evidence and the PREPARED -> SUBMITTED attempt chain."""
    root = Path(evidence_directory)
    names = ("task.json", "task-bundle.json", "prepared-attempt.json",
             "submitted-attempt.json", "local-preparation.json")
    raw = {name: (root / name).read_bytes() for name in names}
    task, bundle, prepared, submitted, local = [json.loads(raw[name]) for name in names]
    output = root / "retrieved-output-terminal-error" / "rhombus_mobile_ion_e2e_output"
    pass_record = report.get("generation_pass_identity", {}).get("evidence_artifact", {})
    pass_name = pass_record.get("relative_path")
    if not isinstance(pass_name, str) or Path(pass_name).name != pass_name:
        raise ValueError("invalid pass-identity sidecar reference")
    pass_raw = (output / pass_name).read_bytes()
    pass_evidence = json.loads(pass_raw)
    protected_name = report.get("protected_artifact_state_artifact", {}).get("relative_path")
    if (not isinstance(protected_name, str) or Path(protected_name).name != protected_name
            or (output / protected_name).exists()):
        raise ValueError("protected-state sidecar availability differs from original limitation")
    identity = report.get("workspace", {}).get("execution_identity", {})
    if (task.get("config", {}).get("preregistration_sha256") != _sha(prereg_raw)
            or task.get("config", {}).get("ordered_parent_ids") !=
            json.loads(prereg_raw)["parent_selection"]["ordered_parent_ids"]
            or task.get("config", {}).get("config_identity") != report.get("config_identity")
            or prepared.get("state") != "PREPARED" or submitted.get("state") != "SUBMITTED"
            or prepared.get("task_content_hash") != _sha(raw["task.json"])
            or prepared.get("task_bundle_hash") != _sha(raw["task-bundle.json"])
            or submitted.get("previous_hash") != _sha(raw["prepared-attempt.json"])
            or any(prepared.get(key) != submitted.get(key) for key in
                   ("task_id", "task_content_hash", "task_bundle_hash", "attempt_id"))
            or local.get("prepared_attempt_hash") != _sha(raw["prepared-attempt.json"])
            or local.get("workspace_identity") != report.get("workspace")
            or identity.get("prepared_attempt_hash") != _sha(raw["prepared-attempt.json"])
            or identity.get("task_id") != submitted.get("task_id")
            or identity.get("task_content_hash") != submitted.get("task_content_hash")
            or identity.get("task_bundle_hash") != submitted.get("task_bundle_hash")
            or identity.get("attempt_id") != submitted.get("attempt_id")
            or report.get("kaggle", {}).get("kernel_ref") != submitted.get("remote_run_id")
            or pass_record.get("sha256") != _sha(pass_raw)
            or pass_record.get("byte_length") != len(pass_raw)
            or {key: value for key, value in report["generation_pass_identity"].items()
                if key != "evidence_artifact"} != pass_evidence
            or pass_evidence.get("byte_identical") is not True
            or any(pass_evidence.get(key, {}).get("sha256") != _sha(panel_raw)
                   for key in ("pass_1", "pass_2"))
            or pass_evidence.get("identity", {}).get("task_attempt") != identity):
        raise ValueError("M6-B retained task/attempt/pass ancestry mismatch")
    return {
        name.removesuffix(".json").replace("-", "_"): {
            "sha256": _sha(value), "byte_length": len(value)}
        for name, value in (*raw.items(), (pass_name, pass_raw))
    }


def build_selection_reconciliation(report_path: Path, panel_path: Path,
                                   preregistration_path: Path,
                                   *, evidence_directory: Path | None = None) -> dict:
    """Bind original bytes and reconcile only the omitted cohort digest."""
    paths = [Path(report_path), Path(panel_path), Path(preregistration_path)]
    raw = [path.read_bytes() for path in paths]
    report, panel, prereg = [json.loads(value) for value in raw]
    selection = prereg["parent_selection"]
    metadata = panel["metadata"]
    ordered = selection["ordered_parent_ids"]
    if evidence_directory is not None:
        blobs = Path(evidence_directory) / "blobs"
        freeze_bytes = (blobs / selection["source_freeze_sha256"]).read_bytes()
        source_bytes = (blobs / selection["source_panel_sha256"]).read_bytes()
    else:
        audit = Path(__file__).resolve().parents[2] / "data" / "batches" / "audit"
        freeze_bytes = (audit / "candidate-supply-v2-version-9-observational-freeze-v1.json").read_bytes()
        source_bytes = (audit / "g_candidate_supply_v2_mobile_ion_displace_diagnostic_panel.json").read_bytes()
    source_panel = json.loads(source_bytes)
    family_by_parent = {row["parent_id"]: row["parent_chemical_family"]
                        for row in source_panel["rows"]}
    excluded = set(selection["excluded_m6a_parent_ids"])
    expected = [parent for family in ("halide", "other", "oxide", "oxyhalide", "sulfide")
                for parent in sorted(parent for parent, label in family_by_parent.items()
                                     if label == family and parent not in excluded)[:3]]
    digest = _sha(json.dumps(ordered, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8"))
    validations = report.get("validations")
    successful_checks = ("schema", "configuration", "authorization",
                         "paired_identity_accounting", "source_identity",
                         "raw_rows", "summary_reconciliation", "pass_identity")
    if (report.get("final_classification") != "SCIENTIFIC_VALIDATION_FAIL"
            or report.get("config_identity") != prereg.get("configuration_identity")
            or report.get("artifact", {}).get("sha256") != _sha(raw[1])
            or not isinstance(validations, dict)
            or validations.get("selection") is not False
            or any(validations.get(key) is not True for key in successful_checks)
            or validations.get("failure") != "M6-B validation failed: selection"
            or panel.get("artifact_type") != "OBSERVATIONAL_DIAGNOSTIC"
            or metadata.get("ordered_cohort_identity") is not None
            or digest != selection.get("ordered_cohort_sha256")
            or metadata.get("ordered_parent_ids") != ordered
            or metadata.get("parent_chemical_families") != selection.get("ordered_chemical_families")
            or metadata.get("selection_rule") != selection.get("rule")
            or metadata.get("excluded_m6a_parent_ids") != selection.get("excluded_m6a_parent_ids")
            or metadata.get("version_9_freeze_sha256") != selection.get("source_freeze_sha256")
            or metadata.get("version_9_panel_sha256") != selection.get("source_panel_sha256")
            or not isinstance(metadata.get("source_structure_hashes"), list)
            or len(metadata["source_structure_hashes"]) != 15
            or any(not isinstance(value, str) or len(value) != 64
                   or any(char not in "0123456789abcdef" for char in value)
                   for value in metadata["source_structure_hashes"])
            or _sha(freeze_bytes) != selection.get("source_freeze_sha256")
            or _sha(source_bytes) != selection.get("source_panel_sha256")
            or ordered != expected
            or len(ordered) != 15 or len(set(ordered)) != 15
            or any(value is not False for value in panel.get("authorization", {}).values())
            or panel.get("activation_authorized") is not False):
        raise ValueError("M6-B selection reconciliation prerequisites failed")
    sidecar = report.get("protected_artifact_state_artifact")
    ancestry = (_run_ancestry(report, raw[1], raw[2], evidence_directory)
                if evidence_directory is not None else None)
    return {
        "schema_version": "candidate-supply-m6b-selection-reconciliation-v1",
        "artifact_type": "APPEND_ONLY_PROVENANCE_RECONCILIATION",
        "source_bytes": {
            name: {"sha256": _sha(value), "byte_length": len(value)}
            for name, value in zip(("original_report", "original_panel", "preregistration"), raw)
        },
        "source_version_9_bytes": {"freeze_sha256": _sha(freeze_bytes),
                                   "panel_sha256": _sha(source_bytes)},
        "source_run_directory_name": (Path(evidence_directory).name
                                      if evidence_directory is not None else None),
        "retained_run_ancestry": ancestry,
        "reconciled_field": "metadata.ordered_cohort_identity",
        "reconciliation_scope": "ONLY_OMITTED_ORDERED_COHORT_IDENTITY",
        "preregistered_ordered_cohort_sha256": digest,
        "selection_provenance_reconciled": True,
        "original_remote_classification": "SCIENTIFIC_VALIDATION_FAIL",
        "original_overall_provenance": "INCOMPLETE",
        "original_report_rewritten": False,
        "standalone_protected_state": "UNVERIFIED_BYTES_NOT_SUPPLIED" if sidecar else "NO_REFERENCE",
        "missing_standalone_protected_state_reference": sidecar,
        "overall_provenance_pass": False,
        "authorization": {"scheduler_activation": False, "p1_eligibility": False,
                          "operator_superiority": False},
    }


def write_selection_reconciliation(report_path: Path, panel_path: Path,
                                   preregistration_path: Path, receipt_path: Path,
                                   *, evidence_directory: Path | None = None) -> Path:
    """Create a new receipt exclusively; never overwrite an old record."""
    receipt = build_selection_reconciliation(
        report_path, panel_path, preregistration_path,
        evidence_directory=evidence_directory)
    encoded = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with Path(receipt_path).open("xb") as handle:
        handle.write(encoded)
    return Path(receipt_path)
