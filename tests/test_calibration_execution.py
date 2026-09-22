"""Commit A tests: calibration TaskSpec identity and lineage rejection."""
import pytest

from rudeus.execution.contracts import ExecutionError, TaskSpec
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
from rudeus.science.calibration_execution import (
    CALIBRATION_STAGE,
    build_calibration_task,
    validate_materialization_lineage,
)
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
        species_composition={"Li": 4}, n_particles=4,
        duration_ps=80.0, sampling_interval_ps=1.0, lag_steps=(1, 2),
        code_revision="f" * 40)


def _truth():
    return TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.GENERATED_MODEL,
        value={"D_m2_per_s": 1.5e-9}, code_revision="f" * 40)


def _generator():
    return GeneratorSpec(
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_name="brownian",
        generator_version="synthetic-v1", parameters={}, initialization_spec={},
        seed_semantics="pcg64", output_coordinate_contract={}, code_hash=_h("code"))


def _valid_graph(store):
    scope_h = store.store(_scope())
    truth_h = store.store(_truth())
    gen_h = store.store(_generator())
    plan = CalibrationPlan(
        objective="pilot", scope_hashes=(scope_h,),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",), truth_requirements={},
        split_rules={}, seed_policy={}, dev_replicate_ids=("rep-1",),
        heldout_replicate_ids=(), independence_rules={},
        selection_stopping_policy={}, frozen_analysis_fields=("estimator",),
        code_revision="f" * 40)
    plan_h = store.store(plan)
    dataset = CalibrationDatasetManifest(
        dataset_id="ds-1", plan_hash=plan_h, scope_hash=scope_h,
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",), trajectory_ids=("traj-1",),
        truth_record_hashes=(truth_h,), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(gen_h,), artifact_manifest_hashes=(),
        attempted_replicate_ids=("rep-1",))
    dataset_h = store.store(dataset)
    return {"plan": plan_h, "scope": scope_h, "dataset": dataset_h,
            "generator": gen_h, "truth": truth_h}


def _task(graph, **over):
    params = dict(
        plan_hash=graph["plan"], scope_hash=graph["scope"],
        dataset_manifest_hash=graph["dataset"], generator_spec_hash=graph["generator"],
        truth_record_hash=graph["truth"], replicate_id="rep-1",
        parameter_cell_id="cell-a", split_assignment=SplitAssignment.DEV,
        seed=7, code_revision="f" * 40)
    params.update(over)
    return build_calibration_task(**params)


def test_deterministic_task_identity(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _valid_graph(store)
    first, second = _task(graph), _task(graph)
    assert isinstance(first, TaskSpec)
    assert first.task_id == second.task_id
    assert first.content_hash == second.content_hash
    assert first.stage == CALIBRATION_STAGE
    assert first.protocol_hash == graph["scope"]
    assert first.candidate_id == "rep-1"
    assert first.seed == 7
    assert first.provenance is None
    validate_materialization_lineage(store, first)


def test_seed_changes_task_identity(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _valid_graph(store)
    assert _task(graph, seed=7).task_id != _task(graph, seed=8).task_id
    assert _task(graph, seed=7).content_hash != _task(graph, seed=8).content_hash


def test_wrong_plan_rejected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _valid_graph(store)
    task = _task(graph, plan_hash=_h("absent-plan"))
    with pytest.raises(ExecutionError) as failure:
        validate_materialization_lineage(store, task)
    assert failure.value.failure_class.value == "INTEGRITY"


def test_wrong_scope_rejected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _valid_graph(store)
    task = _task(graph, scope_hash=_h("foreign-scope"))
    with pytest.raises(ExecutionError) as failure:
        validate_materialization_lineage(store, task)
    assert failure.value.failure_class.value == "INTEGRITY"


def test_dataset_plan_mismatch_rejected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _valid_graph(store)
    other_scope = CalibrationScope(
        estimator="other", estimator_version="v1",
        resampling_method="m", resampling_version="2", protocol_hash=_h("p2"),
        estimand="D_self", units="m2/s",
        generator_class=CalibrationClass.CAGED_CONFINED, generator_version="gv",
        truth_type=TruthType.GENERATED_MODEL, truth_model_version="tmv",
        species_composition={"Li": 4}, n_particles=4,
        duration_ps=40.0, sampling_interval_ps=1.0, lag_steps=(1,),
        code_revision="f" * 40)
    other_scope_h = store.store(other_scope)
    other_plan = CalibrationPlan(
        objective="other", scope_hashes=(other_scope_h,),
        class_inventory=(CalibrationClass.CAGED_CONFINED,),
        parameter_cell_ids=("cell-a",), truth_requirements={},
        split_rules={}, seed_policy={}, dev_replicate_ids=("rep-1",),
        heldout_replicate_ids=(), independence_rules={},
        selection_stopping_policy={}, frozen_analysis_fields=("estimator",),
        code_revision="f" * 40)
    other_plan_h = store.store(other_plan)
    task = _task(graph, plan_hash=other_plan_h)
    with pytest.raises(ExecutionError) as failure:
        validate_materialization_lineage(store, task)
    assert failure.value.failure_class.value == "INTEGRITY"


def test_wrong_generator_rejected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _valid_graph(store)
    task = _task(graph, generator_spec_hash=_h("foreign-generator"))
    with pytest.raises(ExecutionError) as failure:
        validate_materialization_lineage(store, task)
    assert failure.value.failure_class.value == "INTEGRITY"


def test_wrong_truth_rejected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _valid_graph(store)
    task = _task(graph, truth_record_hash=_h("foreign-truth"))
    with pytest.raises(ExecutionError) as failure:
        validate_materialization_lineage(store, task)
    assert failure.value.failure_class.value == "INTEGRITY"


def test_undeclared_replicate_rejected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _valid_graph(store)
    task = _task(graph, replicate_id="rep-ghost")
    with pytest.raises(ExecutionError) as failure:
        validate_materialization_lineage(store, task)
    assert failure.value.failure_class.value == "INTEGRITY"


def test_split_mismatch_rejected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _valid_graph(store)
    task = _task(graph, split_assignment=SplitAssignment.HELD_OUT)
    with pytest.raises(ExecutionError) as failure:
        validate_materialization_lineage(store, task)
    assert failure.value.failure_class.value == "INTEGRITY"
