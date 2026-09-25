"""G.1 storage-only tests: append-only content-addressed persistence."""
import json

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration import (
    CalibrationClass,
    CalibrationDatasetManifest,
    CalibrationPlan,
    CalibrationReplicateManifest,
    CalibrationScope,
    GeneratorSpec,
    HeldoutEvaluationManifest,
    SplitAssignment,
    TruthRecord,
    TruthType,
)
from rudeus.science.calibration_store import CalibrationStore, class_for, directory_for
from rudeus.science.contracts import canonical_bytes, digest


def _h(*parts):
    return digest({"test": list(parts)})


def _scope(**over):
    params = dict(
        estimator="free_intercept_OLS_MSD", estimator_version="p3-integrated-v1-unqualified",
        resampling_method="joint_contiguous_full_origin_blocks-v2-diagnostic",
        resampling_version="2", protocol_hash=_h("protocol"),
        estimand="D_self", units="m2/s",
        generator_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_version="synthetic-v1",
        truth_type=TruthType.GENERATED_MODEL, truth_model_version="brownian-analytical-v1",
        species_composition={"Li": 4}, n_particles=4,
        duration_ps=80.0, sampling_interval_ps=1.0,
        lag_steps=(1, 2, 4, 8), code_revision="f" * 40)
    params.update(over)
    return CalibrationScope(**params)


def _plan(scope_hash=None, **over):
    params = dict(
        objective="pilot", scope_hashes=(scope_hash or _h("scope"),),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",), truth_requirements={},
        split_rules={}, seed_policy={}, dev_replicate_ids=("rep-1",),
        heldout_replicate_ids=("rep-9",), independence_rules={},
        selection_stopping_policy={}, frozen_analysis_fields=("estimator",),
        code_revision="f" * 40)
    params.update(over)
    return CalibrationPlan(**params)


def _all_records():
    scope = _scope()
    plan = _plan(scope.content_hash)
    truth = TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.GENERATED_MODEL,
        value={"D_m2_per_s": 1.5e-9}, code_revision="f" * 40)
    return [
        plan,
        GeneratorSpec(
            calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_name="brownian",
            generator_version="synthetic-v1", parameters={}, initialization_spec={},
            seed_semantics="pcg64", output_coordinate_contract={}, code_hash=_h("code")),
        truth,
        CalibrationDatasetManifest(
            dataset_id="ds-1", plan_hash=plan.content_hash, scope_hash=scope.content_hash,
            calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
            parameter_cell_ids=("cell-a",), trajectory_ids=("traj-1",),
            truth_record_hashes=(truth.content_hash,), split_assignment=SplitAssignment.DEV,
            generator_spec_hashes=(), artifact_manifest_hashes=(),
            attempted_replicate_ids=("rep-1",)),
        CalibrationReplicateManifest(
            replicate_id="rep-1", dataset_id="ds-1", parameter_cell_id="cell-a",
            split_assignment=SplitAssignment.DEV, independence_declaration={},
            trajectory_artifact_hash=_h("traj"), truth_record_hash=truth.content_hash,
            event_info={"event_count": 0}, scientific_outcome="COMPLETED"),
        HeldoutEvaluationManifest(
            plan_hash=plan.content_hash, heldout_dataset_hashes=(_h("ds"),),
            estimator_spec_hash=_h("est"), resampling_spec_hash=_h("res"),
            protocol_hash=_h("protocol"), code_revision="f" * 40),
        scope,
    ]


def test_store_and_retrieve_plan_by_hash(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    plan = _plan()
    identity = store.store(plan)
    assert identity == plan.content_hash
    retrieved = store.retrieve(CalibrationPlan, identity)
    assert retrieved.content_hash == identity
    assert canonical_bytes(retrieved) == canonical_bytes(plan)


def test_repeated_storage_is_idempotent_without_rewrite(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    plan = _plan()
    first, second = store.store(plan), store.store(plan)
    assert first == second == plan.content_hash
    path = tmp_path / "store" / "calibration_plans" / f"{plan.content_hash}.json"
    assert path.read_bytes() == canonical_bytes(plan)


def test_same_identity_different_bytes_fails_closed(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    plan = _plan()
    identity = store.store(plan)
    path = tmp_path / "store" / "calibration_plans" / f"{identity}.json"
    with pytest.raises(ExecutionError):
        from rudeus.science.evidence import append_file
        append_file(path, b'{"tampered": true}')


def test_tampered_bytes_fail_verification(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    plan = _plan()
    identity = store.store(plan)
    path = tmp_path / "store" / "calibration_plans" / f"{identity}.json"
    payload = json.loads(path.read_text())
    payload["objective"] = "rewritten objective"
    path.write_text(json.dumps(payload))
    with pytest.raises(ExecutionError):
        store.retrieve(CalibrationPlan, identity)


def test_wrong_record_type_fails_verification(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    plan = _plan()
    identity = store.store(plan)
    with pytest.raises(ExecutionError):
        store.retrieve(TruthRecord, identity)


def test_missing_record_fails_cleanly(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    with pytest.raises(ExecutionError):
        store.retrieve(CalibrationPlan, _h("absent"))


def test_schema_version_mismatch_fails_cleanly(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    plan = _plan()
    identity = store.store(plan)
    path = tmp_path / "store" / "calibration_plans" / f"{identity}.json"
    payload = json.loads(path.read_text())
    payload["version"] = "calibration-plan-v999"
    path.write_text(json.dumps(payload))
    with pytest.raises(ExecutionError):
        store.retrieve(CalibrationPlan, identity)


def test_all_record_types_round_trip(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    for record in _all_records():
        identity = store.store(record)
        retrieved = store.retrieve(type(record), identity)
        assert retrieved.content_hash == identity
        assert canonical_bytes(retrieved) == canonical_bytes(record)


def test_storage_preserves_scientific_content(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    plan = _plan()
    before = canonical_bytes(plan)
    identity = store.store(plan)
    retrieved = store.retrieve(CalibrationPlan, identity)
    assert canonical_bytes(retrieved) == before
    assert retrieved.content_hash == plan.content_hash


def test_p2_p25_references_remain_hashes(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    record = CalibrationReplicateManifest(
        replicate_id="rep-md", dataset_id="ds-md", parameter_cell_id="cell-md",
        split_assignment=SplitAssignment.DEV, independence_declaration={},
        trajectory_artifact_hash=_h("p2traj"), truth_record_hash=_h("truth"),
        conditions={"p2_batch_id": "abc123"})
    retrieved = store.retrieve(
        CalibrationReplicateManifest, store.store(record))
    assert retrieved.to_dict()["trajectory_artifact_hash"] == _h("p2traj")
    assert retrieved.content_hash == record.content_hash


def test_storage_failures_are_infrastructure_not_scientific(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    with pytest.raises(ExecutionError) as failure:
        store.retrieve(CalibrationPlan, _h("absent"))
    assert failure.value.failure_class.value == "INTEGRITY"
    assert not hasattr(failure.value, "scientific_verdict")


def test_type_binding_rejects_unknown_types():
    with pytest.raises(ValueError):
        directory_for(object)
    with pytest.raises(ValueError):
        class_for("no_such_directory")
    assert directory_for(CalibrationPlan) == "calibration_plans"
    assert class_for("truth_records") is TruthRecord
