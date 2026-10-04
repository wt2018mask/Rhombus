"""One authorized CPU E2E task through the generic Kaggle PREPARED gate.

Staging and collection reuse scripts/run.ps1. This control-plane command does
not execute the diagnostic locally or assign a scientific verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Mapping

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from rudeus.execution.backend import BackendAttempt, TaskBundle, advance
from rudeus.execution.code_bundle import reconstruct_bundle, verify_bundle
from rudeus.execution.contracts import ExecutionError, TaskSpec
from rudeus.execution.kaggle_backend import (
    KaggleBackend, KaggleLocalPreparation, KaggleSubmissionFailure, _hardened_e2e_driver,
)
from rudeus.science.contracts import canonical_bytes, digest


RUN_SCRIPT = REPO / "scripts" / "run.ps1"


def _marker(output: str, name: str, *, required: bool = True) -> str | None:
    values = [line.split("=", 1)[1].strip() for line in output.splitlines()
              if line.startswith(name + "=")]
    if not values:
        if required:
            raise ExecutionError(f"missing Kaggle orchestration marker: {name}", "INTEGRITY")
        return None
    if len(set(values)) != 1:
        raise ExecutionError(f"ambiguous Kaggle orchestration marker: {name}", "INTEGRITY")
    return values[0]


def _last_marker(output: str, name: str) -> str | None:
    values = [line.split("=", 1)[1].strip() for line in output.splitlines()
              if line.startswith(name + "=")]
    return values[-1] if values else None


def _powershell(*arguments: str, timeout: int, env: dict | None = None) -> tuple[int, str]:
    executable = os.environ.get("RHOMBUS_POWERSHELL") or shutil.which("pwsh.exe") or \
        shutil.which("powershell.exe")
    if not executable:
        raise ExecutionError("PowerShell is unavailable for hardened Kaggle orchestration", "UNSUPPORTED_INPUT")
    try:
        completed = subprocess.run(
            [executable, "-NoProfile", "-File", str(RUN_SCRIPT), *arguments],
            cwd=REPO, capture_output=True, timeout=timeout, check=False, env=env,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or b"").decode("utf-8", errors="replace") + "\n" + \
            (exc.stderr or b"").decode("utf-8", errors="replace")
        return 124, output + "\nCONTROL_PLANE_TIMEOUT=true\n"
    output = (completed.stdout or b"").decode("utf-8", errors="replace") + "\n" + \
        (completed.stderr or b"").decode("utf-8", errors="replace")
    return completed.returncode, output


def _write_record(directory: Path, name: str, value) -> None:
    (directory / name).write_bytes(canonical_bytes(value))


def _ordered_retained_inventory(records) -> tuple[dict, ...]:
    return tuple(sorted(records, key=lambda item: item["relative_path"]))


def _stage_identity_environment(task, bundle, attempt) -> dict[str, str]:
    """Bind the embedded remote workspace identity to the immutable prepared inputs."""
    driver = _hardened_e2e_driver()
    configuration_identity = task.config.get(
        "config_identity", driver.PASS_IDENTITY_CANARY_CONFIG_IDENTITY,
    )
    execution_mode = task.config.get("execution_mode", "CANDIDATE_DIAGNOSTIC_E2E")
    kernel_identity = task.config.get("kernel_identity", "wt2018mask/rhombus-mobile-ion-e2e")
    values = {
        "RHOMBUS_TASK_ID": task.task_id,
        "RHOMBUS_TASK_CONTENT_HASH": task.content_hash,
        "RHOMBUS_TASK_BUNDLE_HASH": bundle.content_hash,
        "RHOMBUS_CODE_BUNDLE_HASH": bundle.bundle_hash,
        "RHOMBUS_ATTEMPT_ID": attempt.attempt_id,
        "RHOMBUS_PREPARED_ATTEMPT_HASH": attempt.content_hash,
        "RHOMBUS_TASK_CONFIG_HASH": task.config_hash,
        "RHOMBUS_EXECUTION_MODE": execution_mode,
        "RHOMBUS_CONFIGURATION_IDENTITY": configuration_identity,
        "RHOMBUS_KERNEL_IDENTITY": kernel_identity,
    }
    if any(not isinstance(values[name], str) or len(values[name]) != 64
           or any(character not in "0123456789abcdef" for character in value)
           for name, value in values.items() if name not in (
               "RHOMBUS_EXECUTION_MODE", "RHOMBUS_CONFIGURATION_IDENTITY", "RHOMBUS_KERNEL_IDENTITY")):
        raise ExecutionError("prepared task/attempt identity is malformed", "INTEGRITY")
    if (execution_mode not in ("CANDIDATE_DIAGNOSTIC_E2E", "PASS_IDENTITY_CANARY", "M6A_PAIRED_DIAGNOSTIC", "M6B_PAIRED_DIAGNOSTIC")
            or not isinstance(configuration_identity, str) or not configuration_identity):
        raise ExecutionError("prepared execution mode/configuration identity is malformed", "INTEGRITY")
    expected_configuration = {
        "PASS_IDENTITY_CANARY": driver.PASS_IDENTITY_CANARY_CONFIG_IDENTITY,
        "CANDIDATE_DIAGNOSTIC_E2E": driver.CONFIG_IDENTITY,
        "M6A_PAIRED_DIAGNOSTIC": driver.M6A_CONFIG_IDENTITY,
        "M6B_PAIRED_DIAGNOSTIC": driver.M6B_CONFIG_IDENTITY,
    }[execution_mode]
    if configuration_identity != expected_configuration:
        raise ExecutionError("execution mode and configuration identity disagree", "INTEGRITY")
    if execution_mode == "M6B_PAIRED_DIAGNOSTIC" and not re.fullmatch(
            r"wt2018mask/rhombus-m6b-[0-9a-f]{16}", kernel_identity):
        raise ExecutionError("M6-B requires a run-scoped Kaggle kernel identity", "INTEGRITY")
    return values


def _pass_identity_binding(report: dict, workspace: dict) -> tuple[str, bool]:
    """Verify that persisted pass digests name this exact task/workspace/configuration."""
    driver = _hardened_e2e_driver()
    status = driver.generation_pass_identity_status(report)
    evidence = report.get("generation_pass_identity") if isinstance(report, dict) else None
    identity = evidence.get("identity") if isinstance(evidence, dict) else None
    # The preparation record freezes nested mappings as MappingProxyType.
    # canonical_bytes recursively converts those immutable mappings while
    # preserving the exact sorted compact JSON representation used remotely.
    workspace_hash = driver.sha256_bytes(canonical_bytes(workspace))
    matches = (
        isinstance(identity, dict)
        and identity.get("run_id") == workspace.get("run_id")
        and identity.get("task_attempt") == workspace.get("execution_identity")
        and identity.get("workspace_identity_sha256") == workspace_hash
        and identity.get("runtime_manifest_sha256") == workspace.get("runtime_manifest_sha256")
        and identity.get("configuration_identity") == report.get("config_identity")
        == workspace.get("execution_identity", {}).get("configuration_identity")
        and identity.get("configuration_identity_sha256") == driver.sha256_bytes(
            str(workspace.get("execution_identity", {}).get("configuration_identity", "")).encode("utf-8"))
        and identity.get("task_attempt", {}).get("task_config_hash")
        == workspace.get("execution_identity", {}).get("task_config_hash")
    )
    return status, bool(matches)


def _pass_identity_artifacts_match(report: dict, report_path: Path) -> bool:
    """Verify the persisted evidence sidecar and any mismatch diagnostic copy."""
    evidence = report.get("generation_pass_identity") if isinstance(report, dict) else None
    if not isinstance(evidence, dict):
        return False

    def read_bound_artifact(record):
        if not isinstance(record, dict) or not isinstance(record.get("relative_path"), str):
            return None
        relative = Path(record["relative_path"])
        if relative.is_absolute() or len(relative.parts) != 1 or relative.name in (".", ".."):
            return None
        path = Path(report_path).parent / relative
        try:
            raw = path.read_bytes()
        except OSError:
            return None
        if (hashlib.sha256(raw).hexdigest() != record.get("sha256")
                or len(raw) != record.get("byte_length")):
            return None
        return raw

    sidecar = read_bound_artifact(evidence.get("evidence_artifact"))
    if sidecar is None:
        return False
    try:
        sidecar_payload = json.loads(sidecar.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return False
    report_payload = {key: value for key, value in evidence.items() if key != "evidence_artifact"}
    if sidecar_payload != report_payload:
        return False
    diagnostic = evidence.get("pass_2_diagnostic_artifact")
    if evidence.get("byte_identical") is True:
        return diagnostic is None
    return read_bound_artifact(diagnostic) is not None


def _m6a_frozen_inputs(driver):
    """Verify the predeclared parent bands against immutable version-9 bytes."""
    freeze_path = REPO / "data/batches/audit/candidate-supply-v2-version-9-observational-freeze-v1.json"
    freeze_bytes = freeze_path.read_bytes()
    if hashlib.sha256(freeze_bytes).hexdigest() != driver.M6A_VERSION_9_FREEZE_SHA256:
        raise ExecutionError("version-9 freeze hash differs from the M6-A contract", "INTEGRITY")
    freeze = json.loads(freeze_bytes.decode("utf-8"))
    counts = freeze.get("future_evidence_sets", {}).get("repeated_geometry_failure_counts_by_parent")
    if not isinstance(counts, dict):
        raise ExecutionError("version-9 repeated-failure evidence set is missing", "INTEGRITY")
    bands = {
        "GE_10": tuple((parent_id, count) for parent_id, count in sorted(counts.items()) if count >= 10)[:4],
        "5_TO_9": tuple((parent_id, count) for parent_id, count in sorted(counts.items()) if 5 <= count <= 9)[:4],
        "2_TO_4": tuple((parent_id, count) for parent_id, count in sorted(counts.items()) if 2 <= count <= 4)[:4],
    }
    if bands != driver.M6A_PARENT_FAILURE_BANDS:
        raise ExecutionError("version-9 failure bands do not reproduce the declared M6-A selection", "INTEGRITY")
    panel_record = freeze.get("source_artifacts", {}).get("panel", {})
    panel_path = REPO / panel_record.get("path", "")
    panel_bytes = panel_path.read_bytes()
    if (panel_record.get("sha256") != driver.M6A_VERSION_9_PANEL_SHA256
            or hashlib.sha256(panel_bytes).hexdigest() != driver.M6A_VERSION_9_PANEL_SHA256
            or len(panel_bytes) != panel_record.get("byte_length")):
        raise ExecutionError("version-9 panel integrity does not match its freeze record", "INTEGRITY")
    return [
        (freeze_path.relative_to(REPO).as_posix(), freeze_bytes),
        (panel_path.relative_to(REPO).as_posix(), panel_bytes),
    ]


def _m6b_frozen_inputs(driver):
    """Verify pre-M6-A family evidence and reproduce the frozen M6-B selection."""
    artifacts = _m6a_frozen_inputs(driver)
    panel_bytes = next(raw for relative, raw in artifacts if relative.endswith(
        "g_candidate_supply_v2_mobile_ion_displace_diagnostic_panel.json"))
    panel = json.loads(panel_bytes.decode("utf-8"))
    family_by_parent = {}
    for row in panel.get("rows", []):
        parent_id, family = row.get("parent_id"), row.get("parent_chemical_family")
        if not isinstance(parent_id, str) or not isinstance(family, str):
            raise ExecutionError("version-9 panel lacks parent/family selection evidence", "INTEGRITY")
        if parent_id in family_by_parent and family_by_parent[parent_id] != family:
            raise ExecutionError("version-9 panel has inconsistent parent family labels", "INTEGRITY")
        family_by_parent[parent_id] = family
    excluded = set(driver.M6A_PARENT_IDS)
    selected, families = [], []
    for family in ("halide", "other", "oxide", "oxyhalide", "sulfide"):
        eligible = sorted(parent_id for parent_id, value in family_by_parent.items()
                          if value == family and parent_id not in excluded)
        if len(eligible) < 3:
            raise ExecutionError(f"version-9 evidence has fewer than three M6-B {family} parents", "INTEGRITY")
        selected.extend(eligible[:3])
        families.extend([family] * 3)
    if tuple(selected) != driver.M6B_PARENT_IDS or tuple(families) != driver.M6B_PARENT_FAMILIES:
        raise ExecutionError("version-9 family-stratified M6-B selection differs from preregistration", "INTEGRITY")
    return artifacts


def _protected_artifact_state_binding(report: dict, report_path: Path, workspace: dict) -> dict:
    """Verify the standalone protected-hash record and all PREPARED bindings."""
    driver = _hardened_e2e_driver()
    state = report.get("protected_artifact_state") if isinstance(report, dict) else None
    record = report.get("protected_artifact_state_artifact") if isinstance(report, dict) else None
    reason = "invalid protected-artifact state schema or sidecar reference"
    sidecar_path = None
    sidecar_sha = None
    sidecar_length = None
    try:
        relative = Path(record["relative_path"])
        windows_relative = PureWindowsPath(record["relative_path"])
        if (not isinstance(state, dict) or state.get("schema_version") != "protected-artifact-state-v1"
                or not isinstance(record, dict) or relative.is_absolute()
                or len(relative.parts) != 1 or relative.name in (".", "..")
                or windows_relative.is_absolute() or len(windows_relative.parts) != 1
                or windows_relative.name != relative.name):
            raise ValueError(reason)
        sidecar_path = Path(report_path).parent / relative
        sidecar_bytes = sidecar_path.read_bytes()
        sidecar_sha = hashlib.sha256(sidecar_bytes).hexdigest()
        sidecar_length = len(sidecar_bytes)
        if sidecar_sha != record.get("sha256") or sidecar_length != record.get("byte_length"):
            raise ValueError("protected-artifact state sidecar hash/length mismatch")
        if json.loads(sidecar_bytes.decode("utf-8")) != state:
            raise ValueError("protected-artifact state sidecar differs from report record")
        identity = state.get("identity")
        execution_identity = workspace.get("execution_identity")
        workspace_hash = driver.sha256_bytes(canonical_bytes(workspace))
        if (not isinstance(identity, dict)
                or identity.get("run_id") != workspace.get("run_id")
                or identity.get("task_attempt") != execution_identity
                or identity.get("workspace_identity_sha256") != workspace_hash
                or identity.get("runtime_manifest_sha256") != workspace.get("runtime_manifest_sha256")
                or identity.get("configuration_identity") != execution_identity.get("configuration_identity")
                or report.get("config_identity") != execution_identity.get("configuration_identity")):
            raise ValueError("protected-artifact state task/workspace/runtime/configuration binding mismatch")
        before, after = state.get("before"), state.get("after")
        if not isinstance(before, list) or not before or not isinstance(after, list):
            raise ValueError("protected-artifact before/after hash lists are missing")
        def valid_hashes(items):
            return (all(isinstance(item, dict)
                        and isinstance(item.get("path"), str) and item["path"]
                        and isinstance(item.get("sha256"), str)
                        and len(item["sha256"]) == 64
                        and all(char in "0123456789abcdef" for char in item["sha256"])
                        for item in items)
                    and len({item["path"] for item in items}) == len(items))
        if not valid_hashes(before) or not valid_hashes(after):
            raise ValueError("protected-artifact hash entries are malformed or duplicated")
        before_map = {item["path"]: item["sha256"] for item in before}
        after_map = {item["path"]: item["sha256"] for item in after}
        paired = report.get("protected_artifacts")
        expected_paired = [
            {"path": path, "before_sha256": before_map.get(path), "after_sha256": after_map.get(path)}
            for path in sorted(set(before_map) | set(after_map))
        ]
        if (before_map.keys() != after_map.keys() or paired != expected_paired
                or state.get("unchanged") is not (before_map == after_map)):
            raise ValueError("protected-artifact before/after report reconciliation failed")
        return {
            "verified": True, "reason": None, "sidecar_path": str(sidecar_path),
            "sidecar_sha256": sidecar_sha, "sidecar_byte_length": sidecar_length,
            "before": before, "after": after, "unchanged": state["unchanged"],
            "identity_bindings_match": True, "identity": identity,
        }
    except (OSError, KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "verified": False, "reason": str(exc) or reason,
            "sidecar_path": str(sidecar_path) if sidecar_path else None,
            "sidecar_sha256": sidecar_sha, "sidecar_byte_length": sidecar_length,
            "identity_bindings_match": False,
        }


def _canary_operation_artifact_matches(report: dict, report_path: Path, workspace: dict) -> dict:
    record = report.get("protected_artifact_canary_operation") if isinstance(report, dict) else None
    try:
        if not isinstance(record, dict) or not isinstance(record.get("relative_path"), str):
            raise ValueError("synthetic operation artifact reference is invalid")
        relative = Path(record["relative_path"])
        if relative.is_absolute() or len(relative.parts) != 1:
            raise ValueError("synthetic operation artifact reference is invalid")
        path = Path(report_path).parent / relative
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        retained = payload.get("retained_after_artifact")
        if not isinstance(retained, dict) or not isinstance(retained.get("relative_path"), str):
            raise ValueError("retained synthetic operation artifact reference is invalid")
        retained_relative = Path(retained["relative_path"])
        if retained_relative.is_absolute() or len(retained_relative.parts) != 1:
            raise ValueError("retained synthetic operation artifact reference is invalid")
        retained_path = Path(report_path).parent / retained_relative
        retained_bytes = retained_path.read_bytes()
        driver = _hardened_e2e_driver()
        transition = payload.get("protected_artifact")
        identity = payload.get("identity")
        if not isinstance(transition, dict) or not isinstance(identity, dict):
            raise ValueError("synthetic operation identity or protected transition is malformed")
        if (hashlib.sha256(raw).hexdigest() != record.get("sha256")
                or len(raw) != record.get("byte_length")
                or payload.get("schema_version") != "protected-artifact-provenance-canary-operation-v1"
                or payload.get("run_id") != workspace.get("run_id")
                or identity.get("task_attempt") != workspace.get("execution_identity")
                or identity.get("runtime_manifest_sha256") != workspace.get("runtime_manifest_sha256")
                or identity.get("configuration_identity") !=
                workspace.get("execution_identity", {}).get("configuration_identity")
                or identity.get("workspace_identity_sha256") != driver.sha256_bytes(canonical_bytes(workspace))
                or payload.get("operation") != "deterministic-protected-file-transform"
                or payload.get("input_sha256") != transition.get("before_sha256")
                or payload.get("result_sha256") != transition.get("after_sha256")
                or payload.get("input_sha256") == payload.get("result_sha256")
                or transition.get("before_sha256") != driver.sha256_bytes(
                    driver.PROTECTED_PROVENANCE_CANARY_BEFORE_BYTES)
                or transition.get("after_sha256") != driver.sha256_bytes(
                    driver.PROTECTED_PROVENANCE_CANARY_AFTER_BYTES)
                or len(retained_bytes) != retained.get("byte_length")
                or hashlib.sha256(retained_bytes).hexdigest() != retained.get("sha256")
                or retained.get("sha256") != transition.get("after_sha256")
                or retained_bytes != driver.PROTECTED_PROVENANCE_CANARY_AFTER_BYTES):
            raise ValueError("synthetic operation output hash or identity mismatch")
        return {"verified": True, "path": str(path), "sha256": record["sha256"],
                "byte_length": record["byte_length"],
                "protected_artifact": transition,
                "retained_after_path": str(retained_path),
                "retained_after_sha256": retained.get("sha256"),
                "retained_after_byte_length": retained.get("byte_length")}
    except (OSError, KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        return {"verified": False, "reason": str(exc)}


def _make_task(directory: Path, *, pass_identity_canary: bool = False, m6a_mode: bool = False,
               m6b_mode: bool = False, kernel_identity: str | None = None):
    if sum((pass_identity_canary, m6a_mode, m6b_mode)) > 1:
        raise ValueError("execution mode flags are mutually exclusive")
    driver = _hardened_e2e_driver()
    if m6b_mode and (not isinstance(kernel_identity, str) or not re.fullmatch(
            r"wt2018mask/rhombus-m6b-[0-9a-f]{16}", kernel_identity)):
        raise ValueError("M6-B requires a unique run-scoped Kaggle kernel identity")
    frozen_inputs = (_m6b_frozen_inputs(driver) if m6b_mode else
                     _m6a_frozen_inputs(driver) if m6a_mode else [])
    preregistration = None
    if pass_identity_canary:
        source_bytes = b"rhombus-pass-identity-canary-input-v1\n"
        source_relative = "synthetic/pass-identity-canary-input-v1.bin"
        configuration = {
            "config_identity": driver.PASS_IDENTITY_CANARY_CONFIG_IDENTITY,
            "execution_mode": "PASS_IDENTITY_CANARY",
            "synthetic_pass_sha256": hashlib.sha256(driver.PASS_IDENTITY_CANARY_PASS_BYTES).hexdigest(),
            "synthetic_pass_byte_length": len(driver.PASS_IDENTITY_CANARY_PASS_BYTES),
            "candidate_generation_performed": False,
        }
        candidate_id = "pass-identity-canary"
        stage = "PASS_IDENTITY_CANARY"
        expected_outputs = ("e2e_report", "pass_identity_evidence",
                            "protected_artifact_state", "synthetic_operation")
        provenance = {"purpose": "synthetic pass identity and protected-artifact provenance canary"}
    elif m6a_mode:
        configuration = {
            "config_identity": driver.M6A_CONFIG_IDENTITY,
            "execution_mode": "M6A_PAIRED_DIAGNOSTIC",
            "target_species": driver.M6A_TARGET_SPECIES,
            "sigma_A_provisional": driver.M6A_SIGMA,
            "base_seeds": list(driver.M6A_SEEDS),
            "ordered_parent_ids": list(driver.M6A_PARENT_IDS),
            "historical_geometry_failure_bands": {
                band: [{"parent_id": parent_id, "count": count} for parent_id, count in members]
                for band, members in driver.M6A_PARENT_FAILURE_BANDS.items()
            },
            "selection_rule": "first four IDs lexically per immutable version-9 failure-count band",
            "version_9_freeze_sha256": driver.M6A_VERSION_9_FREEZE_SHA256,
            "version_9_panel_sha256": driver.M6A_VERSION_9_PANEL_SHA256,
            "arms": [
                {"operator_name": "mobile-ion-displace", "operator_version": "mobile-ion-displace-v2"},
                {"operator_name": driver.M6A_OPERATOR_NAME,
                 "operator_version": driver.M6A_OPERATOR_VERSION,
                 "max_direction_trials": driver.M6A_DIRECTION_BUDGET},
            ],
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
            "candidate_generation_mode": "OBSERVATIONAL_PAIRED_DIAGNOSTIC",
            "scheduler_activation": False,
            "p1_authorized": False,
        }
        source_path = REPO / driver.INPUT_RELATIVE
        source_bytes = source_path.read_bytes()
        source_relative = driver.INPUT_RELATIVE
        candidate_id = "candidate-supply-v2-m6a-paired-diagnostic"
        stage = "M6A_PAIRED_DIAGNOSTIC"
        expected_outputs = ("paired_diagnostic_panel", "e2e_report")
        provenance = {
            "source_artifact": source_relative,
            "version_9_freeze_sha256": driver.M6A_VERSION_9_FREEZE_SHA256,
            "version_9_panel_sha256": driver.M6A_VERSION_9_PANEL_SHA256,
        }
    elif m6b_mode:
        source_path = REPO / driver.INPUT_RELATIVE
        source_bytes = source_path.read_bytes()
        source_relative = driver.INPUT_RELATIVE
        config_hash = driver.M6B_CONFIG_IDENTITY
        preregistration = {
            "schema_version": "candidate-supply-v2-m6b-preregistration-v1",
            "evidence_class": "PREREGISTERED_OBSERVATIONAL_DIAGNOSTIC",
            "configuration_identity": config_hash,
            "provider_kernel_identity": kernel_identity,
            "parent_selection": {
                "rule": driver.M6B_SELECTION_RULE,
                "ordered_parent_ids": list(driver.M6B_PARENT_IDS),
                "ordered_chemical_families": list(driver.M6B_PARENT_FAMILIES),
                "excluded_m6a_parent_ids": list(driver.M6A_PARENT_IDS),
                "source_freeze_sha256": driver.M6A_VERSION_9_FREEZE_SHA256,
                "source_panel_sha256": driver.M6A_VERSION_9_PANEL_SHA256,
                "selection_basis": "pre-M6-A version-9 row family labels and lexical parent IDs only",
                "ordered_cohort_sha256": hashlib.sha256(json.dumps(
                    list(driver.M6B_PARENT_IDS), separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")).hexdigest(),
            },
            "experiment": {
                "target_species": "Li",
                "sigma_A": driver.M6B_SIGMA,
                "seeds": list(driver.M6B_SEEDS),
                "arms": [
                    {"id": "BASELINE_GAUSSIAN", "operator": "mobile-ion-displace-v2"},
                    {"id": "GAUSSIAN_LOCAL_D8", "operator": driver.M6A_OPERATOR_VERSION,
                     "max_direction_trials": driver.M6B_DIRECTION_BUDGET},
                ],
                "paired_identity_count": len(driver.M6B_PARENT_IDS) * len(driver.M6B_SEEDS),
                "arm_observation_count": 2 * len(driver.M6B_PARENT_IDS) * len(driver.M6B_SEEDS),
                "rng": "deterministic operator-scoped identities from parent, seed, operator and version",
            },
            "analysis_rules": {
                "primary": "paired geometry-failure transitions; report by family and seed, with generated/accepted/exhausted coverage",
                "secondary": ["novelty", "P0 plausibility", "useful diagnostic yield", "parent-level and seed consistency", "effort"],
                "advance_to_m7_only_if": [
                    "all 45 paired identities are present and both arms preserve the same parent/seed coverage",
                    "D8 has fewer geometry failures overall, in at least 3 of 5 families, and in each of the 3 seed blocks",
                    "D8 useful count is not lower overall, is not lower in at least 3 families, and no family loses more than 2 useful observations",
                    "no repeated new failure mode invalidates the paired geometry finding",
                ],
                "otherwise": "retain D8 as experimental or revise it; do not activate or authorize P1",
                "scheduler_activation": False,
                "p1_eligibility_authorized": False,
                "global_operator_superiority_claim": False,
            },
        }
        prereg_bytes = canonical_bytes(preregistration)
        prereg_path = directory / "m6b-preregistration.json"
        with prereg_path.open("xb") as handle:
            handle.write(prereg_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        configuration = {
            "config_identity": config_hash,
            "execution_mode": "M6B_PAIRED_DIAGNOSTIC",
            "kernel_identity": kernel_identity,
            "target_species": "Li",
            "sigma_A_provisional": driver.M6B_SIGMA,
            "base_seeds": list(driver.M6B_SEEDS),
            "ordered_parent_ids": list(driver.M6B_PARENT_IDS),
            "preregistration_sha256": hashlib.sha256(prereg_bytes).hexdigest(),
            "version_9_freeze_sha256": driver.M6A_VERSION_9_FREEZE_SHA256,
            "version_9_panel_sha256": driver.M6A_VERSION_9_PANEL_SHA256,
            "scheduler_activation": False,
            "p1_eligibility_authorized": False,
        }
        candidate_id = "candidate-supply-v2-m6b-independent-paired-replication"
        stage = "M6B_PAIRED_DIAGNOSTIC"
        expected_outputs = ("paired_diagnostic_panel", "e2e_report", "pass_identity_evidence",
                            "protected_artifact_state")
        provenance = {
            "source_artifact": source_relative,
            "m6b_preregistration_sha256": hashlib.sha256(prereg_bytes).hexdigest(),
            "provider_kernel_identity": kernel_identity,
            "version_9_freeze_sha256": driver.M6A_VERSION_9_FREEZE_SHA256,
            "version_9_panel_sha256": driver.M6A_VERSION_9_PANEL_SHA256,
        }
    else:
        source_path = REPO / driver.INPUT_RELATIVE
        source_bytes = source_path.read_bytes()
        source_relative = driver.INPUT_RELATIVE
        configuration = {
            "test_identity": driver.TEST_IDENTITY,
            "config_identity": driver.CONFIG_IDENTITY,
            "target_species": driver.TARGET_SPECIES,
            "sigmas": driver.SIGMAS,
            "seeds": driver.SEEDS,
            "persistent_threshold": driver.PERSISTENT_THRESHOLD,
            "execution_mode": "CANDIDATE_DIAGNOSTIC_E2E",
        }
        candidate_id = "ordered-obelix-mobile-ion-diagnostic"
        stage = "MOBILE_ION_DIAGNOSTIC_E2E"
        expected_outputs = ("diagnostic_panel", "e2e_report")
        provenance = {"source_artifact": source_relative}
    input_artifacts = [(source_relative, source_bytes), *frozen_inputs]
    source_hashes = [hashlib.sha256(raw).hexdigest() for _relative, raw in input_artifacts]
    source_hash = source_hashes[0]
    provenance = {
        **provenance,
        "input_artifacts": [
            {"relative_path": relative, "sha256": raw_hash, "byte_length": len(raw)}
            for (relative, raw), raw_hash in zip(input_artifacts, source_hashes)
        ],
    }
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, check=True,
    ).stdout.decode("ascii").strip()
    fields = dict(
        candidate_id=candidate_id,
        stage=stage,
        protocol_hash=digest({"diagnostic": stage, "configuration": configuration}),
        config=configuration,
        input_artifact_hashes=tuple(source_hashes), dependencies=(),
        code_revision=head, resource_requirements={"cpu_only": True},
        expected_outputs=expected_outputs,
        retry_policy={"policy": "new-attempt-per-retry"},
        provenance={**provenance, "source_artifact_raw_sha256": source_hash},
    )
    provisional = TaskSpec(**fields)
    code = reconstruct_bundle(provisional, git_root=REPO)
    task = TaskSpec(**fields, code_bundle_hash=code.bundle_hash)
    verify_bundle(code, code.bundle_hash, task, git_root=REPO)
    retained_files = []
    for (_relative, raw), raw_hash in zip(input_artifacts, source_hashes):
        blob = directory / "blobs" / raw_hash
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(raw)
        retained_files.append({"relative_path": f"blobs/{raw_hash}",
                              "raw_sha256": raw_hash, "size_bytes": len(raw)})
    bundle = TaskBundle(
        task=task.to_dict(), task_content_hash=task.content_hash,
        code_bundle=code.to_dict(), bundle_hash=code.bundle_hash,
        retained_files=_ordered_retained_inventory(retained_files),
    )
    _write_record(directory, "task.json", task)
    _write_record(directory, "task-bundle.json", bundle)
    return task, bundle


def _verify_collection(output: str, preparation, submitted, directory: Path) -> dict:
    state = _last_marker(output, "REMOTE_STATE")
    report_path_text = _marker(output, "LOCAL_REPORT_PATH", required=False)
    artifact_path_text = _marker(output, "LOCAL_ARTIFACT_PATH", required=False)
    result = {
        "task_id": submitted.task_id,
        "task_content_hash": submitted.task_content_hash,
        "task_bundle_hash": submitted.task_bundle_hash,
        "attempt_id": submitted.attempt_id,
        "prepared_attempt_hash": preparation.prepared_attempt_hash,
        "submitted_attempt_hash": submitted.content_hash,
        "provider_run_id": submitted.remote_run_id,
        "kernel_identity": preparation.kernel_spec["id"],
        "workspace_run_id": preparation.workspace_identity["run_id"],
        "terminal_provider_state": state,
        "report_path": report_path_text,
        "artifact_path": artifact_path_text,
        "report_sha256": None,
        "artifact_sha256": None,
        "report_workspace_matches": False,
        "artifact_hash_matches": False,
        "artifact_identity_matches": False,
        "power_shell_report_ok": _marker(output, "REPORT_OK", required=False),
        "power_shell_artifact_hash_ok": _marker(output, "ARTIFACT_HASH_OK", required=False),
        "local_acceptance": _marker(output, "LOCAL_ACCEPTANCE", required=False),
        "attempt_chain_ok": submitted.previous_hash == preparation.prepared_attempt_hash,
    }
    if report_path_text and Path(report_path_text).is_file():
        report_path = Path(report_path_text)
        report_bytes = report_path.read_bytes()
        report = json.loads(report_bytes)
        result["report_sha256"] = hashlib.sha256(report_bytes).hexdigest()
        result["report_output_sha256"] = _last_marker(output, "DOWNLOADED_REPORT_SHA256")
        result["report_hash_matches"] = (
            result["report_sha256"] == result["report_output_sha256"]
        )
        result["report_workspace_matches"] = (
            report.get("schema_version") == "mobile-ion-displace-e2e-report-v1"
            and
            report.get("run_id") == preparation.workspace_identity["run_id"]
            and canonical_bytes(report.get("workspace")) == canonical_bytes(preparation.workspace_identity)
            and report.get("kaggle", {}).get("kernel_ref") == preparation.kernel_spec["id"]
        )
        result["remote_classification"] = report.get("final_classification")
        pass_identity_status, pass_identity_binding_matches = _pass_identity_binding(
            report, preparation.workspace_identity,
        )
        result["pass_identity_status"] = pass_identity_status
        result["pass_identity_binding_matches"] = pass_identity_binding_matches
        result["pass_identity_artifacts_match"] = _pass_identity_artifacts_match(report, report_path)
        result["protected_artifact_state"] = _protected_artifact_state_binding(
            report, report_path, preparation.workspace_identity,
        )
        result["protected_artifact_canary_operation"] = _canary_operation_artifact_matches(
            report, report_path, preparation.workspace_identity,
        )
        result["protected_artifact_state_path"] = result["protected_artifact_state"].get("sidecar_path")
        result["protected_artifact_state_sha256"] = result["protected_artifact_state"].get("sidecar_sha256")
        pass_evidence = report.get("generation_pass_identity")
        sidecar_record = (pass_evidence.get("evidence_artifact")
                          if isinstance(pass_evidence, dict) else None)
        if isinstance(sidecar_record, dict) and isinstance(sidecar_record.get("relative_path"), str):
            result["pass_identity_sidecar_path"] = str(
                report_path.parent / sidecar_record["relative_path"])
            result["pass_identity_sidecar_sha256"] = sidecar_record.get("sha256")
            result["pass_identity_sidecar_byte_length"] = sidecar_record.get("byte_length")
        result["artifact_reported_sha256"] = report.get("artifact", {}).get("sha256")
        if artifact_path_text and Path(artifact_path_text).is_file():
            artifact_bytes = Path(artifact_path_text).read_bytes()
            result["artifact_sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
            result["artifact_hash_matches"] = (
                result["artifact_sha256"] == result["artifact_reported_sha256"])
            result["artifact_identity_matches"] = (
                Path(artifact_path_text).name ==
                Path(report.get("artifact", {}).get("relative_path", "")).name
            )
            result["artifact_schema_version"] = json.loads(artifact_bytes).get("schema_version")
            if report.get("config_identity") in (
                    _hardened_e2e_driver().M6A_CONFIG_IDENTITY,
                    _hardened_e2e_driver().M6B_CONFIG_IDENTITY):
                driver = _hardened_e2e_driver()
                artifact = json.loads(artifact_bytes)
                pass_evidence = report.get("generation_pass_identity", {})
                pass1 = pass_evidence.get("pass_1", {})
                sidecar_ok = (
                    result.get("pass_identity_status") == "IDENTICAL"
                    and pass1.get("sha256") == result["artifact_sha256"]
                    and pass1.get("byte_length") == len(artifact_bytes)
                )
                try:
                    validator = (driver.validate_m6b_panel if report.get("config_identity")
                                 == driver.M6B_CONFIG_IDENTITY else driver.validate_m6a_panel)
                    m6_checks = validator(artifact, artifact_bytes, artifact_bytes) if sidecar_ok else None
                except Exception as exc:
                    m6_checks = {"failure": f"{type(exc).__name__}: {exc}"}
                validation_key = "m6b" if report.get("config_identity") == driver.M6B_CONFIG_IDENTITY else "m6a"
                result[f"{validation_key}_artifact_checks"] = m6_checks
                result[f"{validation_key}_artifact_valid"] = isinstance(m6_checks, dict) and not m6_checks.get("failure")
    return result


def _retain_collection_outputs(output: str, evidence_directory: Path) -> str:
    """Copy every downloaded provider output byte-for-byte into the run evidence directory."""
    result_text = _last_marker(output, "LOCAL_RESULT_DIR")
    if not result_text:
        raise ExecutionError("collector did not report its local output directory", "INTEGRITY")
    source_root = Path(result_text)
    if not source_root.is_dir():
        raise ExecutionError("collector output directory is missing", "INTEGRITY")
    destination_root = evidence_directory / "retrieved-output"
    if os.name == "nt" and any(
            len(str(destination_root / path.name)) >= 240
            for path in source_root.rglob("*") if path.is_file()):
        # Preserve report-relative sidecar filenames while allowing long
        # content-addressed names in a deeply nested evidence directory.
        destination_root = Path("\\\\?\\" + str(destination_root.absolute()))
    destination_root.mkdir(parents=True, exist_ok=False)
    report_marker = _last_marker(output, "LOCAL_REPORT_PATH")
    if not report_marker or not Path(report_marker).is_file():
        raise ExecutionError("collector report is missing", "INTEGRITY")
    report = json.loads(Path(report_marker).read_bytes())
    sidecar_record = report.get("protected_artifact_state_artifact")
    sidecar_name = None
    if sidecar_record is not None:
        if not isinstance(sidecar_record, dict) or not isinstance(sidecar_record.get("relative_path"), str):
            raise ExecutionError("invalid protected-state sidecar reference", "INTEGRITY")
        sidecar_name = sidecar_record["relative_path"]
        if (PureWindowsPath(sidecar_name).name != sidecar_name
                or Path(sidecar_name).name != sidecar_name or sidecar_name in (".", "..")):
            raise ExecutionError("unsafe protected-state sidecar path", "INTEGRITY")
    copied = {}
    for source in sorted(source_root.rglob("*")):
        if source.is_symlink():
            raise ExecutionError("collector output unexpectedly contains a symlink", "INTEGRITY")
        if not source.is_file():
            continue
        destination = destination_root / source.name
        if destination.name in copied:
            raise ExecutionError("provider output contains duplicate flat filenames", "INTEGRITY")
        shutil.copyfile(source, destination)
        if source.stat().st_size != destination.stat().st_size or hashlib.sha256(
                source.read_bytes()).digest() != hashlib.sha256(destination.read_bytes()).digest():
            raise ExecutionError("byte-preserving output retention verification failed", "INTEGRITY")
        copied[source.name] = destination
    if sidecar_name is not None:
        retained_sidecar = copied.get(sidecar_name)
        if retained_sidecar is None:
            raise ExecutionError("referenced protected-state sidecar was not downloaded", "INTEGRITY")
        raw = retained_sidecar.read_bytes()
        if (hashlib.sha256(raw).hexdigest() != sidecar_record.get("sha256")
                or len(raw) != sidecar_record.get("byte_length")):
            raise ExecutionError("retained protected-state sidecar differs from report binding", "INTEGRITY")
    rewritten = output.replace(
        f"LOCAL_RESULT_DIR={source_root}", f"LOCAL_RESULT_DIR={destination_root}"
    )
    for marker in ("LOCAL_REPORT_PATH", "LOCAL_ARTIFACT_PATH"):
        old = _last_marker(output, marker)
        if old:
            source_path = Path(old)
            retained = copied.get(source_path.name)
            if retained is None:
                raise ExecutionError(f"collector-reported {marker} was not retained", "INTEGRITY")
            rewritten = rewritten.replace(f"{marker}={old}", f"{marker}={retained}")
    return rewritten


def _verify_pass_identity_canary(result: dict, report_path: Path, workspace: dict) -> dict:
    """Require the expected controlled validation failure and intact evidence."""
    driver = _hardened_e2e_driver()
    report = json.loads(Path(report_path).read_bytes())
    evidence = report.get("generation_pass_identity")
    expected_sha = hashlib.sha256(driver.PASS_IDENTITY_CANARY_PASS_BYTES).hexdigest()
    expected_length = len(driver.PASS_IDENTITY_CANARY_PASS_BYTES)
    validations = report.get("validations")
    state = report.get("protected_artifact_state")
    operation = result.get("protected_artifact_canary_operation", {})
    transition = operation.get("protected_artifact") if isinstance(operation, dict) else None
    before_map = ({item.get("path"): item.get("sha256") for item in state.get("before", [])}
                  if isinstance(state, dict) else {})
    after_map = ({item.get("path"): item.get("sha256") for item in state.get("after", [])}
                 if isinstance(state, dict) else {})
    changed_paths = sorted(path for path in before_map.keys() | after_map.keys()
                           if before_map.get(path) != after_map.get(path))
    transition_matches = (
        isinstance(transition, dict)
        and transition.get("path") == report.get("protected_artifact_canary_target")
        and changed_paths == [transition.get("path")]
        and before_map.get(transition.get("path")) == transition.get("before_sha256")
        and after_map.get(transition.get("path")) == transition.get("after_sha256")
        and isinstance(state, dict)
        and state.get("unchanged") is False
    )
    passed = (
        result.get("terminal_provider_state") == "ERROR"
        and result.get("remote_classification") == "SCIENTIFIC_VALIDATION_FAIL"
        and result.get("report_workspace_matches") is True
        and result.get("report_sha256") is not None
        and result.get("report_hash_matches") is True
        and result.get("attempt_chain_ok") is True
        and result.get("power_shell_report_ok") == "true"
        and result.get("pass_identity_status") == "IDENTICAL"
        and result.get("pass_identity_binding_matches") is True
        and result.get("pass_identity_artifacts_match") is True
        and result.get("protected_artifact_state", {}).get("verified") is True
        and result.get("protected_artifact_state", {}).get("identity_bindings_match") is True
        and result.get("protected_artifact_canary_operation", {}).get("verified") is True
        and transition_matches
        and result.get("initial_provider_observation", {}).get("provider_state") ==
        result.get("terminal_provider_state")
        and isinstance(validations, dict)
        and validations.get("pass_identity_canary") is True
        and validations.get("controlled_failure_code") ==
        "PASS_IDENTITY_CANARY_CONTROLLED_DOWNSTREAM_FAILURE"
        and validations.get("candidate_generation_performed") is False
        and validations.get("protected_artifact_state_persisted") is True
        and isinstance(evidence, dict)
        and evidence.get("byte_identical") is True
        and evidence.get("pass_1") == {"sha256": expected_sha, "byte_length": expected_length}
        and evidence.get("pass_2") == {"sha256": expected_sha, "byte_length": expected_length}
        and evidence.get("identity", {}).get("task_attempt") == workspace.get("execution_identity")
        and evidence.get("identity", {}).get("configuration_identity") ==
        driver.PASS_IDENTITY_CANARY_CONFIG_IDENTITY
        and result.get("artifact_path") in (None, "")
    )
    return {
        "verified": bool(passed),
        "expected_provider_error": result.get("terminal_provider_state") == "ERROR",
        "controlled_validation_failure": validations.get("controlled_failure_code")
        if isinstance(validations, dict) else None,
        "candidate_generation_performed": validations.get("candidate_generation_performed")
        if isinstance(validations, dict) else None,
        "pass_identity_sha256": expected_sha,
        "pass_identity_byte_length": expected_length,
        "pass_1_sha256": (evidence.get("pass_1", {}).get("sha256")
                          if isinstance(evidence, dict) else None),
        "pass_1_byte_length": (evidence.get("pass_1", {}).get("byte_length")
                               if isinstance(evidence, dict) else None),
        "pass_2_sha256": (evidence.get("pass_2", {}).get("sha256")
                          if isinstance(evidence, dict) else None),
        "pass_2_byte_length": (evidence.get("pass_2", {}).get("byte_length")
                               if isinstance(evidence, dict) else None),
        "sidecar_path": result.get("pass_identity_sidecar_path"),
        "sidecar_sha256": result.get("pass_identity_sidecar_sha256"),
        "sidecar_byte_length": result.get("pass_identity_sidecar_byte_length"),
        "report_sha256": result.get("report_sha256"),
        "protected_artifact_state_verified": result.get("protected_artifact_state", {}).get("verified"),
        "protected_artifact_state_reason": result.get("protected_artifact_state", {}).get("reason"),
        "protected_artifact_state_path": result.get("protected_artifact_state_path"),
        "protected_artifact_state_sha256": result.get("protected_artifact_state_sha256"),
        "protected_artifact_state_before": result.get("protected_artifact_state", {}).get("before"),
        "protected_artifact_state_after": result.get("protected_artifact_state", {}).get("after"),
        "protected_artifact_state_unchanged": result.get("protected_artifact_state", {}).get("unchanged"),
        "protected_artifact_state_identity": result.get("protected_artifact_state", {}).get("identity"),
        "protected_artifact_operation": result.get("protected_artifact_canary_operation"),
        "protected_artifact_transition_matches": transition_matches,
    }


def _parse_provider_status_output(kernel_ref: str, exit_code: int, text: str) -> str | None:
    prefix = kernel_ref + " has status "
    if exit_code != 0:
        return None
    pattern = re.compile(
        re.escape(prefix) + r"[\"']?KernelWorkerStatus\.(PENDING|RUNNING|COMPLETE|ERROR|FAILED|CANCELLED|CANCELED)[\"']?\.?"
    )
    for line in text.splitlines():
        match = pattern.fullmatch(line.strip())
        if match:
            return match.group(1)
    return None


def _query_provider_once(kernel_ref: str) -> dict:
    """Make exactly one bounded, read-only provider status query."""
    try:
        venv_python = REPO / ".venv" / "Scripts" / "python.exe"
        kaggle_python = str(venv_python) if venv_python.is_file() else (
            os.environ.get("RHOMBUS_PYTHON") or sys.executable
        )
        response = subprocess.run(
            [kaggle_python, "-m", "kaggle", "kernels", "status", kernel_ref],
            capture_output=True, timeout=45, check=False,
        )
        text = ((response.stdout or b"").decode("utf-8", errors="replace") + "\n" +
                (response.stderr or b"").decode("utf-8", errors="replace"))
        state = _parse_provider_status_output(kernel_ref, response.returncode, text)
        return {
            "kernel_identity": kernel_ref,
            "query_exit_code": response.returncode,
            "provider_state": state or "STATUS_UNOBSERVABLE",
            "observation_class": "STATUS" if state else "QUERY_OR_PARSE_FAILURE",
            "output_tail": text[-4000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "kernel_identity": kernel_ref,
            "query_exit_code": 124,
            "provider_state": "STATUS_UNOBSERVABLE",
            "observation_class": "QUERY_OR_PARSE_FAILURE",
            "output_tail": f"{type(exc).__name__}: {exc}",
        }


def _persist_provider_observation(directory: Path, observation: dict) -> Path:
    existing = [int(match.group(1)) for path in directory.glob("provider-observation-*.json")
                if (match := re.fullmatch(r"provider-observation-(\d{4})\.json", path.name))]
    sequence = max(existing, default=0) + 1
    path = directory / f"provider-observation-{sequence:04d}.json"
    _write_record(directory, path.name, observation)
    return path


def _observe_and_collect(directory: Path, preparation, submitted, *, canary_mode: bool,
                         m6a_mode: bool = False,
                         m6b_mode: bool = False,
                         initial_observation: dict | None = None) -> int:
    kernel_ref = preparation.kernel_spec["id"]
    observation = dict(initial_observation) if initial_observation is not None else _query_provider_once(kernel_ref)
    observation.update({
        "provider_run_id": submitted.remote_run_id,
        "kernel_version": submitted.provider_provenance.get("kernel_version")
        if isinstance(submitted.provider_provenance, Mapping) else None,
        "workspace_run_id": preparation.workspace_identity["run_id"],
        "submitted_attempt_hash": submitted.content_hash,
    })
    observation_path = _persist_provider_observation(directory, observation)
    print(f"PROVIDER_OBSERVATION_PATH={observation_path}", flush=True)
    print(f"PROVIDER_STATE_AFTER_ACCEPTANCE={observation['provider_state']}", flush=True)
    print(f"PROVIDER_RUN_ID={submitted.remote_run_id}", flush=True)
    print(f"KERNEL_IDENTITY={kernel_ref}", flush=True)
    print(f"WORKSPACE_RUN_ID={preparation.workspace_identity['run_id']}", flush=True)
    print(f"SUBMITTED_ATTEMPT_HASH={submitted.content_hash}", flush=True)
    if observation["provider_state"] not in ("COMPLETE", "ERROR", "FAILED", "CANCELLED", "CANCELED"):
        print("GENERIC_E2E_RESULT=OBSERVATION_INCOMPLETE_NO_RESUBMISSION", flush=True)
        return 3

    stage_output = (directory / "stage.log").read_text(encoding="utf-8")
    dataset_root = Path(_marker(stage_output, "STAGED_DATASET_PATH"))
    kernel_stage = Path(_marker(stage_output, "STAGED_KERNEL_PATH"))
    run_id = _marker(stage_output, "STAGED_WORKSPACE_RUN_ID")
    collect_env = {
        **os.environ,
        "RHOMBUS_COLLECT_ONCE": "1",
        "RHOMBUS_KNOWN_PROVIDER_STATE": observation["provider_state"],
        "RHOMBUS_KERNEL_IDENTITY": kernel_ref,
    }
    collect_exit, collect_output = _powershell(
        "kaggle-mobile-ion-collect", str(dataset_root), str(kernel_stage), run_id,
        timeout=180, env=collect_env,
    )
    (directory / "collection.log").write_text(collect_output, encoding="utf-8")
    if m6b_mode and _last_marker(collect_output, "LOCAL_RESULT_DIR"):
        collect_output = _retain_collection_outputs(collect_output, directory)
        (directory / "collection.log").write_text(collect_output, encoding="utf-8")
    collection_state = _last_marker(collect_output, "REMOTE_STATE")
    if collection_state not in ("COMPLETE", "ERROR"):
        _write_record(directory, "collection-observation-incomplete.json", {
            "initial_provider_observation": observation,
            "collection_exit_code": collect_exit,
            "collection_remote_state": collection_state,
            "collection_output_sha256": hashlib.sha256(collect_output.encode("utf-8")).hexdigest(),
            "collection_log": str(directory / "collection.log"),
            "result": "OBSERVATION_INCOMPLETE_NO_RESUBMISSION",
        })
        print("GENERIC_E2E_RESULT=OBSERVATION_INCOMPLETE_NO_RESUBMISSION", flush=True)
        return 3
    result = _verify_collection(collect_output, preparation, submitted, directory)
    result["collector_exit_code"] = collect_exit
    result["initial_provider_observation"] = observation
    if m6a_mode:
        verified = (
            result.get("terminal_provider_state") == "COMPLETE"
            and result.get("report_workspace_matches") is True
            and result.get("report_hash_matches") is True
            and result.get("artifact_hash_matches") is True
            and result.get("artifact_identity_matches") is True
            and result.get("attempt_chain_ok") is True
            and result.get("pass_identity_status") == "IDENTICAL"
            and result.get("pass_identity_binding_matches") is True
            and result.get("pass_identity_artifacts_match") is True
            and result.get("protected_artifact_state", {}).get("verified") is True
            and result.get("m6a_artifact_valid") is True
            and result.get("remote_classification") == "PASS"
            and result.get("local_acceptance") == "PASS"
        )
        result["m6a_verification"] = {"verified": bool(verified)}
        _write_record(directory, "verified-collection.json", result)
        if result.get("terminal_provider_state") == "COMPLETE":
            terminal = advance(submitted, "COMPLETED" if verified else "FAILED",
                               failure_class=None if verified else "INTEGRITY")
            _write_record(directory, "terminal-attempt.json", terminal)
        elif result.get("terminal_provider_state") in ("ERROR", "FAILED", "CANCELLED", "CANCELED"):
            terminal = advance(submitted, "FAILED", failure_class="INFRASTRUCTURE")
            _write_record(directory, "terminal-attempt.json", terminal)
        print("M6A_VERIFICATION=" + ("PASS" if verified else "FAIL"), flush=True)
        print(f"M6A_ARTIFACT_VALID={str(result.get('m6a_artifact_valid', False)).lower()}", flush=True)
        return 0 if verified else 2
    if m6b_mode:
        checks = result.get("m6b_artifact_checks")
        verified = (
            result.get("terminal_provider_state") == "COMPLETE"
            and result.get("report_workspace_matches") is True
            and result.get("report_hash_matches") is True
            and result.get("artifact_hash_matches") is True
            and result.get("artifact_identity_matches") is True
            and result.get("attempt_chain_ok") is True
            and result.get("pass_identity_status") == "IDENTICAL"
            and result.get("pass_identity_binding_matches") is True
            and result.get("pass_identity_artifacts_match") is True
            and result.get("protected_artifact_state", {}).get("verified") is True
            and result.get("m6b_artifact_valid") is True
            and result.get("remote_classification") == "PASS"
            and result.get("local_acceptance") == "PASS"
            and isinstance(checks, dict) and all(checks.values())
        )
        result["m6b_verification"] = {"verified": bool(verified)}
        _write_record(directory, "verified-collection.json", result)
        if result.get("terminal_provider_state") == "COMPLETE":
            terminal = advance(submitted, "COMPLETED" if verified else "FAILED",
                               failure_class=None if verified else "INTEGRITY")
            _write_record(directory, "terminal-attempt.json", terminal)
        elif result.get("terminal_provider_state") in ("ERROR", "FAILED", "CANCELLED", "CANCELED"):
            terminal = advance(submitted, "FAILED", failure_class="INFRASTRUCTURE")
            _write_record(directory, "terminal-attempt.json", terminal)
        print("M6B_VERIFICATION=" + ("PASS" if verified else "FAIL"), flush=True)
        print(f"M6B_ARTIFACT_VALID={str(result.get('m6b_artifact_valid', False)).lower()}", flush=True)
        print(f"M6B_REPORT_PATH={result.get('report_path') or ''}", flush=True)
        print(f"M6B_PANEL_PATH={result.get('artifact_path') or ''}", flush=True)
        print(f"M6B_PASS_IDENTITY_SIDECAR={result.get('pass_identity_sidecar_path') or ''}", flush=True)
        print(f"M6B_PROTECTED_STATE_SIDECAR={result.get('protected_artifact_state_path') or ''}", flush=True)
        return 0 if verified else 2
    print(f"TERMINAL_PROVIDER_STATE={result['terminal_provider_state']}", flush=True)
    print(f"PROVIDER_RUN_ID={submitted.remote_run_id}", flush=True)
    print(f"KERNEL_IDENTITY={kernel_ref}", flush=True)
    if canary_mode and result.get("report_path") and Path(result["report_path"]).is_file():
        result["pass_identity_canary"] = _verify_pass_identity_canary(
            result, Path(result["report_path"]), preparation.workspace_identity,
        )
        _write_record(directory, "verified-collection.json", result)
        canary = result["pass_identity_canary"]
        print("PROTECTED_ARTIFACT_STATE_VERIFIED=" + str(
            canary.get("protected_artifact_state_verified", False)).lower(), flush=True)
        print(f"PROTECTED_ARTIFACT_STATE_PATH={canary.get('protected_artifact_state_path') or ''}", flush=True)
        print(f"PROTECTED_ARTIFACT_STATE_SHA256={canary.get('protected_artifact_state_sha256') or ''}", flush=True)
        print("PROTECTED_ARTIFACT_STATE_BEFORE=" + json.dumps(
            canary.get("protected_artifact_state_before"), sort_keys=True, separators=(",", ":")), flush=True)
        print("PROTECTED_ARTIFACT_STATE_AFTER=" + json.dumps(
            canary.get("protected_artifact_state_after"), sort_keys=True, separators=(",", ":")), flush=True)
        print("PROVENANCE_BINDINGS=" + json.dumps({
            "attempt_chain_ok": result.get("attempt_chain_ok"),
            "report_workspace_matches": result.get("report_workspace_matches"),
            "pass_identity_binding_matches": result.get("pass_identity_binding_matches"),
            "protected_identity": canary.get("protected_artifact_state_identity"),
            "protected_state_identity_match": canary.get("protected_artifact_state_verified"),
            "operation": canary.get("protected_artifact_operation"),
        }, sort_keys=True, separators=(",", ":")), flush=True)
        print(f"CANARY_REPORT_PATH={result.get('report_path') or ''}", flush=True)
        print(f"CANARY_REPORT_SHA256={result.get('report_sha256') or ''}", flush=True)
        print("GENERIC_E2E_RESULT=" + (
            "PROTECTED_ARTIFACT_PROVENANCE_CANARY_VERIFIED" if canary.get("verified")
            else "PROTECTED_ARTIFACT_PROVENANCE_CANARY_VERIFICATION_FAILURE"), flush=True)
        _record_terminal_attempt(directory, submitted, result, canary_mode=canary_mode)
        return 0 if canary.get("verified") else 2
    _record_terminal_attempt(directory, submitted, result, canary_mode=canary_mode)
    return 0 if collect_exit == 0 else 2


def _record_terminal_attempt(directory: Path, submitted, result: dict, *, canary_mode: bool) -> None:
    state = result.get("terminal_provider_state")
    if state == "COMPLETE":
        terminal = advance(submitted, "COMPLETED")
    elif state == "ERROR":
        verified_canary = canary_mode and result.get("pass_identity_canary", {}).get("verified") is True
        terminal = advance(submitted, "FAILED", failure_class=("SOFTWARE" if verified_canary else "INFRASTRUCTURE"))
    else:
        return
    _write_record(directory, "terminal-attempt.json", terminal)


def _resume_protected_canary_once(directory: Path) -> int:
    """Observe one already-submitted canary; never stages or submits work."""
    directory = Path(directory).resolve()
    if any((directory / name).exists() for name in (
            "terminal-attempt.json", "collection.log", "verified-collection.json")):
        raise ExecutionError("this canary already has terminal/collection evidence; refusing repeat retrieval",
                             "INTEGRITY")
    prepared = BackendAttempt.from_dict(json.loads((directory / "prepared-attempt.json").read_bytes()))
    submitted = BackendAttempt.from_dict(json.loads((directory / "submitted-attempt.json").read_bytes()))
    preparation = KaggleLocalPreparation.from_dict(
        json.loads((directory / "local-preparation.json").read_bytes()))
    stage_output = (directory / "stage.log").read_text(encoding="utf-8")
    run_id = _marker(stage_output, "STAGED_WORKSPACE_RUN_ID")
    if (prepared.state != "PREPARED" or submitted.state != "SUBMITTED"
            or submitted.previous_hash != prepared.content_hash
            or preparation.prepared_attempt_hash != prepared.content_hash
            or submitted.remote_run_id is None
            or submitted.task_id != prepared.task_id
            or preparation.workspace_identity.get("run_id") != run_id
            or preparation.kernel_spec.get("id") != submitted.provider_provenance.get("kernel_identity")
            or submitted.provider_provenance.get("provider_run_id") != submitted.remote_run_id
            or submitted.provider_provenance.get("workspace_run_id") != run_id
            or preparation.workspace_identity.get("execution_identity", {}).get("execution_mode")
            != "PASS_IDENTITY_CANARY"):
        raise ExecutionError("saved canary attempt chain or workspace identity is invalid", "INTEGRITY")
    print(f"CONTROL_EVIDENCE_DIR={directory}", flush=True)
    print("GENERIC_PROVIDER_SUBMISSION=NOT_ATTEMPTED", flush=True)
    previous_observations = sorted(directory.glob("provider-observation-*.json"))
    initial_observation = None
    if previous_observations:
        previous_path = previous_observations[-1]
        previous_bytes = previous_path.read_bytes()
        previous = json.loads(previous_bytes)
        reconciled_state = _parse_provider_status_output(
            preparation.kernel_spec["id"], previous.get("query_exit_code"),
            previous.get("output_tail", ""),
        )
        if reconciled_state:
            initial_observation = {
                **previous,
                "provider_state": reconciled_state,
                "observation_class": "STATUS_RECONCILED_FROM_RETAINED_OUTPUT",
                "reconciled_from": str(previous_path),
                "reconciled_from_sha256": hashlib.sha256(previous_bytes).hexdigest(),
            }
    return _observe_and_collect(
        directory, preparation, submitted, canary_mode=True,
        initial_observation=initial_observation,
    )


def _watch_existing_kernel7(directory: Path) -> int:
    """Read-only progress watchdog for the already-pushed version 7; never submits."""
    prepared = BackendAttempt.from_dict(json.loads((directory / "prepared-attempt.json").read_bytes()))
    failed = BackendAttempt.from_dict(json.loads((directory / "failed-attempt.json").read_bytes()))
    preparation = KaggleLocalPreparation.from_dict(json.loads((directory / "local-preparation.json").read_bytes()))
    facts = json.loads((directory / "provider-failure.json").read_bytes())["provider_facts"]
    output = facts.get("output_tail", "")
    kernel_ref = "wt2018mask/rhombus-mobile-ion-e2e"
    def read_provider(command: str) -> tuple[int, str]:
        try:
            response = subprocess.run(
                [sys.executable, "-m", "kaggle", "kernels", command, kernel_ref],
                capture_output=True, timeout=30, check=False,
            )
            return response.returncode, (response.stdout or b"").decode("utf-8", errors="replace") + \
                (response.stderr or b"").decode("utf-8", errors="replace")
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 124, f"{type(exc).__name__}: {exc}"

    if (prepared.state != "PREPARED" or failed.state != "FAILED"
            or failed.previous_hash != prepared.content_hash
            or preparation.prepared_attempt_hash != prepared.content_hash
            or facts.get("kernel_identity") != kernel_ref
            or "Kernel version 7 successfully pushed." not in output
            or "Kernel push was not positively confirmed (exit 0)." not in output):
        raise ExecutionError("kernel-7 recovery evidence is incomplete or mismatched", "INTEGRITY")
    stage_output = (directory / "stage.log").read_text(encoding="utf-8")
    dataset_root = Path(_marker(stage_output, "STAGED_DATASET_PATH"))
    kernel_stage = Path(_marker(stage_output, "STAGED_KERNEL_PATH"))
    run_id = _marker(stage_output, "STAGED_WORKSPACE_RUN_ID")
    if (str(dataset_root.resolve()) != preparation.dataset_root
            or str((kernel_stage / "mobile_ion_displace_e2e.py").resolve()) != preparation.staged_driver_path
            or run_id != preparation.workspace_identity["run_id"]):
        raise ExecutionError("kernel-7 staged workspace differs from PREPARED evidence", "INTEGRITY")

    event_path = directory / "kernel7-watchdog.jsonl"
    started = time.monotonic()
    observation_started_epoch = event_path.stat().st_ctime if event_path.exists() else time.time()
    last_marker = None
    last_state = None
    query_failures = 0
    while True:
        status_code, status_text = read_provider("status")
        import re
        match = re.search(r"KernelWorkerStatus\.(RUNNING|PENDING|COMPLETE|ERROR|FAILED|CANCELLED|CANCELED)\b", status_text)
        state = match.group(1) if (status_code == 0 and
                                   status_text.strip().startswith(kernel_ref + " has status ") and match) else None
        query_failures = 0 if state else query_failures + 1
        if not state:
            with event_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"event": "status_query_failure", "consecutive": query_failures,
                                         "detail": status_text[-1000:]}) + "\n")
        if query_failures >= 3:
            outcome = "STATUS_QUERY_FAILURE"
            break
        if state in ("COMPLETE", "ERROR", "FAILED", "CANCELLED", "CANCELED"):
            outcome = state
            break
        if time.time() - observation_started_epoch >= 4 * 3600:
            outcome = "RUNNING_AT_OBSERVATION_CEILING" if state == "RUNNING" else "OBSERVATION_CEILING"
            break
        state_transition = state is not None and last_state is not None and state != last_state
        if state and state != last_state:
            last_state = state
            with event_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"event": "provider_state", "state": state,
                                         "elapsed_s": round(time.monotonic() - started, 1)}) + "\n")
        logs_code, log_text = read_provider("logs")
        fresh_marker = False
        if logs_code == 0:
            markers = [line.strip() for line in log_text.splitlines() if re.match(
                r"^(?:HEARTBEAT_STAGE=|STAGE=|BOOTSTRAP_STAGE=)", line.strip())]
            if markers and markers[-1] != last_marker:
                last_marker = markers[-1]
                fresh_marker = True
                with event_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"event": "remote_progress", "marker": last_marker,
                                             "elapsed_s": round(time.monotonic() - started, 1)}) + "\n")
                print(f"KERNEL7_PROGRESS={last_marker}", flush=True)
        progress_state = "CONFIRMED" if fresh_marker or state_transition else "UNOBSERVABLE"
        print(f"KERNEL7_STATE={state or 'QUERY_FAILURE'} PROGRESS={progress_state}", flush=True)
        time.sleep(30)

    with event_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": "watchdog_outcome", "outcome": outcome,
                                 "elapsed_s": round(time.monotonic() - started, 1)}) + "\n")
    print(f"KERNEL7_WATCHDOG_OUTCOME={outcome}", flush=True)
    if outcome in ("ERROR", "FAILED", "CANCELLED", "CANCELED"):
        print("KERNEL7_PROVIDER_RESULT=OPERATIONAL_TERMINAL_FAILURE", flush=True)
    if outcome not in ("COMPLETE", "ERROR"):
        return 2
    collect_exit, collect_output = _powershell(
        "kaggle-mobile-ion-collect", str(dataset_root), str(kernel_stage), run_id,
        timeout=1800,
    )
    (directory / "kernel7-collection.log").write_text(collect_output, encoding="utf-8")
    print(f"KERNEL7_COLLECTION_EXIT={collect_exit}", flush=True)
    print(f"KERNEL7_COLLECTION_LOG={directory / 'kernel7-collection.log'}", flush=True)
    return 0 if collect_exit == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live-once", action="store_true", help="authorize exactly one provider submission")
    mode.add_argument("--pass-identity-canary-once", action="store_true",
                      help="authorize one synthetic, non-scientific pass-identity canary")
    mode.add_argument("--m6a-paired-once", action="store_true",
                      help="authorize exactly one fixed 12-parent paired observational experiment")
    mode.add_argument("--m6b-paired-once", action="store_true",
                      help="authorize exactly one preregistered independent 15-parent paired replication")
    mode.add_argument("--watch-existing-kernel7", type=Path,
                      help="read-only progress watchdog for the already-pushed version 7")
    mode.add_argument("--resume-protected-canary-once", type=Path,
                      help="perform one read-only observation of an existing protected-artifact canary")
    args = parser.parse_args()
    if args.watch_existing_kernel7 is not None:
        return _watch_existing_kernel7(args.watch_existing_kernel7)
    if args.resume_protected_canary_once is not None:
        return _resume_protected_canary_once(args.resume_protected_canary_once)
    canary_mode = bool(args.pass_identity_canary_once)
    m6a_mode = bool(args.m6a_paired_once)
    m6b_mode = bool(args.m6b_paired_once)
    if canary_mode:
        directory = REPO / "data" / "batches" / "audit" / "remote-protected-artifact-canaries" / uuid.uuid4().hex
        directory.mkdir(parents=True, exist_ok=False)
    elif m6a_mode:
        directory = REPO / "data" / "batches" / "audit" / "m6a-paired-runs" / uuid.uuid4().hex
        directory.mkdir(parents=True, exist_ok=False)
    elif m6b_mode:
        directory = REPO / "data" / "batches" / "audit" / "m6b-paired-runs" / uuid.uuid4().hex
        directory.mkdir(parents=True, exist_ok=False)
    else:
        directory = Path(tempfile.mkdtemp(prefix="rhombus-generic-kaggle-e2e-"))
    print(f"CONTROL_EVIDENCE_DIR={directory}", flush=True)
    backend = KaggleBackend()
    submitted = None
    preparation = None
    try:
        kernel_identity = (f"wt2018mask/rhombus-m6b-{uuid.uuid4().hex[:16]}" if m6b_mode else None)
        task, bundle = _make_task(directory, pass_identity_canary=canary_mode,
                                  m6a_mode=m6a_mode, m6b_mode=m6b_mode,
                                  kernel_identity=kernel_identity)
        attempt = backend.prepare(bundle, task.resource_requirements)
        _write_record(directory, "prepared-attempt.json", attempt)
        print(f"TASK_ID={task.task_id}", flush=True)
        print(f"PREPARED_ATTEMPT_HASH={attempt.content_hash}", flush=True)
        stage_env = os.environ.copy()
        stage_env.update(_stage_identity_environment(task, bundle, attempt))
        stage_exit, stage_output = _powershell("kaggle-mobile-ion-stage", timeout=900, env=stage_env)
        (directory / "stage.log").write_text(stage_output, encoding="utf-8")
        if stage_exit:
            raise ExecutionError(f"hardened local staging failed (exit {stage_exit})", "INFRASTRUCTURE")
        dataset_root = Path(_marker(stage_output, "STAGED_DATASET_PATH"))
        kernel_stage = Path(_marker(stage_output, "STAGED_KERNEL_PATH"))
        run_id = _marker(stage_output, "STAGED_WORKSPACE_RUN_ID")
        preparation = backend.prepare_local_payload(
            task, bundle, attempt, dataset_root=dataset_root,
            staged_driver_path=kernel_stage / "mobile_ion_displace_e2e.py",
            dataset_metadata_path=dataset_root / "dataset-metadata.json",
            kernel_metadata_path=kernel_stage / "kernel-metadata.json",
        )
        expected_execution_identity = {
            "task_id": task.task_id,
            "task_content_hash": task.content_hash,
            "task_bundle_hash": bundle.content_hash,
            "code_bundle_hash": bundle.bundle_hash,
            "attempt_id": attempt.attempt_id,
            "prepared_attempt_hash": attempt.content_hash,
            "task_config_hash": task.config_hash,
            "execution_mode": ("PASS_IDENTITY_CANARY" if canary_mode else
                               "M6A_PAIRED_DIAGNOSTIC" if m6a_mode else
                               "M6B_PAIRED_DIAGNOSTIC" if m6b_mode else
                               "CANDIDATE_DIAGNOSTIC_E2E"),
            "configuration_identity": task.config["config_identity"],
        }
        if preparation.workspace_identity.get("execution_identity") != expected_execution_identity:
            raise ExecutionError("staged workspace is not bound to the prepared task/attempt", "INTEGRITY")
        if m6b_mode and (preparation.kernel_spec.get("id") != kernel_identity
                         or preparation.workspace_identity.get("provider_kernel_identity") != kernel_identity
                         or task.config.get("kernel_identity") != kernel_identity):
            raise ExecutionError("M6-B provider kernel identity is not bound across PREPARED inputs", "INTEGRITY")
        if preparation.workspace_identity["run_id"] != run_id:
            raise ExecutionError("staging output differs from validated workspace", "INTEGRITY")
        _write_record(directory, "local-preparation.json", preparation)
        print(f"WORKSPACE_RUN_ID={run_id}", flush=True)
        print("GENERIC_PROVIDER_SUBMISSION=STARTING", flush=True)
        submitted = backend.submit_prepared_payload(
            task, bundle, attempt, preparation, submission_authorized=True,
        )
        _write_record(directory, "submitted-attempt.json", submitted)
        print(f"PROVIDER_RUN_ID={submitted.remote_run_id}", flush=True)
        print("GENERIC_PROVIDER_SUBMISSION=ACCEPTED", flush=True)
        if canary_mode:
            return _observe_and_collect(directory, preparation, submitted, canary_mode=True)
        if m6a_mode:
            return _observe_and_collect(directory, preparation, submitted, canary_mode=False,
                                        m6a_mode=True)
        if m6b_mode:
            print(f"M6B_PREREGISTRATION_PATH={directory / 'm6b-preregistration.json'}", flush=True)
            return _observe_and_collect(directory, preparation, submitted, canary_mode=False,
                                        m6b_mode=True)
        collect_exit, collect_output = _powershell(
            "kaggle-mobile-ion-collect", str(dataset_root), str(kernel_stage), run_id,
            timeout=7200,
        )
        (directory / "collection.log").write_text(collect_output, encoding="utf-8")
        result = _verify_collection(collect_output, preparation, submitted, directory)
        result["collector_exit_code"] = collect_exit
        if canary_mode and result.get("report_path") and Path(result["report_path"]).is_file():
            result["pass_identity_canary"] = _verify_pass_identity_canary(
                result, Path(result["report_path"]), preparation.workspace_identity,
            )
        _write_record(directory, "verified-collection.json", result)
        if result["terminal_provider_state"] == "COMPLETE":
            _write_record(directory, "terminal-attempt.json", advance(submitted, "COMPLETED"))
        elif result["terminal_provider_state"] == "ERROR":
            _write_record(directory, "terminal-attempt.json", advance(
                submitted, "FAILED", failure_class=(
                    "SOFTWARE" if canary_mode and result.get("pass_identity_canary", {}).get("verified")
                    else "INFRASTRUCTURE")))
        print(f"TERMINAL_PROVIDER_STATE={result['terminal_provider_state']}", flush=True)
        print(f"ARTIFACT_SHA256={result['artifact_sha256'] or ''}", flush=True)
        if canary_mode:
            print("PASS_IDENTITY_CANARY_VERIFIED=" + str(
                result.get("pass_identity_canary", {}).get("verified", False)).lower(), flush=True)
            canary = result.get("pass_identity_canary", {})
            print(f"CANARY_REPORT_PATH={result.get('report_path') or ''}", flush=True)
            print(f"CANARY_REPORT_SHA256={canary.get('report_sha256') or ''}", flush=True)
            print(f"CANARY_SIDECAR_PATH={canary.get('sidecar_path') or ''}", flush=True)
            print(f"CANARY_SIDECAR_SHA256={canary.get('sidecar_sha256') or ''}", flush=True)
            print(f"CANARY_PASS1_SHA256={canary.get('pass_1_sha256') or ''}", flush=True)
            print(f"CANARY_PASS1_BYTE_LENGTH={canary.get('pass_1_byte_length')}", flush=True)
            print(f"CANARY_PASS2_SHA256={canary.get('pass_2_sha256') or ''}", flush=True)
            print(f"CANARY_PASS2_BYTE_LENGTH={canary.get('pass_2_byte_length')}", flush=True)
            if result.get("pass_identity_canary", {}).get("verified"):
                print("GENERIC_E2E_RESULT=PASS_IDENTITY_CANARY_VERIFIED", flush=True)
                return 0
            print("GENERIC_E2E_RESULT=PASS_IDENTITY_CANARY_VERIFICATION_FAILURE", flush=True)
            return 2
        if (collect_exit == 0 and result["terminal_provider_state"] == "COMPLETE"
                and result["power_shell_report_ok"] == "true"
                and result["power_shell_artifact_hash_ok"] == "true"
                and result["local_acceptance"] == "PASS"
                and result["pass_identity_status"] == "IDENTICAL"
                and result["pass_identity_binding_matches"]
                and result["pass_identity_artifacts_match"]
                and result["report_workspace_matches"]
                and result["artifact_hash_matches"] and result["artifact_identity_matches"]
                and result["attempt_chain_ok"]):
            print("GENERIC_E2E_RESULT=PASS", flush=True)
            return 0
        classification = result.get("remote_classification")
        if (classification == "SCIENTIFIC_VALIDATION_FAIL" and result["report_workspace_matches"]
                and result["artifact_hash_matches"]):
            print("GENERIC_E2E_RESULT=SCIENTIFIC_VALIDATION_FAIL", flush=True)
        else:
            print("GENERIC_E2E_RESULT=OPERATIONAL_VERIFICATION_FAILURE", flush=True)
        return 2
    except KaggleSubmissionFailure as exc:
        if exc.failed_attempt is not None:
            _write_record(directory, "failed-attempt.json", exc.failed_attempt)
        _write_record(directory, "provider-failure.json", {
            "failure_class": exc.failure_class.value,
            "message": str(exc),
            "provider_facts": exc.provider_facts,
        })
        print(f"GENERIC_E2E_FAILURE_CLASS={exc.failure_class.value}", flush=True)
        print(f"GENERIC_E2E_ERROR={exc}", flush=True)
        return 2
    except Exception as exc:
        failure_class = exc.failure_class.value if isinstance(exc, ExecutionError) else "SOFTWARE"
        _write_record(directory, "control-failure.json", {
            "failure_class": failure_class, "message": str(exc),
            "submitted_attempt_hash": submitted.content_hash if submitted else None,
            "workspace_run_id": preparation.workspace_identity["run_id"] if preparation else None,
        })
        print(f"GENERIC_E2E_FAILURE_CLASS={failure_class}", flush=True)
        print(f"GENERIC_E2E_ERROR={exc}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
