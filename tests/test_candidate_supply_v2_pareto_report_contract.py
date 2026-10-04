"""RED contract for a pure, non-authorizing Candidate Supply v2 Pareto report."""

import copy
import importlib
import json

import pytest


ARM_IDS = (
    "BASELINE_GAUSSIAN",
    "BOUNDED_GAUSSIAN_A8",
    "GAUSSIAN_LOCAL_D4",
    "GAUSSIAN_LOCAL_D8",
    "GAUSSIAN_LOCAL_D16",
)
GAUSSIAN_ATTEMPTS = "COMPLETE_GAUSSIAN_PROPOSAL_ATTEMPTS"
LOCAL_TRIALS = "PER_SITE_DIRECTION_TRIALS"
AUTHORIZATION_KEYS = (
    "scheduler_activation", "p1_eligibility", "operator_superiority",
    "automatic_promotion", "sigma_selection", "budget_selection",
    "parent_exclusion", "chemistry_exclusion", "downstream_diffusion_claim",
    "threshold_modification",
)


def _arm_record(arm_id, generated, geometry_fail, novel, useful, parents,
                effort, effort_unit, duplicate_pairs):
    exhausted = 426 - generated
    counts = {
        "requested": 432, "blocked": 0, "inapplicable": 6,
        "attempted": 426, "generated": generated, "accepted": generated,
        "exhausted": exhausted, "geometry_fail": geometry_fail,
        "novel": novel, "rediscovery": generated - novel,
        "p0_plausible": generated - geometry_fail, "useful": useful,
    }
    effort_field = ("total_direction_trials" if effort_unit == LOCAL_TRIALS
                    else "total_attempts")
    return {
        "counts": counts,
        "coverage": {
            "attempted_eligible_parents": 72,
            "generated_parent_coverage": parents,
            "novel_parent_coverage": parents,
            "useful_parent_coverage": parents,
        },
        "effort": {"unit": effort_unit, effort_field: effort},
        "diversity": {
            "parent_rediscovery_count": generated - novel,
            "within_arm_sibling_duplicate_pairs": duplicate_pairs,
            "sibling_duplicate_denominator": generated,
            "distinct_structural_outcomes": None,
            "family_coverage": {
                "UNAVAILABLE": {"generated": None, "novel": None, "useful": None},
            },
        },
        "concentration": {
            "useful": {"maximum_parent_share": 0.05, "observations": useful},
            "novel": {"maximum_parent_share": 0.04, "observations": novel},
        },
        "failure_topology": {
            "blocked_parent_p0": 0, "inapplicable": 6,
            "exhausted": exhausted, "generated_geometry_fail": geometry_fail,
            "generated_other_p0_fail": 0,
        },
        "structural_change": {
            "mobile_displacement_rms_A": None,
            "mobile_mobile_pair_distance_changes_A": None,
            "nearest_host_distance_changes_A": None,
        },
        "displacement": {"global": None},
    }


def _artifact():
    rows = (
        (426, 163, 327, 170, 57, 426, GAUSSIAN_ATTEMPTS, 178),
        (359, 0, 244, 244, 64, 1107, GAUSSIAN_ATTEMPTS, 191),
        (388, 0, 288, 288, 70, 5762, LOCAL_TRIALS, 164),
        (410, 0, 310, 310, 71, 6416, LOCAL_TRIALS, 164),
        (415, 0, 315, 315, 71, 6604, LOCAL_TRIALS, 164),
    )
    details = []
    arms = {}
    effort = {}
    diversity = {}
    concentration = {}
    failure_topology = {}
    structural_change = {}
    displacement = {}
    parent_coverage = {}
    family_coverage = {}
    for arm_id, values in zip(ARM_IDS, rows):
        generated, geometry_fail, novel, useful, parents, effort_count, unit, pairs = values
        if arm_id.startswith("GAUSSIAN_LOCAL_D"):
            operator = "mobile-ion-local-clearance-gaussian-radius"
            version = "mobile-ion-local-clearance-gaussian-radius-v1"
            budget = int(arm_id.rsplit("D", 1)[1])
        elif arm_id == "BOUNDED_GAUSSIAN_A8":
            operator, version, budget = (
                "mobile-ion-displace-clearance", "mobile-ion-displace-clearance-v1", 8,
            )
        else:
            operator, version, budget = "mobile-ion-displace", "mobile-ion-displace-v2", None
        details.append({
            "id": arm_id, "operator_name": operator,
            "operator_version": version, "budget": budget,
        })
        record = _arm_record(
            arm_id, generated, geometry_fail, novel, useful, parents,
            effort_count, unit, pairs,
        )
        arms[arm_id] = record["counts"]
        effort[arm_id] = record["effort"]
        diversity[arm_id] = record["diversity"]
        concentration[arm_id] = record["concentration"]
        failure_topology[arm_id] = record["failure_topology"]
        structural_change[arm_id] = record["structural_change"]
        displacement[arm_id] = record["displacement"]
        parent_coverage[arm_id] = record["coverage"]
        family_coverage[arm_id] = copy.deepcopy(record["diversity"]["family_coverage"])

    diagnostic_hash = "fixture-candidate-supply-v2-tournament-config-sha256"
    parent_ids = [f"obelix:fixture-{index:02d}" for index in range(72)]
    integrity = {
        key: True for key in (
            "all_arm_denominators_reconciled", "first_proposal_match",
            "local_prefix_match", "radius_consistency", "parent_p0_reproduced",
            "source_order_preserved", "source_hashes_reproduced_before_and_after",
            "authorization_all_false",
        )
    }
    authorization = {key: False for key in AUTHORIZATION_KEYS}
    transitions = {
        "D4_TO_D8": {
            "additional_direction_trials": 654, "newly_accepted": 22,
            "newly_novel": 22, "newly_useful": 22,
        },
        "D8_TO_D16": {
            "additional_direction_trials": 188, "newly_accepted": 5,
            "newly_novel": 5, "newly_useful": 5,
        },
    }
    pair_rows = [
        {"pair_id": f"fixture-pair-{index:03d}",
         "arms": {arm_id: {"status": "GENERATED"} for arm_id in ARM_IDS}}
        for index in range(432)
    ]
    metadata = {
        "configurations": list(ARM_IDS), "configuration_details": details,
        "ordered_parent_ids": parent_ids,
        "diagnostic_config_hash": diagnostic_hash,
        "novelty_matcher_version": "novelty-matcher-v2-same-cell",
    }
    return {
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "validation_state": "RECONCILED",
        "integrity": integrity,
        "panel": {
            "schema_version": "candidate-supply-v2-operator-tournament-v1",
            "authorization": authorization,
            "metadata": metadata,
            "rows": pair_rows,
            "summary": {
                "arms": arms, "effort": effort, "diversity": diversity,
                "concentration": concentration, "failure_topology": failure_topology,
                "gaussian_local_budget_response": {"arms": {}, **copy.deepcopy(transitions)},
                "minimum_image_displacement": displacement,
                "prefix_audit": {
                    "D4_TO_D8": {"mismatches": 0, "accepted_to_exhausted": 0},
                    "D8_TO_D16": {"mismatches": 0, "accepted_to_exhausted": 0},
                },
                "structural_change": structural_change,
            },
        },
        "analysis": {
            "parent_coverage": parent_coverage,
            "family_coverage": family_coverage,
            "gaussian_local_marginals": copy.deepcopy(transitions),
        },
    }


def _lane_policy():
    return {
        "EXPLORATION": {
            "minimum_parent_coverage_fraction": 0.0,
            "minimum_useful_yield_fraction": 0.0,
            "maximum_geometry_failure_fraction": 1.0,
            "maximum_exhaustion_fraction": 1.0,
            "maximum_useful_parent_share": 1.0,
            "maximum_sibling_duplicate_pairs": 1000,
            "minimum_diversity_evidence_state": "MISSING",
            "allow_missing_diversity": True,
            "allow_missing_family_coverage": True,
            "allow_missing_structural_change": True,
            "allow_missing_displacement": True,
            "allow_missing_effort": True,
            "allow_incomparable_effort": True,
            "minimum_marginal_useful_recovery": 0,
        },
        "EXPLOITATION": {
            "minimum_parent_coverage_fraction": 0.75,
            "minimum_useful_yield_fraction": 0.60,
            "maximum_geometry_failure_fraction": 0.10,
            "maximum_exhaustion_fraction": 0.20,
            "maximum_useful_parent_share": 0.30,
            "maximum_sibling_duplicate_pairs": 5,
            "minimum_diversity_evidence_state": "PARTIAL",
            "allow_missing_diversity": True,
            "allow_missing_family_coverage": True,
            "allow_missing_structural_change": True,
            "allow_missing_displacement": True,
            "allow_missing_effort": True,
            "allow_incomparable_effort": True,
            "minimum_marginal_useful_recovery": 0,
        },
    }


def _report_builder():
    module = importlib.import_module("rudeus.generation.pareto_report")
    builder = getattr(module, "build_candidate_supply_v2_pareto_report", None)
    if builder is None:
        pytest.fail(
            "missing report API: rudeus.generation.pareto_report."
            "build_candidate_supply_v2_pareto_report"
        )
    return builder


def _build_report(artifact=None, lane_policy=None):
    return _report_builder()(
        _artifact() if artifact is None else artifact,
        lane_policy=_lane_policy() if lane_policy is None else lane_policy,
    )


def _report_arm(report, arm_id):
    return next(row for row in report["pareto_evidence"]["arms"]
                if row["arm_id"] == arm_id)


def test_report_calls_committed_adapter_then_builder_once_and_keeps_exact_evidence(
    monkeypatch,
):
    from rudeus.generation import pareto_selection

    calls = []
    original_normalize = pareto_selection.normalize_candidate_supply_v2_tournament_evidence
    original_build = pareto_selection.build_candidate_supply_v2_pareto_evidence

    def normalize_spy(artifact):
        normalized = original_normalize(artifact)
        calls.append(("normalize", artifact, normalized))
        return normalized

    def build_spy(evidence, *, lane_policy):
        result = original_build(evidence, lane_policy=lane_policy)
        calls.append(("build", evidence, lane_policy, result))
        return result

    monkeypatch.setattr(
        pareto_selection, "normalize_candidate_supply_v2_tournament_evidence",
        normalize_spy,
    )
    monkeypatch.setattr(
        pareto_selection, "build_candidate_supply_v2_pareto_evidence", build_spy,
    )
    artifact = _artifact()
    policy = _lane_policy()
    report = _build_report(artifact, policy)

    assert [call[0] for call in calls] == ["normalize", "build"]
    assert calls[0][1] is artifact
    assert calls[1][1] is calls[0][2]
    assert calls[1][2] == policy
    assert report["pareto_evidence"] == calls[1][3]


def test_report_retains_source_identity_configuration_and_json_ready_contract():
    artifact = _artifact()
    report = _build_report(artifact)
    source = report["source"]
    assert report["schema_version"]
    assert report["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
    assert report["validation_state"] == "RECONCILED"
    assert source["artifact_type"] == artifact["artifact_type"]
    assert source["validation_state"] == artifact["validation_state"]
    assert source["integrity"] == artifact["integrity"]
    assert source["diagnostic_config_hash"] == artifact["panel"]["metadata"][
        "diagnostic_config_hash"
    ]
    assert source["parent_count"] == 72
    assert source["pair_count"] == 432
    assert source["arm_observation_count"] == 2160
    assert source["configured_arm_order"] == list(ARM_IDS)
    assert report["configuration"]["lane_policy"] == _lane_policy()
    json.dumps(report, sort_keys=True)


def test_report_builder_preserves_input_artifact_and_lane_policy():
    artifact = _artifact()
    policy = _lane_policy()
    before_artifact = copy.deepcopy(artifact)
    before_policy = copy.deepcopy(policy)
    _build_report(artifact, policy)
    assert artifact == before_artifact
    assert policy == before_policy


def test_report_authorization_is_all_false_and_contains_no_selection_output():
    report = _build_report()
    assert report["authorization"] == {key: False for key in AUTHORIZATION_KEYS}
    assert report["pareto_evidence"]["authorization"] == {
        key: False for key in AUTHORIZATION_KEYS
    }
    forbidden = {
        "winner", "best_arm", "best_operator", "recommended_arm",
        "recommended_operator", "recommended_budget", "optimal_budget",
        "selected_arm", "selected_budget", "ranking", "ranked_arms",
        "overall_score", "utility", "fitness",
    }
    assert not (forbidden & set(report))
    assert not (forbidden & set(report["pareto_evidence"]))
    assert report["limitations"]["observational_only"] is True
    assert report["limitations"]["scheduler_activation_authorized"] is False
    assert report["limitations"]["operator_superiority_authorized"] is False
    assert report["limitations"]["optimal_budget_authorized"] is False
    assert report["limitations"]["downstream_diffusion_claim_authorized"] is False


def test_real_aggregate_counts_survive_without_report_layer_recalculation():
    report = _build_report()
    expected = {
        "BASELINE_GAUSSIAN": (426, 163, 327, 263, 170, 57),
        "BOUNDED_GAUSSIAN_A8": (359, 0, 244, 359, 244, 64),
        "GAUSSIAN_LOCAL_D4": (388, 0, 288, 388, 288, 70),
        "GAUSSIAN_LOCAL_D8": (410, 0, 310, 410, 310, 71),
        "GAUSSIAN_LOCAL_D16": (415, 0, 315, 415, 315, 71),
    }
    for arm_id in ARM_IDS:
        arm = _report_arm(report, arm_id)
        counts = arm["counts"]
        assert (counts["requested"], counts["attempted"], counts["blocked"],
                counts["inapplicable"]) == (432, 426, 0, 6)
        generated, geometry_fail, novel, plausible, useful, parents = expected[arm_id]
        assert (counts["generated"], counts["geometry_fail"], counts["novel"],
                counts["p0_plausible"], counts["useful"]) == (
                    generated, geometry_fail, novel, plausible, useful
                )
        dimensions = arm["dimensions"]
        assert dimensions["parent_coverage"]["useful_parents"] == parents


def test_native_effort_units_and_values_survive_without_conversion():
    report = _build_report()
    expected = {
        "BASELINE_GAUSSIAN": (426, GAUSSIAN_ATTEMPTS),
        "BOUNDED_GAUSSIAN_A8": (1107, GAUSSIAN_ATTEMPTS),
        "GAUSSIAN_LOCAL_D4": (5762, LOCAL_TRIALS),
        "GAUSSIAN_LOCAL_D8": (6416, LOCAL_TRIALS),
        "GAUSSIAN_LOCAL_D16": (6604, LOCAL_TRIALS),
    }
    for arm_id, (value, unit) in expected.items():
        assert _report_arm(report, arm_id)["dimensions"]["native_effort"] == {
            "value": value, "unit": unit, "state": "OBSERVED",
        }
    comparisons = report["pareto_evidence"]["pareto_relations"][
        "BASELINE_GAUSSIAN"]["dimension_comparisons"]["GAUSSIAN_LOCAL_D4"]
    assert comparisons["native_effort"] == "INCOMPARABLE"


def test_marginals_coverage_concentration_and_diversity_limitation_survive():
    report = _build_report()
    marginals = report["pareto_evidence"]["budget_marginals"]
    assert marginals["D4_TO_D8"] == {
        "additional_direction_trials": 654, "newly_accepted": 22,
        "newly_novel": 22, "newly_useful": 22,
    }
    assert marginals["D8_TO_D16"] == {
        "additional_direction_trials": 188, "newly_accepted": 5,
        "newly_novel": 5, "newly_useful": 5,
    }
    for arm_id in ARM_IDS:
        arm = _report_arm(report, arm_id)
        assert "maximum_parent_share" in arm["dimensions"]["concentration"]["useful"]
        assert arm["dimensions"]["diversity"]["distinct_structural_outcomes"] == {
            "state": "MISSING", "value": None,
        }
    assert report["limitations"]["full_structural_diversity_available"] is False


def _set_comparable_descriptors(artifact, left, right, *, different=False):
    valid_family = {"oxide": {"generated": 426, "novel": 300, "useful": 150}}
    for arm_id in (left, right):
        artifact["panel"]["summary"]["diversity"][arm_id][
            "family_coverage"
        ] = copy.deepcopy(valid_family)
        artifact["analysis"]["family_coverage"][arm_id] = copy.deepcopy(valid_family)
        artifact["panel"]["summary"]["structural_change"][arm_id] = {
            "descriptor": 0.1 if arm_id == left or not different else 0.2,
        }
        artifact["panel"]["summary"]["minimum_image_displacement"][arm_id] = {
            "global": {"rms_A": 0.1 if arm_id == left or not different else 0.2},
        }


@pytest.mark.parametrize("section", ["structural_change", "displacement"])
def test_equal_valid_non_orderable_descriptors_are_preserved_as_equal(section):
    artifact = _artifact()
    _set_comparable_descriptors(artifact, "BASELINE_GAUSSIAN", "GAUSSIAN_LOCAL_D4")
    report = _build_report(artifact)
    comparisons = report["pareto_evidence"]["pareto_relations"][
        "BASELINE_GAUSSIAN"]["dimension_comparisons"]["GAUSSIAN_LOCAL_D4"]
    assert comparisons[section] == "EQUAL"


@pytest.mark.parametrize("section", ["structural_change", "displacement"])
def test_different_valid_non_orderable_descriptors_are_incomparable(section):
    artifact = _artifact()
    _set_comparable_descriptors(
        artifact, "BASELINE_GAUSSIAN", "GAUSSIAN_LOCAL_D4", different=True,
    )
    report = _build_report(artifact)
    relation = report["pareto_evidence"]["pareto_relations"]["BASELINE_GAUSSIAN"]
    assert relation["dimension_comparisons"]["GAUSSIAN_LOCAL_D4"][section] == "INCOMPARABLE"
    assert "GAUSSIAN_LOCAL_D4" in relation["incomparable_with"]
    assert "GAUSSIAN_LOCAL_D4" not in relation["dominates"]


@pytest.mark.parametrize("section", ["structural_change", "displacement"])
def test_missing_descriptor_prevents_dominance(section):
    artifact = _artifact()
    _set_comparable_descriptors(artifact, "BASELINE_GAUSSIAN", "GAUSSIAN_LOCAL_D4")
    summary_key = ("structural_change" if section == "structural_change"
                   else "minimum_image_displacement")
    artifact["panel"]["summary"][summary_key]["BASELINE_GAUSSIAN"] = {
        "state": "NOT_AVAILABLE", "value": None,
    }
    report = _build_report(artifact)
    relation = report["pareto_evidence"]["pareto_relations"]["BASELINE_GAUSSIAN"]
    assert "GAUSSIAN_LOCAL_D4" not in relation["dominates"]


def test_explicit_lane_policies_change_eligibility_without_changing_source():
    artifact = _artifact()
    before = copy.deepcopy(artifact)
    permissive = _lane_policy()
    restrictive = copy.deepcopy(permissive)
    restrictive["EXPLORATION"]["minimum_useful_yield_fraction"] = 0.60
    broad_report = _build_report(artifact, permissive)
    strict_report = _build_report(artifact, restrictive)
    broad = {row["arm_id"]: row["lane_eligibility"]["EXPLORATION"]
             for row in broad_report["pareto_evidence"]["arms"]}
    strict = {row["arm_id"]: row["lane_eligibility"]["EXPLORATION"]
              for row in strict_report["pareto_evidence"]["arms"]}
    assert broad["BASELINE_GAUSSIAN"] is True
    assert strict["BASELINE_GAUSSIAN"] is False
    assert strict["GAUSSIAN_LOCAL_D16"] is True
    assert artifact == before


def _reverse_mapping_order(value):
    if isinstance(value, dict):
        return {key: _reverse_mapping_order(item)
                for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [_reverse_mapping_order(item) for item in value]
    return copy.deepcopy(value)


def test_report_determinism_preserves_declared_arm_order():
    artifact = _artifact()
    reversed_mappings = _reverse_mapping_order(artifact)
    first = _build_report(artifact)
    second = _build_report(reversed_mappings)
    assert first == second
    assert first["source"]["configured_arm_order"] == list(ARM_IDS)
    assert first["pareto_evidence"]["arm_order"] == list(ARM_IDS)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


@pytest.mark.parametrize("invalid_case", [
    "validation_state", "integrity", "authorization", "malformed_adapter_input",
])
def test_invalid_tournament_source_fails_closed(invalid_case):
    artifact = _artifact()
    if invalid_case == "validation_state":
        artifact["validation_state"] = "UNRECONCILED"
    elif invalid_case == "integrity":
        artifact["integrity"]["parent_p0_reproduced"] = False
    elif invalid_case == "authorization":
        del artifact["panel"]["authorization"]["scheduler_activation"]
    else:
        del artifact["panel"]["summary"]["effort"]
    with pytest.raises((TypeError, ValueError)):
        _build_report(artifact)


def test_report_does_not_invent_absent_source_configuration_identity():
    artifact = _artifact()
    del artifact["panel"]["metadata"]["diagnostic_config_hash"]
    with pytest.raises((TypeError, ValueError)):
        _build_report(artifact)


def test_core_report_builder_is_object_based_and_does_not_write_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifact = _artifact()
    report = _build_report(artifact)
    assert report["source"]["pair_count"] == len(artifact["panel"]["rows"])
    assert list(tmp_path.iterdir()) == []
