"""Real local execution -> committed archive -> independently checked receipt."""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science.evidence import EvidenceStore
from rudeus.science.followups import generate_followups
from tests.test_evidence import git
from tests.test_followups import requested


def commit(repo):
    git(repo, "add", "archive")
    git(repo, "-c", "user.name=Receipt Test", "-c", "user.email=receipt@example.invalid",
        "commit", "-m", "Verified local evidence")
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture(scope="module")
def executed(tmp_path_factory):
    base = tmp_path_factory.mktemp("real-local-receipt")
    repo = base/"code"
    source_root = Path(__file__).resolve().parents[1]
    # Commit the actual CodeBundle scope under test in isolation. The local
    # runner rejects dirty computation sources, and CodeBundle v1 requires the
    # rudeus tree plus the three declared project-root files.
    shutil.copytree(source_root/"rudeus", repo/"rudeus",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("pyproject.toml", "requirements.txt", "config.yaml"):
        shutil.copy2(source_root/name, repo/name)
    git(repo, "init")
    git(repo, "add", "rudeus", "pyproject.toml", "requirements.txt", "config.yaml")
    git(repo, "-c", "user.name=Receipt Test", "-c", "user.email=receipt@example.invalid",
        "commit", "-m", "Actual code under test")
    request, followup, _ = requested(base)
    followup = replace(followup, task=replace(followup.task, code_revision=git(repo, "rev-parse", "HEAD")))
    request["followups"] = [followup.to_dict()]
    store = EvidenceStore(repo/"archive")
    source = store.publish(request, source_root=base/"source")
    task = generate_followups(store, source.logical_hash)["tasks"][0]["task"]
    task_file = base/"task.json"
    task_file.write_bytes(canonical_bytes(task))
    historical = {p: p.read_bytes() for p in (base/"source").iterdir()}
    run = subprocess.run([sys.executable, "-B", "-m", "rudeus.execution.local", str(task_file),
        "--store-root", str(store.root)], cwd=repo, env={**os.environ, "PYTHONPATH": str(repo)},
        capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout+run.stderr
    result = json.loads(run.stdout)
    assert result["artifact_status"] == "VERIFIED_LOCAL"
    assert result["git_ingestion"] == "NOT_ATTESTED"
    assert all(p.read_bytes() == data for p, data in historical.items())
    return store.root, result


@pytest.fixture
def archive(tmp_path, executed):
    source, result = executed
    repo = tmp_path/"repo"
    shutil.copytree(source, repo/"archive")
    git(repo, "init")
    return repo, EvidenceStore(repo/"archive"), result


def test_receipt_binds_real_execution_and_is_deterministic(archive):
    repo, store, result = archive
    identity = result["evidence_hash"]
    before = {p: p.read_bytes() for p in store.root.rglob("*") if p.is_file()}
    revision = commit(repo)
    receipt = store.acknowledge_git(identity, git_root=repo, revision="HEAD")
    assert receipt == store.acknowledge_git(identity, git_root=repo, revision=revision)
    assert receipt == store.verify_git_receipt(digest(receipt), git_root=repo)
    assert receipt["git_commit"] == revision
    assert receipt["git_tree"] == git(repo, "rev-parse", "HEAD^{tree}")
    assert receipt["artifact_hash"] == result["artifact"]["logical_hash"]
    assert receipt["producer_attempt"] == result["attempt"]["attempt_id"]
    assert receipt["task_id"] == result["task_id"]
    assert receipt["parent_artifact_hashes"] == sorted(result["artifact"]["parent_artifact_hashes"])
    origin = receipt["task_provenance"]["evidence_hash"]
    assert f"evidence/{origin}.json" in receipt["files"]
    assert receipt["scientific_verdict"] == result["scientific_verdict"] == "UNKNOWN"
    assert receipt["remote_replication"] == "NOT_ATTESTED"
    assert len(list(store.root.glob("receipts/*"))) == 1
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize("state", ["uncommitted", "staged", "missing", "corrupt", "origin_uncommitted"])
def test_unpersisted_or_unverified_evidence_cannot_receive_receipt(archive, state):
    repo, store, result = archive
    identity = result["evidence_hash"]
    if state == "staged":
        git(repo, "add", "archive")
    elif state == "origin_uncommitted":
        task = store.verify(identity)["provenance"]["task"]
        origin = store.path(f"evidence/{task['provenance']['evidence_hash']}.json")
        data = origin.read_bytes()
        origin.unlink()
        commit(repo)
        origin.write_bytes(data)
    elif state in ("missing", "corrupt"):
        commit(repo)
        output = store.path(f"blobs/{result['artifact']['raw_hash']}")
        if state == "missing":
            output.unlink()
        else:
            output.write_bytes(b"changed after commit")
    with pytest.raises(ExecutionError) as failure:
        store.acknowledge_git(identity, git_root=repo, revision="HEAD")
    assert failure.value.failure_class.value == "INTEGRITY"
    assert not list(store.root.glob("receipts/*"))


@pytest.mark.parametrize("tamper", ["content", "rehash", "commit", "blob"])
def test_receipt_verifier_does_not_trust_receipt_or_working_bytes(archive, tamper):
    repo, store, result = archive
    commit(repo)
    receipt = store.acknowledge_git(result["evidence_hash"], git_root=repo, revision="HEAD")
    identity = digest(receipt)
    if tamper == "blob":
        store.path(f"blobs/{result['artifact']['raw_hash']}").write_bytes(b"corrupt")
    else:
        receipt["task_id"] = digest("other task")
        if tamper == "commit":
            receipt["git_commit"] = "f"*40
        if tamper != "content":
            identity = digest(receipt)
        store.path(f"receipts/{identity}.json").write_bytes(canonical_bytes(receipt))
    with pytest.raises(ExecutionError):
        store.verify_git_receipt(identity, git_root=repo)


def test_fresh_clone_cli_verification_and_append_only_conflict(archive, tmp_path):
    repo, store, result = archive
    commit(repo)
    receipt = store.acknowledge_git(result["evidence_hash"], git_root=repo, revision="HEAD")
    receipt_hash = digest(receipt)
    commit(repo)  # The receipt itself belongs to a subsequent commit.
    clone = tmp_path/"clone"
    subprocess.run(["git", "clone", "--no-hardlinks", str(repo), str(clone)],
                   check=True, capture_output=True)
    recovered = EvidenceStore(clone/"archive")
    assert recovered.verify_git_receipt(receipt_hash, git_root=clone) == receipt
    run = subprocess.run([sys.executable, "-B", "-m", "rudeus.science.evidence",
        "verify-git-receipt", receipt_hash, "--store-root", str(recovered.root), "--git-root", str(clone)],
        capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout+run.stderr
    assert json.loads(run.stdout) == receipt
    path = recovered.path(f"receipts/{receipt_hash}.json")
    path.write_bytes(b"existing corrupted receipt")
    with pytest.raises(ExecutionError, match="append-only"):
        recovered.acknowledge_git(result["evidence_hash"], git_root=clone, revision=receipt["git_commit"])
    assert path.read_bytes() == b"existing corrupted receipt"
