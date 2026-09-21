"""Adversarial Git receipts over a real controlled local execution."""
import json
import shutil
import subprocess

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science.evidence import EvidenceStore, VERSION
from tests.test_controlled_launch import committed_code, base_context, launch
from tests.test_evidence import git
from tests.test_git_receipts import commit


@pytest.fixture(scope="module")
def controlled_archive(base_context):
    result = launch(base_context)
    assert result["artifact_status"] == "VERIFIED_LOCAL", result
    return base_context, result


@pytest.fixture
def archive(tmp_path, controlled_archive):
    context, result = controlled_archive
    source_repo, _, _, source_store, _ = context
    repo = tmp_path/"repo"
    subprocess.run(["git", "clone", "--no-hardlinks", str(source_repo), str(repo)],
                   check=True, capture_output=True)
    shutil.copytree(source_store.root, repo/"archive")
    return repo, EvidenceStore(repo/"archive"), result


def acknowledge(archive):
    repo, store, result = archive
    commit(repo)
    return store.acknowledge_git(result["evidence_hash"], git_root=repo, revision="HEAD")


def test_complete_receipt_reproducible_in_fresh_clone(archive, tmp_path):
    repo, store, result = archive
    receipt = acknowledge(archive)
    assert receipt["format_version"] == "claim-evidence-git-v2"
    assert receipt["artifact_status"] == "DURABLY_INGESTED"
    assert receipt["scientific_verdict"] == "UNKNOWN"
    assert receipt["actual_execution_identity"] == "NOT_ATTESTED"
    records = receipt["execution_records"][result["evidence_hash"]]
    for key in ("repository_bundle", "execution_manifest", "runtime_record"):
        assert records[key] == "VERIFIED"
    assert records["actual_execution_identity"] == "NOT_ATTESTED"
    assert "code_identity" not in receipt and "code_identity" not in records
    for directory, key in (("code_bundles", "bundle_hash"),
                           ("execution_manifests", "execution_manifest_hash"),
                           ("runtime_records", "runtime_record_hash")):
        assert receipt["files"][f"{directory}/{result[key]}.json"] == result[key]
    assert receipt == store.acknowledge_git(result["evidence_hash"], git_root=repo, revision="HEAD")
    commit(repo)
    clone = tmp_path/"clone"
    subprocess.run(["git", "clone", "--no-hardlinks", str(repo), str(clone)],
                   check=True, capture_output=True)
    assert EvidenceStore(clone/"archive").verify_git_receipt(digest(receipt), git_root=clone) == receipt


@pytest.mark.parametrize("directory,key", [("code_bundles", "bundle_hash"),
    ("execution_manifests", "execution_manifest_hash"), ("runtime_records", "runtime_record_hash")])
@pytest.mark.parametrize("damage", ["altered", "noncanonical", "missing", "uncommitted"])
def test_records_must_be_canonical_and_committed(archive, directory, key, damage):
    repo, store, result = archive
    path = store.path(f"{directory}/{result[key]}.json")
    data = path.read_bytes()
    if damage == "altered":
        changed = json.loads(data)
        if key == "bundle_hash":
            changed["files"][0]["raw_sha256"] = digest("modified")
        elif key == "execution_manifest_hash":
            changed["task_content_hash"] = digest("modified")
        else:
            changed["unavailable_reasons"].append("modified observations")
        path.write_bytes(canonical_bytes(changed))
    elif damage == "noncanonical":
        path.write_bytes(data + b" ")
    else:
        path.unlink()
    commit(repo)
    if damage == "uncommitted":
        path.write_bytes(data)
    with pytest.raises(ExecutionError) as exc:
        store.acknowledge_git(result["evidence_hash"], git_root=repo, revision="HEAD")
    assert exc.value.failure_class.value == "INTEGRITY"
    assert not list(store.root.glob("receipts/*"))


def rewrite_execution(archive, damage):
    """Rehash malicious records and republish valid science to exercise real ingress."""
    _, store, result = archive
    request = store.verify(result["evidence_hash"])["provenance"]
    attempt = next(a for a in request["attempts"] if a["attempt_id"] == result["attempt"]["attempt_id"])
    env = attempt["environment"]
    manifest = json.loads(store.path(f"execution_manifests/{env['execution_manifest_hash']}.json").read_bytes())
    if damage == "bundle":
        bundle = json.loads(store.path(f"code_bundles/{env['bundle_hash']}.json").read_bytes())
        bundle["files"][0]["raw_sha256"] = digest("forged bytes")
        env["bundle_hash"] = manifest["bundle_hash"] = digest(bundle)
        store.path(f"code_bundles/{digest(bundle)}.json").write_bytes(canonical_bytes(bundle))
    elif damage in ("task_content_hash", "bundle_hash", "runtime_record_hash", "attempt_id"):
        manifest[damage] = digest("unrelated")
    elif damage == "launch_policy":
        env["launch_policy_version"] = "other-policy"
    elif damage == "partial":
        del env["bundle_hash"]
    elif damage == "attested":
        env["actual_execution_identity"] = "VERIFIED"
    env["execution_manifest_hash"] = digest(manifest)
    store.path(f"execution_manifests/{digest(manifest)}.json").write_bytes(canonical_bytes(manifest))
    # Publish's artifact locations reference the original local-run directory;
    # explicitly use retained content-addressed inputs for this adversarial request.
    source = store.root/"adversarial-source"
    for item in request["manifests"]:
        path = source/item["durable_locator"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(store.path(f"blobs/{item['raw_hash']}").read_bytes())
    return store.publish(request, source_root=source).logical_hash


@pytest.mark.parametrize("damage", ["bundle", "bundle_hash", "task_content_hash", "runtime_record_hash",
                                    "attempt_id", "launch_policy", "partial", "attested"])
def test_rehashed_forgery_and_reference_chain_rejected(archive, damage):
    repo, store, _ = archive
    identity = rewrite_execution(archive, damage)
    commit(repo)
    with pytest.raises(ExecutionError) as exc:
        store.acknowledge_git(identity, git_root=repo, revision="HEAD")
    assert exc.value.failure_class.value == "INTEGRITY"


@pytest.mark.parametrize("field", ["code_identity", "actual_execution_identity", "execution_records"])
def test_receipt_cannot_upgrade_observations_to_attestation(archive, field):
    repo, store, _ = archive
    receipt = acknowledge(archive)
    receipt[field] = "VERIFIED"
    identity = digest(receipt)
    store.path(f"receipts/{identity}.json").write_bytes(canonical_bytes(receipt))
    with pytest.raises(ExecutionError):
        store.verify_git_receipt(identity, git_root=repo)


def test_legacy_receipt_keeps_original_byte_only_contract(archive):
    repo, store, result = archive
    commit(repo)
    legacy = store._git_receipt(result["evidence_hash"], git_root=repo, revision="HEAD", receipt_version=VERSION)
    assert "execution_records" not in legacy and "actual_execution_identity" not in legacy
    identity = digest(legacy)
    store.path(f"receipts/{identity}.json").parent.mkdir(exist_ok=True)
    store.path(f"receipts/{identity}.json").write_bytes(canonical_bytes(legacy))
    for directory in ("code_bundles", "runtime_records", "execution_manifests"):
        for path in (store.root/directory).glob("*.json"):
            path.unlink()
    assert store.verify_git_receipt(identity, git_root=repo) == legacy


def test_code_commit_must_be_retained_in_durability_history(archive):
    repo, store, result = archive
    git(repo, "checkout", "--orphan", "unrelated")
    git(repo, "rm", "-r", "--cached", ".")
    commit(repo)
    with pytest.raises(ExecutionError):
        store.acknowledge_git(result["evidence_hash"], git_root=repo, revision="HEAD")
