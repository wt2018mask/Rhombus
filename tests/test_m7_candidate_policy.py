import pytest

from rudeus.generation.m7_candidate_policy import (
    M6B_OBSERVATION, decide_candidate_supply, operator_rng_identity,
)


def _evidence():
    return {
        "BASELINE_GAUSSIAN": {
            "generated": 24, "geometry_failures": 9, "exhausted": 0,
            "novel": 17, "useful": 8,
            "effort": {"value": 24, "unit": "baseline_proposal_attempts"},
        },
        "GAUSSIAN_LOCAL_D8": {
            "generated": 24, "geometry_failures": 0, "exhausted": 0,
            "novel": 16, "useful": 16,
            "effort": {"value": 100, "unit": "local_direction_trials"},
        },
    }


def _decision(**extra):
    args = dict(parent_context={"parent_id": "source:one", "target_species": "Na",
                                "parent_p0_neutrality_ok": True, "family": "oxide"},
                evidence=_evidence(), sigma_policy={"Na": 0.2},
                base_seed=44, policy_identity="m7-diagnostic", lane="EXPLORATION")
    args.update(extra)
    return decide_candidate_supply(**args)


def test_portfolio_is_deterministic_species_neutral_and_default_off():
    first = _decision()
    assert first == _decision()
    assert first["enabled"] is False
    assert first["status"] == "DIAGNOSTIC_PROPOSAL_ONLY"
    assert first["portfolio"] == ["BASELINE_GAUSSIAN", "GAUSSIAN_LOCAL_D8"]
    assert set(first["pareto_front"]) == set(first["portfolio"])
    assert first["sigma_policy"]["target_species"] == "Na"
    assert first["effort_comparison"] == "UNSUPPORTED_DIFFERENT_OPERATOR_UNITS"
    assert all(value is False for value in first["authorization"].values())
    assert operator_rng_identity("source:one", 44, "BASELINE_GAUSSIAN", "p") != \
        operator_rng_identity("source:one", 44, "GAUSSIAN_LOCAL_D8", "p")
    assert M6B_OBSERVATION["novel"] == {"BASELINE_GAUSSIAN": 17, "GAUSSIAN_LOCAL_D8": 16}


def test_exploitation_uses_useful_and_geometry_not_novelty_alone():
    decision = _decision(lane="EXPLOITATION")
    assert decision["selected_arm"] == "GAUSSIAN_LOCAL_D8"
    assert decision["evidence"]["BASELINE_GAUSSIAN"]["novel"] == 17


def test_parent_block_and_activation_refusal():
    blocked = _decision(parent_context={"parent_id": "source:one", "target_species": "Na",
                                        "parent_p0_neutrality_ok": False})
    assert blocked["status"] == "BLOCKED_BY_PARENT_P0"
    assert blocked["selected_arm"] is None
    with pytest.raises(ValueError, match="default-off"):
        _decision(enabled=True)
    with pytest.raises(ValueError, match="sigma"):
        _decision(sigma_policy={"Li": 0.35})
