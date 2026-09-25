"""Batch orchestration tests: declared-inventory execution, isolation, idempotence."""
import json

import numpy as np
import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration import (
    CalibrationClass,
    CalibrationDatasetManifest,
    CalibrationPlan,
    CalibrationReplicateManifest,
    CalibrationScope,
    GeneratorSpec,
    SplitAssignment,
    TruthRecord,
    TruthType,
)
from rudeus.science.calibration_batch import materialize_calibration_dataset
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.contracts import digest


def _h(*parts):
    return digest({"test": list(parts)})


def _scope():
    return CalibrationScope(
        estimator="free_intercept_OLS_MSD", estimator_version="v1",
        resampling_method="m", resampling_version="2", protocol_hash=_h("protocol"),
        estimand="D_self", units="m2/s",
        generator_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_version="gv",
        truth_type=TruthType.GENERATED_MODEL, truth_model_version="tmv",
        species_composition={"Li": 2}, n_particles=2,
        duration_ps=8.0, sampling_interval_ps=1.0, lag_steps=(1, 2),
        code_revision="f" * 40)


def _fixture(store, reps=("rep-a", "rep-b", "rep-c"), **over):
    scope_h = store.store(_scope())
    truth_h = store.store(TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.GENERATED_MODEL,
        value={"D_m2_per_s": 1.5e-9}, code_revision="f" * 40))
    gen_h = store.store(GeneratorSpec(
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_name="brownian",
        generator_version="synthetic-v1",
        parameters={"n_frames": 8, "n_ions": 2,
                    "diffusion_tensor": (0.1 * np.eye(3)).tolist(), "dt_ps": 1.0},
        initialization_spec={}, seed_semantics="pcg64",
        output_coordinate_contract={}, code_hash=_h("code")))
    plan = CalibrationPlan(
        objective="pilot", scope_hashes=(scope_h,),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",), truth_requirements={},
        split_rules={}, seed_policy={}, dev_replicate_ids=tuple(reps),
        heldout_replicate_ids=(), independence_rules={},
        selection_stopping_policy={}, frozen_analysis_fields=("estimator",),
        code_revision="f" * 40)
    plan_h = store.store(plan)
    params = dict(
        dataset_id="ds-1", plan_hash=plan_h, scope_hash=scope_h,
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",), trajectory_ids=tuple(f"traj-{r}" for r in reps),
        truth_record_hashes=(truth_h,), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(gen_h,), artifact_manifest_hashes=(),
        attempted_replicate_ids=tuple(reps))
    params.update(over)
    dataset_h = store.store(CalibrationDatasetManifest(**params))
    seeds = {rep: 100 + i for i, rep in enumerate(reps)}
    return dataset_h, seeds


def _run(store, root, dataset_h, seeds, **kwargs):
    return materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=dataset_h,
        artifact_root=root, seeds=seeds, code_revision="f" * 40, **kwargs)


def test_executes_every_declared_replicate_once(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    dataset_h, seeds = _fixture(store)
    result = _run(store, tmp_path / "artifacts", dataset_h, seeds)
    assert result["dataset_manifest_hash"] == dataset_h
    assert result["declared_replicates"] == ["rep-a", "rep-b", "rep-c"]
    assert result["attempted"] == 3
    assert result["succeeded"] == ["rep-a", "rep-b", "rep-c"]
    assert result["failed"] == []
    for rep in ("rep-a", "rep-b", "rep-c"):
        assert result["results"][rep]["artifact_status"] == "STORED"
    manifests = list((tmp_path / "store" / "calibration_replicates").glob("*.json"))
    assert len(manifests) == 3


def test_deterministic_ordering(tmp_path, monkeypatch):
    import rudeus.science.calibration_batch as batch_module
    store = CalibrationStore(tmp_path / "store")
    dataset_h, seeds = _fixture(store, reps=("rep-c", "rep-a", "rep-b"))
    calls = []
    real = batch_module.materialize_replicate

    def spy(**kwargs):
        calls.append(kwargs["task"].config["replicate_id"])
        return real(**kwargs)

    monkeypatch.setattr(batch_module, "materialize_replicate", spy)
    result = _run(store, tmp_path / "artifacts", dataset_h, seeds)
    assert calls == ["rep-a", "rep-b", "rep-c"]
    assert result["declared_replicates"] == ["rep-a", "rep-b", "rep-c"]


def test_lineage_validated_before_execution(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    with pytest.raises(ExecutionError) as failure:
        _run(store, tmp_path / "artifacts", _h("absent-dataset"), {})
    assert failure.value.failure_class.value == "INTEGRITY"
    assert not (tmp_path / "artifacts").exists()


def test_incomplete_seeds_rejected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    dataset_h, seeds = _fixture(store)
    seeds.pop("rep-c")
    with pytest.raises(ExecutionError):
        _run(store, tmp_path / "artifacts", dataset_h, seeds)
    assert list((tmp_path / "store" / "calibration_replicates").glob("*.json")) == []


def test_empty_inventory_completes_without_replicates(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    dataset_h, _ = _fixture(store, reps=())
    result = _run(store, tmp_path / "artifacts", dataset_h, {})
    assert result == {"dataset_manifest_hash": dataset_h, "declared_replicates": [],
                      "attempted": 0, "succeeded": [], "failed": [], "results": {}}


def test_partial_failure_isolation(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    dataset_h, seeds = _fixture(store, reps=("rep-ok", "rep-bad"))
    first = _run(store, tmp_path / "artifacts", dataset_h, seeds)
    assert first["succeeded"] == ["rep-bad", "rep-ok"]
    blocked = tmp_path / "blocked"
    probe_hashes = {rep: first["results"][rep]["trajectory_logical_hash"]
                    for rep in ("rep-ok", "rep-bad")}
    assert probe_hashes["rep-ok"] != probe_hashes["rep-bad"]
    (blocked / "blobs").mkdir(parents=True)
    (blocked / "blobs" / probe_hashes["rep-bad"]).write_bytes(b'{"forged": true}')
    second = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=dataset_h,
        artifact_root=blocked, seeds=seeds, code_revision="f" * 40)
    assert second["succeeded"] == ["rep-ok"]
    assert second["failed"] == ["rep-bad"]
    assert second["results"]["rep-bad"]["artifact_status"] == "FAILED"
    assert second["results"]["rep-bad"]["failure_class"] == "INTEGRITY"
    assert "replicate_manifest_hash" not in second["results"]["rep-bad"]
    assert second["results"]["rep-ok"]["artifact_status"] == "STORED"


def test_rerun_is_idempotent(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    dataset_h, seeds = _fixture(store, reps=("rep-a", "rep-b"))
    first = _run(store, tmp_path / "artifacts", dataset_h, seeds)
    second = _run(store, tmp_path / "artifacts", dataset_h, seeds)
    assert first["succeeded"] == second["succeeded"] == ["rep-a", "rep-b"]
    for rep in ("rep-a", "rep-b"):
        assert (first["results"][rep]["trajectory_logical_hash"]
                == second["results"][rep]["trajectory_logical_hash"])
        first_bytes = (tmp_path / "artifacts" / "blobs"
                       / first["results"][rep]["trajectory_logical_hash"]).read_bytes()
        assert first_bytes == (tmp_path / "artifacts" / "blobs"
                               / second["results"][rep]["trajectory_logical_hash"]).read_bytes()


def test_conflicting_artifact_still_fails_closed(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    dataset_h, seeds = _fixture(store, reps=("rep-a",))
    probe = _run(store, tmp_path / "probe", dataset_h, seeds)
    logical = probe["results"]["rep-a"]["trajectory_logical_hash"]
    (tmp_path / "blocked" / "blobs").mkdir(parents=True)
    (tmp_path / "blocked" / "blobs" / logical).write_bytes(b'{"forged": true}')
    result = _run(store, tmp_path / "blocked", dataset_h, seeds)
    assert result["failed"] == ["rep-a"]
    assert result["results"]["rep-a"]["failure_class"] == "INTEGRITY"


def test_provenance_preserved_per_replicate(tmp_path):
    from rudeus.execution.contracts import ArtifactManifest, ExecutionAttempt
    store = CalibrationStore(tmp_path / "store")
    dataset_h, seeds = _fixture(store, reps=("rep-a", "rep-b"))
    result = _run(store, tmp_path / "artifacts", dataset_h, seeds)
    attempts = {json.loads(p.read_text())["attempt_id"]: json.loads(p.read_text())
                for p in (tmp_path / "artifacts" / "attempts").glob("*.json")}
    assert len(attempts) == 2
    manifests = {json.loads(p.read_text())["logical_hash"]: json.loads(p.read_text())
                 for p in (tmp_path / "artifacts" / "trajectory_manifests").glob("*.json")}
    assert len(manifests) == 2
    for rep in ("rep-a", "rep-b"):
        entry = result["results"][rep]
        replicate = store.retrieve(CalibrationReplicateManifest,
                                   entry["replicate_manifest_hash"])
        assert replicate.replicate_id == rep
        attempt = ExecutionAttempt.from_dict(attempts[entry["attempt_id"]])
        manifest = ArtifactManifest.from_dict(
            manifests[entry["trajectory_logical_hash"]])
        assert attempt.output_manifest == {"trajectory": manifest.content_hash}
        assert manifest.producer_attempt == attempt.attempt_id
        assert manifest.logical_hash == entry["trajectory_logical_hash"]
        assert replicate.execution_attempt_hash == attempt.content_hash
        assert replicate.trajectory_artifact_hash == entry["trajectory_logical_hash"]


def test_no_qualification_emitted(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    dataset_h, seeds = _fixture(store, reps=("rep-a", "rep-b"))
    result = _run(store, tmp_path / "artifacts", dataset_h, seeds)
    assert set(result) == {"dataset_manifest_hash", "declared_replicates", "attempted",
                           "succeeded", "failed", "results"}
    texts = [json.dumps(result)]
    for directory in ("blobs", "trajectory_manifests", "attempts"):
        for path in (tmp_path / "artifacts" / directory).glob("*"):
            texts.append(path.read_bytes().decode("utf-8"))
    for path in (tmp_path / "store" / "calibration_replicates").glob("*.json"):
        texts.append(path.read_bytes().decode("utf-8"))
    for text in texts:
        for token in ("QualificationRecord", "acceptance", "coverage", "bias",
                      "qualified", '"PASS"', '"FAIL"', '"INDETERMINATE"',
                      "D_m2_per_s", "bootstrap", "effective"):
            assert token not in text


def test_no_estimator_imports():
    import sys
    recorded = set(sys.modules)
    import importlib
    importlib.import_module("rudeus.science.calibration_batch")
    introduced = set(sys.modules) - recorded
    for module in ("rudeus.science.transport", "rudeus.science.temperature",
                   "rudeus.science.statistics", "rudeus.science.claims",
                   "rudeus.mlip.p2", "rudeus.mlip.p25"):
        assert module not in introduced
