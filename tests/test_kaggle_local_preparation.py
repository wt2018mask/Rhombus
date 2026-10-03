import base64
import hashlib
import json
import uuid
from pathlib import Path

import pytest

from rudeus.execution.backend import TaskBundle, build_task_bundle, prepare_attempt
from rudeus.execution.contracts import ExecutionError, TaskSpec
from rudeus.execution.kaggle_backend import KaggleBackend
from rudeus.science.contracts import digest
from tests.test_controlled_launch import base_context, committed_code


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _preparation_inputs(tmp_path, repo, task_bundle, *, runtime_file_variant=None):
    from rudeus.execution.kaggle_backend import _hardened_e2e_driver

    driver = _hardened_e2e_driver()
    root = tmp_path / "runtime-payload"
    root.mkdir()
    kernel_stage = tmp_path / "kernel-stage"
    kernel_stage.mkdir()
    driver_path = kernel_stage / "mobile_ion_displace_e2e.py"
    dataset_meta_path = root / "dataset-metadata.json"
    kernel_meta_path = kernel_stage / "kernel-metadata.json"
    runtime_files = sorted(set(driver.RUNTIME_SOURCE_FILES + driver.OBELIX_RUNTIME_FILES))
    code_paths = {item["relative_path"] for item in task_bundle.code_bundle["files"]}
    protected_path = "data/batches/audit/preparation-fixture.json"
    transport_files = sorted(runtime_files + [protected_path])
    for relative in transport_files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative in code_paths:
            path.write_bytes((repo / relative).read_bytes())
        else:
            path.write_bytes(("fixture:" + relative).encode("utf-8"))

    driver_template = b'EMBEDDED_WORKSPACE_IDENTITY_B64 = "__RHOMBUS_WORKSPACE_IDENTITY_B64__"\n'
    driver_path.write_bytes(driver_template)
    template_hash = _sha(driver.canonical_driver_template_bytes(driver_template))
    workspace = {
        "schema_version": "rhombus-workspace-identity-v1",
        "run_id": str(uuid.UUID("12345678-1234-5678-1234-567812345678")),
        "git_head": "a" * 40, "branch": "fixture", "tracked_dirty": False,
        "status_porcelain": [], "repository_tracked_files": [],
        "repository_workspace_manifest_sha256": digest("repository"),
        "tracked_delta_sha256": digest("delta"), "driver_template_sha256": template_hash,
        "driver_path": "mobile_ion_displace_e2e.py",
        "explicitly_staged_untracked_inputs": ["data/obelix"],
        "explicitly_staged_input_manifest_sha256": driver.sha256_bytes(
            driver.canonical_manifest(root, list(driver.OBELIX_RUNTIME_FILES)).encode("utf-8")),
        "runtime_files": ["mobile_ion_displace_e2e.py", *runtime_files],
        "runtime_manifest_sha256": "",
        "runtime_dataset_files": runtime_files,
        "runtime_dataset_manifest_sha256": driver.sha256_bytes(
            driver.canonical_manifest(root, runtime_files).encode("utf-8")),
        "dataset_transport_files": transport_files,
        "dataset_transport_manifest_sha256": driver.sha256_bytes(
            driver.canonical_manifest(root, transport_files).encode("utf-8")),
        "protected_artifacts": [{"path": protected_path, "sha256": _sha(("fixture:" + protected_path).encode())}],
    }
    if runtime_file_variant == "missing":
        workspace["runtime_files"].remove("config.yaml")
    elif runtime_file_variant == "extra":
        workspace["runtime_files"].append("unlisted-runtime.py")
    runtime_manifest = driver.canonical_manifest(
        root, ["mobile_ion_displace_e2e.py", *runtime_files],
        "mobile_ion_displace_e2e.py", driver_source_path=driver_path,
    )
    workspace["runtime_manifest_sha256"] = driver.sha256_bytes(runtime_manifest.encode("utf-8"))
    encoded = base64.b64encode(json.dumps(workspace, separators=(",", ":")).encode()).decode()
    driver_path.write_bytes(driver_template.replace(
        b"__RHOMBUS_WORKSPACE_IDENTITY_B64__", encoded.encode("ascii")))

    dataset_spec = {
        "id": "wt2018mask/rhombus-mobile-ion-runtime",
        "title": "rhombus-mobile-ion-runtime", "isPrivate": True,
        "licenses": [{"name": "other"}],
    }
    kernel_spec = {
        "id": "wt2018mask/rhombus-mobile-ion-e2e", "title": "rhombus-mobile-ion-e2e",
        "code_file": "mobile_ion_displace_e2e.py", "language": "python",
        "kernel_type": "script", "is_private": True, "enable_gpu": False,
        "enable_internet": True,
        "dataset_sources": ["wt2018mask/rhombus-mobile-ion-runtime"],
        "competition_sources": [], "kernel_sources": [], "model_sources": [],
    }
    dataset_meta_path.write_text(json.dumps(dataset_spec), encoding="utf-8")
    kernel_meta_path.write_text(json.dumps(kernel_spec), encoding="utf-8")
    return root, driver_path, dataset_meta_path, kernel_meta_path


@pytest.fixture(scope="module")
def prepared_kaggle(base_context):
    repo, task, code, store, _ = base_context
    bundle = build_task_bundle(task, code, store=store, git_root=repo)
    backend = KaggleBackend()
    attempt = backend.prepare(bundle, task.resource_requirements)
    return repo, task, bundle, attempt, backend


def test_local_payload_preparation_binds_existing_prepared_attempt_without_submit(
    tmp_path, prepared_kaggle, monkeypatch,
):
    repo, task, bundle, attempt, backend = prepared_kaggle
    inputs = _preparation_inputs(tmp_path, repo, bundle)
    called = []
    monkeypatch.setattr(backend, "submit", lambda *_args, **_kwargs: called.append(True))

    prepared = backend.prepare_local_payload(
        task, bundle, attempt, dataset_root=inputs[0], staged_driver_path=inputs[1],
        dataset_metadata_path=inputs[2], kernel_metadata_path=inputs[3],
    )

    assert prepared.task_id == task.task_id
    assert prepared.task_content_hash == bundle.task_content_hash
    assert prepared.task_bundle_hash == bundle.content_hash
    assert prepared.code_bundle_hash == bundle.bundle_hash
    assert prepared.backend_identity == attempt.backend == "kaggle"
    assert prepared.attempt_id == attempt.attempt_id
    assert prepared.prepared_attempt_hash == attempt.content_hash
    assert prepared.prepared_from_hash == attempt.previous_hash
    assert prepared.attempt_state == attempt.state == "PREPARED"
    assert prepared.submission_gate == "CLOSED"
    assert prepared.workspace_identity["run_id"] == "12345678-1234-5678-1234-567812345678"
    assert prepared.dataset_spec["isPrivate"] is True
    assert prepared.kernel_spec["enable_gpu"] is False
    assert len(prepared.dataset_transport_inventory) == len(prepared.workspace_identity["dataset_transport_files"])
    assert called == []
    assert attempt.state == "PREPARED"


def test_provider_preparation_metadata_does_not_change_scientific_task_identity(
    tmp_path, prepared_kaggle,
):
    repo, task, bundle, attempt, backend = prepared_kaggle
    inputs = _preparation_inputs(tmp_path, repo, bundle)
    before = task.task_id
    backend.prepare_local_payload(
        task, bundle, attempt, dataset_root=inputs[0], staged_driver_path=inputs[1],
        dataset_metadata_path=inputs[2], kernel_metadata_path=inputs[3],
    )
    assert task.task_id == before
    assert TaskSpec.from_dict(bundle.task).task_id == before


def test_mismatched_prepared_attempt_is_rejected(tmp_path, prepared_kaggle):
    repo, task, bundle, _, backend = prepared_kaggle
    inputs = _preparation_inputs(tmp_path, repo, bundle)
    wrong = prepare_attempt(bundle, "other-provider")
    with pytest.raises(ExecutionError) as error:
        backend.prepare_local_payload(
            task, bundle, wrong, dataset_root=inputs[0], staged_driver_path=inputs[1],
            dataset_metadata_path=inputs[2], kernel_metadata_path=inputs[3],
        )
    assert error.value.failure_class.value == "INTEGRITY"


@pytest.mark.parametrize("damage", ["missing", "malformed", "dataset_sha", "driver_identity", "protected_sha"])
def test_invalid_local_payload_fails_as_operational_integrity_error(
    tmp_path, prepared_kaggle, damage,
):
    repo, task, bundle, attempt, backend = prepared_kaggle
    inputs = list(_preparation_inputs(tmp_path, repo, bundle))
    if damage == "missing":
        inputs[3] = tmp_path / "missing-kernel-metadata.json"
    elif damage == "malformed":
        inputs[3].write_text("{not-json", encoding="utf-8")
    elif damage == "dataset_sha":
        file = inputs[0] / "config.yaml"
        file.write_bytes(file.read_bytes() + b"changed")
    elif damage == "protected_sha":
        file = inputs[0] / "data/batches/audit/preparation-fixture.json"
        file.write_bytes(file.read_bytes() + b"changed")
    else:
        inputs[1].write_bytes(inputs[1].read_bytes() + b"# mutation\n")
    with pytest.raises(ExecutionError) as error:
        backend.prepare_local_payload(
            task, bundle, attempt, dataset_root=inputs[0], staged_driver_path=inputs[1],
            dataset_metadata_path=inputs[2], kernel_metadata_path=inputs[3],
        )
    assert error.value.failure_class.value == "INTEGRITY"
    assert "FAIL" not in str(error.value)


@pytest.mark.parametrize("damage", ["external_metadata", "missing_staged_metadata", "conflicting_metadata"])
def test_dataset_metadata_must_be_the_exact_top_level_upload_metadata(
    tmp_path, prepared_kaggle, damage,
):
    repo, task, bundle, attempt, backend = prepared_kaggle
    inputs = list(_preparation_inputs(tmp_path, repo, bundle))
    external = tmp_path / "external-dataset-metadata.json"
    external.write_bytes(inputs[2].read_bytes())
    if damage == "external_metadata":
        inputs[2] = external
    elif damage == "missing_staged_metadata":
        inputs[2].unlink()
        inputs[2] = external
    else:
        inputs[2].write_text(json.dumps({"id": "other/dataset"}), encoding="utf-8")
        inputs[2] = external
    with pytest.raises(ExecutionError) as error:
        backend.prepare_local_payload(
            task, bundle, attempt, dataset_root=inputs[0], staged_driver_path=inputs[1],
            dataset_metadata_path=inputs[2], kernel_metadata_path=inputs[3],
        )
    assert error.value.failure_class.value == "INTEGRITY"


def test_arbitrary_extra_dataset_transport_file_is_still_rejected(
    tmp_path, prepared_kaggle,
):
    repo, task, bundle, attempt, backend = prepared_kaggle
    inputs = _preparation_inputs(tmp_path, repo, bundle)
    (inputs[0] / "unexpected-science.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ExecutionError, match="exact E2E manifest"):
        backend.prepare_local_payload(
            task, bundle, attempt, dataset_root=inputs[0], staged_driver_path=inputs[1],
            dataset_metadata_path=inputs[2], kernel_metadata_path=inputs[3],
        )


@pytest.mark.parametrize("damage", ["wrong_name", "different_directory", "missing_driver"])
def test_kernel_driver_must_match_spec_and_share_kernel_staging_directory(
    tmp_path, prepared_kaggle, damage,
):
    repo, task, bundle, attempt, backend = prepared_kaggle
    inputs = list(_preparation_inputs(tmp_path, repo, bundle))
    if damage == "wrong_name":
        wrong = inputs[1].with_name("renamed-driver.py")
        wrong.write_bytes(inputs[1].read_bytes())
        inputs[1] = wrong
    elif damage == "different_directory":
        other = tmp_path / "elsewhere"
        other.mkdir()
        wrong = other / inputs[1].name
        wrong.write_bytes(inputs[1].read_bytes())
        inputs[1] = wrong
    else:
        inputs[1].unlink()
    with pytest.raises(ExecutionError) as error:
        backend.prepare_local_payload(
            task, bundle, attempt, dataset_root=inputs[0], staged_driver_path=inputs[1],
            dataset_metadata_path=inputs[2], kernel_metadata_path=inputs[3],
        )
    assert error.value.failure_class.value == "INTEGRITY"


@pytest.mark.parametrize("variant", ["missing", "extra"])
def test_adapter_reuses_exact_hardened_workspace_runtime_file_set(
    tmp_path, prepared_kaggle, variant,
):
    repo, task, bundle, attempt, backend = prepared_kaggle
    inputs = _preparation_inputs(tmp_path, repo, bundle, runtime_file_variant=variant)
    with pytest.raises(ExecutionError, match="runtime and dataset file sets disagree"):
        backend.prepare_local_payload(
            task, bundle, attempt, dataset_root=inputs[0], staged_driver_path=inputs[1],
            dataset_metadata_path=inputs[2], kernel_metadata_path=inputs[3],
        )


def test_shared_workspace_runtime_file_set_helper_accepts_exact_set_and_rejects_differences(tmp_path, prepared_kaggle):
    from rudeus.execution.kaggle_backend import _hardened_e2e_driver

    driver = _hardened_e2e_driver()
    repo, _, bundle, _, _ = prepared_kaggle
    inputs = _preparation_inputs(tmp_path, repo, bundle)
    workspace = driver.load_embedded_workspace_identity(inputs[1])
    assert set(driver.require_workspace_runtime_files(workspace)) == \
        set(workspace["runtime_dataset_files"]) | {workspace["driver_path"]}
    with pytest.raises(driver.InfrastructureFailure, match="file sets disagree"):
        driver.require_workspace_runtime_files({
            **workspace, "runtime_files": workspace["runtime_files"][:-1],
        })
    with pytest.raises(driver.InfrastructureFailure, match="file sets disagree"):
        driver.require_workspace_runtime_files({
            **workspace, "runtime_files": [*workspace["runtime_files"], "unlisted.py"],
        })


def test_capability_report_preserves_historical_context_without_overclaiming(monkeypatch, tmp_path):
    monkeypatch.setattr("rudeus.execution.kaggle_backend.Path.home", lambda: tmp_path)
    report = KaggleBackend().capabilities()
    assert report["repository_evidence"]["historical_remote_execution"]["state"] == \
        "HISTORICAL_SUCCESS_REPORTED_NOT_REVALIDATED"
    assert report["capabilities"]["gpu"] == {"state": "UNKNOWN", "value": None}
    assert report["capabilities"]["runtime_limit_s"] == {"state": "UNKNOWN", "value": None}
