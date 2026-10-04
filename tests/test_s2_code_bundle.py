"""Fixture-only tests for prospective S2 CodeBundle binding.

All repositories, stores, and artifacts live under pytest temporary
directories. No real HELDOUT root, outcomes, qualification, or closure are
touched.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration import (
    CalibrationClass,
    CalibrationDatasetManifest,
    CalibrationPlan,
    CalibrationScope,
    GeneratorSpec,
    SplitAssignment,
    TruthRecord,
    TruthType,
)
from rudeus.science.calibration_batch import materialize_calibration_dataset
from rudeus.science.calibration_execution import (
    build_calibration_task,
    materialize_replicate,
    resolve_verified_code_bundle,
    validate_materialization_lineage,
    verify_task_code_bundle,
)
from rudeus.science.calibration_estimator import (
    estimate_calibration_replicate,
    verify_s2_provenance,
)
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration import CalibrationReplicateManifest
from rudeus.execution.contracts import ArtifactManifest
from rudeus.science.calibration_s2v2_populations import S2V2_HELDOUT_SEEDS
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science import run_s2v2_heldout as heldout


def _git(root: Path, *args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], input=data, check=True,
        capture_output=True).stdout


def _commit(root: Path) -> str:
    _git(root, "-c", "user.name=S2 Fixture", "-c", "user.email=s2@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
    return _git(root, "rev-parse", "HEAD").decode().strip()


@pytest.fixture
def source_repo(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    _git(root, "init", "--object-format=sha1")
    files = {
        "rudeus/execution/local.py": b"print('fixture')\n",
        "rudeus/analysis.py": b"value = 1\n",
        "pyproject.toml": b"[project]\nname = 'fixture'\n",
        "requirements.txt": b"numpy\n",
        "config.yaml": b"fixture: true\n",
    }
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    _git(root, "add", ".")
    return root, _commit(root)


def _h(value):
    return digest({"s2-fixture": value})


def _graph(store: CalibrationStore, revision: str):
    scope = CalibrationScope(
        estimator="free_intercept_OLS_MSD", estimator_version="v1",
        resampling_method="m", resampling_version="1",
        protocol_hash=_h("protocol"), estimand="D_self", units="m2/s",
        generator_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        generator_version="fixture-v1", truth_type=TruthType.ANALYTICAL,
        truth_model_version="fixture-truth", species_composition={"Li": 2},
        n_particles=2, duration_ps=4.0, sampling_interval_ps=1.0,
        lag_steps=(1, 2), code_revision=revision)
    truth = TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.ANALYTICAL,
        value={"D_m2_per_s": 1.0e-9}, code_revision=revision)
    generator = GeneratorSpec(
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        generator_name="brownian", generator_version="fixture-v1",
        parameters={"n_frames": 4, "n_ions": 2,
                    "diffusion_tensor": [[0.1, 0.0, 0.0], [0.0, 0.1, 0.0],
                                         [0.0, 0.0, 0.1]],
                    "dt_ps": 1.0},
        initialization_spec={}, seed_semantics="explicit",
        output_coordinate_contract={}, code_hash=_h("generator"))
    scope_hash = store.store(scope)
    truth_hash = store.store(truth)
    generator_hash = store.store(generator)
    plan = CalibrationPlan(
        objective="s2-provenance-fixture", scope_hashes=(scope_hash,),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",), truth_requirements={}, split_rules={},
        seed_policy={}, dev_replicate_ids=("rep-1",), heldout_replicate_ids=(),
        independence_rules={}, selection_stopping_policy={},
        frozen_analysis_fields=("estimator",), code_revision=revision)
    plan_hash = store.store(plan)
    dataset = CalibrationDatasetManifest(
        dataset_id="ds-s2-provenance", plan_hash=plan_hash, scope_hash=scope_hash,
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",), trajectory_ids=("traj-1",),
        truth_record_hashes=(truth_hash,), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(generator_hash,), artifact_manifest_hashes=(),
        attempted_replicate_ids=("rep-1",))
    return {"plan": plan_hash, "scope": scope_hash, "dataset": store.store(dataset),
            "generator": generator_hash, "truth": truth_hash}


def _legacy_task(graph, revision):
    return build_calibration_task(
        plan_hash=graph["plan"], scope_hash=graph["scope"],
        dataset_manifest_hash=graph["dataset"], generator_spec_hash=graph["generator"],
        truth_record_hash=graph["truth"], replicate_id="rep-1",
        parameter_cell_id="cell-a", split_assignment=SplitAssignment.DEV,
        seed=7, code_revision=revision)


def _batch_graph(store: CalibrationStore, revision: str,
                 reps=("rep-1", "rep-2", "rep-3")):
    """Multi-replicate fixture graph for batch-level tests (fixture repos only)."""
    scope = CalibrationScope(
        estimator="free_intercept_OLS_MSD", estimator_version="v1",
        resampling_method="m", resampling_version="1",
        protocol_hash=_h("protocol"), estimand="D_self", units="m2/s",
        generator_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        generator_version="fixture-v1", truth_type=TruthType.ANALYTICAL,
        truth_model_version="fixture-truth", species_composition={"Li": 2},
        n_particles=2, duration_ps=4.0, sampling_interval_ps=1.0,
        lag_steps=(1, 2), code_revision=revision)
    truth = TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.ANALYTICAL,
        value={"D_m2_per_s": 1.0e-9}, code_revision=revision)
    generator = GeneratorSpec(
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        generator_name="brownian", generator_version="fixture-v1",
        parameters={"n_frames": 4, "n_ions": 2,
                    "diffusion_tensor": [[0.1, 0.0, 0.0], [0.0, 0.1, 0.0],
                                         [0.0, 0.0, 0.1]],
                    "dt_ps": 1.0},
        initialization_spec={}, seed_semantics="explicit",
        output_coordinate_contract={}, code_hash=_h("generator"))
    scope_hash = store.store(scope)
    truth_hash = store.store(truth)
    generator_hash = store.store(generator)
    plan = CalibrationPlan(
        objective="s2-batch-fixture", scope_hashes=(scope_hash,),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",), truth_requirements={}, split_rules={},
        seed_policy={}, dev_replicate_ids=tuple(reps), heldout_replicate_ids=(),
        independence_rules={}, selection_stopping_policy={},
        frozen_analysis_fields=("estimator",), code_revision=revision)
    plan_hash = store.store(plan)
    dataset = CalibrationDatasetManifest(
        dataset_id="ds-s2-batch", plan_hash=plan_hash, scope_hash=scope_hash,
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",),
        trajectory_ids=tuple(f"traj-{rep}" for rep in reps),
        truth_record_hashes=(truth_hash,), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(generator_hash,), artifact_manifest_hashes=(),
        attempted_replicate_ids=tuple(reps))
    return {"plan": plan_hash, "scope": scope_hash, "dataset": store.store(dataset),
            "generator": generator_hash, "truth": truth_hash}


def _task(root, graph, revision, **over):
    values = dict(
        plan_hash=graph["plan"], scope_hash=graph["scope"],
        dataset_manifest_hash=graph["dataset"], generator_spec_hash=graph["generator"],
        truth_record_hash=graph["truth"], replicate_id="rep-1",
        parameter_cell_id="cell-a", split_assignment=SplitAssignment.DEV,
        seed=7, code_revision=revision, git_root=root,
        require_code_bundle=True)
    values.update(over)
    return build_calibration_task(**values)


def test_legacy_taskspec_mapping_identity_stable(source_repo, tmp_path):
    _, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _legacy_task(graph, revision)
    assert "code_bundle_hash" not in task.to_dict()
    assert task.task_id == digest({
        "version": task.schema_version, "candidate": "rep-1",
        "stage": "CALIBRATION", "protocol": graph["scope"],
        "config": task.config_hash, "inputs": sorted(task.input_artifact_hashes),
        "dependencies": [], "code": revision, "temperature": None,
        "replica": None, "seed": 7, "outputs": ["trajectory"]})


def test_prospective_task_identity_sensitive_to_bundle(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    legacy = _legacy_task(graph, revision)
    assert task.code_bundle_hash is not None
    assert task.task_id != legacy.task_id
    assert task.content_hash != legacy.content_hash
    assert replace(task, code_bundle_hash="0" * 64).task_id != task.task_id


def test_correct_revision_wrong_bundle_rejected(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    with pytest.raises(ExecutionError):
        _task(root, graph, revision, code_bundle_hash="0" * 64)


def test_wrong_revision_rejected(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    with pytest.raises(ExecutionError):
        _task(root, graph, "0" * 40)
    (root / "rudeus/analysis.py").write_bytes(b"value = 2\n")
    _git(root, "add", "rudeus/analysis.py")
    other = _commit(root)
    bundle = resolve_verified_code_bundle(code_revision=revision, git_root=root)
    with pytest.raises(ExecutionError):
        resolve_verified_code_bundle(
            code_revision=other, git_root=root,
            code_bundle=bundle, code_bundle_hash=bundle.bundle_hash)


@pytest.mark.parametrize("relative_path", [
    "rudeus/analysis.py", "pyproject.toml", "requirements.txt", "config.yaml"])
def test_mutated_bundle_scope_rejected(source_repo, tmp_path, relative_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    bundle = resolve_verified_code_bundle(code_revision=revision, git_root=root)
    changed = copy.deepcopy(bundle.to_dict())
    item = next(value for value in changed["files"]
                if value["relative_path"] == relative_path)
    item["raw_sha256"] = "0" * 64
    with pytest.raises(ExecutionError):
        verify_task_code_bundle(task, git_root=root, code_bundle=changed)


def test_missing_bundle_rejected(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    legacy = _legacy_task(graph, revision)
    with pytest.raises(ExecutionError):
        verify_task_code_bundle(legacy, git_root=root)
    with pytest.raises(ExecutionError):
        build_calibration_task(
            plan_hash=graph["plan"], scope_hash=graph["scope"],
            dataset_manifest_hash=graph["dataset"],
            generator_spec_hash=graph["generator"],
            truth_record_hash=graph["truth"], replicate_id="rep-1",
            parameter_cell_id="cell-a", split_assignment=SplitAssignment.DEV,
            seed=7, code_revision=revision, require_code_bundle=True)


def test_foreign_bundle_rejected(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "--object-format=sha1")
    for name, data in {
        "rudeus/execution/local.py": b"print('other')\n",
        "rudeus/analysis.py": b"value = 9\n",
        "pyproject.toml": b"[project]\n", "requirements.txt": b"numpy\n",
        "config.yaml": b"{}\n",
    }.items():
        path = other / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    _git(other, "add", ".")
    foreign_revision = _commit(other)
    foreign = resolve_verified_code_bundle(
        code_revision=foreign_revision, git_root=other)
    with pytest.raises(ExecutionError):
        verify_task_code_bundle(task, git_root=root, code_bundle=foreign)


def test_dirty_scoped_files_refuse_execution(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    (root / "rudeus/analysis.py").write_bytes(b"dirty = True\n")
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts", git_root=root)
    assert result["artifact_status"] == "FAILED"
    assert result["failure_class"] == "INTEGRITY"


def test_out_of_scope_modifications_do_not_fail(source_repo, tmp_path):
    root, revision = source_repo
    _git(root, "-c", "user.name=S2 Fixture", "-c", "user.email=s2@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "empty")
    docs = root / "docs/notes.md"
    docs.parent.mkdir(parents=True, exist_ok=True)
    docs.write_bytes(b"notes\n")
    store = CalibrationStore(tmp_path / "store")
    revision = _git(root, "rev-parse", "HEAD").decode().strip()
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts", git_root=root)
    assert result["artifact_status"] == "STORED"


def test_ignored_pycache_artifact_allowed(source_repo, tmp_path):
    root, revision = source_repo
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n*.pyo\n*.pyd\n")
    cache = root / "rudeus/execution/__pycache__/module.cpython-312.pyc"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(b"cache\n")
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts", git_root=root)
    assert result["artifact_status"] == "STORED"


@pytest.mark.parametrize("suffix", ["pyc", "pyo", "pyd"])
def test_ignored_bytecode_artifact_allowed(source_repo, tmp_path, suffix):
    root, revision = source_repo
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n*.pyo\n*.pyd\n")
    artifact = root / f"rudeus/cached_module.{suffix}"
    artifact.write_bytes(b"bytecode\n")
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts", git_root=root)
    assert result["artifact_status"] == "STORED"


def test_ignored_source_py_still_rejected(source_repo, tmp_path):
    root, revision = source_repo
    (root / ".gitignore").write_text("rudeus/some_ignored_module.py\n")
    (root / "rudeus/some_ignored_module.py").write_bytes(b"value = 1\n")
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts", git_root=root)
    assert result["artifact_status"] == "FAILED"
    assert result["failure_class"] == "INTEGRITY"


def test_untracked_scoped_source_rejected(source_repo, tmp_path):
    root, revision = source_repo
    (root / "rudeus/new_untracked_module.py").write_bytes(b"value = 1\n")
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts", git_root=root)
    assert result["artifact_status"] == "FAILED"
    assert result["failure_class"] == "INTEGRITY"


def test_staged_scoped_source_rejected(source_repo, tmp_path):
    root, revision = source_repo
    (root / "rudeus/analysis.py").write_bytes(b"value = 2\n")
    _git(root, "add", "rudeus/analysis.py")
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts", git_root=root)
    assert result["artifact_status"] == "FAILED"
    assert result["failure_class"] == "INTEGRITY"


def test_batch_prospective_resolves_git_once(source_repo, tmp_path, monkeypatch):
    import rudeus.science.calibration_batch as batch_module
    import rudeus.science.calibration_execution as exec_module
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _batch_graph(store, revision)
    seeds = {"rep-1": 11, "rep-2": 12, "rep-3": 13}
    real = exec_module.resolve_verified_code_bundle
    calls = {"batch": 0, "exec": 0, "guard": 0}
    real_guard = exec_module._require_clean_bundle_scope

    def batch_spy(**kwargs):
        calls["batch"] += 1
        return real(**kwargs)

    def exec_spy(**kwargs):
        calls["exec"] += 1
        return real(**kwargs)

    def guard_spy(*args, **kwargs):
        calls["guard"] += 1
        return real_guard(*args, **kwargs)

    monkeypatch.setattr(batch_module, "resolve_verified_code_bundle", batch_spy)
    monkeypatch.setattr(exec_module, "resolve_verified_code_bundle", exec_spy)
    monkeypatch.setattr(exec_module, "_require_clean_bundle_scope", guard_spy)
    result = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=graph["dataset"],
        artifact_root=tmp_path / "artifacts", seeds=seeds,
        code_revision=revision, git_root=root, require_code_bundle=True)
    assert result["succeeded"] == ["rep-1", "rep-2", "rep-3"]
    assert result["failed"] == []
    assert calls["batch"] == 1
    assert calls["exec"] == 0
    assert calls["guard"] == 1


def test_batch_prospective_tasks_bundle_bound(source_repo, tmp_path, monkeypatch):
    import rudeus.science.calibration_batch as batch_module
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _batch_graph(store, revision)
    seeds = {"rep-1": 21, "rep-2": 22, "rep-3": 23}
    seen = {}
    real_build = batch_module.build_calibration_task

    def build_spy(**kwargs):
        task = real_build(**kwargs)
        seen[task.candidate_id] = task
        return task

    monkeypatch.setattr(batch_module, "build_calibration_task", build_spy)
    result = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=graph["dataset"],
        artifact_root=tmp_path / "artifacts", seeds=seeds,
        code_revision=revision, git_root=root, require_code_bundle=True)
    assert result["succeeded"] == ["rep-1", "rep-2", "rep-3"]
    bundle = resolve_verified_code_bundle(code_revision=revision, git_root=root)
    assert set(seen) == {"rep-1", "rep-2", "rep-3"}
    task_ids = set()
    for rep, seed in seeds.items():
        task = seen[rep]
        assert task.code_bundle_hash == bundle.bundle_hash
        assert task.candidate_id == rep
        assert task.seed == seed
        task_ids.add(task.task_id)
    assert len(task_ids) == 3
    attempt_ids = {json.loads(path.read_text())["task_id"]
                   for path in (tmp_path / "artifacts" / "attempts").glob("*.json")}
    assert attempt_ids == task_ids


def test_batch_structural_wrong_hash_rejected(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    bundle = resolve_verified_code_bundle(code_revision=revision, git_root=root)
    task = build_calibration_task(
        plan_hash=graph["plan"], scope_hash=graph["scope"],
        dataset_manifest_hash=graph["dataset"],
        generator_spec_hash=graph["generator"],
        truth_record_hash=graph["truth"], replicate_id="rep-1",
        parameter_cell_id="cell-a", split_assignment=SplitAssignment.DEV,
        seed=7, code_revision=revision,
        verified_bundle_hash=bundle.bundle_hash)
    with pytest.raises(ExecutionError):
        validate_materialization_lineage(
            store, task, verified_bundle_hash="0" * 64)
    with pytest.raises(ExecutionError):
        validate_materialization_lineage(
            store, task, git_root=root,
            verified_bundle_hash=bundle.bundle_hash)
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts",
        verified_bundle_hash="0" * 64)
    assert result["artifact_status"] == "FAILED"
    assert result["failure_class"] == "INTEGRITY"


def test_batch_task_identity_mismatch_rejected(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _batch_graph(store, revision, reps=("rep-1", "rep-2"))
    seeds = {"rep-1": 31, "rep-2": 32}
    result = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=graph["dataset"],
        artifact_root=tmp_path / "artifacts", seeds=seeds,
        code_revision=revision, git_root=root, require_code_bundle=True)
    assert result["succeeded"] == ["rep-1", "rep-2"]
    bundle = resolve_verified_code_bundle(code_revision=revision, git_root=root)
    expected = build_calibration_task(
        plan_hash=graph["plan"], scope_hash=graph["scope"],
        dataset_manifest_hash=graph["dataset"],
        generator_spec_hash=graph["generator"],
        truth_record_hash=graph["truth"], replicate_id="rep-1",
        parameter_cell_id="cell-a", split_assignment=SplitAssignment.DEV,
        seed=31, code_revision=revision,
        verified_bundle_hash=bundle.bundle_hash)
    manifest_hash = result["results"]["rep-1"]["replicate_manifest_hash"]
    verify_s2_provenance(
        artifact_root=tmp_path / "artifacts",
        replicate_manifest_hash=manifest_hash,
        calibration_store=store, expected_task=expected,
        expected_bundle_hash=bundle.bundle_hash)
    wrong_seed = replace(expected, seed=99)
    assert wrong_seed.task_id != expected.task_id
    with pytest.raises(ExecutionError):
        verify_s2_provenance(
            artifact_root=tmp_path / "artifacts",
            replicate_manifest_hash=manifest_hash,
            calibration_store=store, expected_task=wrong_seed,
            expected_bundle_hash=bundle.bundle_hash)
    wrong_bundle = replace(expected, code_bundle_hash="0" * 64)
    with pytest.raises(ExecutionError):
        verify_s2_provenance(
            artifact_root=tmp_path / "artifacts",
            replicate_manifest_hash=manifest_hash,
            calibration_store=store, expected_task=wrong_bundle,
            expected_bundle_hash=bundle.bundle_hash)


def test_batch_dirty_tracked_source_raises(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _batch_graph(store, revision, reps=("rep-1", "rep-2"))
    (root / "rudeus/analysis.py").write_bytes(b"dirty = True\n")
    with pytest.raises(ExecutionError):
        materialize_calibration_dataset(
            calibration_store=store, dataset_manifest_hash=graph["dataset"],
            artifact_root=tmp_path / "artifacts",
            seeds={"rep-1": 41, "rep-2": 42},
            code_revision=revision, git_root=root, require_code_bundle=True)


def test_batch_ignored_pycache_allowed(source_repo, tmp_path):
    root, revision = source_repo
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n*.pyo\n*.pyd\n")
    cache = root / "rudeus/execution/__pycache__/module.cpython-312.pyc"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(b"cache\n")
    store = CalibrationStore(tmp_path / "store")
    graph = _batch_graph(store, revision, reps=("rep-1", "rep-2"))
    result = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=graph["dataset"],
        artifact_root=tmp_path / "artifacts",
        seeds={"rep-1": 51, "rep-2": 52},
        code_revision=revision, git_root=root, require_code_bundle=True)
    assert result["succeeded"] == ["rep-1", "rep-2"]


def test_batch_ignored_source_py_raises(source_repo, tmp_path):
    root, revision = source_repo
    (root / ".gitignore").write_text("rudeus/some_ignored_module.py\n")
    (root / "rudeus/some_ignored_module.py").write_bytes(b"value = 1\n")
    store = CalibrationStore(tmp_path / "store")
    graph = _batch_graph(store, revision, reps=("rep-1", "rep-2"))
    with pytest.raises(ExecutionError):
        materialize_calibration_dataset(
            calibration_store=store, dataset_manifest_hash=graph["dataset"],
            artifact_root=tmp_path / "artifacts",
            seeds={"rep-1": 61, "rep-2": 62},
            code_revision=revision, git_root=root, require_code_bundle=True)


def test_batch_legacy_path_unchanged(source_repo, tmp_path, monkeypatch):
    import rudeus.science.calibration_batch as batch_module
    import rudeus.science.calibration_execution as exec_module
    _, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _batch_graph(store, revision, reps=("rep-1", "rep-2"))
    real = exec_module.resolve_verified_code_bundle
    calls = {"batch": 0, "exec": 0}
    seen = {}

    def batch_spy(**kwargs):
        calls["batch"] += 1
        return real(**kwargs)

    def exec_spy(**kwargs):
        calls["exec"] += 1
        return real(**kwargs)

    real_build = batch_module.build_calibration_task

    def build_spy(**kwargs):
        task = real_build(**kwargs)
        seen[task.candidate_id] = task
        return task

    monkeypatch.setattr(batch_module, "resolve_verified_code_bundle", batch_spy)
    monkeypatch.setattr(exec_module, "resolve_verified_code_bundle", exec_spy)
    monkeypatch.setattr(batch_module, "build_calibration_task", build_spy)
    result = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=graph["dataset"],
        artifact_root=tmp_path / "artifacts",
        seeds={"rep-1": 71, "rep-2": 72}, code_revision=revision)
    assert result["succeeded"] == ["rep-1", "rep-2"]
    assert calls == {"batch": 0, "exec": 0}
    for rep in ("rep-1", "rep-2"):
        assert seen[rep].code_bundle_hash is None


def test_structural_content_hash_mismatch_rejected(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts", git_root=root)
    assert result["artifact_status"] == "STORED"
    variant = replace(task, resource_requirements={"cpu": 1})
    assert variant.task_id == task.task_id
    assert variant.content_hash != task.content_hash
    with pytest.raises(ExecutionError):
        verify_s2_provenance(
            artifact_root=tmp_path / "artifacts",
            replicate_manifest_hash=result["replicate_manifest_hash"],
            calibration_store=store, expected_task=variant)


def test_wrong_attempt_binding_rejected(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts", git_root=root)
    assert result["artifact_status"] == "STORED"
    attempt_path = next((tmp_path / "artifacts" / "attempts").glob("*.json"))
    attempt = json.loads(attempt_path.read_text())
    attempt["task_id"] = "0" * 64
    attempt_path.unlink()
    (attempt_path.parent / f"{digest(attempt)}.json").write_bytes(
        canonical_bytes(attempt))
    with pytest.raises(ExecutionError):
        verify_s2_provenance(
            artifact_root=tmp_path / "artifacts",
            replicate_manifest_hash=result["replicate_manifest_hash"],
            calibration_store=store, expected_task=task)


def test_wrong_estimator_lineage_rejected(source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts", git_root=root)
    estimated = estimate_calibration_replicate(
        calibration_store=store, artifact_root=tmp_path / "artifacts",
        replicate_manifest_hash=result["replicate_manifest_hash"],
        estimator_config={"lag_steps": [1, 2], "fit_window_ps": [0.5, 2.5],
                          "selected_species": ["Li"], "volume_A3": 1000.0,
                          "temperature_K": 550.0,
                          "reference_frame": "simulation_cell"},
        code_revision=revision, git_root=root, expected_task=task,
        require_code_bundle=True)
    other_task = _task(root, graph, revision, replicate_id="rep-1", seed=8,
                       code_bundle_hash=task.code_bundle_hash)
    assert other_task.task_id != task.task_id
    with pytest.raises(ExecutionError):
        verify_s2_provenance(
            artifact_root=tmp_path / "artifacts",
            replicate_manifest_hash=result["replicate_manifest_hash"],
            calibration_store=store, expected_task=other_task)
    assert estimated["estimator_result_hash"]


def test_estimator_artifact_binding_tampered_manifest_rejected(
        source_repo, tmp_path):
    root, revision = source_repo
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store, revision)
    task = _task(root, graph, revision)
    result = materialize_replicate(
        task=task, calibration_store=store,
        artifact_root=tmp_path / "artifacts", git_root=root)
    assert result["artifact_status"] == "STORED"
    estimated = estimate_calibration_replicate(
        calibration_store=store, artifact_root=tmp_path / "artifacts",
        replicate_manifest_hash=result["replicate_manifest_hash"],
        estimator_config={"lag_steps": [1, 2], "fit_window_ps": [0.5, 2.5],
                          "selected_species": ["Li"], "volume_A3": 1000.0,
                          "temperature_K": 550.0,
                          "reference_frame": "simulation_cell"},
        code_revision=revision, git_root=root, expected_task=task,
        require_code_bundle=True)
    art = tmp_path / "artifacts"
    replicate = store.retrieve(
        CalibrationReplicateManifest, result["replicate_manifest_hash"])
    manifest = replicate.to_dict()
    attempt = json.loads(
        (art / "attempts" / f"{replicate.execution_attempt_hash}.json").read_text())
    record = json.loads(
        (art / "estimator_results"
         / f"{estimated['estimator_result_hash']}.json").read_text())
    heldout._verify_estimator_artifact_binding(
        art, manifest, attempt, record, "rep-1")
    tampered = dict(record)
    tampered["trajectory_manifest_hash"] = "0" * 64
    with pytest.raises(ExecutionError, match="trajectory lineage binding mismatch"):
        heldout._verify_estimator_artifact_binding(
            art, manifest, attempt, tampered, "rep-1")


HELDOUT_PLAN = "1" * 64
HELDOUT_DATASET = "2" * 64
HELDOUT_SCOPE = "e" * 64
HELDOUT_GENERATOR = "f" * 64


def _heldout_lineage(tmp_path, root, revision, truth_hash, bundle_hash):
    """Build 379 tiny prospective fixtures; bundle hash comes from one resolve."""
    from rudeus.science.calibration import TruthRecord, TruthType

    store_root, artifact_root = tmp_path / "hstore", tmp_path / "hartifacts"
    store = CalibrationStore(store_root)
    store.store(TruthRecord(
        estimand="self_diffusion", units="m2/s", truth_type=TruthType.ANALYTICAL,
        value={"D_m2_per_s": 1e-9}, code_revision="s1-fixture"))

    def _write(path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_bytes(payload))

    for replicate_id in sorted(S2V2_HELDOUT_SEEDS):
        seed = S2V2_HELDOUT_SEEDS[replicate_id]
        task = build_calibration_task(
            plan_hash=HELDOUT_PLAN, scope_hash=HELDOUT_SCOPE,
            dataset_manifest_hash=HELDOUT_DATASET,
            generator_spec_hash=HELDOUT_GENERATOR,
            truth_record_hash=truth_hash, replicate_id=replicate_id,
            parameter_cell_id="cell-a", split_assignment="HELD_OUT",
            seed=seed, code_revision=revision,
            verified_bundle_hash=bundle_hash)
        trajectory = {"replicate_id": replicate_id, "seed": seed,
                      "scope_hash": HELDOUT_SCOPE,
                      "generator_spec_hash": HELDOUT_GENERATOR, "frames": []}
        trajectory_data = canonical_bytes(trajectory)
        trajectory_hash = digest(trajectory)
        (artifact_root / "blobs" / trajectory_hash).parent.mkdir(
            parents=True, exist_ok=True)
        (artifact_root / "blobs" / trajectory_hash).write_bytes(trajectory_data)
        attempt_id = digest({"attempt": replicate_id})
        artifact = ArtifactManifest(
            logical_hash=trajectory_hash,
            raw_hash=hashlib.sha256(trajectory_data).hexdigest(),
            canonicalization_version="canonical-json-v1",
            format="json", format_version="calibration-trajectory-v1",
            size_bytes=len(trajectory_data),
            durable_locator=f"blobs/{trajectory_hash}",
            producer_attempt=attempt_id, parent_artifact_hashes=(),
            retrieval_verification={"status": "STORED",
                                    "verifier": "canonical-json-v1"})
        _write(artifact_root / "trajectory_manifests"
               / f"{artifact.content_hash}.json", artifact.to_dict())
        attempt = {"attempt_id": attempt_id, "task_id": task.task_id,
                   "task_content_hash": task.content_hash,
                   "status": "COMPLETED", "exit_status": 0,
                   "environment": {"code_revision": revision},
                   "output_manifest": {"trajectory": artifact.content_hash}}
        attempt_hash = digest(attempt)
        _write(artifact_root / "attempts" / f"{attempt_hash}.json", attempt)
        store.store(CalibrationReplicateManifest(
            replicate_id=replicate_id, dataset_id=heldout.DATASET_ID,
            parameter_cell_id="cell-a", split_assignment="HELD_OUT",
            independence_declaration={}, seed=seed,
            trajectory_artifact_hash=trajectory_hash,
            truth_record_hash=truth_hash,
            conditions={"code_revision": revision, "seed": seed,
                        "scope_hash": HELDOUT_SCOPE},
            execution_attempt_hash=attempt_hash,
            scientific_outcome="COMPLETED"))
    return store_root, artifact_root


def test_prospective_heldout_materialization_replay(source_repo, tmp_path):
    root, revision = source_repo
    bundle = resolve_verified_code_bundle(
        code_revision=revision, git_root=root)
    store_root, artifact_root = _heldout_lineage(
        tmp_path, root, revision, "d" * 64, bundle.bundle_hash)
    result = heldout.verify_heldout_materialization_complete(
        store_root=store_root, artifact_root=artifact_root,
        truth_hash="d" * 64, code_revision=revision,
        plan_hash=HELDOUT_PLAN, dataset_hash=HELDOUT_DATASET,
        scope_hash=HELDOUT_SCOPE, generator_hash=HELDOUT_GENERATOR,
        git_root=root, require_code_bundle=True)
    assert result["materialized"] == 379


def test_uniform_wrong_heldout_bundle_rejected(source_repo, tmp_path):
    root, revision = source_repo
    bundle = resolve_verified_code_bundle(
        code_revision=revision, git_root=root)
    store_root, artifact_root = _heldout_lineage(
        tmp_path, root, revision, "d" * 64, bundle.bundle_hash)
    with pytest.raises(ExecutionError):
        heldout.verify_heldout_materialization_complete(
            store_root=store_root, artifact_root=artifact_root,
            truth_hash="d" * 64, code_revision=revision,
            plan_hash=HELDOUT_PLAN, dataset_hash=HELDOUT_DATASET,
            scope_hash=HELDOUT_SCOPE, generator_hash=HELDOUT_GENERATOR,
            git_root=root, code_bundle_hash="0" * 64)
