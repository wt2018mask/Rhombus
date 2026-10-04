import copy
from dataclasses import replace
import hashlib
import json
import subprocess

import pytest

from rudeus.execution.code_bundle import CodeBundle, reconstruct_bundle, verify_bundle
from rudeus.execution.contracts import ExecutionError, TaskSpec
from rudeus.science.contracts import canonical_bytes, digest


def git(root, *args, data=None):
    return subprocess.run(["git", "-C", str(root), *args], input=data,
                          check=True, capture_output=True).stdout


def commit(root):
    git(root, "-c", "user.name=Bundle Test", "-c", "user.email=bundle@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-qm", "Bundle fixture")
    return git(root, "rev-parse", "HEAD").decode().strip()


@pytest.fixture
def source(tmp_path):
    git(tmp_path, "init", "--object-format=sha1")
    files = {"rudeus/execution/local.py": b"print('runner')\n", "rudeus/analysis.py": b"value = 1\n",
             "pyproject.toml": b"[project]\n", "requirements.txt": b"numpy\n", "config.yaml": b"{}\n",
             ".gitattributes": b"*.py text eol=crlf\n", "unrelated.txt": b"outside scope\n"}
    for name, data in files.items():
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    git(tmp_path, "add", ".")
    revision = commit(tmp_path)
    task = TaskSpec(candidate_id="fixture", stage="P3", protocol_hash=digest("protocol"),
        config={}, input_artifact_hashes=(), dependencies=(), code_revision=revision,
        resource_requirements={}, expected_outputs=("record.json",), retry_policy={})
    return tmp_path, task


def test_valid_deterministic_and_checkout_independent(source, monkeypatch):
    root, task = source
    first = reconstruct_bundle(task, git_root=root)
    assert first.bundle_hash == hashlib.sha256(canonical_bytes(first)).hexdigest()
    assert first.bundle_hash == digest(first.to_dict())
    assert len(first.files) == 5
    assert "rudeus/execution/local.py" in [f["relative_path"] for f in first.files]
    retained = json.loads(canonical_bytes(first))
    (root/"rudeus/execution/local.py").write_bytes(b"changed checkout\r\n")
    (root/"rudeus/extra.py").write_bytes(b"untracked\n")
    assert reconstruct_bundle(task, git_root=root) == first
    # HEAD may advance: the immutable requested revision remains authoritative.
    git(root, "add", ".")
    commit(root)
    monkeypatch.setenv("GIT_DIR", str(root/"nonexistent"))
    assert reconstruct_bundle(task, git_root=root) == first
    result = verify_bundle(retained, first.bundle_hash, task, git_root=root)
    assert result["repository_bundle"] == "VERIFIED"
    assert result["execution_identity"] == "NOT_ATTESTED"
    assert task.code_revision == first.code_revision


@pytest.mark.parametrize("damage", ["modified_file", "missing_file", "extra_file", "revision",
    "tree", "mode", "blob", "raw", "hash", "entrypoint", "external", "unsorted"])
def test_adversarial_inventory_rejected_even_when_rehashed(source, damage):
    root, task = source
    original = reconstruct_bundle(task, git_root=root)
    value = copy.deepcopy(original.to_dict())
    item = next(f for f in value["files"] if f["relative_path"] == "rudeus/analysis.py")
    if damage == "modified_file":
        data = b"value = 99\n"
        item["raw_sha256"] = hashlib.sha256(data).hexdigest()
        item["git_blob_oid"] = git(root, "hash-object", "-w", "--stdin", data=data).decode().strip()
    elif damage == "missing_file":
        value["files"].remove(item)
    elif damage == "extra_file":
        value["files"].append({**item, "relative_path": "rudeus/extra.py"})
        value["files"].sort(key=lambda f: f["relative_path"])
    elif damage in ("revision", "tree"):
        value["code_revision" if damage == "revision" else "git_tree"] = "f"*40
    elif damage == "mode":
        item["git_mode"] = "100755"
    elif damage == "blob":
        item["git_blob_oid"] = "f"*40
    elif damage == "raw":
        item["raw_sha256"] = "f"*64
    elif damage == "entrypoint":
        value["entrypoint"] = "outside/runner.py"
    elif damage == "external":
        item["relative_path"] = "rudeus/../../outside.py"
    elif damage == "unsorted":
        value["files"].reverse()
    claimed_hash = "f"*64 if damage == "hash" else digest(value)
    with pytest.raises(ExecutionError) as failure:
        verify_bundle(value, claimed_hash, task, git_root=root)
    assert failure.value.failure_class.value == "INTEGRITY"


@pytest.mark.parametrize("kind", ["symlink", "submodule", "lfs"])
def test_external_objects_rejected_without_checkout_support(source, kind):
    root, task = source
    if kind == "submodule":
        oid, mode = task.code_revision, "160000"
    else:
        data = (b"../../external.py" if kind == "symlink" else
                b"version https://git-lfs.github.com/spec/v1\noid sha256:"+b"a"*64+b"\nsize 10\n")
        oid = git(root, "hash-object", "-w", "--stdin", data=data).decode().strip()
        mode = "120000" if kind == "symlink" else "100644"
    git(root, "update-index", "--add", "--cacheinfo", f"{mode},{oid},rudeus/external")
    task = replace(task, code_revision=commit(root))
    with pytest.raises(ExecutionError) as failure:
        reconstruct_bundle(task, git_root=root)
    assert failure.value.failure_class.value == "UNSUPPORTED_INPUT"


def test_wrong_requested_revision_and_missing_required_file(source):
    root, task = source
    bundle = reconstruct_bundle(task, git_root=root)
    git(root, "rm", "requirements.txt")
    other = replace(task, code_revision=commit(root))
    for selected in (other, replace(task, code_revision="f"*40), replace(task, code_revision="HEAD")):
        with pytest.raises(ExecutionError):
            verify_bundle(bundle, bundle.bundle_hash, selected, git_root=root)


def test_git_replacement_cannot_change_inventory(source):
    root, task = source
    expected = reconstruct_bundle(task, git_root=root)
    (root/"rudeus/analysis.py").write_bytes(b"substituted\n")
    git(root, "add", ".")
    other = commit(root)
    git(root, "replace", task.code_revision, other)
    assert reconstruct_bundle(task, git_root=root) == expected


def test_verification_from_bare_clone_and_retained_json(source, tmp_path):
    root, task = source
    bundle = reconstruct_bundle(task, git_root=root)
    clone = tmp_path/"bare.git"
    subprocess.run(["git", "clone", "--bare", "--no-hardlinks", str(root), str(clone)],
                   check=True, capture_output=True)
    assert verify_bundle(json.loads(canonical_bytes(bundle)), bundle.bundle_hash, task,
                         git_root=clone)["execution_identity"] == "NOT_ATTESTED"


def test_sha256_git_object_format(source, tmp_path):
    root, task = source
    other = tmp_path/"sha256"
    other.mkdir()
    git(other, "init", "--object-format=sha256")
    for name in ("pyproject.toml", "requirements.txt", "config.yaml", "rudeus/execution/local.py"):
        path = other/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((root/name).read_bytes())
    git(other, "add", ".")
    task = replace(task, code_revision=commit(other))
    bundle = reconstruct_bundle(task, git_root=other)
    assert bundle.git_object_format == "sha256"
    assert all(len(f["git_blob_oid"]) == 64 for f in bundle.files)
    assert verify_bundle(bundle, bundle.bundle_hash, task, git_root=other)["repository_bundle"] == "VERIFIED"
