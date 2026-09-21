"""Backend contracts and gated Kaggle behavior, not a simulated provider success."""
from dataclasses import replace
import json
import shutil
import subprocess
import sys

import pytest

from rudeus.execution.backend import (TaskBundle, advance, build_task_bundle, new_attempt,
    operational_failure, retain_attempt, verify_ingested, verify_retrieved, verify_task_bundle)
from rudeus.execution.contracts import ExecutionError, TaskSpec
from rudeus.execution import kaggle_backend
from rudeus.science.contracts import canonical_bytes, digest
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
    submitted = advance(first, "SUBMITTED", remote_run_id="provider-run-1")
    running = advance(submitted, "RUNNING")
    completed = advance(running, "COMPLETED")
    assert first.state == "CREATED" and submitted.previous_hash == first.content_hash
    assert completed.previous_hash == running.content_hash
    store = EvidenceStore(tmp_path)
    for snapshot in (first, submitted, running, completed):
        assert retain_attempt(snapshot, store=store) == retain_attempt(snapshot, store=store)
    assert len(list(store.root.glob("backend_attempts/*"))) == 4
    with pytest.raises(ExecutionError):
        advance(running, "RUNNING", remote_run_id="other-run")
    with pytest.raises(ExecutionError):
        advance(completed, "RETRIEVED", evidence_hash=digest("unverified"))
    assert "scientific_verdict" not in completed.to_dict()


@pytest.mark.parametrize("state", ["PREEMPTED", "INTERRUPTED", "FAILED"])
def test_operational_failure_is_terminal_and_not_scientific(prepared, state):
    accepted = advance(new_attempt(prepared, "kaggle"), "SUBMITTED", remote_run_id="run")
    failed = advance(accepted, state, failure_class="INFRASTRUCTURE")
    assert failed.state == state and failed.evidence_hash is None
    with pytest.raises(ExecutionError):
        advance(failed, "RUNNING")
    assert new_attempt(prepared, "kaggle").attempt_id != failed.attempt_id


@pytest.mark.parametrize("exc,expected", [(TimeoutError(), "INFRASTRUCTURE"),
    (ConnectionError(), "INFRASTRUCTURE"), (MemoryError(), "RESOURCE"),
    (FloatingPointError(), "NUMERICAL"), (RuntimeError(), "SOFTWARE"),
    (FileNotFoundError(), "INTEGRITY"), (ExecutionError("unsupported", "UNSUPPORTED_INPUT"), "UNSUPPORTED_INPUT")])
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
    assert "secret-must-not-appear" not in json.dumps(report)


def test_submission_status_and_retrieval_stay_gated(prepared):
    backend = kaggle_backend.KaggleBackend()
    attempt = new_attempt(prepared, "kaggle")
    for call in (lambda: backend.submit(prepared, prepared.task["resource_requirements"]),
                 lambda: backend.status(attempt), lambda: backend.retrieve(attempt)):
        with pytest.raises(ExecutionError) as exc:
            call()
        assert exc.value.failure_class.value == "UNSUPPORTED_INPUT"
    with pytest.raises(ExecutionError, match="immutable"):
        backend.submit(prepared, {"invented": "resource"})
    with pytest.raises(ExecutionError, match="another backend"):
        backend.status(new_attempt(prepared, "other"))
    assert attempt.state == "CREATED"


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
    completed = advance(advance(initial, "SUBMITTED", remote_run_id="test-run"), "COMPLETED")
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
