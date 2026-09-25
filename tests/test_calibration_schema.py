"""G.1 schema-only tests: identity, hashing, lanes, and hash-reference policy."""
import pytest

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
        lag_steps=(1, 2, 4, 8), fit_window_ps=(20.0, 70.0),
        temperature_K=550.0, cell_geometry={"lattice": "cubic", "size_A": 10.0},
        coordinate_regime="unwrapped_simulation_cell", reference_frame="simulation_cell",
        dependence_regime="independent_increments", selection_policy="none",
        code_revision="f" * 40, generator_hash=_h("generator"),
        reference_computation_hash=None)
    params.update(over)
    return CalibrationScope(**params)


def _truth(**over):
    params = dict(
        estimand="D_self", units="m2/s", truth_type=TruthType.GENERATED_MODEL,
        value={"D_m2_per_s": 1.5e-9}, unavailable_reason=None,
        statistical_interpretation="ensemble", window_interpretation="long_time",
        cell_interpretation="bulk", generator_spec_hash=_h("genspec"),
        parameter_set_hash=_h("params"), seed=7, initialization_hash=_h("init"),
        code_revision="f" * 40, protocol_hash=_h("protocol"),
        derivation_hashes=(_h("deriv"),), approximation_notes=None)
    params.update(over)
    return TruthRecord(**params)


def test_all_six_records_construct_with_valid_data():
    scope = _scope()
    plan = CalibrationPlan(
        objective="pilot scope identity", scope_hashes=(scope.content_hash,),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,), parameter_cell_ids=("cell-a",),
        truth_requirements={"D_self": "generated_model"}, split_rules={"dev": 0.8},
        seed_policy={"scheme": "explicit_list"}, dev_replicate_ids=("rep-1",),
        heldout_replicate_ids=("rep-9",), independence_rules={"replicas": "independent_seeds"},
        selection_stopping_policy={"stopping": "fixed_duration"},
        frozen_analysis_fields=("estimator", "lag_steps"), exclusions=(),
        protocol_config_hashes={"p3": scope.protocol_hash}, code_revision="f" * 40)
    assert plan.scope_hashes[0] == scope.content_hash
    assert GeneratorSpec(
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_name="brownian",
        generator_version="synthetic-v1", parameters={"diffusion_tensor": [[1.0]]},
        initialization_spec={"positions": "origin"}, seed_semantics="pcg64_int_seed",
        output_coordinate_contract={"coordinates": "unwrapped_cartesian_A"},
        truth_definition={"derivation": "analytical"}, code_hash=_h("code"))
    assert _truth()
    assert CalibrationDatasetManifest(
        dataset_id="ds-1", plan_hash=plan.content_hash, scope_hash=scope.content_hash,
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",), trajectory_ids=("traj-1",),
        truth_record_hashes=(_truth().content_hash,), split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(_h("genspec"),), artifact_manifest_hashes=(_h("manifest"),),
        attempted_replicate_ids=("rep-1",))
    assert CalibrationReplicateManifest(
        replicate_id="rep-1", dataset_id="ds-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.DEV, independence_declaration={"seed": "independent"},
        seed=7, trajectory_artifact_hash=_h("traj"), truth_record_hash=_h("truth"),
        computational_outcome=None, scientific_outcome="COMPLETED")
    assert HeldoutEvaluationManifest(
        plan_hash=plan.content_hash, heldout_dataset_hashes=(_h("ds"),),
        estimator_spec_hash=_h("est"), resampling_spec_hash=_h("res"),
        protocol_hash=_h("protocol"), code_revision="f" * 40,
        unblinding_declaration={"state": "declared"})


def test_canonical_serialization_and_content_hash_deterministic():
    first, second = _scope(), _scope()
    assert canonical_bytes(first) == canonical_bytes(second)
    assert first.content_hash == second.content_hash
    assert TruthRecord.from_dict(_truth().to_dict()).content_hash == _truth().content_hash


def test_hash_bound_field_change_changes_hash():
    assert _scope().content_hash != _scope(duration_ps=90.0).content_hash
    assert _scope().content_hash != _scope(temperature_K=None).content_hash


def test_schema_version_is_hash_bound():
    scope = _scope()
    assert scope.to_dict()["version"] == "calibration-scope-v1"
    altered = dict(scope.to_dict())
    altered["version"] = "calibration-scope-v2"
    with pytest.raises(ValueError):
        CalibrationScope.from_dict(altered)


def test_required_hash_references_validated():
    with pytest.raises(ValueError):
        _scope(protocol_hash="not-a-hash")
    with pytest.raises(ValueError):
        _truth(generator_spec_hash="short")


def test_nonfinite_numerics_rejected_by_canonical_rules():
    with pytest.raises(ValueError):
        _scope(duration_ps=float("nan"))
    with pytest.raises(ValueError):
        _truth(value={"D_m2_per_s": float("inf")})


def test_unknown_truth_without_fake_value():
    record = _truth(value=None, unavailable_reason="empirical_reference_unavailable",
                    truth_type=TruthType.UNKNOWN)
    assert record.value is None
    assert record.truth_type == TruthType.UNKNOWN
    with pytest.raises(ValueError):
        _truth(value=None, unavailable_reason=None)
    with pytest.raises(ValueError):
        _truth(value={"D_m2_per_s": 1.0}, unavailable_reason="both_set")


def test_explicit_null_semantics_documented_and_hashed():
    scoped, unscoped = _scope(temperature_K=None), _scope(temperature_K=550.0)
    assert scoped.to_dict()["temperature_K"] is None
    assert scoped.content_hash != unscoped.content_hash
    assert "temperature_K" in scoped.to_dict()


def test_split_assignment_is_hashed_not_sidecar():
    dev = CalibrationReplicateManifest(
        replicate_id="rep-1", dataset_id="ds-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.DEV, independence_declaration={})
    held = CalibrationReplicateManifest(
        replicate_id="rep-1", dataset_id="ds-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.HELD_OUT, independence_declaration={})
    assert dev.to_dict()["split_assignment"] == "DEV"
    assert dev.content_hash != held.content_hash


def test_computational_and_scientific_lanes_stay_separate():
    record = CalibrationReplicateManifest(
        replicate_id="rep-1", dataset_id="ds-1", parameter_cell_id="cell-a",
        split_assignment=SplitAssignment.DEV, independence_declaration={},
        computational_outcome="NUMERICAL", scientific_outcome="INDETERMINATE")
    assert record.computational_outcome == "NUMERICAL"
    assert record.scientific_outcome == "INDETERMINATE"
    with pytest.raises(ValueError):
        CalibrationReplicateManifest(
            replicate_id="rep-1", dataset_id="ds-1", parameter_cell_id="cell-a",
            split_assignment=SplitAssignment.DEV, independence_declaration={},
            computational_outcome="NOT_A_FAILURE_CLASS")


def test_zero_event_hopping_is_completed_replicate():
    record = CalibrationReplicateManifest(
        replicate_id="rep-hop-0", dataset_id="ds-1", parameter_cell_id="cell-hop",
        split_assignment=SplitAssignment.DEV, independence_declaration={},
        event_info={"event_count": 0}, computational_outcome=None,
        scientific_outcome="COMPLETED")
    assert record.event_info["event_count"] == 0
    with pytest.raises(ValueError):
        CalibrationReplicateManifest(
            replicate_id="rep-hop-0", dataset_id="ds-1", parameter_cell_id="cell-a",
            split_assignment=SplitAssignment.DEV, independence_declaration={},
            event_info={"event_count": -1})


def test_large_payloads_referenced_by_hash():
    manifest = CalibrationDatasetManifest(
        dataset_id="ds-1", plan_hash=_h("plan"), scope_hash=_h("scope"),
        calibration_class=CalibrationClass.REALISTIC_TRAJECTORY,
        parameter_cell_ids=("cell-a",), trajectory_ids=("traj-1",),
        truth_record_hashes=(_h("truth"),), split_assignment=SplitAssignment.HELD_OUT,
        generator_spec_hashes=(), artifact_manifest_hashes=(_h("blob"),),
        attempted_replicate_ids=("rep-1",))
    blob = manifest.to_dict()["artifact_manifest_hashes"][0]
    assert len(blob) == 64


def test_p2_p25_references_are_hash_only():
    record = CalibrationReplicateManifest(
        replicate_id="rep-md-1", dataset_id="ds-md", parameter_cell_id="cell-md",
        split_assignment=SplitAssignment.DEV, independence_declaration={"parent": "p2_batch"},
        trajectory_artifact_hash=_h("p2traj"), truth_record_hash=_h("truth"),
        conditions={"p2_batch_id": "abc123", "early_stop_reason": "pass_at_tier_8000"})
    assert record.to_dict()["trajectory_artifact_hash"] == _h("p2traj")
    assert "p2_verdict" not in record.to_dict()["conditions"]
