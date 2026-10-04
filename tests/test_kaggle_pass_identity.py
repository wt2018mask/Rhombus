import json
import hashlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

import pytest

from rudeus.execution.kaggle_backend import _hardened_e2e_driver
from rudeus.science.contracts import freeze

_generic_path = Path(__file__).resolve().parents[1] / "scripts" / "kaggle" / "run_generic_mobile_ion_e2e.py"
_generic_spec = importlib.util.spec_from_file_location("rhombus_generic_kaggle_e2e", _generic_path)
generic = importlib.util.module_from_spec(_generic_spec)
sys.modules[_generic_spec.name] = generic
_generic_spec.loader.exec_module(generic)


driver = _hardened_e2e_driver()


def _workspace():
    return {
        "run_id": str(uuid.UUID("12345678-1234-5678-1234-567812345678")),
        "runtime_manifest_sha256": "a" * 64,
        "execution_identity": {
            "task_id": "b" * 64,
            "task_content_hash": "c" * 64,
            "task_bundle_hash": "d" * 64,
            "code_bundle_hash": "e" * 64,
            "attempt_id": "f" * 64,
            "prepared_attempt_hash": "1" * 64,
            "task_config_hash": "2" * 64,
            "execution_mode": "CANDIDATE_DIAGNOSTIC_E2E",
            "configuration_identity": driver.CONFIG_IDENTITY,
        },
    }


def test_equal_pass_outputs_persist_hashes_lengths_equality_and_identity(tmp_path):
    first = b'{"rows":[],"runs":[],"summary":{}}\n'
    report = {"final_classification": "INFRA_FAILURE"}
    report_path = tmp_path / "report.json"

    evidence = driver.persist_generation_pass_identity(
        report, tmp_path, first, first, _workspace(), report_path=report_path,
    )

    assert evidence["schema_version"] == "mobile-ion-generation-pass-identity-v1"
    assert evidence["pass_1"] == {"sha256": driver.sha256_bytes(first), "byte_length": len(first)}
    assert evidence["pass_2"] == evidence["pass_1"]
    assert evidence["byte_identical"] is True
    assert evidence["identity"]["task_attempt"] == _workspace()["execution_identity"]
    assert evidence["identity"]["run_id"] == _workspace()["run_id"]
    assert evidence["identity"]["workspace_identity_sha256"]
    assert evidence["identity"]["configuration_identity"] == driver.CONFIG_IDENTITY
    sidecar = tmp_path / evidence["evidence_artifact"]["relative_path"]
    assert json.loads(sidecar.read_text(encoding="utf-8"))["byte_identical"] is True
    saved_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved_report["generation_pass_identity"] == evidence
    assert generic._pass_identity_artifacts_match(saved_report, report_path)


def test_unequal_pass_outputs_retain_exact_pass_two_diagnostic_artifact(tmp_path):
    first, second = b"pass one bytes", b"pass two diagnostic bytes"
    report = {}
    report_path = tmp_path / "report.json"
    evidence = driver.persist_generation_pass_identity(
        report, tmp_path, first, second, _workspace(), report_path=report_path,
    )

    assert evidence["byte_identical"] is False
    retained = tmp_path / evidence["pass_2_diagnostic_artifact"]["relative_path"]
    assert retained.read_bytes() == second
    assert evidence["pass_2_diagnostic_artifact"]["sha256"] == driver.sha256_bytes(second)
    assert evidence["pass_2_diagnostic_artifact"]["byte_length"] == len(second)
    assert driver.generation_pass_identity_status(report) == "MISMATCH"
    assert generic._pass_identity_artifacts_match(report, report_path)


def test_pass2_cleanup_uses_validated_identity_and_preserves_unverified_copy(tmp_path):
    equal = b"identical outputs"
    equal_dir = tmp_path / "equal"
    equal_dir.mkdir()
    matching_report = {}
    matching = driver.persist_generation_pass_identity(
        matching_report, equal_dir, equal, equal, _workspace(),
    )
    assert driver.pass2_temp_cleanup_allowed(equal, matching) is True

    mismatch_dir = tmp_path / "mismatch"
    mismatch_dir.mkdir()
    mismatch_report = {}
    mismatch = driver.persist_generation_pass_identity(
        mismatch_report, mismatch_dir, b"first", b"second", _workspace(),
    )
    assert driver.pass2_temp_cleanup_allowed(b"second", mismatch) is True

    mismatch_without_retained_diagnostic = {
        **mismatch,
        "pass_2_diagnostic_artifact": None,
    }
    assert driver.pass2_temp_cleanup_allowed(b"second", mismatch_without_retained_diagnostic) is False
    assert driver.pass2_temp_cleanup_allowed(None, matching) is False


def test_downstream_validation_failure_keeps_already_persisted_pass_evidence(tmp_path):
    payload = b"same pass bytes"
    report = {"final_classification": "INFRA_FAILURE"}
    report_path = tmp_path / "report.json"
    driver.persist_generation_pass_identity(
        report, tmp_path, payload, payload, _workspace(), report_path=report_path,
    )
    protected_path = tmp_path / "protected-p2.json"
    protected_path.write_bytes(b"frozen bytes")
    protected_paths = ["protected-p2.json"]
    protected_before = driver.hash_protected(tmp_path, protected_paths)
    protected_after = driver.capture_protected_artifact_evidence(
        report, tmp_path, protected_paths, protected_before, _workspace(),
        evidence_output_root=tmp_path,
    )
    assert protected_after == protected_before
    driver.write_json(report_path, report)

    with pytest.raises(driver.ScientificValidationFailure):
        driver.validate_panel({}, protected_before, protected_after, payload, payload, {})

    report["final_classification"] = "SCIENTIFIC_VALIDATION_FAIL"
    report["failure_reason"] = "synthetic downstream validation failure"
    driver.write_json(report_path, report)
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["generation_pass_identity"]["byte_identical"] is True
    assert saved["generation_pass_identity"]["pass_1"]["sha256"] == driver.sha256_bytes(payload)
    assert saved["final_classification"] == "SCIENTIFIC_VALIDATION_FAIL"
    protected = saved["protected_artifact_state"]
    assert protected["schema_version"] == "protected-artifact-state-v1"
    assert protected["unchanged"] is True
    assert protected["before"] == protected["after"]
    assert protected["identity"]["run_id"] == _workspace()["run_id"]
    assert protected["identity"]["task_attempt"] == _workspace()["execution_identity"]
    assert protected["identity"]["configuration_identity"] == driver.CONFIG_IDENTITY


def test_protected_artifact_hash_change_is_explicitly_persisted(tmp_path):
    protected_path = tmp_path / "protected-p2.json"
    protected_path.write_bytes(b"before")
    paths = ["protected-p2.json"]
    before = driver.hash_protected(tmp_path, paths)
    report = {}
    driver.require_prepared_execution_identity(_workspace())
    protected_path.write_bytes(b"after")
    after = driver.capture_protected_artifact_evidence(
        report, tmp_path, paths, before, _workspace(),
    )
    assert report["protected_artifacts"][0]["before_sha256"] == driver.sha256_bytes(b"before")
    assert report["protected_artifacts"][0]["after_sha256"] == driver.sha256_bytes(b"after")
    assert report["protected_artifact_state"]["unchanged"] is False
    assert after[0]["sha256"] == driver.sha256_bytes(b"after")


def test_historical_report_without_pass_two_identity_remains_unknown():
    version_7_style_report = {
        "execution": {"generation_pass_1_success": True, "generation_pass_2_success": True},
        "artifact": {"sha256": "a" * 64},
        "validations": {"determinism_byte_identical": None},
    }
    assert driver.generation_pass_identity_status(version_7_style_report) == "UNKNOWN"
    assert driver.generation_pass_identity_status({
        "generation_pass_identity": {
            "schema_version": "mobile-ion-generation-pass-identity-v1",
            "pass_1": {"sha256": "a" * 64, "byte_length": 10},
            "byte_identical": True,
        },
    }) == "UNKNOWN"


def test_generic_staging_exports_exact_prepared_task_and_attempt_identity():
    task = SimpleNamespace(
        task_id="a" * 64, content_hash="b" * 64, config_hash="2" * 64,
        config={"config_identity": driver.CONFIG_IDENTITY},
    )
    bundle = SimpleNamespace(content_hash="c" * 64, bundle_hash="d" * 64)
    attempt = SimpleNamespace(attempt_id="e" * 64, content_hash="f" * 64)

    identity_env = generic._stage_identity_environment(task, bundle, attempt)

    assert identity_env == {
        "RHOMBUS_TASK_ID": task.task_id,
        "RHOMBUS_TASK_CONTENT_HASH": task.content_hash,
        "RHOMBUS_TASK_BUNDLE_HASH": bundle.content_hash,
        "RHOMBUS_CODE_BUNDLE_HASH": bundle.bundle_hash,
        "RHOMBUS_ATTEMPT_ID": attempt.attempt_id,
        "RHOMBUS_PREPARED_ATTEMPT_HASH": attempt.content_hash,
        "RHOMBUS_TASK_CONFIG_HASH": task.config_hash,
        "RHOMBUS_EXECUTION_MODE": "CANDIDATE_DIAGNOSTIC_E2E",
        "RHOMBUS_CONFIGURATION_IDENTITY": driver.CONFIG_IDENTITY,
        "RHOMBUS_KERNEL_IDENTITY": "wt2018mask/rhombus-mobile-ion-e2e",
    }


def test_pass_identity_canary_task_is_synthetic_and_non_scientific(tmp_path):
    task, bundle = generic._make_task(tmp_path, pass_identity_canary=True)
    config = task.config

    assert task.stage == "PASS_IDENTITY_CANARY"
    assert task.candidate_id == "pass-identity-canary"
    assert config["execution_mode"] == "PASS_IDENTITY_CANARY"
    assert config["candidate_generation_performed"] is False
    assert task.expected_outputs == (
        "e2e_report", "pass_identity_evidence", "protected_artifact_state", "synthetic_operation",
    )
    assert len(bundle.retained_files) == 1
    retained = tmp_path / bundle.retained_files[0]["relative_path"]
    assert retained.read_bytes() == b"rhombus-pass-identity-canary-input-v1\n"


def test_generic_retained_input_inventory_is_sorted_for_task_bundle_contract():
    inventory = [
        {"relative_path": "blobs/" + "f" * 64, "raw_sha256": "f" * 64, "size_bytes": 2},
        {"relative_path": "blobs/" + "1" * 64, "raw_sha256": "1" * 64, "size_bytes": 1},
    ]
    ordered = generic._ordered_retained_inventory(inventory)
    assert [record["relative_path"] for record in ordered] == sorted(
        record["relative_path"] for record in inventory
    )


def test_pass_identity_canary_verification_accepts_expected_controlled_failure(tmp_path):
    workspace = _workspace()
    identity = workspace["execution_identity"]
    identity["execution_mode"] = "PASS_IDENTITY_CANARY"
    identity["configuration_identity"] = driver.PASS_IDENTITY_CANARY_CONFIG_IDENTITY
    payload = driver.PASS_IDENTITY_CANARY_PASS_BYTES
    report = {
        "config_identity": driver.PASS_IDENTITY_CANARY_CONFIG_IDENTITY,
        "final_classification": "SCIENTIFIC_VALIDATION_FAIL",
        "validations": {
            "pass_identity_canary": True,
            "controlled_failure_code": "PASS_IDENTITY_CANARY_CONTROLLED_DOWNSTREAM_FAILURE",
            "candidate_generation_performed": False,
            "protected_artifact_state_persisted": True,
        },
    }
    report_path = tmp_path / "report.json"
    driver.persist_generation_pass_identity(report, tmp_path, payload, bytes(payload), workspace,
                                           report_path=report_path)
    protected_target = driver.prepare_protected_artifact_provenance_canary(
        tmp_path, workspace, integrity_checks={"all_required": True},
    )
    report["protected_artifact_canary_target"] = protected_target
    protected_paths = [protected_target]
    before = driver.hash_protected(tmp_path, protected_paths)
    report["protected_artifact_canary_operation"] = (
        driver.execute_protected_artifact_provenance_canary_operation(
            tmp_path, tmp_path, workspace, protected_target,
        )
    )
    driver.capture_protected_artifact_evidence(
        report, tmp_path, protected_paths, before, workspace, evidence_output_root=tmp_path,
    )
    driver.write_json(report_path, report)
    assert generic._pass_identity_binding(report, freeze(workspace)) == ("IDENTICAL", True)
    collected_report = json.loads(report_path.read_bytes())
    result = {
        "terminal_provider_state": "ERROR",
        "remote_classification": "SCIENTIFIC_VALIDATION_FAIL",
        "report_workspace_matches": True,
        "report_sha256": "a" * 64,
        "report_hash_matches": True,
        "attempt_chain_ok": True,
        "power_shell_report_ok": "true",
        "pass_identity_status": "IDENTICAL",
        "pass_identity_binding_matches": True,
        "pass_identity_artifacts_match": True,
        "protected_artifact_state": generic._protected_artifact_state_binding(
            report, report_path, workspace,
        ),
        "protected_artifact_canary_operation": generic._canary_operation_artifact_matches(
            report, report_path, workspace,
        ),
        "protected_artifact_state_path": str(
            report_path.parent / report["protected_artifact_state_artifact"]["relative_path"]),
        "protected_artifact_state_sha256": report["protected_artifact_state_artifact"]["sha256"],
        "initial_provider_observation": {"provider_state": "ERROR"},
        "artifact_path": "",
    }
    assert generic._verify_pass_identity_canary(result, report_path, workspace)["verified"]
    assert generic._verify_pass_identity_canary(result, report_path, workspace)[
        "protected_artifact_transition_matches"] is True

    mismatched_identity = dict(workspace)
    mismatched_identity["execution_identity"] = dict(identity, task_config_hash="9" * 64)
    assert generic._pass_identity_binding(report, freeze(mismatched_identity)) == ("IDENTICAL", False)

    collected_report["generation_pass_identity"]["pass_2"]["sha256"] = "0" * 64
    driver.write_json(report_path, collected_report)
    assert not generic._verify_pass_identity_canary(result, report_path, workspace)["verified"]


def test_protected_canary_creation_requires_completed_workspace_integrity(tmp_path):
    workspace = _workspace()
    with pytest.raises(driver.InfrastructureFailure, match="requires successful workspace integrity"):
        driver.prepare_protected_artifact_provenance_canary(
            tmp_path, workspace, integrity_checks={"all_required": False},
        )

    relative = driver.prepare_protected_artifact_provenance_canary(
        tmp_path, workspace, integrity_checks={"all_required": True},
    )
    assert (tmp_path / relative).read_bytes() == driver.PROTECTED_PROVENANCE_CANARY_BEFORE_BYTES


def test_controlled_canary_failure_is_labeled_after_provenance_persistence():
    lines = []
    observer = driver.StageObservability(
        writer=lambda line, **_kwargs: lines.append(line),
    )
    observer.stage("protected_artifact_provenance_persisted")
    observer.failed()

    assert lines == [
        "STAGE=protected_artifact_provenance_persisted",
        "STAGE_FAILED=protected_artifact_provenance_persisted",
    ]
    assert observer.snapshot()["last_stage"] == "protected_artifact_provenance_persisted"


def test_protected_artifact_state_sidecar_is_content_addressed_and_bound(tmp_path):
    workspace = _workspace()
    protected_file = tmp_path / "protected.bin"
    protected_file.write_bytes(b"unchanged protected evidence")
    before = driver.hash_protected(tmp_path, [protected_file.name])
    report = {"config_identity": driver.CONFIG_IDENTITY}

    driver.capture_protected_artifact_evidence(
        report, tmp_path, [protected_file.name], before, workspace,
        evidence_output_root=tmp_path,
    )
    report_path = tmp_path / "report.json"
    driver.write_json(report_path, report)

    binding = generic._protected_artifact_state_binding(report, report_path, workspace)
    assert binding["verified"] is True
    assert binding["identity_bindings_match"] is True
    assert binding["unchanged"] is True
    assert binding["before"] == binding["after"]
    sidecar = Path(binding["sidecar_path"])
    raw = sidecar.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == binding["sidecar_sha256"]
    assert len(raw) == binding["sidecar_byte_length"]

    damaged = json.loads(raw.decode("utf-8"))
    damaged["identity"]["runtime_manifest_sha256"] = "0" * 64
    sidecar.write_text(json.dumps(damaged), encoding="utf-8")
    assert generic._protected_artifact_state_binding(report, report_path, workspace)["verified"] is False


def test_provider_status_observation_is_single_query_and_preserves_running(monkeypatch):
    calls = []

    class Completed:
        returncode = 0
        stdout = b"wt2018mask/rhombus-mobile-ion-e2e has status KernelWorkerStatus.RUNNING.\n"
        stderr = b""

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return Completed()

    monkeypatch.setattr(generic.subprocess, "run", fake_run)
    observation = generic._query_provider_once("wt2018mask/rhombus-mobile-ion-e2e")
    assert observation["provider_state"] == "RUNNING"
    assert observation["observation_class"] == "STATUS"
    assert len(calls) == 1
    assert calls[0][1]["timeout"] == 45


@pytest.mark.parametrize("text,expected", [
    ('wt2018mask/rhombus-mobile-ion-e2e has status "KernelWorkerStatus.ERROR"\n', "ERROR"),
    ("wt2018mask/rhombus-mobile-ion-e2e has status KernelWorkerStatus.RUNNING.\n", "RUNNING"),
])
def test_provider_status_parser_accepts_kaggle_quoted_and_plain_enum(text, expected):
    assert generic._parse_provider_status_output(
        "wt2018mask/rhombus-mobile-ion-e2e", 0, text,
    ) == expected


def test_running_canary_observation_stops_without_collection_or_resubmission(tmp_path, monkeypatch):
    directory = tmp_path / "control"
    directory.mkdir()
    calls = []
    monkeypatch.setattr(generic, "_query_provider_once", lambda kernel: (
        calls.append(kernel) or {"kernel_identity": kernel, "provider_state": "RUNNING"}
    ))
    monkeypatch.setattr(generic, "_powershell", lambda *args, **kwargs: pytest.fail(
        "collector must not run while provider state is RUNNING"))
    preparation = SimpleNamespace(
        kernel_spec={"id": "wt2018mask/rhombus-mobile-ion-e2e"},
        workspace_identity={"run_id": "canary-run"},
    )
    submitted = SimpleNamespace(
        remote_run_id="wt2018mask/rhombus-mobile-ion-e2e",
        provider_provenance={}, content_hash="a" * 64,
    )

    assert generic._observe_and_collect(directory, preparation, submitted, canary_mode=True) == 3
    assert calls == [preparation.kernel_spec["id"]]
    observation_files = list(directory.glob("provider-observation-*.json"))
    assert len(observation_files) == 1
    assert json.loads(observation_files[0].read_text(encoding="utf-8"))["provider_state"] == "RUNNING"


def test_terminal_recheck_uses_one_shot_collector_and_stops_if_state_changes(tmp_path, monkeypatch):
    directory = tmp_path / "control"
    directory.mkdir()
    (directory / "stage.log").write_text(
        "STAGED_DATASET_PATH=fake-dataset\nSTAGED_KERNEL_PATH=fake-kernel\n"
        "STAGED_WORKSPACE_RUN_ID=canary-run\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(generic, "_query_provider_once", lambda kernel: {
        "kernel_identity": kernel, "provider_state": "ERROR",
    })
    calls = []

    def fake_powershell(*args, **kwargs):
        calls.append((args, kwargs))
        return 12, "REMOTE_STATE=RUNNING\nE2E_CLASS=ORCHESTRATION_TIMEOUT\n"

    monkeypatch.setattr(generic, "_powershell", fake_powershell)
    preparation = SimpleNamespace(
        kernel_spec={"id": "wt2018mask/rhombus-mobile-ion-e2e"},
        workspace_identity={"run_id": "canary-run"},
    )
    submitted = SimpleNamespace(
        remote_run_id="wt2018mask/rhombus-mobile-ion-e2e",
        provider_provenance={}, content_hash="a" * 64,
    )

    assert generic._observe_and_collect(directory, preparation, submitted, canary_mode=True) == 3
    assert len(calls) == 1
    assert calls[0][1]["env"]["RHOMBUS_COLLECT_ONCE"] == "1"
    evidence = json.loads((directory / "collection-observation-incomplete.json").read_text(encoding="utf-8"))
    assert evidence["collection_remote_state"] == "RUNNING"
    assert evidence["result"] == "OBSERVATION_INCOMPLETE_NO_RESUBMISSION"


def test_pass_identity_persistence_rejects_workspace_without_prepared_task_attempt(tmp_path):
    workspace = _workspace()
    del workspace["execution_identity"]
    with pytest.raises(driver.InfrastructureFailure, match="prepared task/attempt identity"):
        driver.persist_generation_pass_identity({}, tmp_path, b"one", b"one", workspace)


def test_collection_binding_checks_task_attempt_workspace_and_configuration(tmp_path):
    workspace = _workspace()
    report = {"config_identity": driver.CONFIG_IDENTITY}
    payload = b"deterministic output"
    driver.persist_generation_pass_identity(report, tmp_path, payload, payload, workspace)

    assert generic._pass_identity_binding(report, workspace) == ("IDENTICAL", True)
    report["generation_pass_identity"]["identity"]["task_attempt"]["attempt_id"] = "9" * 64
    assert generic._pass_identity_binding(report, workspace) == ("IDENTICAL", False)
