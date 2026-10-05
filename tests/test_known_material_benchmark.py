"""B0 contract tests: no material identities or benchmark outcomes are fixtures."""
from dataclasses import replace

import pytest

from rudeus.science.contracts import UNRESOLVED, digest
from rudeus.science.known_material_benchmark import (
    STAGES,
    BenchmarkDecision,
    KnownMaterialBenchmarkProtocol,
    build_known_material_benchmark_protocol,
)


def protocol():
    return build_known_material_benchmark_protocol()


def test_b0_protocol_is_deterministic_immutable_and_roundtrips():
    first = protocol()
    second = protocol()
    assert first == second
    assert first.content_hash == second.content_hash == digest(first.to_dict())
    assert KnownMaterialBenchmarkProtocol.from_dict(first.to_dict()) == first
    with pytest.raises(TypeError):
        first.evaluation.numeric_thresholds["sensitivity"] = 1.0


def test_blinding_hides_truth_and_identity_from_execution():
    p = protocol()
    visible = set(p.blinding.visible_fields)
    sealed = set(p.blinding.sealed_fields)
    assert {"benchmark_id", "split", "structure_hash", "benchmark_protocol_hash"} <= visible
    assert {"material_identity", "truth_class", "literature_evidence",
            "expected_stage_outcomes"} <= sealed
    assert not visible & sealed
    assert p.blinding.unblind_after_frozen_results_only


def test_held_out_is_one_shot_evaluation_not_tuning_data():
    p = protocol()
    assert p.split.dev_tuning_allowed
    assert not p.split.held_out_tuning_allowed
    assert p.split.held_out_membership_immutable
    assert not p.split.unblinded_held_out_reusable
    assert not p.split.bootstrap_resamples_independent_datasets
    with pytest.raises(ValueError, match="HELD_OUT"):
        replace(p.split, held_out_tuning_allowed=True)


def test_known_material_controls_bypass_g_without_validating_generation():
    p = protocol()
    assert p.stages == STAGES
    assert "G" not in p.stages
    assert p.ingress.bypass_generation
    assert p.ingress.first_stage == "P0"
    assert not p.ingress.generation_claims_authorized
    assert not p.ingress.production_candidate_promotion_authorized
    assert not p.production_search_authorized


def test_b0_freezes_metrics_but_not_numeric_qualification_thresholds():
    p = protocol()
    assert p.evaluation.numeric_threshold_status == UNRESOLVED
    assert dict(p.evaluation.numeric_thresholds) == {}
    assert p.evaluation.scalar_score_forbidden
    assert tuple(p.decisions) == tuple(v.value for v in BenchmarkDecision)
    with pytest.raises(ValueError, match="B0"):
        replace(p.evaluation, numeric_thresholds={"sensitivity": 0.95})


def test_every_stage_has_explicit_falsification_and_no_extrapolation():
    p = protocol()
    assert tuple(r.stage for r in p.stage_rules) == STAGES
    assert all(r.truth_dimensions for r in p.stage_rules)
    assert all(r.falsification_events for r in p.stage_rules)
    assert all(r.unsupported_policy == "UNKNOWN_OR_INDETERMINATE_NO_EXTRAPOLATION"
               for r in p.stage_rules)


def test_stage_semantics_target_external_validity_failures():
    p = {r.stage: r for r in protocol().stage_rules}
    assert "self_diffusion_state" in p["P2.5"].truth_dimensions
    assert "experimental_conductivity_as_self_diffusion_truth" in p["P3"].falsification_events
    assert "known_material_classified_novel" in p["N"].falsification_events
    assert "synthesized_material_false_unsynthesizable" in p["S"].falsification_events


def test_b0_cannot_mutate_existing_science_or_reinterpret_v1_evidence():
    p = protocol()
    assert not p.threshold_mutation_authorized
    assert not p.historical_reinterpretation_authorized
    assert not p.production_search_authorized
