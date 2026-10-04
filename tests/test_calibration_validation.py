"""G.1 validator tests: integrity/provenance over real stored records."""
import json

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
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import (
    INCOMPLETE,
    INVALID,
    VALID,
    validate_dataset,
    validate_graph,
    validate_heldout_evaluation,
    validate_plan,
    validate_replicates,
)
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


def _graph(store, *, split=SplitAssignment.DEV, rep="rep-1", traj=None,
           truth_hash=None, dataset_id="ds-1", cell="cell-a"):
    scope_h = store.store(_scope())
    truth_h = store.store(_truth()) if truth_hash is None else truth_hash
    plan = CalibrationPlan(
        objective="pilot", scope_hashes=(scope_h,),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=(cell,), truth_requirements={},
        split_rules={}, seed_policy={}, dev_replicate_ids=(rep,) if split == SplitAssignment.DEV else (),
        heldout_replicate_ids=(rep,) if split == SplitAssignment.HELD_OUT else (),
        independence_rules={}, selection_stopping_policy={},
        frozen_analysis_fields=("estimator",), code_revision="f" * 40)
    plan_h = store.store(plan)
    dataset = CalibrationDatasetManifest(
        dataset_id=dataset_id, plan_hash=plan_h, scope_hash=scope_h,
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=(cell,), trajectory_ids=("traj-1",),
        truth_record_hashes=(truth_h,), split_assignment=split,
        generator_spec_hashes=(), artifact_manifest_hashes=(),
        attempted_replicate_ids=(rep,))
    dataset_h = store.store(dataset)
    replicate = CalibrationReplicateManifest(
        replicate_id=rep, dataset_id=dataset_id, parameter_cell_id=cell,
        split_assignment=split, independence_declaration={}, seed=7,
        trajectory_artifact_hash=traj or _h("traj", rep),
        truth_record_hash=truth_h, scientific_outcome="COMPLETED")
    replicate_h = store.store(replicate)
    return {"plan": plan_h, "dataset": dataset_h, "replicate": replicate_h,
            "scope": scope_h, "truth": truth_h}


def _codes(result):
    return [v["code"] for v in result.violations]


def test_valid_graph_validates(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    result = validate_graph(store, graph["plan"], (graph["dataset"],),
                            (graph["replicate"],))
    assert result.status == VALID
    assert result.violations == ()


def test_wrong_plan_hash_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    other = CalibrationPlan(
        objective="other", scope_hashes=(graph["scope"],),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",), truth_requirements={},
        split_rules={}, seed_policy={}, dev_replicate_ids=(),
        heldout_replicate_ids=(), independence_rules={},
        selection_stopping_policy={}, frozen_analysis_fields=("estimator",),
        code_revision="f" * 40)
    other_h = store.store(other)
    result = validate_graph(store, other_h, (graph["dataset"],),
                            (graph["replicate"],))
    assert result.status == INVALID
    assert "plan_hash_mismatch" in _codes(result)


def test_wrong_scope_hash_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    dataset = store.retrieve(CalibrationDatasetManifest, graph["dataset"])
    from dataclasses import replace
    tampered = replace(dataset, scope_hash=_h("foreign-scope"))
    tampered_h = store.store(tampered)
    result = validate_dataset(store, tampered_h,
                              plan=store.retrieve(CalibrationPlan, graph["plan"]))
    assert result.status == INVALID
    assert "scope_not_in_plan" in _codes(result)


def test_missing_referenced_record_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    result = validate_plan(store, graph["plan"])
    assert result.status == VALID
    ghost_scope = _h("ghost")
    plan = store.retrieve(CalibrationPlan, graph["plan"])
    from dataclasses import replace
    broken = replace(plan, scope_hashes=(ghost_scope,))
    broken_h = store.store(broken)
    result = validate_plan(store, broken_h)
    assert result.status == INCOMPLETE
    assert "unresolved_reference" in _codes(result)


def test_corrupted_bytes_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    path = (tmp_path / "store" / "calibration_datasets"
            / f"{graph['dataset']}.json")
    payload = json.loads(path.read_text())
    payload["dataset_id"] = "rewritten"
    path.write_text(json.dumps(payload))
    result = validate_dataset(store, graph["dataset"])
    assert result.status == INVALID
    assert "content_integrity_mismatch" in _codes(result)


def test_split_mismatch_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    dataset = store.retrieve(CalibrationDatasetManifest, graph["dataset"])
    from dataclasses import replace
    flipped = replace(dataset, split_assignment=SplitAssignment.HELD_OUT)
    flipped_h = store.store(flipped)
    result = validate_replicates(store, (graph["replicate"],),
                                 datasets=(flipped_h,))
    assert result.status == INVALID
    assert "split_mismatch" in _codes(result)


def test_same_replicate_in_both_splits_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    dev = _graph(store, split=SplitAssignment.DEV, rep="rep-x",
                 dataset_id="ds-dev")
    held = _graph(store, split=SplitAssignment.HELD_OUT, rep="rep-x",
                  dataset_id="ds-held", traj=_h("other-traj"))
    result = validate_graph(store, dev["plan"],
                            (dev["dataset"], held["dataset"]),
                            (dev["replicate"], held["replicate"]))
    codes = _codes(result)
    assert result.status == INVALID
    assert "heldout_contamination" in codes


def test_same_trajectory_in_both_splits_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    shared = _h("shared-traj")
    dev = _graph(store, split=SplitAssignment.DEV, rep="rep-a",
                 dataset_id="ds-dev", traj=shared)
    held = _graph(store, split=SplitAssignment.HELD_OUT, rep="rep-b",
                  dataset_id="ds-held", traj=shared)
    result = validate_replicates(store, (dev["replicate"], held["replicate"]))
    assert result.status == INVALID
    assert "trajectory_in_both_splits" in _codes(result)


def test_duplicate_replicate_id_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    first = CalibrationReplicateManifest(
        replicate_id="rep-dup", dataset_id="ds-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.DEV, independence_declaration={}, seed=1)
    second = CalibrationReplicateManifest(
        replicate_id="rep-dup", dataset_id="ds-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.DEV, independence_declaration={}, seed=2)
    assert first.content_hash != second.content_hash
    first_h, second_h = store.store(first), store.store(second)
    result = validate_replicates(store, (first_h, second_h))
    assert result.status == INVALID
    assert "conflicting_replicate_definition" in _codes(result)


def test_conflicting_manifest_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    other_truth = TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.GENERATED_MODEL,
        value={"D_m2_per_s": 9.9e-9}, code_revision="f" * 40)
    other_truth_h = store.store(other_truth)
    alt = _graph(store, split=SplitAssignment.HELD_OUT, rep="rep-alt",
                 dataset_id="ds-held", truth_hash=other_truth_h)
    result = validate_graph(store, graph["plan"],
                            (graph["dataset"], alt["dataset"]),
                            (graph["replicate"], alt["replicate"]))
    assert result.status == INVALID
    assert "truth_substituted_across_splits" in _codes(result)


def test_heldout_contamination_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    dev = _graph(store, split=SplitAssignment.DEV, rep="rep-a",
                 dataset_id="same-ds")
    held = _graph(store, split=SplitAssignment.HELD_OUT, rep="rep-b",
                  dataset_id="same-ds")
    result = validate_graph(store, dev["plan"],
                            (dev["dataset"], held["dataset"]),
                            (dev["replicate"], held["replicate"]))
    assert result.status == INVALID
    assert "heldout_contamination" in _codes(result)


def test_undeclared_heldout_content_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    extra = CalibrationReplicateManifest(
        replicate_id="rep-ghost", dataset_id="ds-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.DEV, independence_declaration={})
    extra_h = store.store(extra)
    result = validate_replicates(store, (graph["replicate"], extra_h),
                                 datasets=(graph["dataset"],),
                                 plan_hash=graph["plan"])
    assert result.status == INVALID
    assert "undeclared_replicate" in _codes(result)


def test_unblinding_state_handled(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    evaluation = HeldoutEvaluationManifest(
        plan_hash=graph["plan"], heldout_dataset_hashes=(graph["dataset"],),
        estimator_spec_hash=_h("est"), resampling_spec_hash=_h("res"),
        protocol_hash=_h("protocol"), code_revision="f" * 40,
        unblinding_declaration=None)
    evaluation_h = store.store(evaluation)
    result = validate_heldout_evaluation(store, evaluation_h,
                                         plan_hash=graph["plan"])
    assert result.status == INCOMPLETE
    assert "unblinding_undeclared" in _codes(result)
    declared = HeldoutEvaluationManifest(
        plan_hash=graph["plan"], heldout_dataset_hashes=(graph["dataset"],),
        estimator_spec_hash=_h("est"), resampling_spec_hash=_h("res"),
        protocol_hash=_h("protocol"), code_revision="f" * 40,
        unblinding_declaration={"state": "declared"})
    declared_h = store.store(declared)
    result = validate_heldout_evaluation(store, declared_h,
                                         plan_hash=graph["plan"])
    assert result.status == VALID
    assert any("temporal order" in note for note in result.notes)


def test_post_freeze_mutation_detected(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    assert validate_graph(store, graph["plan"], (graph["dataset"],),
                          (graph["replicate"],)).status == VALID
    path = tmp_path / "store" / "calibration_plans" / f"{graph['plan']}.json"
    payload = json.loads(path.read_text())
    payload["objective"] = "mutated after freeze"
    path.write_text(json.dumps(payload))
    result = validate_graph(store, graph["plan"], (graph["dataset"],),
                            (graph["replicate"],))
    assert result.status == INVALID


def test_missing_evidence_is_incomplete_not_fail(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    result = validate_plan(store, _h("absent"))
    assert result.status == INCOMPLETE
    assert "unresolved_reference" in _codes(result)
    assert "FAIL" not in result.status


def test_validator_does_not_mutate_bytes(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    before = {}
    for directory in ("calibration_plans", "calibration_datasets",
                      "calibration_replicates", "calibration_scopes",
                      "truth_records"):
        for path in (tmp_path / "store" / directory).glob("*.json"):
            before[str(path)] = path.read_bytes()
    validate_graph(store, graph["plan"], (graph["dataset"],),
                   (graph["replicate"],))
    after = {str(p): p.read_bytes()
             for d in ("calibration_plans", "calibration_datasets",
                       "calibration_replicates", "calibration_scopes",
                       "truth_records")
             for p in (tmp_path / "store" / d).glob("*.json")}
    assert before == after


def test_validator_leaves_p2_p25_untouched(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    marker = tmp_path / "p2artifact.json"
    marker.write_bytes(b'{"p2": true}')
    _graph(store)
    validate_graph(store, _h("absent"), (), ())
    assert marker.read_bytes() == b'{"p2": true}'


def test_deterministic_output(tmp_path):
    store = CalibrationStore(tmp_path / "store")
    graph = _graph(store)
    first = validate_graph(store, graph["plan"], (graph["dataset"],),
                           (graph["replicate"],))
    second = validate_graph(store, graph["plan"], (graph["dataset"],),
                            (graph["replicate"],))
    assert first == second
    assert first.status == VALID
