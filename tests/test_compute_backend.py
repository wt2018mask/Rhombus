"""Backend contracts and gated Kaggle behavior, not a simulated provider success."""
from dataclasses import FrozenInstanceError, replace
import json
import shutil
import subprocess
import sys

import pytest

from rudeus.execution.backend import (BackendCapabilities, TaskBundle, advance, build_task_bundle,
    new_attempt, operational_failure, prepare_attempt, retain_attempt, validate_prepared_attempt, verify_ingested,
    verify_retrieved, verify_task_bundle)
from rudeus.execution.contracts import ExecutionError, TaskSpec
from rudeus.execution import kaggle_backend
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.execution.candidate_supply import bind_candidate_supply_work_item
from rudeus.science.evidence import EvidenceStore
from tests.test_controlled_launch import committed_code, base_context, launch
from tests.test_git_receipts import commit


@pytest.fixture(scope="module")
def prepared(base_context):
    repo, task, code, store, _ = base_context
    return build_task_bundle(task, code, store=store, git_root=repo)


def test_bundle_deterministic_and_full_task_bound(base_context, prepared):
    repo, task, code, store, _ = base_context
    assert build_task_bundle(task, code, store=store, git_root=repo) == prepared
    assert verify_task_bundle(prepared.to_dict(), prepared.content_hash, store=store, git_root=repo) == prepared
    assert TaskSpec.from_dict(prepared.task).task_id == task.task_id
    with pytest.raises(ValueError):
        replace(prepared, task={**task.to_dict(), "provenance": {"changed": True}})


@pytest.mark.parametrize("damage", ["missing", "hash", "extra", "size"])
def test_task_inventory_reconstruction_rejects_tampering(base_context, prepared, damage):
    repo, _, _, store, _ = base_context
    data = prepared.to_dict()
    if damage == "missing":
        data["retained_files"].pop()
    elif damage == "extra":
        data["retained_files"].append({"relative_path": f"blobs/{digest('extra')}",
                                      "raw_sha256": digest("extra"), "size_bytes": 5})
        data["retained_files"].sort(key=lambda row: row["relative_path"])
    elif damage == "size":
        data["retained_files"][0]["size_bytes"] += 1
    else:
        data["retained_files"][0]["raw_sha256"] = digest("changed")
    with pytest.raises(ExecutionError):
        verify_task_bundle(data, digest(data), store=store, git_root=repo)


def test_bundle_wrong_hash_and_external_path(base_context, prepared):
    repo, _, _, store, _ = base_context
    with pytest.raises(ExecutionError):
        verify_task_bundle(prepared, digest("other"), store=store, git_root=repo)
    data = prepared.to_dict()
    data["retained_files"][0]["relative_path"] = "../secret"
    with pytest.raises(ValueError):
        TaskBundle.from_dict(data)


def test_lifecycle_retry_identity_and_append_only(prepared, tmp_path):
    first, retry = new_attempt(prepared, "kaggle"), new_attempt(prepared, "kaggle")
    assert first.attempt_id != retry.attempt_id
    assert first.task_content_hash == retry.task_content_hash == prepared.task_content_hash
    assert new_attempt(prepared, "other-provider").task_content_hash == first.task_content_hash
    with pytest.raises(FrozenInstanceError):
        first.backend = "mutated"
    prepared_snapshot = prepare_attempt(prepared, "kaggle")
    assert prepared_snapshot.state == "PREPARED"
    with pytest.raises(ExecutionError):
        advance(prepared_snapshot, "RUNNING")
    submitted = advance(prepared_snapshot, "SUBMITTED", remote_run_id="provider-run-1")
    running = advance(submitted, "RUNNING")
    completed = advance(running, "COMPLETED")
    assert first.state == "CREATED"
    assert submitted.previous_hash == prepared_snapshot.content_hash
    assert completed.previous_hash == running.content_hash
    store = EvidenceStore(tmp_path)
    for snapshot in (first, prepared_snapshot, submitted, running, completed):
        assert retain_attempt(snapshot, store=store) == retain_attempt(snapshot, store=store)
    assert len(list(store.root.glob("backend_attempts/*"))) == 5
    with pytest.raises(ExecutionError):
        advance(running, "RUNNING", remote_run_id="other-run")
    with pytest.raises(ExecutionError):
        advance(completed, "RETRIEVED", evidence_hash=digest("unverified"))
    assert submitted.remote_run_id == "provider-run-1"
    assert submitted.task_content_hash == first.task_content_hash
    assert "scientific_verdict" not in completed.to_dict()
    assert first.creation_provenance["backend_identity"] == "kaggle"
    assert first.task_content_hash == prepared.task_content_hash


@pytest.mark.parametrize("state", ["PREEMPTED", "INTERRUPTED", "FAILED"])
def test_operational_failure_is_terminal_and_not_scientific(prepared, state):
    accepted = advance(prepare_attempt(prepared, "kaggle"), "SUBMITTED", remote_run_id="run")
    failed = advance(accepted, state, failure_class="INFRASTRUCTURE")
    assert failed.state == state and failed.evidence_hash is None
    with pytest.raises(ExecutionError):
        advance(failed, "RUNNING")
    assert new_attempt(prepared, "kaggle").attempt_id != failed.attempt_id


@pytest.mark.parametrize("exc,expected", [(TimeoutError(), "TIMEOUT"),
    (ConnectionError(), "NETWORK"), (MemoryError(), "RESOURCE"),
    (FloatingPointError(), "NUMERICAL"), (RuntimeError(), "SOFTWARE"),
    (FileNotFoundError(), "INTEGRITY"), (ExecutionError("unsupported", "UNSUPPORTED_INPUT"), "UNSUPPORTED_INPUT"),
    (ExecutionError("unclassified", "UNKNOWN"), "UNKNOWN")])
def test_failure_classification(exc, expected):
    assert operational_failure(exc) == expected


@pytest.mark.parametrize("prerequisites", [False, True])
def test_capabilities_never_promote_prerequisites_to_execution(monkeypatch, tmp_path, prerequisites):
    monkeypatch.setattr(kaggle_backend.Path, "home", lambda: tmp_path)
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path))
    for key in ("KAGGLE_API_TOKEN", "KAGGLE_USERNAME", "KAGGLE_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(kaggle_backend.shutil, "which", lambda _: "cli" if prerequisites else None)
    monkeypatch.setattr(kaggle_backend.importlib.util, "find_spec", lambda _: object() if prerequisites else None)
    if prerequisites:
        monkeypatch.setenv("KAGGLE_API_TOKEN", "secret-must-not-appear")
    report = kaggle_backend.KaggleBackend().capabilities()
    assert report["availability"] == report["free_execution"] == "UNKNOWN"
    assert report["execution_mode"]["state"] == "UNSUPPORTED"
    assert all(item == {"state": "UNKNOWN", "value": None} for item in report["capabilities"].values())
    assert report["capability_model"]["verification_state"] == "UNKNOWN"
    assert report["capability_model"]["gpu"] == {"state": "UNKNOWN", "value": None}
    assert "secret-must-not-appear" not in json.dumps(report)


def test_submission_status_and_retrieval_stay_gated(prepared, monkeypatch):
    backend = kaggle_backend.KaggleBackend()
    attempt = new_attempt(prepared, "kaggle")
    with pytest.raises(ExecutionError, match="invalid backend transition"):
        advance(attempt, "SUBMITTED", remote_run_id="must-not-submit")
    with pytest.raises(ValueError, match="link to its CREATED snapshot"):
        replace(attempt, state="PREPARED")
    with pytest.raises(ExecutionError, match="prepared"):
        backend.submit(attempt, prepared, prepared.task["resource_requirements"])
    for call in (lambda: backend.status(attempt), lambda: backend.retrieve(attempt)):
        with pytest.raises(ExecutionError) as exc:
            call()
        assert exc.value.failure_class.value == "UNSUPPORTED_INPUT"
    prepared_attempt = backend.prepare(prepared, prepared.task["resource_requirements"])
    monkeypatch.setattr(backend, "capabilities", lambda: {"availability": "UNKNOWN"})
    with pytest.raises(ExecutionError, match="submission disabled"):
        backend.submit(prepared_attempt, prepared, prepared.task["resource_requirements"])
    with pytest.raises(ExecutionError, match="immutable"):
        backend.submit(prepared_attempt, prepared, {"invented": "resource"})
    with pytest.raises(ExecutionError, match="another backend"):
        backend.status(new_attempt(prepared, "other"))
    assert attempt.state == "CREATED"
    assert prepared_attempt.state == "PREPARED"
    assert prepared_attempt.task_content_hash == prepared.task_content_hash
    assert prepared_attempt.backend == "kaggle"


def test_explicit_probe_cli():
    run = subprocess.run([sys.executable, "-B", "-m", "rudeus.execution.kaggle_backend"],
                         capture_output=True, text=True, timeout=30)
    assert run.returncode == 2
    assert json.loads(run.stdout)["probe_scope"] == "LOCAL_PREREQUISITES_ONLY"


@pytest.fixture(scope="module")
def output(base_context, prepared):
    result = launch(base_context)
    assert result["artifact_status"] == "VERIFIED_LOCAL", result
    return result


@pytest.fixture
def downloaded(tmp_path, base_context, prepared, output):
    repo, _, _, source, _ = base_context
    local = tmp_path/"repo"
    subprocess.run(["git", "clone", "--no-hardlinks", str(repo), str(local)], check=True, capture_output=True)
    shutil.copytree(source.root, local/"archive")
    store = EvidenceStore(local/"archive")
    request = store.verify(output["evidence_hash"])["provenance"]
    # Synthetic transport envelope around real output; not a Kaggle execution test.
    producer = next(a for a in request["attempts"] if a["attempt_id"] == output["attempt"]["attempt_id"])
    producer.update(backend="test-transport", remote_session_id="test-run")
    for item in request["manifests"]:
        path = store.root/"source"/item["durable_locator"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(store.path(f"blobs/{item['raw_hash']}").read_bytes())
    identity = store.publish(request, source_root=store.root/"source").logical_hash
    initial = replace(new_attempt(prepared, "test-transport"), attempt_id=producer["attempt_id"])
    completed = advance(advance(advance(initial, "PREPARED"),
                                "SUBMITTED", remote_run_id="test-run"), "COMPLETED")
    return local, store, identity, completed


def test_download_verification_and_existing_git_receipt(downloaded, prepared):
    repo, store, identity, attempt = downloaded
    retrieved = verify_retrieved(attempt, prepared, store=store, evidence_hash=identity, git_root=repo)
    assert retrieved.state == "RETRIEVED" and retrieved.receipt_hash is None
    commit(repo)
    receipt = store.acknowledge_git(identity, git_root=repo, revision="HEAD")
    with pytest.raises(ExecutionError, match="attempt mismatch"):
        verify_ingested(replace(retrieved, task_content_hash=digest("other task")),
                        store=store, receipt_hash=digest(receipt), git_root=repo)
    durable = verify_ingested(retrieved, store=store, receipt_hash=digest(receipt), git_root=repo)
    assert durable.state == "DURABLY_INGESTED"
    assert receipt["actual_execution_identity"] == "NOT_ATTESTED"
    assert receipt["scientific_verdict"] == "UNKNOWN"


@pytest.mark.parametrize("damage", ["bytes", "artifact", "malformed", "identity", "task", "runtime"])
def test_download_rejects_tampering(downloaded, prepared, damage):
    repo, store, identity, attempt = downloaded
    if damage == "identity":
        attempt = replace(attempt, attempt_id=digest("different"))
    elif damage == "task":
        attempt = replace(attempt, task_content_hash=digest("different"))
    elif damage == "artifact":
        provenance = store.verify(identity)["provenance"]
        output = next(m for m in provenance["manifests"] if digest(m) == provenance["record_manifest"])
        store.path(f"blobs/{output['raw_hash']}").write_bytes(b"tampered artifact")
    elif damage == "runtime":
        next((store.root/"runtime_records").glob("*.json")).write_bytes(b"{}")
    else:
        store.path(f"blobs/{identity}").write_bytes(b"not json" if damage == "malformed" else b"{}")
    with pytest.raises(ExecutionError) as exc:
        verify_retrieved(attempt, prepared, store=store, evidence_hash=identity, git_root=repo)
    assert exc.value.failure_class.value == "INTEGRITY"
    assert attempt.state == "COMPLETED"

def test_scientific_tasks_cannot_dispatch_to_local_backend(prepared, base_context):
    from rudeus.execution.local_backend import LocalBackend

    backend = LocalBackend(
        git_root=base_context[0],
        store=base_context[3],
    )

    assert callable(backend.capabilities)
    assert callable(backend.submit)
    assert callable(backend.status)
    assert callable(backend.retrieve)

    assert backend.capabilities()["execution_mode"]["state"] == "UNSUPPORTED"
    with pytest.raises(ExecutionError, match="remote-only") as error:
        backend.prepare(prepared, prepared.task["resource_requirements"])
    assert error.value.failure_class.value == "UNSUPPORTED_INPUT"
    local_prepared = prepare_attempt(prepared, "local")
    with pytest.raises(ExecutionError, match="remote-only") as error:
        backend.submit(local_prepared, prepared, prepared.task["resource_requirements"])
    assert error.value.failure_class.value == "UNSUPPORTED_INPUT"


def test_backend_capability_model_preserves_verified_data_and_unknowns():
    caps = BackendCapabilities(
        backend_identity="test-provider",
        verification_state="VERIFIED",
        cpu={"state": "VERIFIED", "value": True},
        gpu={"state": "VERIFIED", "value": False},
        supported_task_modes={"state": "VERIFIED", "value": ["remote-python"]},
    ).to_dict()
    assert caps["cpu"] == {"state": "VERIFIED", "value": True}
    assert caps["gpu"] == {"state": "VERIFIED", "value": False}
    assert caps["memory_bytes"] == {"state": "UNKNOWN", "value": None}
    with pytest.raises(ValueError, match="must not invent"):
        BackendCapabilities(backend_identity="test", cpu={"state": "UNKNOWN", "value": True})


def test_certified_runtime_work_item_metadata_is_provenance_not_task_identity(base_context):
    code = base_context[2]
    item = {
        "work_item_id": "000000-fixture", "parent_id": "obelix:abc", "arm_id": "BASELINE_GAUSSIAN",
        "allocation_unit_id": digest("unit"), "lane": "EXPLORATION", "seed": 42,
        "operator_identity": {"operator_name": "mobile-ion-displace", "operator_version": "v2"},
        "allocation_unit_semantics": "ONE_OPERATOR_PARENT_CHILD_REQUEST",
    }
    item["seed_material"] = {
        "parent_id": item["parent_id"], "seed": item["seed"],
        "operator_name": item["operator_identity"]["operator_name"],
        "operator_version": item["operator_identity"]["operator_version"],
        "generation_config_hash": "generation-config-fixture",
        "allocation_unit_id": item["allocation_unit_id"],
    }
    item["operator_rng_identity"] = digest(item["seed_material"])
    plan = {
        "schema_version": "candidate-supply-v2-scheduler-runtime-plan-v1",
        "execution_performed": False,
        "generation_config_hash": "generation-config-fixture",
        "parent_cohort_identity": {"canonical_content_sha256": digest("cohort")},
        "work_items": [item],
    }
    plan["manifest_identity"] = digest(plan)
    task, bundle = bind_candidate_supply_work_item(plan, item, code, git_root=base_context[0])
    original = dict(item)
    assert task.candidate_id == original["parent_id"]
    assert task.config["operator_identity"] == original["operator_identity"]
    assert task.provenance["work_item"] == original
    assert task.provenance["work_item"]["operator_rng_identity"] == original["operator_rng_identity"]
    assert task.provenance["runtime_plan_identity"] == plan["manifest_identity"]
    assert task.provenance["runtime_plan_artifact_identity"] == digest(plan)
    assert bundle.task_content_hash == task.content_hash
    assert bundle.task["provenance"]["work_item"] == item
    alternate = replace(task, resource_requirements={"backend_hint": "different"})
    assert alternate.task_id == task.task_id
    assert bundle.task["provenance"]["work_item"] == item

    changed_item = dict(item)
    changed_allocation = digest("other-unit")
    changed_item.update({"work_item_id": "other-work-item", "allocation_unit_id": changed_allocation,
                         "lane": "EXPLOITATION", "arm_id": "SAME_OPERATOR_DIFFERENT_LANE"})
    changed_item["seed_material"] = {**item["seed_material"], "allocation_unit_id": changed_allocation}
    changed_item["operator_rng_identity"] = digest(changed_item["seed_material"])
    changed_plan = dict(plan)
    changed_plan["work_items"] = [changed_item]
    changed_plan["manifest_identity"] = digest({k: v for k, v in changed_plan.items()
                                                 if k != "manifest_identity"})
    changed_task, changed_bundle = bind_candidate_supply_work_item(
        changed_plan, changed_item, code, git_root=base_context[0])
    assert changed_task.task_id == task.task_id
    assert changed_task.provenance["work_item"] == changed_item
    assert changed_task.provenance["runtime_plan_identity"] != task.provenance["runtime_plan_identity"]
    assert changed_bundle.retained_files != bundle.retained_files

    scientific_change = replace(task, seed=task.seed + 1)
    assert scientific_change.task_id != task.task_id


def test_submission_requires_exact_prepared_attempt_binding(prepared):
    backend = kaggle_backend.KaggleBackend()
    requirements = prepared.task["resource_requirements"]
    valid = backend.prepare(prepared, requirements)
    assert validate_prepared_attempt(valid, prepared, "kaggle") == prepared

    with pytest.raises(ExecutionError, match="binding mismatch"):
        validate_prepared_attempt(prepare_attempt(prepared, "other-backend"), prepared, "kaggle")

    wrong_task = replace(TaskSpec.from_dict(prepared.task), seed=999)
    wrong_bundle = replace(prepared, task=wrong_task.to_dict(), task_content_hash=wrong_task.content_hash)
    with pytest.raises(ExecutionError, match="binding mismatch"):
        validate_prepared_attempt(valid, wrong_bundle, "kaggle")

    wrong_content = replace(valid, task_content_hash=digest("other task content"))
    with pytest.raises(ExecutionError, match="binding mismatch"):
        validate_prepared_attempt(wrong_content, prepared, "kaggle")

    wrong_code_task = replace(TaskSpec.from_dict(prepared.task), code_bundle_hash=digest("other code bundle"))
    with pytest.raises(ValueError, match="task bundle binding mismatch"):
        replace(prepared, task=wrong_code_task.to_dict(), task_content_hash=wrong_code_task.content_hash)

    wrong_bundle_hash = replace(valid, task_bundle_hash=digest("other task bundle"),
                                creation_provenance={"contract": "backend-attempt-v1",
                                                     "task_bundle_hash": digest("other task bundle"),
                                                     "task_id": valid.task_id,
                                                     "backend_identity": "kaggle"})
    with pytest.raises(ExecutionError, match="binding mismatch"):
        validate_prepared_attempt(wrong_bundle_hash, prepared, "kaggle")
