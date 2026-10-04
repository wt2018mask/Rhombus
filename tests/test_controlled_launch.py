from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
from types import SimpleNamespace

import pytest

from rudeus.execution.bootstrap import OriginGuard, check_snapshot
from rudeus.execution.code_bundle import reconstruct_bundle
from rudeus.execution.contracts import ExecutionError, TaskSpec
from rudeus.execution.launcher import launch_local, prepare_snapshot
from rudeus.execution.runtime import ExecutionManifest, RuntimeRecord, file_identity, verify_execution_records
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science.evidence import EvidenceStore
from rudeus.science.followups import generate_followups
from tests.test_evidence import git
from tests.test_followups import requested


@pytest.fixture(scope="module")
def committed_code(tmp_path_factory):
    repo = tmp_path_factory.mktemp("controlled-code")
    project = Path(__file__).resolve().parents[1]
    shutil.copytree(project/"rudeus", repo/"rudeus", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("pyproject.toml", "requirements.txt", "config.yaml"):
        shutil.copyfile(project/name, repo/name)
    git(repo, "init")
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Launcher Test", "-c", "user.email=launcher@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-m", "Actual sources under test")
    marker = repo/"i1-non-head-marker.txt"
    marker.write_text("I1 non-HEAD revision marker\n")
    git(repo, "add", marker.name)
    git(repo, "-c", "user.name=Launcher Test", "-c", "user.email=launcher@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-m", "I1 marker commit")
    return repo


@pytest.fixture(scope="module")
def base_context(tmp_path_factory, committed_code):
    tmp_path = tmp_path_factory.mktemp("controlled-inputs")
    request, followup, record = requested(tmp_path)
    followup = replace(followup, task=replace(followup.task,
                                            code_revision=git(committed_code, "rev-parse", "HEAD")))
    request["followups"] = [followup.to_dict()]
    store = EvidenceStore(tmp_path/"archive")
    evidence = store.publish(request, source_root=tmp_path/"source")
    task = TaskSpec.from_dict(generate_followups(store, evidence.logical_hash)["tasks"][0]["task"])
    bundle = reconstruct_bundle(task, git_root=committed_code)
    return committed_code, task, bundle, store, record


@pytest.fixture
def context(tmp_path, base_context):
    repo, task, bundle, source, record = base_context
    shutil.copytree(source.root, tmp_path/"archive")
    return repo, task, bundle, EvidenceStore(tmp_path/"archive"), record


def launch(context, **kwargs):
    repo, task, bundle, store, _ = context
    return launch_local(task, bundle, bundle.bundle_hash, git_root=repo, store_root=store.root,
        interpreter=str(Path(sys.executable).absolute()),
        dependency_roots=kwargs.pop("dependency_roots", [sysconfig.get_path("purelib")]), **kwargs)


def test_real_controlled_launch_and_retained_records(context):
    repo, task, bundle, store, record = context
    before = canonical_bytes(task)
    result = launch(context)
    assert result["artifact_status"] == "VERIFIED_LOCAL", result
    assert result["actual_execution_identity"] == "NOT_ATTESTED"
    assert store.verify(result["evidence_hash"])["scientific_record"] == record
    manifest = ExecutionManifest.from_dict(json.loads(store.path(
        f"execution_manifests/{result['execution_manifest_hash']}.json").read_bytes()))
    runtime = RuntimeRecord.from_dict(json.loads(store.path(
        f"runtime_records/{result['runtime_record_hash']}.json").read_bytes()))
    assert manifest.attempt_id == result["attempt"]["attempt_id"]
    assert manifest.task_content_hash == task.content_hash == result["attempt"]["task_content_hash"]
    assert result["attempt"]["environment"]["execution_manifest_hash"] == manifest.content_hash
    assert runtime.launch_flags["isolated"] == runtime.launch_flags["no_site"] == 1
    assert runtime.dependencies["numpy"]["version"]
    assert runtime.interpreter["executable_sha256"]
    assert canonical_bytes(task) == before
    assert verify_execution_records(manifest, manifest.content_hash, runtime, runtime.content_hash,
        bundle, task)["actual_execution_identity"] == "NOT_ATTESTED"
    assert str(repo).encode() not in canonical_bytes(runtime)
    repeated = launch(context)
    assert repeated["artifact_status"] == "VERIFIED_LOCAL", repeated
    assert repeated["runtime_record_hash"] == runtime.content_hash
    assert repeated["artifact"]["logical_hash"] == result["artifact"]["logical_hash"]
    assert repeated["execution_manifest_hash"] != manifest.content_hash


@pytest.mark.parametrize("damage", ["modified", "missing", "extra", "wrong_hash"])
def test_wrong_bundle_rejected_before_application_import(context, tmp_path, damage):
    repo, task, bundle, store, _ = context
    changed = bundle.to_dict()
    if damage == "modified":
        changed["files"][0]["raw_sha256"] = digest("wrong")
    elif damage == "missing":
        changed["files"] = [f for f in changed["files"] if f["relative_path"] != "rudeus/science/p3.py"]
    elif damage == "extra":
        changed["files"].append({**changed["files"][0], "relative_path": "rudeus/extra.py"})
        changed["files"].sort(key=lambda item: item["relative_path"])
    from rudeus.execution.code_bundle import CodeBundle
    changed = CodeBundle.from_dict(changed)
    destination = tmp_path/"prepared"
    destination.mkdir()
    with pytest.raises(ExecutionError):
        prepare_snapshot(task, changed, digest("wrong") if damage == "wrong_hash" else changed.bundle_hash,
                         git_root=repo, destination=destination)
    assert list(destination.iterdir()) == []
    assert not list(store.root.glob("execution_manifests/*"))


@pytest.mark.parametrize("damage", ["modified", "missing"])
def test_materialized_damage_rejected_before_any_application_import(context, tmp_path, damage):
    repo, task, bundle, store, _ = context
    code = tmp_path/"prepared"
    code.mkdir()
    prepare_snapshot(task, bundle, bundle.bundle_hash, git_root=repo, destination=code)
    marker = tmp_path/"application-imported"
    target = code/"rudeus/__init__.py"
    if damage == "modified":
        target.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    else:
        target.unlink()
    configuration = tmp_path/"context.json"
    configuration.write_bytes(canonical_bytes({"bundle": bundle.to_dict()}))
    response = tmp_path/"response.json"
    run = subprocess.run([sys.executable, "-I", "-S", "-B", str(code/"rudeus/execution/bootstrap.py"),
        str(configuration), str(response)], capture_output=True, timeout=60)
    assert run.returncode != 0 and not marker.exists()
    assert json.loads(response.read_text())["actual_execution_identity"] == "NOT_ATTESTED"


def test_pythonpath_user_site_and_current_directory_injection_ignored(context, tmp_path, monkeypatch):
    marker = tmp_path/"injected"
    injection = tmp_path/"injection"
    injection.mkdir()
    malicious = f"from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError('injected')\n"
    for name in ("sitecustomize.py", "usercustomize.py", "numpy.py"):
        (injection/name).write_text(malicious)
    user_site = Path(sysconfig.get_path("purelib", scheme="nt_user" if sys.platform == "win32" else "posix_user",
                                      vars={"userbase": str(injection)}))
    user_site.mkdir(parents=True)
    (user_site/"usercustomize.py").write_text(malicious)
    (injection/"rudeus").mkdir()
    (injection/"rudeus/__init__.py").write_text(malicious)
    monkeypatch.setenv("PYTHONPATH", str(injection))
    monkeypatch.setenv("PYTHONUSERBASE", str(injection))
    monkeypatch.chdir(injection)
    result = launch(context)
    assert result["artifact_status"] == "VERIFIED_LOCAL", result
    assert not marker.exists()


def test_alternate_repository_import_root_rejected(context, tmp_path):
    alternate = tmp_path/"packages"
    (alternate/"rudeus").mkdir(parents=True)
    result = launch(context, dependency_roots=[str(alternate), sysconfig.get_path("purelib")])
    assert result["artifact_status"] == "FAILED"
    assert "alternate" in result["reason"]


def test_guard_rejects_dependency_module_origin_mismatch(context, tmp_path):
    _, _, bundle, _, _ = context
    guard = OriginGuard(tmp_path/"code", bundle.to_dict(), [tmp_path/"packages"], [])
    with pytest.raises(ValueError, match="outside controlled"):
        guard.check("numpy", tmp_path/"injected/numpy.py")
    with pytest.raises(ValueError, match="alternate repository"):
        guard.check("rudeus.science.p3", tmp_path/"packages/p3.py")


def test_dependency_metadata_and_module_from_different_roots_rejected(context, tmp_path, monkeypatch):
    from rudeus.execution import runtime as observations
    _, _, bundle, _, _ = context
    metadata_root, module_root = tmp_path/"metadata", tmp_path/"modules"
    metadata_root.mkdir()
    module_root.mkdir()
    path = module_root/"numpy.py"
    path.write_text("value = 1\n")
    guard = OriginGuard(tmp_path/"code", bundle.to_dict(), [metadata_root, module_root], [])
    module = SimpleNamespace(__file__=str(path), __spec__=SimpleNamespace(origin=str(path)))
    monkeypatch.setattr(observations, "sys", SimpleNamespace(modules={"numpy": module}))
    monkeypatch.setattr(observations.importlib.metadata, "distribution",
                        lambda _: SimpleNamespace(locate_file=lambda _: metadata_root, version="test"))
    with pytest.raises(ExecutionError, match="metadata/module origin mismatch"):
        observations.capture_runtime(guard)


def test_dependency_origin_redirection_rejected_during_launch(context, tmp_path):
    packages, outside = tmp_path/"packages", tmp_path/"outside"
    (packages/"numpy").mkdir(parents=True)
    outside.mkdir()
    marker = tmp_path/"imported-outside"
    (outside/"injected.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    (packages/"numpy/__init__.py").write_text(f"__path__ = [{str(outside)!r}]\nfrom . import injected\n")
    result = launch(context, dependency_roots=[str(packages), sysconfig.get_path("purelib")])
    assert result["artifact_status"] == "FAILED", result
    assert "outside controlled" in result["reason"]
    assert not marker.exists()


def test_explicit_launcher_cli(context, tmp_path):
    repo, task, bundle, store, _ = context
    task_file, bundle_file = tmp_path/"task.json", tmp_path/"bundle.json"
    task_file.write_bytes(canonical_bytes(task))
    bundle_file.write_bytes(canonical_bytes(bundle))
    run = subprocess.run([sys.executable, "-I", "-S", "-B", str(repo/"rudeus/execution/launcher.py"),
        str(task_file), str(bundle_file), "--bundle-hash", bundle.bundle_hash,
        "--git-root", str(repo), "--store-root", str(store.root), "--interpreter", sys.executable,
        "--dependency-root", sysconfig.get_path("purelib")], cwd=tmp_path,
        capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout+run.stderr
    assert json.loads(run.stdout)["actual_execution_identity"] == "NOT_ATTESTED"


def test_manifest_determinism_unavailability_and_tampering(context):
    _, task, bundle, _, _ = context
    unavailable = []
    assert file_identity(None, unavailable, "library") is None
    assert unavailable
    runtime = RuntimeRecord(interpreter={"library_sha256": None}, launch_flags={}, dependencies={},
                            modules=(), unavailable_reasons=tuple(unavailable))
    manifest = ExecutionManifest(attempt_id=digest("attempt"), task_content_hash=task.content_hash,
        bundle_hash=bundle.bundle_hash, runtime_record_hash=runtime.content_hash)
    reordered = dict(reversed(list(manifest.to_dict().items())))
    assert ExecutionManifest.from_dict(reordered).content_hash == manifest.content_hash
    assert verify_execution_records(manifest, manifest.content_hash, runtime, runtime.content_hash,
                                     bundle, task)["runtime_record"] == "VERIFIED"
    with pytest.raises(ExecutionError):
        verify_execution_records(manifest, manifest.content_hash, replace(runtime, unavailable_reasons=()),
                                 runtime.content_hash, bundle, task)


def test_controlled_launch_non_head_revision(context, tmp_path):
    repo, task, bundle, store, record = context
    first_revision = git(repo, "rev-list", "--max-parents=0", "HEAD")

    request, followup, historical_record = requested(tmp_path)

    historical_task = replace(
        followup.task,
        code_revision=first_revision,
    )
    request["followups"] = [
        replace(followup, task=historical_task).to_dict()
    ]

    historical_store = EvidenceStore(tmp_path/"historical-archive")
    evidence = historical_store.publish(
        request,
        source_root=tmp_path/"source",
    )
    generated = generate_followups(historical_store, evidence.logical_hash)
    generated_task = TaskSpec.from_dict(generated["tasks"][0]["task"])

    assert generated_task.code_revision == first_revision

    historical_bundle = reconstruct_bundle(
        generated_task,
        git_root=repo,
    )
    assert historical_bundle.code_revision == first_revision
    assert historical_bundle.bundle_hash != bundle.bundle_hash

    result = launch_local(
        generated_task,
        historical_bundle,
        historical_bundle.bundle_hash,
        git_root=repo,
        store_root=historical_store.root,
        interpreter=str(Path(sys.executable).absolute()),
        dependency_roots=[sysconfig.get_path("purelib")],
    )

    assert result["artifact_status"] == "VERIFIED_LOCAL", result
    assert result["actual_execution_identity"] == "NOT_ATTESTED"
    assert historical_store.verify(result["evidence_hash"])["scientific_record"] == historical_record
