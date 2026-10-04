"""RED contract for analytical Candidate Supply v2 Pareto evidence.

The proposed public API is
``rudeus.generation.pareto_selection.build_candidate_supply_v2_pareto_evidence``.
It consumes a reconciled, observational tournament evidence projection and an
explicit lane policy. It does not generate candidates or authorize science.
These small fixtures are not production thresholds or a tournament replay.
"""

import copy
import importlib
import json
import math

import pytest


GAUSSIAN_ATTEMPTS = "COMPLETE_GAUSSIAN_PROPOSAL_ATTEMPTS"
LOCAL_TRIALS = "PER_SITE_DIRECTION_TRIALS"
REAL_ARMS = (
    "BASELINE_GAUSSIAN",
    "BOUNDED_GAUSSIAN_A8",
    "GAUSSIAN_LOCAL_D4",
    "GAUSSIAN_LOCAL_D8",
    "GAUSSIAN_LOCAL_D16",
)
INTEGRITY_FLAGS = (
    "all_arm_denominators_reconciled",
    "first_proposal_match",
    "local_prefix_match",
    "radius_consistency",
    "parent_p0_reproduced",
    "source_order_preserved",
    "source_hashes_reproduced_before_and_after",
    "authorization_all_false",
)
FORBIDDEN_SELECTION_KEYS = {
    "score", "overall_score", "utility", "fitness", "rank_score",
    "winner", "best_operator", "best_arm", "optimal_budget",
    "recommended_arm", "recommended_budget",
}
FORBIDDEN_DOWNSTREAM_KEYS = {
    "p1_keep", "p2_pass", "p25_diffusive", "p3_authorized",
    "scheduler_activation_authorized", "p1_eligibility_authorized",
    "downstream_scientific_claims_authorized",
}


def _arm(
    arm_id, *, requested=10, blocked=0, inapplicable=0, exhausted=0,
    useful=6, novel=7, geometry_fail=0, useful_parents=3,
    attempted_parents=4, useful_parent_share=None, sibling_pairs=0,
    distinct_outcomes="AUTO", effort=100, effort_unit=GAUSSIAN_ATTEMPTS,
):
    attempted = requested - blocked - inapplicable
    generated = attempted - exhausted
    assert 0 <= useful <= novel <= generated
    assert 0 <= geometry_fail <= generated
    assert 0 <= useful_parents <= attempted_parents
    assert useful_parents <= useful
    if useful_parent_share is None:
        useful_parent_share = math.ceil(useful / useful_parents) / useful if useful else 0.0
    assert 0.0 <= useful_parent_share <= 1.0
    if distinct_outcomes == "AUTO":
        distinct_outcomes = min(generated, 8)
    if arm_id.startswith("GAUSSIAN_LOCAL_D"):
        operator, version = (
            "mobile-ion-local-clearance-gaussian-radius",
            "mobile-ion-local-clearance-gaussian-radius-v1",
        )
        budget = int(arm_id.rsplit("D", 1)[1])
    elif arm_id == "BOUNDED_GAUSSIAN_A8":
        operator, version, budget = (
            "mobile-ion-displace-clearance", "mobile-ion-displace-clearance-v1", 8,
        )
    elif arm_id == "BASELINE_GAUSSIAN":
        operator, version, budget = "mobile-ion-displace", "mobile-ion-displace-v2", None
    else:
        operator, version, budget = "fixture-operator", "fixture-v1", None
    return {
        "id": arm_id,
        "operator_name": operator,
        "operator_version": version,
        "budget": budget,
        "counts": {
            "requested": requested, "blocked": blocked,
            "inapplicable": inapplicable, "attempted": attempted,
            "generated": generated,
            "accepted": 0 if arm_id == "BASELINE_GAUSSIAN" else generated,
            "exhausted": exhausted, "geometry_fail": geometry_fail,
            "novel": novel, "rediscovery": generated - novel,
            "p0_plausible": generated - geometry_fail, "useful": useful,
            "generated_over_attempted": generated / attempted if attempted else 0.0,
            "novel_over_attempted": novel / attempted if attempted else 0.0,
            "novel_over_generated": novel / generated if generated else 0.0,
            "useful_over_attempted": useful / attempted if attempted else 0.0,
            "useful_over_generated": useful / generated if generated else 0.0,
        },
        "coverage": {
            "attempted_eligible_parents": attempted_parents,
            "generated_parent_coverage": min(attempted_parents, generated),
            "novel_parent_coverage": min(attempted_parents, novel),
            "useful_parent_coverage": useful_parents,
        },
        "concentration": {
            "useful": {
                "observations": useful,
                "maximum_parent_share": useful_parent_share,
                "parents_for_50_percent": None,
                "parents_for_80_percent": None,
            },
            "novel": {
                "observations": novel,
                "maximum_parent_share": (
                    math.ceil(novel / min(attempted_parents, novel)) / novel
                    if novel else 0.0
                ),
            },
        },
        "diversity": {
            "parent_rediscovery_count": generated - novel,
            "within_arm_sibling_duplicate_pairs": sibling_pairs,
            "sibling_duplicate_denominator": generated,
            "distinct_structural_outcomes": distinct_outcomes,
            "family_coverage": {
                "oxide": {"generated": generated, "novel": novel, "useful": useful},
                "UNAVAILABLE": {"generated": 0, "novel": 0, "useful": 0},
            },
        },
        "effort": {
            "unit": effort_unit,
            ("total_direction_trials" if effort_unit == LOCAL_TRIALS else "total_attempts"): effort,
        },
        "structural_change": {
            "mobile_displacement_rms_A": {"mean_A": 0.30},
            "mobile_mobile_pair_distance_changes_A": {"median_A": 0.10},
            "nearest_host_distance_changes_A": {"median_A": 0.05},
        },
        "minimum_image_displacement": {
            "global": {"mobile_site_count": generated, "rms_A": 0.30,
                       "mean_over_sigma": 1.0, "rms_over_sigma": 1.0},
        },
        "failure_topology": {
            "blocked_parent_p0": blocked, "inapplicable": inapplicable,
            "exhausted": exhausted, "generated_geometry_fail": geometry_fail,
            "generated_other_p0_fail": 0,
        },
    }


def _policy():
    # Test values define two *explicit* hypothetical policies, not project gates.
    return {
        "EXPLORATION": {
            "minimum_parent_coverage_fraction": 0.25,
            "minimum_useful_yield_fraction": 0.0,
            "maximum_geometry_failure_fraction": 0.20,
            "maximum_exhaustion_fraction": 0.50,
            "maximum_useful_parent_share": 0.70,
            "maximum_sibling_duplicate_pairs": 0,
            "minimum_diversity_evidence_state": "PARTIAL",
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


def _evidence(arms):
    """Compact projection of the tournament's existing aggregate sections."""
    order = [arm["id"] for arm in arms]
    assert len(order) == len(set(order))
    local_arms = {arm["id"]: arm for arm in arms if arm["id"].startswith("GAUSSIAN_LOCAL_D")}
    prefix = {}
    for smaller, larger in (("GAUSSIAN_LOCAL_D4", "GAUSSIAN_LOCAL_D8"),
                            ("GAUSSIAN_LOCAL_D8", "GAUSSIAN_LOCAL_D16")):
        if smaller in local_arms and larger in local_arms:
            prefix[f"{smaller.rsplit('_', 1)[1]}_TO_{larger.rsplit('_', 1)[1]}"] = {
                "mismatches": 0, "accepted_to_exhausted": 0,
            }
    return {
        "schema_version": "candidate-supply-v2-operator-tournament-v1",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "validation_state": "RECONCILED",
        "integrity": {flag: True for flag in INTEGRITY_FLAGS},
        "authorization": {
            "scheduler_activation": False, "p1_eligibility": False,
            "operator_superiority": False, "automatic_promotion": False,
            "sigma_selection": False, "budget_selection": False,
            "parent_exclusion": False, "chemistry_exclusion": False,
            "downstream_diffusion_claim": False, "threshold_modification": False,
        },
        "metadata": {
            "configurations": order,
            "configuration_details": [
                {key: arm[key] for key in ("id", "operator_name", "operator_version", "budget")}
                for arm in arms
            ],
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
            "ordered_parent_ids": [
                f"fixture:p{index}" for index in range(
                    1, max(arm["coverage"]["attempted_eligible_parents"] for arm in arms) + 1
                )
            ],
        },
        "summary": {
            "arms": {arm["id"]: arm["counts"] for arm in arms},
            "effort": {arm["id"]: arm["effort"] for arm in arms},
            "diversity": {arm["id"]: arm["diversity"] for arm in arms},
            "concentration": {arm["id"]: arm["concentration"] for arm in arms},
            "failure_topology": {arm["id"]: arm["failure_topology"] for arm in arms},
            "minimum_image_displacement": {
                arm["id"]: arm["minimum_image_displacement"] for arm in arms
            },
            "structural_change": {
                arm["id"]: arm["structural_change"] for arm in arms
            },
            "parent_coverage": {arm["id"]: arm["coverage"] for arm in arms},
            "prefix_audit": prefix,
            "gaussian_local_budget_response": {
                "arms": {
                    arm_id: {
                        "accepted": arm["counts"]["accepted"],
                        "exhausted": arm["counts"]["exhausted"],
                        "novel": arm["counts"]["novel"],
                        "useful": arm["counts"]["useful"],
                        "direction_trials": arm["effort"]["total_direction_trials"],
                    } for arm_id, arm in local_arms.items()
                },
            },
        },
        "analysis": {"budget_marginals": {}},
    }


def _build(evidence, *, lane_policy=None):
    # Missing production module/API is the intended RED, not malformed tests.
    module = importlib.import_module("rudeus.generation.pareto_selection")
    builder = getattr(module, "build_candidate_supply_v2_pareto_evidence")
    return builder(evidence, lane_policy=_policy() if lane_policy is None else lane_policy)


def _row(result, arm_id):
    return next(row for row in result["arms"] if row["arm_id"] == arm_id)


def _assert_non_authorizing(result):
    assert result["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
    assert all(value is False for value in result["authorization"].values())
    assert result["authorization"]["scheduler_activation"] is False
    assert result["authorization"]["p1_eligibility"] is False
    assert result["authorization"]["downstream_diffusion_claim"] is False
    assert not (FORBIDDEN_SELECTION_KEYS & set(result))
    assert not (FORBIDDEN_DOWNSTREAM_KEYS & set(result))
    for row in result["arms"]:
        assert not (FORBIDDEN_SELECTION_KEYS & set(row))
        assert not (FORBIDDEN_DOWNSTREAM_KEYS & set(row))


def test_synthetic_evidence_fixture_reconciles_before_selection():
    evidence = _evidence([_arm("ARM_A", blocked=1, inapplicable=1, exhausted=2,
                             useful=3, novel=4)])
    counts = evidence["summary"]["arms"]["ARM_A"]
    assert counts["requested"] == 10
    assert counts["attempted"] == 8
    assert counts["generated"] == 6
    assert counts["requested"] == counts["blocked"] + counts["inapplicable"] + counts["attempted"]
    assert counts["attempted"] == counts["generated"] + counts["exhausted"]
    assert evidence["validation_state"] == "RECONCILED"


def test_default_evidence_keeps_separate_dimensions_and_has_no_score_or_winner():
    result = _build(_evidence([_arm("ARM_A")]))
    _assert_non_authorizing(result)
    assert result["arm_order"] == ["ARM_A"]
    assert "nondominated_arm_ids" in result
    dimensions = _row(result, "ARM_A")["dimensions"]
    assert {
        "yield", "survival", "novelty", "geometry_failure", "exhaustion",
        "parent_coverage", "family_coverage", "concentration", "diversity",
        "native_effort", "budget_response", "structural_change",
        "displacement", "failure_topology",
    } <= dimensions.keys()
    assert not (FORBIDDEN_SELECTION_KEYS & set(dimensions))


def test_pareto_dominance_and_tradeoffs_use_explicit_comparable_dimensions():
    dominated = _evidence([
        _arm("ARM_A", useful=8, novel=8, useful_parents=4,
             useful_parent_share=0.25, effort=100),
        _arm("ARM_B", useful=6, novel=6, useful_parents=3,
             useful_parent_share=1 / 3, effort=120),
    ])
    relations = _build(dominated)["pareto_relations"]
    assert "ARM_B" in relations["ARM_A"]["dominates"]
    assert "ARM_A" in relations["ARM_B"]["dominated_by"]

    tradeoff = _evidence([
        _arm("ARM_C", useful=9, novel=9, effort=200),
        _arm("ARM_D", useful=7, novel=7, effort=100),
    ])
    relations = _build(tradeoff)["pareto_relations"]
    assert "ARM_D" not in relations["ARM_C"]["dominates"]
    assert "ARM_C" not in relations["ARM_D"]["dominates"]
    assert "ARM_D" in relations["ARM_C"]["incomparable_with"]


def test_native_effort_units_are_incomparable_without_conversion():
    evidence = _evidence([
        _arm("ARM_GAUSSIAN", useful=8, novel=8, effort=1107,
             useful_parents=4, effort_unit=GAUSSIAN_ATTEMPTS),
        _arm("ARM_LOCAL", useful=6, novel=6, effort=6416,
             useful_parents=3, effort_unit=LOCAL_TRIALS),
    ])
    result = _build(evidence)
    relation = result["pareto_relations"]["ARM_GAUSSIAN"]
    assert "ARM_LOCAL" not in relation["dominates"]
    assert relation["dimension_comparisons"]["ARM_LOCAL"]["native_effort"] == "INCOMPARABLE"
    assert _row(result, "ARM_GAUSSIAN")["dimensions"]["native_effort"]["unit"] == GAUSSIAN_ATTEMPTS
    assert _row(result, "ARM_LOCAL")["dimensions"]["native_effort"]["unit"] == LOCAL_TRIALS


def test_missing_distinct_outcomes_stays_missing_and_sibling_pairs_are_partial():
    evidence = _evidence([_arm("ARM_PARTIAL", sibling_pairs=3,
                              distinct_outcomes=None)])
    result = _build(evidence)
    diversity = _row(result, "ARM_PARTIAL")["dimensions"]["diversity"]
    assert diversity["within_arm_sibling_duplicate_pairs"] == 3
    assert diversity["distinct_structural_outcomes"] == {"state": "MISSING", "value": None}
    assert diversity["evidence_state"] == "PARTIAL"
    assert result["limitations"]["distinct_structural_outcomes"] == "MISSING"


def test_lane_eligibility_is_distinct_complementary_and_policy_driven():
    evidence = _evidence([
        _arm("ARM_EXPLORE", useful=3, novel=8, useful_parents=2,
             useful_parent_share=2 / 3, sibling_pairs=0, effort=70),
        _arm("ARM_EXPLOIT", useful=8, novel=8, useful_parents=4,
             useful_parent_share=0.25, sibling_pairs=2, effort=110),
    ])
    policy = _policy()
    result = _build(evidence, lane_policy=policy)
    assert result["lane_policy"] == policy
    assert _row(result, "ARM_EXPLORE")["lane_eligibility"] == {
        "EXPLORATION": True, "EXPLOITATION": False,
    }
    assert _row(result, "ARM_EXPLOIT")["lane_eligibility"] == {
        "EXPLORATION": False, "EXPLOITATION": True,
    }
    _assert_non_authorizing(result)
    stricter = copy.deepcopy(policy)
    stricter["EXPLORATION"]["minimum_useful_yield_fraction"] = 0.40
    assert _row(_build(evidence, lane_policy=stricter), "ARM_EXPLORE")["lane_eligibility"]["EXPLORATION"] is False


def test_missing_lane_policy_threshold_is_rejected_instead_of_hidden_default():
    policy = _policy()
    del policy["EXPLOITATION"]["minimum_parent_coverage_fraction"]
    with pytest.raises((TypeError, ValueError), match="(?i)policy|coverage|missing"):
        _build(_evidence([_arm("ARM_A")]), lane_policy=policy)


@pytest.mark.parametrize("broken", ["state", *INTEGRITY_FLAGS])
def test_unreconciled_or_invalid_integrity_fails_before_interpretation(broken):
    evidence = _evidence([_arm("ARM_A")])
    if broken == "state":
        evidence["validation_state"] = "UNRECONCILED"
    else:
        evidence["integrity"][broken] = False
    with pytest.raises((ValueError, RuntimeError), match="(?i)reconcil|integrity|invalid|prefix|radius|source"):
        _build(evidence)


def test_numerators_denominators_and_failure_states_remain_distinct():
    evidence = _evidence([
        _arm("ARM_BLOCKED", requested=12, blocked=2, inapplicable=0,
             exhausted=1, useful=4, novel=5, geometry_fail=0),
        _arm("ARM_INAPPLICABLE", requested=12, blocked=0, inapplicable=2,
             exhausted=1, useful=4, novel=5, geometry_fail=1),
        _arm("ARM_EXHAUSTED", requested=12, blocked=0, inapplicable=0,
             exhausted=3, useful=4, novel=5, geometry_fail=2),
    ])
    result = _build(evidence)
    for arm_id in ("ARM_BLOCKED", "ARM_INAPPLICABLE", "ARM_EXHAUSTED"):
        row = _row(result, arm_id)
        counts = evidence["summary"]["arms"][arm_id]
        assert row["dimensions"]["yield"]["useful_count"] == counts["useful"]
        assert row["dimensions"]["yield"]["attempted_count"] == counts["attempted"]
        assert row["dimensions"]["yield"]["useful_over_attempted"] == pytest.approx(
            counts["useful"] / counts["attempted"]
        )
        assert row["dimensions"]["parent_coverage"]["useful_parents"] == 3
        assert row["dimensions"]["parent_coverage"]["attempted_eligible_parents"] == 4
        assert row["dimensions"]["failure_topology"] == evidence["summary"]["failure_topology"][arm_id]
    topologies = [_row(result, arm)["dimensions"]["failure_topology"] for arm in (
        "ARM_BLOCKED", "ARM_INAPPLICABLE", "ARM_EXHAUSTED",
    )]
    assert len({json.dumps(topology, sort_keys=True) for topology in topologies}) == 3


def test_nested_budget_marginals_preserve_breadth_depth_and_native_effort():
    evidence = _evidence([
        _arm("GAUSSIAN_LOCAL_D4", exhausted=3, useful=6, novel=6,
             useful_parents=3, effort=100, effort_unit=LOCAL_TRIALS),
        _arm("GAUSSIAN_LOCAL_D8", exhausted=1, useful=8, novel=8,
             useful_parents=4, effort=110, effort_unit=LOCAL_TRIALS),
        _arm("GAUSSIAN_LOCAL_D16", exhausted=0, useful=9, novel=9,
             useful_parents=4, effort=118, effort_unit=LOCAL_TRIALS),
    ])
    evidence["analysis"]["budget_marginals"] = {
        "D4_TO_D8": {
            "additional_direction_trials": 10, "newly_accepted": 2,
            "newly_novel": 2, "newly_useful": 2,
            "newly_covered_parents": 1, "affected_sigma_values": [0.30, 0.35],
            "hard_tail_only": False,
        },
        "D8_TO_D16": {
            "additional_direction_trials": 8, "newly_accepted": 1,
            "newly_novel": 1, "newly_useful": 1,
            "newly_covered_parents": 0, "affected_sigma_values": [0.40],
            "hard_tail_only": True,
        },
    }
    evidence["summary"]["gaussian_local_budget_response"] = {
        "arms": {},
        **{key: {field: value for field, value in marginal.items()
                 if field in {"additional_direction_trials", "newly_accepted",
                              "newly_novel", "newly_useful"}}
           for key, marginal in evidence["analysis"]["budget_marginals"].items()},
    }
    result = _build(evidence)
    for key, expected in evidence["analysis"]["budget_marginals"].items():
        assert result["budget_marginals"][key] == expected
    assert result["budget_marginals"]["D4_TO_D8"]["newly_covered_parents"] == 1
    assert result["budget_marginals"]["D8_TO_D16"]["newly_covered_parents"] == 0
    assert "optimal_budget" not in result


def test_marginal_interpretation_requires_valid_prefix_audit():
    evidence = _evidence([_arm("GAUSSIAN_LOCAL_D4", effort_unit=LOCAL_TRIALS),
                          _arm("GAUSSIAN_LOCAL_D8", effort_unit=LOCAL_TRIALS)])
    evidence["summary"]["prefix_audit"]["D4_TO_D8"]["mismatches"] = 1
    with pytest.raises((ValueError, RuntimeError), match="(?i)prefix|integrity"):
        _build(evidence)


def test_yield_concentration_coverage_family_and_diversity_are_not_collapsed():
    evidence = _evidence([
        _arm("ARM_CONCENTRATED", requested=40, useful=9, novel=9,
             useful_parents=2, attempted_parents=10, useful_parent_share=8 / 9),
        _arm("ARM_DISTRIBUTED", requested=40, useful=7, novel=7,
             useful_parents=7, attempted_parents=10, useful_parent_share=1 / 7),
    ])
    evidence["summary"]["diversity"]["ARM_DISTRIBUTED"]["family_coverage"] = {
        "oxide": {"generated": 20, "novel": 4, "useful": 4},
        "sulfide": {"generated": 19, "novel": 3, "useful": 3},
        "UNAVAILABLE": {"generated": 1, "novel": 0, "useful": 0},
    }
    result = _build(evidence)
    relation = result["pareto_relations"]
    assert "ARM_DISTRIBUTED" not in relation["ARM_CONCENTRATED"]["dominates"]
    assert "ARM_CONCENTRATED" not in relation["ARM_DISTRIBUTED"]["dominates"]
    distributed = _row(result, "ARM_DISTRIBUTED")["dimensions"]
    assert distributed["concentration"]["useful"]["maximum_parent_share"] == 1 / 7
    assert distributed["parent_coverage"]["useful_parents"] == 7
    assert distributed["family_coverage"]["sulfide"]["useful"] == 3
    assert "UNAVAILABLE" in distributed["family_coverage"]


def test_raw_novelty_and_zero_geometry_fail_cannot_by_themselves_authorize_exploitation():
    high_novelty = _evidence([
        _arm("ARM_NOVEL_DAMAGED", useful=1, novel=9, geometry_fail=9,
             useful_parents=1),
        _arm("ARM_USABLE", useful=7, novel=7, geometry_fail=0,
             useful_parents=4),
    ])
    result = _build(high_novelty)
    assert _row(result, "ARM_NOVEL_DAMAGED")["lane_eligibility"]["EXPLOITATION"] is False
    assert _row(result, "ARM_USABLE")["lane_eligibility"]["EXPLOITATION"] is True

    safe_but_exhausted = _evidence([
        _arm("ARM_SAFE_EXHAUSTED", exhausted=8, useful=2, novel=2,
             geometry_fail=0, useful_parents=1),
        _arm("ARM_SURVIVING", exhausted=0, useful=5, novel=7,
             geometry_fail=2, useful_parents=4),
    ])
    relations = _build(safe_but_exhausted)["pareto_relations"]
    assert "ARM_SURVIVING" not in relations["ARM_SAFE_EXHAUSTED"]["dominates"]


def test_output_order_is_declared_order_independent_of_mapping_insertion_order():
    evidence = _evidence([_arm("Z_ARM"), _arm("A_ARM")])
    reordered = copy.deepcopy(evidence)
    for key in ("arms", "effort", "diversity", "concentration", "failure_topology",
                "minimum_image_displacement", "structural_change", "parent_coverage"):
        mapping = reordered["summary"][key]
        reordered["summary"][key] = dict(reversed(list(mapping.items())))
    first, second = _build(evidence), _build(reordered)
    assert first["arm_order"] == second["arm_order"] == ["Z_ARM", "A_ARM"]
    assert [row["arm_id"] for row in first["arms"]] == ["Z_ARM", "A_ARM"]
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_arm_identity_and_native_units_survive_analytical_projection():
    evidence = _evidence([_arm(arm, effort_unit=(LOCAL_TRIALS if "LOCAL" in arm
                                                   else GAUSSIAN_ATTEMPTS))
                          for arm in REAL_ARMS])
    result = _build(evidence)
    for detail in evidence["metadata"]["configuration_details"]:
        row = _row(result, detail["id"])
        assert row["arm_id"] == detail["id"]
        assert row["operator_name"] == detail["operator_name"]
        assert row["operator_version"] == detail["operator_version"]
        assert row["budget"] == detail["budget"]
        assert row["dimensions"]["native_effort"]["unit"] == evidence["summary"]["effort"][detail["id"]]["unit"]


def test_selection_is_read_only_and_does_not_call_generation_or_scheduler(monkeypatch, tmp_path):
    from rudeus.generation import generator, mobile_ion_diagnostic, scheduler

    def forbidden(*_args, **_kwargs):
        pytest.fail("analytical selection invoked generation or scheduling")

    monkeypatch.setattr(generator, "generate_children", forbidden)
    monkeypatch.setattr(mobile_ion_diagnostic,
                        "build_candidate_supply_v2_operator_tournament_panel", forbidden)
    monkeypatch.setattr(scheduler, "schedule_candidate_supply_v2", forbidden)
    monkeypatch.chdir(tmp_path)
    evidence = _evidence([_arm("ARM_A")])
    before = copy.deepcopy(evidence)
    result = _build(evidence)
    assert evidence == before
    assert list(tmp_path.iterdir()) == []
    _assert_non_authorizing(result)


def test_real_aggregate_shape_is_compatible_but_remains_non_authorizing():
    # Five real IDs and selected aggregate values only; no 36 MB artifact read.
    counts = (
        ("BASELINE_GAUSSIAN", 426, 170, 327, 163, 0, 57, 0.03529, 35, 178, 426, GAUSSIAN_ATTEMPTS),
        ("BOUNDED_GAUSSIAN_A8", 359, 244, 244, 0, 67, 64, 0.02459, 42, 191, 1107, GAUSSIAN_ATTEMPTS),
        ("GAUSSIAN_LOCAL_D4", 388, 288, 288, 0, 38, 70, 0.02083, 46, 164, 5762, LOCAL_TRIALS),
        ("GAUSSIAN_LOCAL_D8", 410, 310, 310, 0, 16, 71, 0.01935, 46, 164, 6416, LOCAL_TRIALS),
        ("GAUSSIAN_LOCAL_D16", 415, 315, 315, 0, 11, 71, 0.01905, 47, 164, 6604, LOCAL_TRIALS),
    )
    arms = []
    for arm_id, generated, useful, novel, geometry_fail, exhausted, coverage, share, p80, siblings, effort, unit in counts:
        arm = _arm(
            arm_id, requested=432, inapplicable=6, exhausted=exhausted,
            useful=useful, novel=novel, geometry_fail=geometry_fail,
            useful_parents=coverage, attempted_parents=71,
            useful_parent_share=share, sibling_pairs=siblings,
            distinct_outcomes=None, effort=effort, effort_unit=unit,
        )
        assert arm["counts"]["generated"] == generated
        # Only the fields listed above are observed real aggregate values.
        # Leave all other scientific quantities unknown in this shape fixture.
        arm["coverage"]["generated_parent_coverage"] = None
        arm["coverage"]["novel_parent_coverage"] = None
        arm["concentration"]["novel"]["maximum_parent_share"] = None
        arm["concentration"]["useful"]["parents_for_80_percent"] = p80
        arm["diversity"]["family_coverage"] = {
            "UNAVAILABLE": {"generated": None, "novel": None, "useful": None},
        }
        arm["structural_change"] = {
            "mobile_displacement_rms_A": None,
            "mobile_mobile_pair_distance_changes_A": None,
            "nearest_host_distance_changes_A": None,
        }
        arm["minimum_image_displacement"] = {"global": None}
        arms.append(arm)
    evidence = _evidence(arms)
    evidence["metadata"]["ordered_parent_ids"] = [f"obelix:fixture-{n}" for n in range(72)]
    evidence["summary"]["gaussian_local_budget_response"].update({
        "D4_TO_D8": {"additional_direction_trials": 654, "newly_accepted": 22,
                     "newly_novel": 22, "newly_useful": 22},
        "D8_TO_D16": {"additional_direction_trials": 188, "newly_accepted": 5,
                      "newly_novel": 5, "newly_useful": 5},
    })
    result = _build(evidence)
    assert result["arm_order"] == list(REAL_ARMS)
    assert len(result["arms"]) == 5
    assert all(_row(result, arm)["dimensions"]["yield"]["attempted_count"] == 426
               for arm in REAL_ARMS)
    _assert_non_authorizing(result)
    assert "optimal_budget" not in result


@pytest.mark.parametrize("section,missing_value,policy_field", [
    ("diversity", None, "allow_missing_family_coverage"),
    ("structural_change", None, "allow_missing_structural_change"),
    ("minimum_image_displacement", {"global": None}, "allow_missing_displacement"),
])
def test_missing_evidence_policy_changes_lane_eligibility(
    section, missing_value, policy_field,
):
    evidence = _evidence([_arm("ARM_A")])
    if section == "diversity":
        evidence["summary"][section]["ARM_A"]["family_coverage"] = missing_value
    else:
        evidence["summary"][section]["ARM_A"] = missing_value
    permissive = _policy()
    restrictive = _policy()
    restrictive["EXPLORATION"][policy_field] = False
    assert _row(_build(evidence, lane_policy=permissive), "ARM_A")[
        "lane_eligibility"]["EXPLORATION"] is True
    assert _row(_build(evidence, lane_policy=restrictive), "ARM_A")[
        "lane_eligibility"]["EXPLORATION"] is False


def test_incomparable_effort_policy_changes_lane_eligibility():
    evidence = _evidence([
        _arm("ARM_GAUSSIAN", effort_unit=GAUSSIAN_ATTEMPTS),
        _arm("ARM_LOCAL", effort_unit=LOCAL_TRIALS),
    ])
    permissive = _policy()
    restrictive = _policy()
    restrictive["EXPLORATION"]["allow_incomparable_effort"] = False
    allowed = _build(evidence, lane_policy=permissive)
    denied = _build(evidence, lane_policy=restrictive)
    assert allowed["pareto_relations"]["ARM_GAUSSIAN"]["dimension_comparisons"][
        "ARM_LOCAL"]["native_effort"] == "INCOMPARABLE"
    assert _row(allowed, "ARM_GAUSSIAN")["lane_eligibility"]["EXPLORATION"] is True
    assert _row(denied, "ARM_GAUSSIAN")["lane_eligibility"]["EXPLORATION"] is False


def _nested_marginal_evidence():
    evidence = _evidence([
        _arm("GAUSSIAN_LOCAL_D4", requested=40, exhausted=30, useful=5,
             novel=5, effort=5762, effort_unit=LOCAL_TRIALS),
        _arm("GAUSSIAN_LOCAL_D8", requested=40, exhausted=8, useful=27,
             novel=27, effort=6416, effort_unit=LOCAL_TRIALS),
        _arm("GAUSSIAN_LOCAL_D16", requested=40, exhausted=3, useful=32,
             novel=32, effort=6604, effort_unit=LOCAL_TRIALS),
    ])
    evidence["analysis"]["budget_marginals"] = {
        "D4_TO_D8": {"newly_useful": 22, "additional_direction_trials": 654},
        "D8_TO_D16": {"newly_useful": 5, "additional_direction_trials": 188},
    }
    return evidence


def test_nested_budget_increment_is_not_credited_to_the_lower_budget():
    result = _build(_nested_marginal_evidence())
    for arm_id, transition in (
        ("GAUSSIAN_LOCAL_D4", "D4_TO_D8"),
        ("GAUSSIAN_LOCAL_D8", "D8_TO_D16"),
    ):
        # Outgoing recovery is not recovery already achieved by this arm.
        response = _row(result, arm_id)["dimensions"]["budget_response"]
        assert transition not in response.get("marginals", {}).keys()


def test_nested_budget_incoming_and_outgoing_transitions_remain_distinct():
    result = _build(_nested_marginal_evidence())
    d8 = _row(result, "GAUSSIAN_LOCAL_D8")["dimensions"]["budget_response"]
    d16 = _row(result, "GAUSSIAN_LOCAL_D16")["dimensions"]["budget_response"]
    assert d8.get("incoming_marginal") == {
        "transition": "D4_TO_D8", "newly_useful": 22,
        "additional_direction_trials": 654,
    }
    assert d8.get("outgoing_marginal") == {
        "transition": "D8_TO_D16", "newly_useful": 5,
        "additional_direction_trials": 188,
    }
    assert d16.get("incoming_marginal") == {
        "transition": "D8_TO_D16", "newly_useful": 5,
        "additional_direction_trials": 188,
    }


def test_required_marginal_recovery_missing_is_not_eligible():
    evidence = _evidence([
        _arm("GAUSSIAN_LOCAL_D4", effort_unit=LOCAL_TRIALS),
        _arm("GAUSSIAN_LOCAL_D8", effort_unit=LOCAL_TRIALS),
    ])
    # D8 has an incoming nested-budget transition, but no observed delta.
    policy = _policy()
    policy["EXPLORATION"]["minimum_marginal_useful_recovery"] = 1
    result = _build(evidence, lane_policy=policy)
    response = _row(result, "GAUSSIAN_LOCAL_D8")["dimensions"]["budget_response"]
    assert response.get("incoming_marginal_state") in {"MISSING", "NOT_COMPARABLE"}
    assert _row(result, "GAUSSIAN_LOCAL_D8")["lane_eligibility"]["EXPLORATION"] is False


def _zero_attempt_evidence():
    return _evidence([_arm(
        "ARM_ZERO", requested=4, blocked=2, inapplicable=2,
        useful=0, novel=0, geometry_fail=0,
        useful_parents=0, attempted_parents=0,
    )])


@pytest.mark.parametrize("dimension,field", [
    ("yield", "useful_over_attempted"),
    ("survival", "generated_over_attempted"),
    ("geometry_failure", "fraction"),
    ("novelty", "novel_over_generated"),
])
def test_zero_denominator_fraction_is_undefined(dimension, field):
    row = _row(_build(_zero_attempt_evidence()), "ARM_ZERO")
    fraction = row["dimensions"][dimension][field]
    assert fraction is None or (
        isinstance(fraction, dict)
        and fraction.get("state") in {"MISSING", "NOT_APPLICABLE", "UNDEFINED"}
        and fraction.get("value") is None
    )
    assert row["dimensions"]["yield"]["useful_count"] == 0
    assert row["dimensions"]["yield"]["attempted_count"] == 0


def test_zero_attempt_arm_is_not_lane_eligible_or_observed_zero_performance():
    evidence = _evidence([
        _arm("ARM_ZERO", requested=4, blocked=2, inapplicable=2,
             useful=0, novel=0, useful_parents=0, attempted_parents=0),
        _arm("ARM_GENERATED"),
    ])
    policy = _policy()
    policy["EXPLORATION"].update({
        "minimum_parent_coverage_fraction": 0.0,
        "maximum_geometry_failure_fraction": 1.0,
        "maximum_exhaustion_fraction": 1.0,
        "maximum_useful_parent_share": 1.0,
    })
    result = _build(evidence, lane_policy=policy)
    assert _row(result, "ARM_ZERO")["lane_eligibility"]["EXPLORATION"] is False
    assert result["pareto_relations"]["ARM_ZERO"]["dimension_comparisons"][
        "ARM_GENERATED"]["yield"] in {"MISSING", "INCOMPARABLE", "NOT_APPLICABLE"}


def test_observed_effort_without_unit_is_not_comparable():
    evidence = _evidence([_arm("ARM_A"), _arm("ARM_B")])
    for arm_id in ("ARM_A", "ARM_B"):
        evidence["summary"]["effort"][arm_id]["unit"] = None
    with pytest.raises((TypeError, ValueError), match="(?i)effort|unit|comparab"):
        _build(evidence)


def test_diversity_complete_partial_and_missing_are_distinct_policy_states():
    arms = [
        _arm("ARM_COMPLETE"),
        _arm("ARM_PARTIAL", distinct_outcomes=None),
        _arm("ARM_MISSING", distinct_outcomes=None),
    ]
    arms[-1]["diversity"]["within_arm_sibling_duplicate_pairs"] = None
    arms[-1]["diversity"]["sibling_duplicate_denominator"] = None
    evidence = _evidence(arms)
    permissive = _policy()
    restrictive = _policy()
    restrictive["EXPLORATION"]["allow_missing_diversity"] = False
    allowed = _build(evidence, lane_policy=permissive)
    denied = _build(evidence, lane_policy=restrictive)
    for arm_id, state in (
        ("ARM_COMPLETE", "COMPLETE"),
        ("ARM_PARTIAL", "PARTIAL"),
        ("ARM_MISSING", "MISSING"),
    ):
        assert _row(allowed, arm_id)["dimensions"]["diversity"]["evidence_state"] == state
    assert _row(allowed, "ARM_COMPLETE")["lane_eligibility"]["EXPLORATION"] is True
    assert _row(allowed, "ARM_PARTIAL")["lane_eligibility"]["EXPLORATION"] is True
    assert _row(denied, "ARM_PARTIAL")["lane_eligibility"]["EXPLORATION"] is True
    assert _row(allowed, "ARM_MISSING")["lane_eligibility"]["EXPLORATION"] is True
    assert _row(denied, "ARM_MISSING")["lane_eligibility"]["EXPLORATION"] is False


def test_analysis_effort_aliases_preserve_observed_values_and_native_unit():
    # These requested analysis-form names differ from the checked-in tournament
    # builder's summary.effort key (total_attempts); keep that distinction explicit.
    evidence = _evidence([_arm("BASELINE_GAUSSIAN"), _arm("BOUNDED_GAUSSIAN_A8")])
    for arm_id, field, value in (
        ("BASELINE_GAUSSIAN", "attempted_complete_proposals", 426),
        ("BOUNDED_GAUSSIAN_A8", "total_complete_proposal_attempts", 1107),
    ):
        evidence["summary"]["effort"][arm_id] = {"unit": GAUSSIAN_ATTEMPTS, field: value}
    result = _build(evidence)
    assert _row(result, "BASELINE_GAUSSIAN")["dimensions"]["native_effort"] == {
        "value": 426, "unit": GAUSSIAN_ATTEMPTS, "state": "OBSERVED",
    }
    assert _row(result, "BOUNDED_GAUSSIAN_A8")["dimensions"]["native_effort"] == {
        "value": 1107, "unit": GAUSSIAN_ATTEMPTS, "state": "OBSERVED",
    }


@pytest.mark.parametrize("missing_key", [None, "scheduler_activation", "threshold_modification"])
def test_observational_authorization_requires_all_expected_keys(missing_key):
    evidence = _evidence([_arm("ARM_A")])
    if missing_key is None:
        evidence["authorization"] = {}
    else:
        del evidence["authorization"][missing_key]
    with pytest.raises((TypeError, ValueError), match="(?i)authorization|integrity|missing"):
        _build(evidence)


def test_sibling_duplication_comparison_accounts_for_opportunities():
    low = _arm("ARM_LOW_OPPORTUNITY", sibling_pairs=2)
    high = _arm("ARM_HIGH_OPPORTUNITY", sibling_pairs=3)
    low["diversity"]["sibling_duplicate_denominator"] = 10
    high["diversity"]["sibling_duplicate_denominator"] = 100
    result = _build(_evidence([low, high]))
    for arm_id, count, denominator in (
        ("ARM_LOW_OPPORTUNITY", 2, 10),
        ("ARM_HIGH_OPPORTUNITY", 3, 100),
    ):
        diversity = _row(result, arm_id)["dimensions"]["diversity"]
        assert diversity["within_arm_sibling_duplicate_pairs"] == count
        assert diversity["sibling_duplicate_denominator"] == denominator
    relation = result["pareto_relations"]["ARM_LOW_OPPORTUNITY"]
    assert relation["dimension_comparisons"]["ARM_HIGH_OPPORTUNITY"][
        "sibling_duplication"] in {"WORSE", "INCOMPARABLE"}
    assert "ARM_HIGH_OPPORTUNITY" not in relation["dominates"]


def _real_tournament_shape_fixture():
    """Small aggregate-only fixture preserving the artifact's physical layout."""
    real_arms = (
        ("BASELINE_GAUSSIAN", 426, 170, 327, 163, 0, 57, 0.03529, 35, 178, 426, GAUSSIAN_ATTEMPTS),
        ("BOUNDED_GAUSSIAN_A8", 359, 244, 244, 0, 67, 64, 0.02459, 42, 191, 1107, GAUSSIAN_ATTEMPTS),
        ("GAUSSIAN_LOCAL_D4", 388, 288, 288, 0, 38, 70, 0.02083, 46, 164, 5762, LOCAL_TRIALS),
        ("GAUSSIAN_LOCAL_D8", 410, 310, 310, 0, 16, 71, 0.01935, 46, 164, 6416, LOCAL_TRIALS),
        ("GAUSSIAN_LOCAL_D16", 415, 315, 315, 0, 11, 71, 0.01905, 47, 164, 6604, LOCAL_TRIALS),
    )
    arms = []
    for arm_id, generated, useful, novel, geometry_fail, exhausted, coverage, share, p80, siblings, effort, unit in real_arms:
        arm = _arm(
            arm_id, requested=432, inapplicable=6, exhausted=exhausted,
            useful=useful, novel=novel, geometry_fail=geometry_fail,
            useful_parents=coverage, attempted_parents=71,
            useful_parent_share=share, sibling_pairs=siblings,
            distinct_outcomes=None, effort=effort, effort_unit=unit,
        )
        assert arm["counts"]["generated"] == generated
        arm["coverage"]["generated_parent_coverage"] = None
        arm["coverage"]["novel_parent_coverage"] = None
        arm["concentration"]["novel"]["maximum_parent_share"] = None
        arm["concentration"]["useful"]["parents_for_80_percent"] = p80
        arm["diversity"]["family_coverage"] = {
            "UNAVAILABLE": {"generated": None, "novel": None, "useful": None},
        }
        arm["structural_change"] = {
            "mobile_displacement_rms_A": None,
            "mobile_mobile_pair_distance_changes_A": None,
            "nearest_host_distance_changes_A": None,
        }
        arm["minimum_image_displacement"] = {"global": None}
        arms.append(arm)

    normalized_fixture = _evidence(arms)
    normalized_fixture["metadata"]["ordered_parent_ids"] = [
        f"obelix:fixture-{index}" for index in range(72)
    ]
    normalized_fixture["summary"]["gaussian_local_budget_response"].update({
        "D4_TO_D8": {
            "additional_direction_trials": 654, "newly_accepted": 22,
            "newly_novel": 22, "newly_useful": 22,
        },
        "D8_TO_D16": {
            "additional_direction_trials": 188, "newly_accepted": 5,
            "newly_novel": 5, "newly_useful": 5,
        },
    })
    normalized_fixture["analysis"]["budget_marginals"] = {
        key: dict(value) for key, value in
        normalized_fixture["summary"]["gaussian_local_budget_response"].items()
        if key != "arms"
    }

    panel_summary = normalized_fixture["summary"]
    parent_coverage = panel_summary.pop("parent_coverage")
    family_coverage = {
        arm_id: copy.deepcopy(panel_summary["diversity"][arm_id]["family_coverage"])
        for arm_id in normalized_fixture["metadata"]["configurations"]
    }
    return {
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "validation_state": "RECONCILED",
        "integrity": dict(normalized_fixture["integrity"]),
        "panel": {
            "schema_version": normalized_fixture["schema_version"],
            "authorization": dict(normalized_fixture["authorization"]),
            "metadata": normalized_fixture["metadata"],
            "summary": panel_summary,
        },
        "analysis": {
            "parent_coverage": parent_coverage,
            "family_coverage": family_coverage,
            "gaussian_local_marginals": normalized_fixture["analysis"]["budget_marginals"],
        },
        "provenance": {},
    }


def _real_parent_coverage_shape_fixture():
    """Real analysis.parent_coverage names with compact supporting sections."""
    artifact = _real_tournament_shape_fixture()
    artifact["analysis"]["parent_coverage"] = {
        "BASELINE_GAUSSIAN": {
            "distinct_attempted_parents": 71,
            "distinct_generated_parents": 71,
            "distinct_novel_parents": 71,
            "distinct_useful_parents": 57,
        },
        "BOUNDED_GAUSSIAN_A8": {
            "distinct_attempted_parents": 71,
            "distinct_generated_parents": 66,
            "distinct_novel_parents": 64,
            "distinct_useful_parents": 64,
        },
        "GAUSSIAN_LOCAL_D4": {
            "distinct_attempted_parents": 71,
            "distinct_generated_parents": 70,
            "distinct_novel_parents": 70,
            "distinct_useful_parents": 70,
        },
        "GAUSSIAN_LOCAL_D8": {
            "distinct_attempted_parents": 71,
            "distinct_generated_parents": 71,
            "distinct_novel_parents": 71,
            "distinct_useful_parents": 71,
        },
        "GAUSSIAN_LOCAL_D16": {
            "distinct_attempted_parents": 71,
            "distinct_generated_parents": 71,
            "distinct_novel_parents": 71,
            "distinct_useful_parents": 71,
        },
    }
    return artifact


def _real_nested_marginal_shape_fixture():
    """Real analysis marginal nesting with only required transition counts."""
    artifact = _real_tournament_shape_fixture()
    artifact["analysis"]["gaussian_local_marginals"] = {
        "D4_TO_D8": {
            "counts": {
                "additional_direction_trials": 654,
                "newly_accepted": 22,
                "newly_novel": 22,
                "newly_useful": 22,
            },
        },
        "D8_TO_D16": {
            "counts": {
                "additional_direction_trials": 188,
                "newly_accepted": 5,
                "newly_novel": 5,
                "newly_useful": 5,
            },
        },
    }
    return artifact


def _normalize_real_tournament(artifact):
    module = importlib.import_module("rudeus.generation.pareto_selection")
    adapter = getattr(module, "normalize_candidate_supply_v2_tournament_evidence")
    return adapter(artifact)


def _reverse_mapping_insertion_order(value):
    if isinstance(value, dict):
        return {key: _reverse_mapping_insertion_order(item)
                for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [_reverse_mapping_insertion_order(item) for item in value]
    return copy.deepcopy(value)


def test_real_tournament_layout_is_accepted_and_builder_consumes_normalized_output():
    normalized = _normalize_real_tournament(_real_tournament_shape_fixture())
    result = _build(normalized)
    assert result["arm_order"] == list(REAL_ARMS)
    _assert_non_authorizing(result)
    assert "winner" not in result
    assert "optimal_budget" not in result


def test_real_artifact_sections_map_to_explicit_normalized_sections():
    artifact = _real_tournament_shape_fixture()
    normalized = _normalize_real_tournament(artifact)
    panel = artifact["panel"]
    for section in (
        "arms", "effort", "diversity", "concentration", "failure_topology",
        "gaussian_local_budget_response", "minimum_image_displacement",
        "prefix_audit", "structural_change",
    ):
        assert normalized["summary"][section] == panel["summary"][section]
    assert normalized["metadata"] == panel["metadata"]
    assert normalized["authorization"] == panel["authorization"]
    assert normalized["analysis"]["budget_marginals"] == artifact["analysis"][
        "gaussian_local_marginals"
    ]
    assert normalized["summary"]["parent_coverage"] == artifact["analysis"][
        "parent_coverage"
    ]


def test_real_parent_coverage_adapter_output_is_consumable_by_pareto_builder():
    artifact = _real_parent_coverage_shape_fixture()
    before = copy.deepcopy(artifact)
    normalized = _normalize_real_tournament(artifact)
    coverage = normalized["summary"]["parent_coverage"]
    assert artifact == before
    expected_useful = {
        "BASELINE_GAUSSIAN": 57,
        "BOUNDED_GAUSSIAN_A8": 64,
        "GAUSSIAN_LOCAL_D4": 70,
        "GAUSSIAN_LOCAL_D8": 71,
        "GAUSSIAN_LOCAL_D16": 71,
    }
    for arm_id, useful_count in expected_useful.items():
        assert coverage[arm_id]["distinct_attempted_parents"] == 71
        assert coverage[arm_id]["distinct_useful_parents"] == useful_count
        assert coverage[arm_id]["attempted_eligible_parents"] == 71
        assert coverage[arm_id]["useful_parent_coverage"] == useful_count
        assert coverage[arm_id]["distinct_novel_parents"] == artifact[
            "analysis"]["parent_coverage"][arm_id]["distinct_novel_parents"]

    module = importlib.import_module("rudeus.generation.pareto_selection")
    builder = getattr(module, "build_candidate_supply_v2_pareto_evidence")
    result = builder(normalized, lane_policy=_policy())
    assert result["arm_order"] == list(REAL_ARMS)

    conflicting = copy.deepcopy(artifact)
    conflicting["analysis"]["parent_coverage"]["BASELINE_GAUSSIAN"][
        "attempted_eligible_parents"
    ] = 72
    with pytest.raises(ValueError, match="conflicting parent coverage aliases"):
        _normalize_real_tournament(conflicting)


def test_real_parent_coverage_keeps_cohort_and_attempt_denominators_distinct():
    artifact = _real_parent_coverage_shape_fixture()
    normalized = _normalize_real_tournament(artifact)
    parent_count = len(normalized["metadata"]["ordered_parent_ids"])
    assert parent_count == 72

    for arm_id, values in normalized["summary"]["parent_coverage"].items():
        attempted = values["attempted_eligible_parents"]
        novel = values["distinct_novel_parents"]
        useful = values["useful_parent_coverage"]
        assert attempted == 71
        assert parent_count - attempted == 1  # the real cohort's inapplicable parent
        assert 0 <= useful <= novel <= attempted <= parent_count
        assert normalized["summary"]["arms"][arm_id]["attempted"] == 426


def test_family_coverage_is_preserved_and_duplicate_views_must_agree():
    artifact = _real_tournament_shape_fixture()
    fixture_family = {"fixture-family": {"generated": 1, "novel": 1, "useful": 1}}
    artifact["panel"]["summary"]["diversity"]["GAUSSIAN_LOCAL_D8"][
        "family_coverage"
    ] = copy.deepcopy(fixture_family)
    artifact["analysis"]["family_coverage"]["GAUSSIAN_LOCAL_D8"] = copy.deepcopy(
        fixture_family
    )
    normalized = _normalize_real_tournament(artifact)
    assert normalized["summary"]["diversity"] == artifact["panel"]["summary"]["diversity"]
    assert normalized["analysis"]["family_coverage"] == artifact["analysis"][
        "family_coverage"
    ]
    assert "family_coverage" not in normalized["summary"]

    conflicting = copy.deepcopy(artifact)
    conflicting["analysis"]["family_coverage"]["GAUSSIAN_LOCAL_D8"] = {
        "other-fixture-family": {"generated": 1, "novel": 1, "useful": 1},
    }
    with pytest.raises((TypeError, ValueError), match="(?i)family|coverage|disagree|conflict"):
        _normalize_real_tournament(conflicting)


def test_real_artifact_family_reconciliation_does_not_mutate_source():
    artifact = _real_tournament_shape_fixture()
    valid = {"fixture-family": {"generated": 1, "novel": 1, "useful": 1}}
    artifact["panel"]["summary"]["diversity"]["GAUSSIAN_LOCAL_D8"][
        "family_coverage"
    ] = copy.deepcopy(valid)
    artifact["analysis"]["family_coverage"]["GAUSSIAN_LOCAL_D8"] = {
        "state": "MISSING", "value": None,
    }
    before = copy.deepcopy(artifact)

    normalized = _normalize_real_tournament(artifact)

    assert artifact == before
    assert normalized["analysis"]["family_coverage"]["GAUSSIAN_LOCAL_D8"] == valid
    assert normalized["summary"]["diversity"]["GAUSSIAN_LOCAL_D8"][
        "family_coverage"
    ] == valid


def test_real_native_effort_values_and_units_survive_normalization():
    normalized = _normalize_real_tournament(_real_tournament_shape_fixture())
    expected = {
        "BASELINE_GAUSSIAN": (426, GAUSSIAN_ATTEMPTS),
        "BOUNDED_GAUSSIAN_A8": (1107, GAUSSIAN_ATTEMPTS),
        "GAUSSIAN_LOCAL_D4": (5762, LOCAL_TRIALS),
        "GAUSSIAN_LOCAL_D8": (6416, LOCAL_TRIALS),
        "GAUSSIAN_LOCAL_D16": (6604, LOCAL_TRIALS),
    }
    for arm_id, (value, unit) in expected.items():
        effort = normalized["summary"]["effort"][arm_id]
        row = _row(_build(normalized), arm_id)
        assert row["dimensions"]["native_effort"]["value"] == value
        assert row["dimensions"]["native_effort"]["unit"] == unit
        assert effort["unit"] == unit


def test_real_denominators_preserve_inapplicability_separately_from_blocking():
    normalized = _normalize_real_tournament(_real_tournament_shape_fixture())
    for arm_id in REAL_ARMS:
        counts = normalized["summary"]["arms"][arm_id]
        assert counts["requested"] == 432
        assert counts["attempted"] == 426
        assert counts["blocked"] == 0
        assert counts["inapplicable"] == 6


def test_real_nested_budget_marginals_preserve_direction_and_fields():
    artifact = _real_tournament_shape_fixture()
    normalized = _normalize_real_tournament(artifact)
    for key, expected in (
        ("D4_TO_D8", (654, 22)),
        ("D8_TO_D16", (188, 5)),
    ):
        marginal = normalized["analysis"]["budget_marginals"][key]
        assert marginal["additional_direction_trials"] == expected[0]
        assert marginal["newly_accepted"] == expected[1]
        assert marginal["newly_novel"] == expected[1]
        assert marginal["newly_useful"] == expected[1]


def test_real_nested_marginal_counts_project_to_builder_fields():
    normalized = _normalize_real_tournament(_real_nested_marginal_shape_fixture())
    marginals = normalized["analysis"]["budget_marginals"]
    expected = {
        "D4_TO_D8": {
            "additional_direction_trials": 654,
            "newly_accepted": 22,
            "newly_novel": 22,
            "newly_useful": 22,
        },
        "D8_TO_D16": {
            "additional_direction_trials": 188,
            "newly_accepted": 5,
            "newly_novel": 5,
            "newly_useful": 5,
        },
    }
    assert list(marginals) == ["D4_TO_D8", "D8_TO_D16"]
    for transition, fields in expected.items():
        for field, value in fields.items():
            assert marginals[transition].get(field) == value

    module = importlib.import_module("rudeus.generation.pareto_selection")
    builder = getattr(module, "build_candidate_supply_v2_pareto_evidence")
    result = builder(normalized, lane_policy=_policy())
    result_arms = {row["arm_id"]: row for row in result["arms"]}
    assert result_arms["GAUSSIAN_LOCAL_D8"]["dimensions"][
        "budget_response"]["incoming_marginal"]["transition"] == "D4_TO_D8"
    assert result_arms["GAUSSIAN_LOCAL_D16"]["dimensions"][
        "budget_response"]["incoming_marginal"]["transition"] == "D8_TO_D16"


@pytest.mark.parametrize("missing_path", [
    "panel", "panel.summary", "analysis.parent_coverage",
    "panel.authorization.scheduler_activation",
])
def test_real_artifact_adapter_rejects_missing_critical_sections(missing_path):
    artifact = _real_tournament_shape_fixture()
    parts = missing_path.split(".")
    current = artifact
    for part in parts[:-1]:
        current = current[part]
    del current[parts[-1]]
    with pytest.raises((TypeError, ValueError), match="(?i)missing|panel|summary|analysis|authorization"):
        _normalize_real_tournament(artifact)


def test_real_artifact_adapter_is_deterministic_and_preserves_declared_arm_order():
    artifact = _real_tournament_shape_fixture()
    normalized = _normalize_real_tournament(artifact)
    reordered_mappings = _normalize_real_tournament(
        _reverse_mapping_insertion_order(artifact)
    )
    assert normalized["metadata"]["configurations"] == list(REAL_ARMS)
    assert json.dumps(normalized, sort_keys=True) == json.dumps(
        reordered_mappings, sort_keys=True
    )


@pytest.mark.parametrize("section,state", [
    ("structural_change", "MISSING"),
    ("structural_change", "NOT_AVAILABLE"),
    ("minimum_image_displacement", "MISSING"),
    ("minimum_image_displacement", "NOT_AVAILABLE"),
])
def test_explicit_missing_scientific_state_is_not_observed_for_lane_policy(section, state):
    evidence = _evidence([_arm("ARM_MARKED_MISSING")])
    marker = {"state": state, "value": None}
    evidence["summary"][section]["ARM_MARKED_MISSING"] = copy.deepcopy(marker)
    allowed_policy = _policy()
    denied_policy = _policy()
    policy_field = (
        "allow_missing_structural_change"
        if section == "structural_change" else "allow_missing_displacement"
    )
    denied_policy["EXPLORATION"][policy_field] = False
    allowed = _build(evidence, lane_policy=allowed_policy)
    denied = _build(evidence, lane_policy=denied_policy)
    assert _row(allowed, "ARM_MARKED_MISSING")["lane_eligibility"][
        "EXPLORATION"
    ] is True
    assert _row(denied, "ARM_MARKED_MISSING")["lane_eligibility"][
        "EXPLORATION"
    ] is False


def _set_real_family_sources(artifact, arm_id, panel_value, analysis_value):
    artifact["panel"]["summary"]["diversity"][arm_id]["family_coverage"] = copy.deepcopy(
        panel_value
    )
    artifact["analysis"]["family_coverage"][arm_id] = copy.deepcopy(analysis_value)


@pytest.mark.parametrize("missing_source", ["panel", "analysis"])
def test_one_valid_and_one_missing_family_source_preserves_the_valid_view(missing_source):
    artifact = _real_tournament_shape_fixture()
    valid = {"fixture-family": {"generated": 1, "novel": 1, "useful": 1}}
    missing = {"state": "MISSING", "value": None}
    panel_value, analysis_value = (
        (missing, valid) if missing_source == "panel" else (valid, missing)
    )
    _set_real_family_sources(
        artifact, "GAUSSIAN_LOCAL_D8", panel_value, analysis_value
    )
    normalized = _normalize_real_tournament(artifact)
    assert normalized["summary"]["diversity"]["GAUSSIAN_LOCAL_D8"][
        "family_coverage"
    ] == valid


def test_both_missing_family_sources_remain_explicitly_missing():
    artifact = _real_tournament_shape_fixture()
    missing = {"state": "MISSING", "value": None}
    _set_real_family_sources(
        artifact, "GAUSSIAN_LOCAL_D8", missing, missing
    )
    normalized = _normalize_real_tournament(artifact)
    assert normalized["summary"]["diversity"]["GAUSSIAN_LOCAL_D8"][
        "family_coverage"
    ] == missing


def test_equal_valid_family_sources_normalize_successfully():
    artifact = _real_tournament_shape_fixture()
    valid = {"fixture-family": {"generated": 1, "novel": 1, "useful": 1}}
    _set_real_family_sources(
        artifact, "GAUSSIAN_LOCAL_D8", valid, valid
    )
    normalized = _normalize_real_tournament(artifact)
    assert normalized["summary"]["diversity"]["GAUSSIAN_LOCAL_D8"][
        "family_coverage"
    ] == valid


def test_missing_family_lane_permission_does_not_remove_pareto_requirement():
    evidence = _evidence([
        _arm("ARM_FAMILY_MISSING", useful=8, novel=8, useful_parents=4,
             useful_parent_share=0.25, effort=100),
        _arm("ARM_FAMILY_PRESENT", useful=6, novel=6, useful_parents=3,
             useful_parent_share=1 / 3, effort=120),
    ])
    evidence["summary"]["diversity"]["ARM_FAMILY_MISSING"]["family_coverage"] = {
        "state": "MISSING", "value": None,
    }
    result = _build(evidence)
    assert _row(result, "ARM_FAMILY_MISSING")["lane_eligibility"][
        "EXPLORATION"
    ] is True
    relation = result["pareto_relations"]["ARM_FAMILY_MISSING"]
    assert "ARM_FAMILY_PRESENT" not in relation["dominates"]
    assert relation["dimension_comparisons"]["ARM_FAMILY_PRESENT"].get(
        "family_coverage"
    ) in {"MISSING", "INCOMPARABLE"}


@pytest.mark.parametrize("section,comparison_key", [
    ("structural_change", "structural_change"),
    ("minimum_image_displacement", "displacement"),
])
def test_missing_structural_or_displacement_evidence_blocks_dominance(
    section, comparison_key,
):
    evidence = _evidence([
        _arm("ARM_MISSING_DESCRIPTOR", useful=8, novel=8, useful_parents=4,
             useful_parent_share=0.25, effort=100),
        _arm("ARM_OBSERVED_DESCRIPTOR", useful=6, novel=6, useful_parents=3,
             useful_parent_share=1 / 3, effort=120),
    ])
    evidence["summary"][section]["ARM_MISSING_DESCRIPTOR"] = {
        "state": "MISSING", "value": None,
    }
    result = _build(evidence)
    relation = result["pareto_relations"]["ARM_MISSING_DESCRIPTOR"]
    assert "ARM_OBSERVED_DESCRIPTOR" not in relation["dominates"]
    assert relation["dimension_comparisons"]["ARM_OBSERVED_DESCRIPTOR"].get(
        comparison_key
    ) in {"MISSING", "INCOMPARABLE"}


@pytest.mark.parametrize("section,comparison_key", [
    ("structural_change", "structural_change"),
    ("minimum_image_displacement", "displacement"),
])
def test_different_non_orderable_descriptors_make_arms_incomparable(
    section, comparison_key,
):
    evidence = _evidence([_arm("ARM_LEFT"), _arm("ARM_RIGHT")])
    if section == "structural_change":
        evidence["summary"][section]["ARM_LEFT"] = {"descriptor": 0.1}
        evidence["summary"][section]["ARM_RIGHT"] = {"descriptor": 0.2}
    else:
        evidence["summary"][section]["ARM_LEFT"] = {
            "global": {"mobile_site_count": 5, "rms_A": 0.1}
        }
        evidence["summary"][section]["ARM_RIGHT"] = {
            "global": {"mobile_site_count": 5, "rms_A": 0.2}
        }
    result = _build(evidence)
    relation = result["pareto_relations"]["ARM_LEFT"]
    assert relation["dimension_comparisons"]["ARM_RIGHT"].get(
        comparison_key
    ) in {"INCOMPARABLE", "NON_ORDERABLE"}
    assert "ARM_RIGHT" in relation["incomparable_with"]
    assert "ARM_RIGHT" not in relation["dominates"]


def test_identical_valid_non_orderable_descriptors_are_explicitly_equal():
    evidence = _evidence([_arm("ARM_LEFT"), _arm("ARM_RIGHT")])
    result = _build(evidence)
    comparisons = result["pareto_relations"]["ARM_LEFT"][
        "dimension_comparisons"]["ARM_RIGHT"]
    assert comparisons.get("structural_change") == "EQUAL"
    assert comparisons.get("displacement") == "EQUAL"


def test_family_tradeoff_compares_the_same_support_without_scalarization():
    evidence = _evidence([
        _arm("ARM_OXIDE", useful=6, novel=7, useful_parents=3),
        _arm("ARM_SULFIDE", useful=6, novel=7, useful_parents=3),
    ])
    evidence["summary"]["diversity"]["ARM_OXIDE"]["family_coverage"] = {
        "oxide": {"generated": 8, "novel": 7, "useful": 6},
        "sulfide": {"generated": 2, "novel": 0, "useful": 0},
    }
    evidence["summary"]["diversity"]["ARM_SULFIDE"]["family_coverage"] = {
        "oxide": {"generated": 2, "novel": 0, "useful": 0},
        "sulfide": {"generated": 8, "novel": 7, "useful": 6},
    }
    relation = _build(evidence)["pareto_relations"]["ARM_OXIDE"]
    assert relation["dimension_comparisons"]["ARM_SULFIDE"].get(
        "family_coverage"
    ) in {"INCOMPARABLE", "NON_ORDERABLE"}
    assert "ARM_SULFIDE" in relation["incomparable_with"]
    assert "ARM_SULFIDE" not in relation["dominates"]


@pytest.mark.parametrize("state", [
    "MISSING", "NOT_AVAILABLE", "NOT_APPLICABLE", "INCOMPARABLE",
])
def test_family_sentinel_lane_policy_respects_explicit_missing_state(state):
    evidence = _evidence([_arm("ARM_FAMILY_SENTINEL")])
    marker = {"state": state, "value": None}
    evidence["summary"]["diversity"]["ARM_FAMILY_SENTINEL"][
        "family_coverage"
    ] = copy.deepcopy(marker)

    denied_policy = _policy()
    denied_policy["EXPLORATION"]["allow_missing_family_coverage"] = False
    denied = _build(evidence, lane_policy=denied_policy)
    row = _row(denied, "ARM_FAMILY_SENTINEL")
    assert row["lane_eligibility"]["EXPLORATION"] is False
    assert row["dimensions"]["family_coverage"] == marker

    allowed_policy = _policy()
    allowed_policy["EXPLORATION"]["allow_missing_family_coverage"] = True
    allowed = _build(evidence, lane_policy=allowed_policy)
    allowed_row = _row(allowed, "ARM_FAMILY_SENTINEL")
    assert allowed_row["lane_eligibility"]["EXPLORATION"] is True
    assert allowed_row["dimensions"]["family_coverage"] == marker


def test_valid_family_coverage_satisfies_lane_evidence_requirement():
    evidence = _evidence([_arm("ARM_FAMILY_VALID")])
    valid = {
        "oxide": {"generated": 6, "novel": 4, "useful": 3},
        "sulfide": {"generated": 4, "novel": 3, "useful": 2},
    }
    evidence["summary"]["diversity"]["ARM_FAMILY_VALID"][
        "family_coverage"
    ] = copy.deepcopy(valid)
    policy = _policy()
    policy["EXPLORATION"]["allow_missing_family_coverage"] = False

    result = _build(evidence, lane_policy=policy)
    row = _row(result, "ARM_FAMILY_VALID")
    assert row["lane_eligibility"]["EXPLORATION"] is True
    assert row["dimensions"]["family_coverage"] == valid
