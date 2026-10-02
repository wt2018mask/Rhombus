"""RED contract for a distinct, explicitly authorized scheduler activation."""

import copy
import hashlib
import importlib
import json

import pytest


POLICY_SCHEMA = "candidate-supply-v2-scheduler-policy-v1"
PARETO_SCHEMA = "candidate-supply-v2-pareto-report-v1"
ARM_ORDER = (
    "BASELINE_GAUSSIAN",
    "BOUNDED_GAUSSIAN_A8",
    "GAUSSIAN_LOCAL_D4",
    "GAUSSIAN_LOCAL_D8",
    "GAUSSIAN_LOCAL_D16",
)
POLICY_AUTHORIZATION = {
    "scheduler_activation_authorized": False,
    "operator_superiority_authorized": False,
    "optimal_budget_authorized": False,
    "downstream_diffusion_claim_authorized": False,
}
EXPLORATION_ALLOCATIONS = {arm: 6 for arm in ARM_ORDER}
EXPLOITATION_ALLOCATIONS = {
    "BASELINE_GAUSSIAN": 11,
    "BOUNDED_GAUSSIAN_A8": 13,
    "GAUSSIAN_LOCAL_D4": 15,
    "GAUSSIAN_LOCAL_D8": 15,
    "GAUSSIAN_LOCAL_D16": 16,
}


def _policy_fixture():
    """Small deterministic fixture in the committed pre-activation schema."""
    return {
        "schema_version": POLICY_SCHEMA,
        "artifact_type": "CANDIDATE_SUPPLY_POLICY",
        "validation_state": "PRE_ACTIVATION",
        "source": {
            "pareto_report_schema_version": PARETO_SCHEMA,
            "diagnostic_config_hash": "diagnostic-config-sha256-fixture",
            "arm_order": list(ARM_ORDER),
            "lane_eligibility": {
                lane: {arm: True for arm in ARM_ORDER}
                for lane in ("EXPLORATION", "EXPLOITATION")
            },
        },
        "configuration": {
            "total_allocation_units": 100,
            "lane_quotas": {"EXPLORATION": 30, "EXPLOITATION": 70},
            "lane_weights": {
                "EXPLORATION": {arm: 1 for arm in ARM_ORDER},
                "EXPLOITATION": {
                    "BASELINE_GAUSSIAN": 1.2018779342723005,
                    "BOUNDED_GAUSSIAN_A8": 1.4741784037558685,
                    "GAUSSIAN_LOCAL_D4": 1.6619718309859155,
                    "GAUSSIAN_LOCAL_D8": 1.727699530516432,
                    "GAUSSIAN_LOCAL_D16": 1.73943661971831,
                },
            },
        },
        "lanes": {
            "EXPLORATION": {
                "quota": 30,
                "participants": list(ARM_ORDER),
                "allocations": dict(EXPLORATION_ALLOCATIONS),
            },
            "EXPLOITATION": {
                "quota": 70,
                "participants": list(ARM_ORDER),
                "allocations": dict(EXPLOITATION_ALLOCATIONS),
            },
        },
        "authorization": dict(POLICY_AUTHORIZATION),
        "limitations": {
            "observational_only": True,
            "scheduler_activation_authorized": False,
            "operator_superiority_authorized": False,
            "optimal_budget_authorized": False,
            "downstream_diffusion_claim_authorized": False,
        },
        "evidence": {
            "budget_marginals": {
                "D4_TO_D8": {"newly_useful": 22},
                "D8_TO_D16": {"newly_useful": 5},
            },
            "pareto_evidence_limitations": {
                "distinct_structural_outcomes": "MISSING",
            },
            "report_limitations": {"observational_only": True},
            "per_arm": {
                arm: {
                    "diversity": {
                        "evidence_state": "PARTIAL",
                        "distinct_structural_outcomes": {
                            "state": "MISSING",
                            "value": None,
                        },
                    },
                    "useful_over_attempted": 0.5,
                    "useful_parent_coverage": 60,
                    "native_effort_value": 100,
                    "native_effort_unit": "PER_SITE_DIRECTION_TRIALS",
                }
                for arm in ARM_ORDER
            },
            "incomparable_effort_units_preserved": True,
        },
    }


def _policy_digest(policy):
    canonical = json.dumps(
        policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _activation_request(policy):
    return {
        "activation_requested": True,
        "source_policy_identity": {
            "schema_version": policy["schema_version"],
            "content_sha256": _policy_digest(policy),
            "source_pareto_report_schema_version": policy["source"][
                "pareto_report_schema_version"
            ],
            "source_diagnostic_config_hash": policy["source"][
                "diagnostic_config_hash"
            ],
        },
    }


def _builder():
    module = importlib.import_module(
        "rudeus.generation.candidate_supply_activation"
    )
    return module.build_candidate_supply_v2_scheduler_activation


def test_preactivation_policy_is_not_implicitly_executable():
    policy = _policy_fixture()
    assert policy["authorization"]["scheduler_activation_authorized"] is False
    with pytest.raises((TypeError, ValueError)):
        _builder()(policy)


def test_missing_activation_request_fails_closed():
    with pytest.raises((TypeError, ValueError)):
        _builder()(_policy_fixture(), activation_request=None)


def test_false_activation_request_remains_inactive():
    policy = _policy_fixture()
    request = _activation_request(policy)
    request["activation_requested"] = False
    with pytest.raises((TypeError, ValueError)):
        _builder()(policy, activation_request=request)


def test_policy_digest_mismatch_fails_closed():
    policy = _policy_fixture()
    request = _activation_request(policy)
    request["source_policy_identity"]["content_sha256"] = "0" * 64
    with pytest.raises((TypeError, ValueError)):
        _builder()(policy, activation_request=request)


@pytest.mark.parametrize("schema_change", ["missing", "unsupported"])
def test_malformed_or_missing_policy_schema_fails_closed(schema_change):
    policy = _policy_fixture()
    request = _activation_request(policy)
    if schema_change == "missing":
        del policy["schema_version"]
    else:
        policy["schema_version"] = "candidate-supply-v2-scheduler-policy-v999"
    with pytest.raises((TypeError, ValueError)):
        _builder()(policy, activation_request=request)


def test_allocation_conservation_mismatch_fails_closed():
    policy = _policy_fixture()
    policy["lanes"]["EXPLORATION"]["allocations"][ARM_ORDER[0]] -= 1
    with pytest.raises((TypeError, ValueError)):
        _builder()(policy, activation_request=_activation_request(policy))


def test_altered_arm_allocation_cannot_reuse_bound_policy_identity():
    policy = _policy_fixture()
    request = _activation_request(policy)
    policy["lanes"]["EXPLOITATION"]["allocations"][ARM_ORDER[0]] += 1
    with pytest.raises((TypeError, ValueError)):
        _builder()(policy, activation_request=request)


@pytest.mark.parametrize(
    "scientific_authorization",
    [
        "operator_superiority_authorized",
        "optimal_budget_authorized",
        "downstream_diffusion_claim_authorized",
    ],
)
def test_scientific_authorization_cannot_be_enabled_by_activation(
    scientific_authorization,
):
    policy = _policy_fixture()
    policy["authorization"][scientific_authorization] = True
    with pytest.raises((TypeError, ValueError)):
        _builder()(policy, activation_request=_activation_request(policy))


def test_explicit_activation_preserves_exact_allocations_and_limited_authority():
    policy = _policy_fixture()
    request = _activation_request(policy)
    activated = _builder()(policy, activation_request=request)

    assert activated["lanes"]["EXPLORATION"]["allocations"] == EXPLORATION_ALLOCATIONS
    assert activated["lanes"]["EXPLOITATION"]["allocations"] == EXPLOITATION_ALLOCATIONS
    assert activated["lanes"]["EXPLORATION"]["quota"] == 30
    assert activated["lanes"]["EXPLOITATION"]["quota"] == 70
    assert activated["total_allocation_units"] == 100
    assert activated["authorization"] == {
        "scheduler_activation_authorized": True,
        "operator_superiority_authorized": False,
        "optimal_budget_authorized": False,
        "downstream_diffusion_claim_authorized": False,
    }


def test_activation_is_deterministic_auditable_and_does_not_claim_a_winner():
    policy = _policy_fixture()
    request = _activation_request(policy)
    first = _builder()(policy, activation_request=request)
    second = _builder()(policy, activation_request=request)

    assert first == second
    assert first["source_policy_identity"]["content_sha256"] == _policy_digest(policy)
    assert first["source_policy_identity"]["schema_version"] == POLICY_SCHEMA
    assert first["source_policy_identity"]["source_diagnostic_config_hash"] == (
        policy["source"]["diagnostic_config_hash"]
    )
    forbidden = {
        "winner", "best_arm", "recommended_arm", "ranked_arms",
        "optimal_budget", "overall_score", "utility_score", "fitness_score",
        "timestamp", "uuid",
    }
    assert forbidden.isdisjoint(first)


def test_activation_builder_does_not_mutate_policy_or_request():
    policy = _policy_fixture()
    request = _activation_request(policy)
    before_policy = copy.deepcopy(policy)
    before_request = copy.deepcopy(request)

    _builder()(policy, activation_request=request)

    assert policy == before_policy
    assert request == before_request


def test_activation_construction_does_not_enter_generation_or_scientific_runtime(
    monkeypatch,
):
    from rudeus.generation import generator, scheduler

    def forbidden(*args, **kwargs):
        raise AssertionError("activation construction invoked runtime work")

    monkeypatch.setattr(generator, "generate_children", forbidden)
    monkeypatch.setattr(generator, "op_displace", forbidden)
    monkeypatch.setattr(scheduler, "execute_candidate_supply_v2_for_parent", forbidden)
    monkeypatch.setattr(scheduler, "execute_candidate_supply_v2_cohort", forbidden)

    policy = _policy_fixture()
    _builder()(policy, activation_request=_activation_request(policy))
