"""RED contract for a non-authorizing Candidate Supply v2 policy plan."""

import copy
import importlib
from itertools import combinations

import pytest


ARM_ORDER = (
    "BASELINE_GAUSSIAN",
    "BOUNDED_GAUSSIAN_A8",
    "GAUSSIAN_LOCAL_D4",
    "GAUSSIAN_LOCAL_D8",
    "GAUSSIAN_LOCAL_D16",
)

AUTHORIZATION_FIELDS = (
    "scheduler_activation_authorized",
    "operator_superiority_authorized",
    "optimal_budget_authorized",
    "downstream_diffusion_claim_authorized",
)
PARETO_REPORT_AUTHORIZATION_FIELDS = (
    "scheduler_activation", "p1_eligibility", "operator_superiority",
    "automatic_promotion", "sigma_selection", "budget_selection",
    "parent_exclusion", "chemistry_exclusion", "downstream_diffusion_claim",
    "threshold_modification",
)

FORBIDDEN_SELECTION_FIELDS = {
    "winner", "best_arm", "best_operator", "optimal_budget", "ranked_arms",
    "overall_score", "utility_score", "fitness_score",
}


def _report():
    arm_specs = (
        ("BASELINE_GAUSSIAN", "mobile-ion-displace-v2", 170, 57,
         "COMPLETE_GAUSSIAN_PROPOSAL_ATTEMPTS", 426),
        ("BOUNDED_GAUSSIAN_A8", "mobile-ion-displace-clearance-v1", 244, 64,
         "COMPLETE_GAUSSIAN_PROPOSAL_ATTEMPTS", 1107),
        ("GAUSSIAN_LOCAL_D4", "mobile-ion-local-clearance-v1", 288, 70,
         "PER_SITE_DIRECTION_TRIALS", 5762),
        ("GAUSSIAN_LOCAL_D8", "mobile-ion-local-clearance-v1", 310, 71,
         "PER_SITE_DIRECTION_TRIALS", 6416),
        ("GAUSSIAN_LOCAL_D16", "mobile-ion-local-clearance-v1", 315, 71,
         "PER_SITE_DIRECTION_TRIALS", 6604),
    )
    arms = []
    for arm_id, version, useful, parents, effort_unit, effort in arm_specs:
        arms.append({
            "arm_id": arm_id,
            "operator_name": arm_id,
            "operator_version": version,
            "lane_eligibility": {"EXPLORATION": True, "EXPLOITATION": True},
            "dimensions": {
                "yield": {
                    "useful_count": useful,
                    "attempted_count": 426,
                    "useful_over_attempted": useful / 426,
                },
                "parent_coverage": {
                    "attempted_eligible_parents": 71,
                    "useful_parent_coverage": parents,
                },
                "native_effort": {"value": effort, "unit": effort_unit,
                                  "state": "OBSERVED"},
            },
        })
    pair_relations = {}
    for left, right in combinations(ARM_ORDER, 2):
        comparison = {
            "family_coverage": "INCOMPARABLE",
            "structural_change": "INCOMPARABLE",
            "displacement": "INCOMPARABLE",
            "distinct_structural_outcomes": "MISSING",
        }
        pair_relations.setdefault(left, {"dominates": [], "incomparable_with": []})
        pair_relations.setdefault(right, {"dominates": [], "incomparable_with": []})
        pair_relations[left]["incomparable_with"].append(right)
        pair_relations[right]["incomparable_with"].append(left)
        pair_relations[left].setdefault("dimension_comparisons", {})[right] = comparison
        pair_relations[right].setdefault("dimension_comparisons", {})[left] = comparison

    marginal_evidence = {
        "D4_TO_D8": {
            "additional_direction_trials": 654,
            "newly_accepted": 22,
            "newly_novel": 22,
            "newly_useful": 22,
            "newly_useful_parents": 1,
        },
        "D8_TO_D16": {
            "additional_direction_trials": 188,
            "newly_accepted": 5,
            "newly_novel": 5,
            "newly_useful": 5,
            "newly_useful_parents": 0,
        },
    }
    limitations = {
        "observational_only": True,
        "scheduler_activation_authorized": False,
        "operator_superiority_authorized": False,
        "optimal_budget_authorized": False,
        "downstream_diffusion_claim_authorized": False,
        "full_structural_diversity_available": False,
    }
    return {
        "schema_version": "candidate-supply-v2-pareto-report-v1",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "validation_state": "RECONCILED",
        "source": {
            "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
            "validation_state": "RECONCILED",
            "diagnostic_config_hash": "fixture-config-hash-v1",
            "parent_count": 72,
            "pair_count": 432,
            "arm_observation_count": 2160,
            "configured_arm_order": list(ARM_ORDER),
        },
        "pareto_evidence": {
            "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
            "authorization": {key: False for key in (
                "scheduler_activation", "p1_eligibility", "operator_superiority",
                "automatic_promotion", "sigma_selection", "budget_selection",
                "parent_exclusion", "chemistry_exclusion",
                "downstream_diffusion_claim", "threshold_modification",
            )},
            "arm_order": list(ARM_ORDER),
            "arms": arms,
            "pareto_relations": pair_relations,
            "nondominated_arm_ids": list(ARM_ORDER),
            "budget_marginals": marginal_evidence,
            "limitations": {"distinct_structural_outcomes": "MISSING"},
        },
        "authorization": {key: False for key in PARETO_REPORT_AUTHORIZATION_FIELDS},
        "limitations": limitations,
    }


def _policy_config():
    return {
        "total_allocation_units": 100,
        "lane_quotas": {"EXPLORATION": 30, "EXPLOITATION": 70},
        "minimum_exploration_units_per_participant": 1,
        "only_lane_eligible_arms": True,
        "allow_unallocated_reserve": False,
        "empty_lane_behavior": "ERROR",
        "rounding_rule": "LARGEST_REMAINDER_ARM_ID_ASCENDING",
        "lane_weights": {
            lane: {arm: 1 for arm in ARM_ORDER}
            for lane in ("EXPLORATION", "EXPLOITATION")
        },
        "exploitation_evidence_fields": [
            "useful_over_attempted", "useful_parent_coverage",
        ],
        "marginal_evidence_handling": "PRESERVE_DIRECTIONAL_NO_BUDGET_SELECTION",
    }


def _three_arm_unequal_evidence_case(exploitation_weights):
    report = _report()
    quota_config = _policy_config()
    quota_config["total_allocation_units"] = 100
    quota_config["lane_quotas"] = {"EXPLORATION": 60, "EXPLOITATION": 40}
    arm_data = {
        "BASELINE_GAUSSIAN": (43, 426, 7, 71),
        "BOUNDED_GAUSSIAN_A8": (340, 426, 57, 71),
        "GAUSSIAN_LOCAL_D4": (170, 426, 28, 71),
    }
    for arm in report["pareto_evidence"]["arms"]:
        arm_id = arm["arm_id"]
        if arm_id not in arm_data:
            arm["lane_eligibility"]["EXPLOITATION"] = False
            continue
        useful, attempted, coverage, eligible_parents = arm_data[arm_id]
        yield_dimensions = arm["dimensions"]["yield"]
        yield_dimensions["useful_count"] = useful
        yield_dimensions["attempted_count"] = attempted
        yield_dimensions["useful_over_attempted"] = useful / attempted
        coverage_dimensions = arm["dimensions"]["parent_coverage"]
        coverage_dimensions["useful_parent_coverage"] = coverage
        coverage_dimensions["attempted_eligible_parents"] = eligible_parents
    quota_config["lane_weights"]["EXPLOITATION"] = dict(exploitation_weights)
    return report, quota_config


def _build(report=None, policy_config=None):
    module = importlib.import_module("rudeus.generation.candidate_supply_policy")
    builder = getattr(module, "build_candidate_supply_v2_scheduler_policy")
    if policy_config is None:
        return builder(report if report is not None else _report())
    return builder(
        report if report is not None else _report(),
        policy_config=policy_config,
    )


def _assert_no_selection_fields(value):
    if isinstance(value, dict):
        assert not (FORBIDDEN_SELECTION_FIELDS & set(value))
        for child in value.values():
            _assert_no_selection_fields(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_no_selection_fields(child)


def test_policy_is_a_non_authorizing_multi_arm_two_lane_plan():
    report = _report()
    config = _policy_config()
    policy = _build(report, config)

    assert policy["artifact_type"] == "CANDIDATE_SUPPLY_POLICY"
    assert policy["source"]["pareto_report_schema_version"] == report["schema_version"]
    assert policy["source"]["diagnostic_config_hash"] == "fixture-config-hash-v1"
    assert policy["source"]["arm_order"] == list(ARM_ORDER)
    assert policy["configuration"] == config
    assert set(policy["lanes"]) == {"EXPLORATION", "EXPLOITATION"}
    for lane, quota in config["lane_quotas"].items():
        lane_policy = policy["lanes"][lane]
        assert lane_policy["quota"] == quota
        assert sum(lane_policy["allocations"].values()) == quota
        assert lane_policy["participants"]
        assert len(lane_policy["participants"]) > 1
        assert set(lane_policy["participants"]) == set(lane_policy["allocations"])
        assert all(value > 0 for value in lane_policy["allocations"].values())
    assert sum(x["quota"] for x in policy["lanes"].values()) == 100
    assert policy["authorization"] == {key: False for key in AUTHORIZATION_FIELDS}
    _assert_no_selection_fields(policy)


def test_actual_pareto_report_v1_authorization_schema_is_accepted():
    report = _report()
    assert set(report["authorization"]) == set(PARETO_REPORT_AUTHORIZATION_FIELDS)
    policy = _build(report, _policy_config())
    assert policy["authorization"] == {key: False for key in AUTHORIZATION_FIELDS}


def test_policy_is_deterministic_and_preserves_inputs_and_evidence():
    report = _report()
    config = _policy_config()
    report_before = copy.deepcopy(report)
    config_before = copy.deepcopy(config)
    first = _build(report, config)
    second = _build(report, config)

    assert first == second
    assert report == report_before
    assert config == config_before
    assert first["evidence"]["budget_marginals"] == report[
        "pareto_evidence"]["budget_marginals"]
    assert first["evidence"]["pareto_relations"] == report[
        "pareto_evidence"]["pareto_relations"]
    assert first["evidence"]["report_limitations"] == report["limitations"]
    assert first["evidence"]["per_arm"]["BASELINE_GAUSSIAN"][
        "useful_over_attempted"] == 170 / 426
    assert first["evidence"]["per_arm"]["BASELINE_GAUSSIAN"][
        "useful_parent_coverage"] == 57
    assert first["evidence"]["per_arm"]["GAUSSIAN_LOCAL_D4"][
        "native_effort_unit"] == "PER_SITE_DIRECTION_TRIALS"
    assert first["evidence"]["per_arm"]["BASELINE_GAUSSIAN"][
        "native_effort_unit"] == "COMPLETE_GAUSSIAN_PROPOSAL_ATTEMPTS"


def test_exploitation_caller_weights_are_final_relative_allocation_weights():
    arm_weights = {
        "BASELINE_GAUSSIAN": 1,
        "BOUNDED_GAUSSIAN_A8": 2,
        "GAUSSIAN_LOCAL_D4": 1,
    }
    report, config = _three_arm_unequal_evidence_case(arm_weights)
    policy = _build(report, config)

    assert policy["lanes"]["EXPLOITATION"]["allocations"] == {
        "BASELINE_GAUSSIAN": 10,
        "BOUNDED_GAUSSIAN_A8": 20,
        "GAUSSIAN_LOCAL_D4": 10,
    }


def test_exploitation_allocation_changes_directly_with_caller_weights():
    equal_weights = {
        "BASELINE_GAUSSIAN": 1,
        "BOUNDED_GAUSSIAN_A8": 1,
        "GAUSSIAN_LOCAL_D4": 1,
    }
    weighted_weights = {
        "BASELINE_GAUSSIAN": 1,
        "BOUNDED_GAUSSIAN_A8": 2,
        "GAUSSIAN_LOCAL_D4": 1,
    }
    report_a, config_a = _three_arm_unequal_evidence_case(equal_weights)
    report_b, config_b = _three_arm_unequal_evidence_case(weighted_weights)
    allocation_a = _build(report_a, config_a)["lanes"]["EXPLOITATION"]["allocations"]
    allocation_b = _build(report_b, config_b)["lanes"]["EXPLOITATION"]["allocations"]

    assert allocation_a == {
        "BASELINE_GAUSSIAN": 14,
        "BOUNDED_GAUSSIAN_A8": 13,
        "GAUSSIAN_LOCAL_D4": 13,
    }
    assert allocation_b == {
        "BASELINE_GAUSSIAN": 10,
        "BOUNDED_GAUSSIAN_A8": 20,
        "GAUSSIAN_LOCAL_D4": 10,
    }


@pytest.mark.parametrize("missing_dimension", ["yield", "parent_coverage"])
def test_exploitation_still_requires_useful_yield_and_parent_coverage(missing_dimension):
    report, config = _three_arm_unequal_evidence_case({
        "BASELINE_GAUSSIAN": 1,
        "BOUNDED_GAUSSIAN_A8": 1,
        "GAUSSIAN_LOCAL_D4": 1,
    })
    del report["pareto_evidence"]["arms"][0]["dimensions"][missing_dimension]
    with pytest.raises(ValueError, match="(?i)yield|coverage"):
        _build(report, config)


def test_returned_marginals_are_detached_from_input_report():
    report = _report()
    config = _policy_config()
    before = copy.deepcopy(report)
    policy = _build(report, config)

    assert report == before
    source_newly_useful = report["pareto_evidence"]["budget_marginals"][
        "D4_TO_D8"]["newly_useful"]
    policy["evidence"]["budget_marginals"]["D4_TO_D8"]["newly_useful"] += 1

    assert report == before
    assert report["pareto_evidence"]["budget_marginals"][
        "D4_TO_D8"]["newly_useful"] == source_newly_useful


def test_policy_preserves_and_detaches_per_arm_diversity_and_pareto_limitations():
    report = _report()
    arm = report["pareto_evidence"]["arms"][0]
    arm["dimensions"]["diversity"] = {
        "evidence_state": "PARTIAL",
        "within_arm_sibling_duplicate_pairs": 3,
        "sibling_duplicate_denominator": 8,
        "sibling_duplicate_fraction": 3 / 8,
        "distinct_structural_outcomes": {"state": "MISSING", "value": None},
    }
    report["pareto_evidence"]["limitations"] = {
        "distinct_structural_outcomes": "MISSING",
    }
    before = copy.deepcopy(report)
    policy = _build(report, _policy_config())

    assert report == before
    assert policy["evidence"]["per_arm"][arm["arm_id"]]["diversity"] == arm[
        "dimensions"]["diversity"]
    assert policy["evidence"]["pareto_evidence_limitations"] == report[
        "pareto_evidence"]["limitations"]
    assert policy["evidence"]["report_limitations"] == report["limitations"]

    policy["evidence"]["per_arm"][arm["arm_id"]]["diversity"][
        "distinct_structural_outcomes"]["state"] = "COMPLETE"
    policy["evidence"]["pareto_evidence_limitations"][
        "distinct_structural_outcomes"] = "RESOLVED"
    assert report == before
    assert report["pareto_evidence"]["arms"][0]["dimensions"]["diversity"][
        "distinct_structural_outcomes"] == {"state": "MISSING", "value": None}
    assert report["pareto_evidence"]["limitations"][
        "distinct_structural_outcomes"] == "MISSING"


def test_lane_eligibility_is_enforced_without_cross_lane_migration():
    report = _report()
    eligibility = {
        "BASELINE_GAUSSIAN": (True, False),
        "BOUNDED_GAUSSIAN_A8": (False, True),
        "GAUSSIAN_LOCAL_D4": (True, True),
        "GAUSSIAN_LOCAL_D8": (False, False),
        "GAUSSIAN_LOCAL_D16": (False, False),
    }
    for row in report["pareto_evidence"]["arms"]:
        row["lane_eligibility"]["EXPLORATION"], row["lane_eligibility"][
            "EXPLOITATION"] = eligibility[row["arm_id"]]
    policy = _build(report, _policy_config())
    assert set(policy["lanes"]["EXPLORATION"]["participants"]) == {
        "BASELINE_GAUSSIAN", "GAUSSIAN_LOCAL_D4",
    }
    assert set(policy["lanes"]["EXPLOITATION"]["participants"]) == {
        "BOUNDED_GAUSSIAN_A8", "GAUSSIAN_LOCAL_D4",
    }
    for arm_id in ("GAUSSIAN_LOCAL_D8", "GAUSSIAN_LOCAL_D16"):
        for lane in ("EXPLORATION", "EXPLOITATION"):
            assert arm_id not in policy["lanes"][lane]["participants"]
            assert policy["lanes"][lane]["allocations"].get(arm_id, 0) == 0


def test_empty_lane_fails_closed_instead_of_selecting_an_ineligible_arm():
    report = _report()
    for row in report["pareto_evidence"]["arms"]:
        row["lane_eligibility"]["EXPLORATION"] = False
    with pytest.raises(ValueError, match="(?i)empty|eligible|lane"):
        _build(report, _policy_config())


def test_policy_config_is_required_explicitly():
    with pytest.raises(TypeError):
        _build(_report())


def test_unsupported_nonempty_pareto_report_schema_fails_closed():
    report = _report()
    report["schema_version"] = "candidate-supply-v2-pareto-report-v999"
    with pytest.raises(ValueError, match="(?i)unsupported.*Pareto report schema"):
        _build(report, _policy_config())


@pytest.mark.parametrize("defect", [
    "authorization", "validation_state", "source_identity", "lane_eligibility",
])
def test_invalid_report_evidence_fails_closed(defect):
    report = _report()
    if defect == "authorization":
        report["authorization"]["operator_superiority"] = True
    elif defect == "validation_state":
        report["validation_state"] = "UNRECONCILED"
    elif defect == "source_identity":
        del report["source"]["diagnostic_config_hash"]
    else:
        del report["pareto_evidence"]["arms"][0]["lane_eligibility"]["EXPLORATION"]
    with pytest.raises((TypeError, ValueError), match="(?i)authorization|valid|source|lane"):
        _build(report, _policy_config())


@pytest.mark.parametrize("authorization_key", [
    "scheduler_activation", "operator_superiority", "budget_selection",
    "downstream_diffusion_claim",
])
def test_true_pareto_report_authorization_fails_closed(authorization_key):
    report = _report()
    report["authorization"][authorization_key] = True
    with pytest.raises(ValueError, match="(?i)authorization"):
        _build(report, _policy_config())


def test_missing_pareto_report_authorization_key_fails_closed():
    report = _report()
    del report["authorization"]["budget_selection"]
    with pytest.raises(ValueError, match="(?i)authorization keys missing.*budget_selection"):
        _build(report, _policy_config())


@pytest.mark.parametrize("defect", [
    "quota_conservation", "negative_quota", "impossible_minimum",
    "novelty_only_exploitation",
])
def test_invalid_or_underspecified_policy_configuration_fails_closed(defect):
    config = _policy_config()
    if defect == "quota_conservation":
        config["lane_quotas"]["EXPLOITATION"] = 69
    elif defect == "negative_quota":
        config["lane_quotas"]["EXPLORATION"] = -1
    elif defect == "impossible_minimum":
        config["minimum_exploration_units_per_participant"] = 7
    else:
        config["exploitation_evidence_fields"] = ["novel_over_attempted"]
    with pytest.raises((TypeError, ValueError), match="(?i)quota|negative|minimum|useful|coverage|evidence"):
        _build(_report(), config)
