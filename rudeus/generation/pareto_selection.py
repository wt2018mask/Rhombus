"""Read-only Pareto evidence projection for candidate-supply-v2 diagnostics.

This module analyzes already-reconciled tournament summaries. It does not run
generation, choose an arm, or authorize scientific or scheduler actions.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping


_INTEGRITY_FLAGS = (
    "all_arm_denominators_reconciled",
    "first_proposal_match",
    "local_prefix_match",
    "radius_consistency",
    "parent_p0_reproduced",
    "source_order_preserved",
    "source_hashes_reproduced_before_and_after",
    "authorization_all_false",
)
_POLICY_FIELDS = (
    "minimum_parent_coverage_fraction",
    "minimum_useful_yield_fraction",
    "maximum_geometry_failure_fraction",
    "maximum_exhaustion_fraction",
    "maximum_useful_parent_share",
    "maximum_sibling_duplicate_pairs",
    "minimum_diversity_evidence_state",
    "allow_missing_diversity",
    "allow_missing_family_coverage",
    "allow_missing_structural_change",
    "allow_missing_displacement",
    "allow_missing_effort",
    "allow_incomparable_effort",
    "minimum_marginal_useful_recovery",
)
_AUTHORIZATION = (
    "scheduler_activation",
    "p1_eligibility",
    "operator_superiority",
    "automatic_promotion",
    "sigma_selection",
    "budget_selection",
    "parent_exclusion",
    "chemistry_exclusion",
    "downstream_diffusion_claim",
    "threshold_modification",
)
_STATE_ORDER = {"MISSING": 0, "PARTIAL": 1, "COMPLETE": 2}
_ABSENT_EVIDENCE_STATES = {
    "MISSING", "NOT_AVAILABLE", "NOT_APPLICABLE", "INCOMPARABLE",
}


def _mapping(value, name):
    if not isinstance(value, Mapping):
        raise ValueError(f"invalid {name}: expected a mapping")
    return value


def _number(value, name, *, allow_none=False):
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid {name}: expected a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"invalid {name}: expected a finite number")
    return value


def _fraction(numerator, denominator):
    return numerator / denominator if denominator else None


def _family_support_signature(value):
    if not isinstance(value, Mapping) or not _has_observed_values(value):
        return None
    generated = {}
    for family, counts in value.items():
        if family == "UNAVAILABLE" or not isinstance(counts, Mapping):
            continue
        count = counts.get("generated")
        if isinstance(count, int) and not isinstance(count, bool) and count > 0:
            generated[family] = count
    total = sum(generated.values())
    if total <= 0:
        return None
    return {family: count / total for family, count in generated.items()}


def _has_observed_values(value):
    """Recognize measured aggregate leaves without interpreting absent data as 0."""
    if isinstance(value, Mapping):
        state = value.get("state")
        if isinstance(state, str) and state.upper() in _ABSENT_EVIDENCE_STATES:
            return False
        return any(_has_observed_values(item) for key, item in value.items()
                   if key != "state")
    if isinstance(value, (list, tuple)):
        return any(_has_observed_values(item) for item in value)
    return value is not None


def _validate_policy(policy):
    _mapping(policy, "lane policy")
    for lane in ("EXPLORATION", "EXPLOITATION"):
        values = _mapping(policy.get(lane), f"{lane} policy")
        missing = [field for field in _POLICY_FIELDS if field not in values]
        if missing:
            raise ValueError(f"missing {lane} policy fields: {', '.join(missing)}")
        for field in _POLICY_FIELDS:
            value = values[field]
            if field.startswith("allow_"):
                if type(value) is not bool:
                    raise ValueError(f"invalid policy {lane}.{field}: expected bool")
            elif field == "minimum_diversity_evidence_state":
                if value not in _STATE_ORDER:
                    raise ValueError(f"invalid policy {lane}.{field}")
            else:
                _number(value, f"policy {lane}.{field}")
        for field in _POLICY_FIELDS[:5]:
            if not 0 <= float(values[field]) <= 1:
                raise ValueError(f"invalid policy fraction {lane}.{field}")
        if values["maximum_sibling_duplicate_pairs"] < 0:
            raise ValueError(f"invalid policy {lane}.maximum_sibling_duplicate_pairs")
        if values["minimum_marginal_useful_recovery"] < 0:
            raise ValueError(f"invalid policy {lane}.minimum_marginal_useful_recovery")


def _validate_evidence(evidence):
    _mapping(evidence, "evidence")
    if evidence.get("artifact_type") != "OBSERVATIONAL_DIAGNOSTIC":
        raise ValueError("invalid evidence artifact type; expected observational diagnostic")
    if evidence.get("validation_state") != "RECONCILED":
        raise ValueError("evidence is not reconciled")
    integrity = _mapping(evidence.get("integrity"), "integrity")
    bad = [name for name in _INTEGRITY_FLAGS if integrity.get(name) is not True]
    if bad:
        raise ValueError(f"integrity failure: {', '.join(bad)}")
    authorization = _mapping(evidence.get("authorization"), "authorization")
    missing = [key for key in _AUTHORIZATION if key not in authorization]
    if missing:
        raise ValueError(f"integrity authorization keys missing: {', '.join(missing)}")
    if any(value is not False for value in authorization.values()):
        raise ValueError("integrity authorization boundary is not all false")
    metadata = _mapping(evidence.get("metadata"), "metadata")
    summary = _mapping(evidence.get("summary"), "summary")
    order = metadata.get("configurations")
    if not isinstance(order, list) or not order or len(order) != len(set(order)):
        raise ValueError("invalid configuration order")
    details = metadata.get("configuration_details")
    if not isinstance(details, list) or [d.get("id") for d in details] != order:
        raise ValueError("configuration identity/order mismatch")
    for detail in details:
        if not all(detail.get(key) is not None for key in ("operator_name", "operator_version")):
            raise ValueError("invalid operator configuration identity")
    if not isinstance(metadata.get("ordered_parent_ids"), list):
        raise ValueError("invalid ordered source parent identity")
    if not isinstance(summary.get("arms"), Mapping):
        raise ValueError("invalid arm summary")
    for section in ("effort", "diversity", "concentration", "failure_topology",
                    "minimum_image_displacement", "structural_change", "parent_coverage"):
        _mapping(summary.get(section), f"summary.{section}")
    for arm_id in order:
        if arm_id not in summary["arms"]:
            raise ValueError(f"missing summary for arm {arm_id}")
    prefix = summary.get("prefix_audit", {})
    for smaller, larger, key in (
        ("GAUSSIAN_LOCAL_D4", "GAUSSIAN_LOCAL_D8", "D4_TO_D8"),
        ("GAUSSIAN_LOCAL_D8", "GAUSSIAN_LOCAL_D16", "D8_TO_D16"),
    ):
        if smaller in order and larger in order:
            record = _mapping(prefix.get(key), f"prefix audit {key}")
            if record.get("mismatches") != 0 or record.get("accepted_to_exhausted") != 0:
                raise ValueError(f"prefix integrity failure: {key}")
    return metadata, summary, order, details


def _arm_projection(arm_id, detail, summary):
    counts = _mapping(summary["arms"][arm_id], f"counts for {arm_id}")
    names = ("requested", "blocked", "inapplicable", "attempted", "generated",
             "accepted", "exhausted", "geometry_fail", "novel", "rediscovery",
             "p0_plausible", "useful")
    values = {}
    for name in names:
        raw = counts.get(name)
        if type(raw) is not int or raw < 0:
            raise ValueError(f"invalid {arm_id} denominator/count {name}")
        values[name] = raw
    if values["requested"] != values["blocked"] + values["inapplicable"] + values["attempted"]:
        raise ValueError(f"arm denominator reconciliation failed: {arm_id}")
    if values["attempted"] != values["generated"] + values["exhausted"]:
        raise ValueError(f"generation reconciliation failed: {arm_id}")
    if values["generated"] != values["geometry_fail"] + values["p0_plausible"]:
        raise ValueError(f"P0 reconciliation failed: {arm_id}")
    if values["generated"] != values["novel"] + values["rediscovery"]:
        raise ValueError(f"novelty reconciliation failed: {arm_id}")
    if values["useful"] > min(values["novel"], values["p0_plausible"]):
        raise ValueError(f"useful count reconciliation failed: {arm_id}")

    coverage = _mapping(summary["parent_coverage"].get(arm_id), f"coverage {arm_id}")
    attempted_parents = coverage.get("attempted_eligible_parents")
    useful_parents = coverage.get("useful_parent_coverage")
    for name, value in (("attempted eligible parents", attempted_parents),
                        ("useful parents", useful_parents)):
        if type(value) is not int or value < 0:
            raise ValueError(f"invalid {arm_id} {name}")
    if useful_parents > attempted_parents:
        raise ValueError(f"parent coverage reconciliation failed: {arm_id}")

    diversity = _mapping(summary["diversity"].get(arm_id), f"diversity {arm_id}")
    distinct = diversity.get("distinct_structural_outcomes")
    if distinct is None:
        distinct_value = {"state": "MISSING", "value": None}
        diversity_state = "PARTIAL" if diversity.get("within_arm_sibling_duplicate_pairs") is not None else "MISSING"
    else:
        if type(distinct) is not int or distinct < 0:
            raise ValueError(f"invalid distinct structural outcomes: {arm_id}")
        distinct_value = {"state": "OBSERVED", "value": distinct}
        diversity_state = "COMPLETE"
    sibling_pairs = diversity.get("within_arm_sibling_duplicate_pairs")
    sibling_denominator = diversity.get("sibling_duplicate_denominator")
    if sibling_pairs is not None and (type(sibling_pairs) is not int or sibling_pairs < 0):
        raise ValueError(f"invalid sibling duplicate pairs: {arm_id}")
    if sibling_denominator is not None and (type(sibling_denominator) is not int or sibling_denominator < 0):
        raise ValueError(f"invalid sibling duplicate denominator: {arm_id}")

    concentration = _mapping(summary["concentration"].get(arm_id), f"concentration {arm_id}")
    useful_concentration = _mapping(concentration.get("useful"), f"useful concentration {arm_id}")
    novel_concentration = _mapping(concentration.get("novel"), f"novel concentration {arm_id}")
    useful_share = _number(useful_concentration.get("maximum_parent_share"), "useful parent share", allow_none=True)
    if useful_share is not None and not 0 <= useful_share <= 1:
        raise ValueError(f"invalid useful parent share: {arm_id}")
    family_coverage = diversity.get("family_coverage")
    if not isinstance(family_coverage, Mapping):
        family_coverage = {"state": "MISSING", "value": None}
    else:
        family_coverage = {family: dict(values) if isinstance(values, Mapping) else values
                          for family, values in family_coverage.items()}
    family_observed = _has_observed_values(family_coverage)

    effort = _mapping(summary["effort"].get(arm_id), f"effort {arm_id}")
    effort_unit = effort.get("unit")
    effort_fields = (
        "attempted_complete_proposals", "attempted_complete_proposal_attempts",
        "total_complete_proposal_attempts", "total_attempts", "total_direction_trials",
    )
    observed_efforts = [effort[name] for name in effort_fields
                        if effort.get(name) is not None]
    if len(set(observed_efforts)) > 1:
        raise ValueError(f"conflicting native effort aliases for {arm_id}")
    effort_value = observed_efforts[0] if observed_efforts else None
    if effort_value is not None:
        if type(effort_value) is not int or effort_value < 0:
            raise ValueError(f"invalid native effort for {arm_id}")
        if not isinstance(effort_unit, str) or not effort_unit:
            raise ValueError(f"observed native effort requires a unit: {arm_id}")

    counts_projection = dict(values)
    dimensions = {
        "yield": {
            "useful_count": values["useful"], "attempted_count": values["attempted"],
            "generated_count": values["generated"],
            "useful_over_attempted": _fraction(values["useful"], values["attempted"]),
            "useful_over_generated": _fraction(values["useful"], values["generated"]),
        },
        "survival": {"generated_count": values["generated"], "attempted_count": values["attempted"],
                     "generated_over_attempted": _fraction(values["generated"], values["attempted"])},
        "novelty": {"novel_count": values["novel"], "generated_count": values["generated"],
                    "novel_over_generated": _fraction(values["novel"], values["generated"]),
                    "novel_over_attempted": _fraction(values["novel"], values["attempted"]),
                    "rediscovery_count": values["rediscovery"]},
        "geometry_failure": {"geometry_fail_count": values["geometry_fail"],
                              "generated_count": values["generated"],
                              "fraction": _fraction(values["geometry_fail"], values["generated"])},
        "exhaustion": {"exhausted_count": values["exhausted"], "attempted_count": values["attempted"],
                       "fraction": _fraction(values["exhausted"], values["attempted"])},
        "parent_coverage": {
            "useful_parents": useful_parents,
            "attempted_eligible_parents": attempted_parents,
            "generated_parent_coverage": coverage.get("generated_parent_coverage"),
            "novel_parent_coverage": coverage.get("novel_parent_coverage"),
            "useful_parent_coverage": useful_parents,
            "fraction": _fraction(useful_parents, attempted_parents),
        },
        "family_coverage": family_coverage,
        "concentration": {
            "useful": dict(useful_concentration), "novel": dict(novel_concentration),
        },
        "diversity": {
            "parent_rediscovery_count": diversity.get("parent_rediscovery_count"),
            "within_arm_sibling_duplicate_pairs": sibling_pairs,
            "sibling_duplicate_denominator": sibling_denominator,
            "sibling_duplicate_fraction": _fraction(sibling_pairs, sibling_denominator)
            if sibling_pairs is not None else None,
            "distinct_structural_outcomes": distinct_value,
            "evidence_state": diversity_state,
        },
        "native_effort": {"value": effort_value, "unit": effort_unit,
                           "state": "OBSERVED" if effort_value is not None else "MISSING"},
        "budget_response": {},
        "structural_change": summary["structural_change"].get(arm_id),
        "displacement": summary["minimum_image_displacement"].get(arm_id),
        "failure_topology": dict(summary["failure_topology"].get(arm_id, {})),
    }
    return {
        "arm_id": arm_id,
        "operator_name": detail["operator_name"],
        "operator_version": detail["operator_version"],
        "budget": detail.get("budget"),
        "counts": counts_projection,
        "dimensions": dimensions,
        "_diversity_state": diversity_state,
        "_useful_share": useful_share,
        "_effort_value": effort_value,
        "_effort_unit": effort_unit,
        "_family_observed": family_observed,
        "_structural_change_observed": _has_observed_values(
            summary["structural_change"].get(arm_id)
        ),
        "_displacement_observed": _has_observed_values(
            summary["minimum_image_displacement"].get(arm_id)
        ),
    }


def _lane_assessment(row, policy):
    dims = row["dimensions"]
    useful_yield = dims["yield"]["useful_over_attempted"]
    coverage = dims["parent_coverage"]["fraction"]
    geometry = dims["geometry_failure"]["fraction"]
    exhaustion = dims["exhaustion"]["fraction"]
    share = row["_useful_share"]
    siblings = dims["diversity"]["within_arm_sibling_duplicate_pairs"]
    effort_missing = row["_effort_value"] is None
    state = row["_diversity_state"]
    diversity_ok = (
        policy["allow_missing_diversity"] if state == "MISSING"
        else _STATE_ORDER[state] >= _STATE_ORDER[policy["minimum_diversity_evidence_state"]]
    )
    checks = (
        ("PARENT_COVERAGE_UNDEFINED_OR_LOW", coverage is not None
         and coverage >= policy["minimum_parent_coverage_fraction"]),
        ("USEFUL_YIELD_UNDEFINED_OR_LOW", useful_yield is not None
         and useful_yield >= policy["minimum_useful_yield_fraction"]),
        ("GEOMETRY_FAILURE_UNDEFINED_OR_HIGH", geometry is not None
         and geometry <= policy["maximum_geometry_failure_fraction"]),
        ("EXHAUSTION_UNDEFINED_OR_HIGH", exhaustion is not None
         and exhaustion <= policy["maximum_exhaustion_fraction"]),
        ("USEFUL_CONCENTRATION_MISSING_OR_HIGH", share is not None
         and share <= policy["maximum_useful_parent_share"]),
        ("SIBLING_DUPLICATION_MISSING_OR_HIGH",
         (siblings is None and state == "MISSING" and policy["allow_missing_diversity"])
         or (siblings is not None
             and siblings <= policy["maximum_sibling_duplicate_pairs"])),
        ("DIVERSITY_EVIDENCE_INSUFFICIENT", diversity_ok),
        ("FAMILY_COVERAGE_MISSING", row["_family_observed"]
         or policy["allow_missing_family_coverage"]),
        ("STRUCTURAL_CHANGE_MISSING", row["_structural_change_observed"]
         or policy["allow_missing_structural_change"]),
        ("DISPLACEMENT_MISSING", row["_displacement_observed"]
         or policy["allow_missing_displacement"]),
        ("NATIVE_EFFORT_MISSING", not effort_missing
         or policy["allow_missing_effort"]),
        ("NATIVE_EFFORT_INCOMPARABLE", not row["_effort_incomparable"]
         or policy["allow_incomparable_effort"]),
    )
    reasons = [name for name, passed in checks if not passed]
    minimum_recovery = policy["minimum_marginal_useful_recovery"]
    if minimum_recovery > 0:
        response = dims["budget_response"]
        incoming_state = response["incoming_marginal_state"]
        if incoming_state == "MISSING":
            reasons.append("MARGINAL_RECOVERY_MISSING")
        elif incoming_state == "OBSERVED" and (
            response["incoming_marginal"]["newly_useful"] < minimum_recovery
        ):
            reasons.append("MARGINAL_RECOVERY_LOW")
        # NOT_APPLICABLE is a structural absence, distinct from missing data.
    return not reasons, reasons


def _pareto_dimensions(row):
    d = row["dimensions"]
    return {
        "yield": (d["yield"]["useful_over_attempted"], True),
        "survival": (d["survival"]["generated_over_attempted"], True),
        "novelty": (d["novelty"]["novel_over_attempted"], True),
        "geometry_failure": (d["geometry_failure"]["fraction"], False),
        "exhaustion": (d["exhaustion"]["fraction"], False),
        "parent_coverage": (d["parent_coverage"]["fraction"], True),
        "useful_concentration": (row["_useful_share"], False),
        "sibling_duplication": (d["diversity"]["sibling_duplicate_fraction"], False),
        "distinct_structural_outcomes": (d["diversity"]["distinct_structural_outcomes"]["value"], True),
        # Required descriptor evidence with no justified monotonic direction.
        "family_coverage": (None, None),
        "structural_change": (None, None),
        "displacement": (None, None),
    }


def _compare(left, right):
    comparisons = {}
    has_better = has_worse = has_incomparable = False
    left_metrics, right_metrics = _pareto_dimensions(left), _pareto_dimensions(right)
    for name in left_metrics:
        a, maximize = left_metrics[name]
        b, _ = right_metrics[name]
        if name == "native_effort":
            continue
        if name in {"family_coverage", "structural_change", "displacement"}:
            left_value = left["dimensions"][name]
            right_value = right["dimensions"][name]
            left_observed = (left["_family_observed"] if name == "family_coverage"
                             else left[f"_{name}_observed"])
            right_observed = (right["_family_observed"] if name == "family_coverage"
                              else right[f"_{name}_observed"])
            if not left_observed or not right_observed:
                comparisons[name] = "MISSING"
                has_incomparable = True
            elif name == "family_coverage":
                left_support = _family_support_signature(left_value)
                right_support = _family_support_signature(right_value)
                if left_support is None or right_support is None:
                    comparisons[name] = "MISSING"
                    has_incomparable = True
                elif left_support == right_support:
                    comparisons[name] = "EQUAL"
                else:
                    comparisons[name] = "INCOMPARABLE"
                    has_incomparable = True
            elif left_value == right_value:
                comparisons[name] = "EQUAL"
            else:
                comparisons[name] = "INCOMPARABLE"
                has_incomparable = True
            continue
        if a is None or b is None:
            comparisons[name] = "MISSING"
            has_incomparable = True
            continue
        if a == b:
            status = "EQUAL"
        else:
            better = a > b if maximize else a < b
            status = "BETTER" if better else "WORSE"
            has_better |= better
            has_worse |= not better
        comparisons[name] = status

    a, b = left["_effort_value"], right["_effort_value"]
    if a is None or b is None:
        comparisons["native_effort"] = "MISSING"
        has_incomparable = True
    elif left["_effort_unit"] != right["_effort_unit"]:
        comparisons["native_effort"] = "INCOMPARABLE"
        has_incomparable = True
    elif a == b:
        comparisons["native_effort"] = "EQUAL"
    else:
        status = "BETTER" if a < b else "WORSE"
        comparisons["native_effort"] = status
        has_better |= status == "BETTER"
        has_worse |= status == "WORSE"
    dominates = has_better and not has_worse and not has_incomparable
    incomparable = has_incomparable or (has_better and has_worse)
    return comparisons, dominates, incomparable


def _nested_budget_links(order):
    """Map adjacent declared local budgets by parsed identity, never substrings."""
    local = []
    for arm_id in order:
        prefix = "GAUSSIAN_LOCAL_D"
        if arm_id.startswith(prefix) and arm_id[len(prefix):].isdigit():
            local.append((int(arm_id[len(prefix):]), arm_id))
    local.sort()
    links = {}
    for index, (budget, arm_id) in enumerate(local):
        incoming = (f"D{local[index - 1][0]}_TO_D{budget}"
                    if index else None)
        outgoing = (f"D{budget}_TO_D{local[index + 1][0]}"
                    if index + 1 < len(local) else None)
        links[arm_id] = incoming, outgoing
    return links


def _directional_marginal(key, analysis_marginals, summary_response):
    if key is None:
        return None, "NOT_APPLICABLE"
    data = analysis_marginals.get(key)
    if data is None:
        data = summary_response.get(key)
    if not isinstance(data, Mapping):
        return None, "MISSING"
    value = data.get("newly_useful")
    if type(value) is not int or value < 0:
        return None, "MISSING"
    return {**data, "transition": key}, "OBSERVED"


def build_candidate_supply_v2_pareto_evidence(evidence, *, lane_policy):
    """Project reconciled tournament aggregates into explicit Pareto evidence.

    ``lane_policy`` must provide both EXPLORATION and EXPLOITATION policy
    thresholds. These thresholds describe hypothetical analytical eligibility;
    the returned booleans never authorize execution or downstream science.
    """
    _validate_policy(lane_policy)
    metadata, summary, order, details = _validate_evidence(evidence)
    detail_by_id = {item["id"]: item for item in details}
    rows = []
    limitations = {}
    for arm_id in order:
        row = _arm_projection(arm_id, detail_by_id[arm_id], summary)
        rows.append(row)
        if row["_diversity_state"] != "COMPLETE":
            limitations["distinct_structural_outcomes"] = "MISSING"
        family = row["dimensions"]["family_coverage"]
        if family == {"state": "MISSING", "value": None} or "UNAVAILABLE" in family:
            limitations["family_coverage"] = "PARTIAL"

    marginals = evidence.get("analysis", {}).get("budget_marginals", {})
    if not isinstance(marginals, Mapping):
        raise ValueError("invalid budget marginals")
    marginals_out = {key: dict(value) for key, value in marginals.items()}
    links = _nested_budget_links(order)
    response = summary.get("gaussian_local_budget_response", {})
    response = _mapping(response, "Gaussian local budget response")
    arms_response = _mapping(response.get("arms", {}), "Gaussian local arm response")
    for row in rows:
        arm_id = row["arm_id"]
        incoming_key, outgoing_key = links.get(arm_id, (None, None))
        incoming, incoming_state = _directional_marginal(
            incoming_key, marginals_out, response
        )
        outgoing, outgoing_state = _directional_marginal(
            outgoing_key, marginals_out, response
        )
        row["dimensions"]["budget_response"] = {
            "arm": dict(arms_response.get(arm_id, {})),
            "marginals": {incoming_key: dict(incoming)} if incoming is not None else {},
            "incoming_marginal": incoming,
            "incoming_marginal_state": incoming_state,
            "outgoing_marginal": outgoing,
            "outgoing_marginal_state": outgoing_state,
        }
        row["_effort_incomparable"] = any(
            other["arm_id"] != arm_id
            and row["_effort_value"] is not None
            and other["_effort_value"] is not None
            and row["_effort_unit"] != other["_effort_unit"]
            for other in rows
        )
        assessments = {
            lane: _lane_assessment(row, lane_policy[lane])
            for lane in ("EXPLORATION", "EXPLOITATION")
        }
        row["lane_eligibility"] = {
            lane: eligible for lane, (eligible, _) in assessments.items()
        }
        row["lane_eligibility_reasons"] = {
            lane: reasons for lane, (_, reasons) in assessments.items()
        }

    relations = {}
    for left in rows:
        aid = left["arm_id"]
        dominates, dominated_by, incomparable_with, detail = [], [], [], {}
        for right in rows:
            bid = right["arm_id"]
            if aid == bid:
                continue
            comparisons, left_dominates, is_incomparable = _compare(left, right)
            detail[bid] = comparisons
            if left_dominates:
                dominates.append(bid)
            if is_incomparable:
                incomparable_with.append(bid)
        # Reverse dominance is computed symmetrically to avoid inferred ranking.
        for other in rows:
            bid = other["arm_id"]
            if aid != bid and aid in _dominates_ids(other, rows):
                dominated_by.append(bid)
        relations[aid] = {
            "dominates": dominates,
            "dominated_by": dominated_by,
            "incomparable_with": incomparable_with,
            "dimension_comparisons": detail,
        }

    # Replace internal work fields and emit only observational evidence.
    clean_rows = []
    for row in rows:
        clean_rows.append({key: value for key, value in row.items()
                           if not key.startswith("_")})
    return {
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "authorization": {key: False for key in _AUTHORIZATION},
        "metadata": {
            "schema_version": "candidate-supply-v2-pareto-evidence-v1",
            "source_schema_version": evidence.get("schema_version"),
            "ordered_parent_ids": list(metadata["ordered_parent_ids"]),
            "novelty_matcher_version": metadata.get("novelty_matcher_version"),
        },
        "arm_order": list(order),
        "arms": clean_rows,
        "pareto_relations": relations,
        "nondominated_arm_ids": [arm_id for arm_id in order
                                 if not relations[arm_id]["dominated_by"]],
        "lane_policy": {lane: dict(values) for lane, values in lane_policy.items()},
        "budget_marginals": marginals_out,
        "limitations": limitations,
    }


def _dominates_ids(candidate, rows):
    result = []
    for other in rows:
        if candidate["arm_id"] == other["arm_id"]:
            continue
        if _compare(candidate, other)[1]:
            result.append(other["arm_id"])
    return result


def _required_mapping(parent, key, path):
    if key not in parent:
        raise ValueError(f"missing required tournament section: {path}")
    value = parent[key]
    if not isinstance(value, Mapping):
        raise ValueError(f"invalid tournament section {path}: expected a mapping")
    return value


def _family_sources_agree(panel_diversity, analysis_family, arm_order):
    """Reject disagreement only when both family views contain observations."""
    def valid(value):
        return isinstance(value, Mapping) and _has_observed_values(value)

    for arm_id in arm_order:
        panel_arm = panel_diversity.get(arm_id)
        if panel_arm is not None and not isinstance(panel_arm, Mapping):
            raise ValueError(f"invalid panel family evidence for {arm_id}")
        panel_has = isinstance(panel_arm, Mapping) and "family_coverage" in panel_arm
        analysis_has = arm_id in analysis_family
        if analysis_has and not isinstance(analysis_family[arm_id], Mapping):
            raise ValueError(f"invalid analysis family evidence for {arm_id}")
        if panel_has and analysis_has:
            if (valid(panel_arm["family_coverage"])
                    and valid(analysis_family[arm_id])
                    and panel_arm["family_coverage"] != analysis_family[arm_id]):
                raise ValueError(f"family coverage sources disagree for {arm_id}")


def normalize_candidate_supply_v2_tournament_evidence(artifact):
    """Explicitly project a real tournament artifact into Pareto builder input.

    The real artifact stores its generation panel under ``panel`` and some
    analytical summaries under ``analysis``. This adapter maps only those
    documented sections; it performs no scientific recomputation or
    imputation.
    """
    artifact = _mapping(artifact, "tournament artifact")
    for key in ("artifact_type", "validation_state", "integrity", "panel", "analysis"):
        if key not in artifact:
            raise ValueError(f"missing required tournament section: {key}")
    panel = _required_mapping(artifact, "panel", "panel")
    panel_authorization = _required_mapping(panel, "authorization", "panel.authorization")
    metadata = _required_mapping(panel, "metadata", "panel.metadata")
    panel_summary = _required_mapping(panel, "summary", "panel.summary")
    analysis = _required_mapping(artifact, "analysis", "analysis")
    parent_coverage = _required_mapping(
        analysis, "parent_coverage", "analysis.parent_coverage"
    )
    analysis_family = copy.deepcopy(analysis.get("family_coverage", {}))
    if not isinstance(analysis_family, Mapping):
        raise ValueError("invalid tournament section analysis.family_coverage")
    marginals = _required_mapping(
        analysis, "gaussian_local_marginals", "analysis.gaussian_local_marginals"
    )
    if artifact["artifact_type"] != "OBSERVATIONAL_DIAGNOSTIC":
        raise ValueError("invalid tournament artifact_type")
    if artifact["validation_state"] != "RECONCILED":
        raise ValueError("tournament evidence is not reconciled")
    panel_schema = panel.get("schema_version")
    if not isinstance(panel_schema, str) or not panel_schema:
        raise ValueError("missing required tournament section: panel.schema_version")
    configurations = metadata.get("configurations")
    if not isinstance(configurations, list) or not configurations:
        raise ValueError("missing declared arm order in panel.metadata.configurations")

    summary_sections = (
        "arms", "effort", "diversity", "concentration", "failure_topology",
        "gaussian_local_budget_response", "minimum_image_displacement",
        "prefix_audit", "structural_change",
    )
    normalized_summary = {}
    for section in summary_sections:
        normalized_summary[section] = copy.deepcopy(
            _required_mapping(panel_summary, section, f"panel.summary.{section}")
        )
    normalized_summary["parent_coverage"] = copy.deepcopy(parent_coverage)

    diversity = normalized_summary["diversity"]
    _family_sources_agree(diversity, analysis_family, configurations)
    for arm_id in configurations:
        panel_arm = diversity.get(arm_id)
        if panel_arm is not None and not isinstance(panel_arm, Mapping):
            raise ValueError(f"invalid panel diversity evidence for {arm_id}")
        if panel_arm is None:
            panel_arm = {}
            diversity[arm_id] = panel_arm
        panel_has = "family_coverage" in panel_arm
        analysis_has = arm_id in analysis_family
        panel_value = panel_arm.get("family_coverage")
        analysis_value = analysis_family.get(arm_id)
        panel_valid = panel_has and _has_observed_values(panel_value)
        analysis_valid = analysis_has and _has_observed_values(analysis_value)
        if panel_valid and not analysis_valid:
            analysis_family[arm_id] = copy.deepcopy(panel_value)
        elif analysis_valid and not panel_valid:
            panel_arm["family_coverage"] = copy.deepcopy(analysis_value)
        elif not panel_has and not analysis_has:
            missing = {"state": "MISSING", "value": None}
            panel_arm["family_coverage"] = copy.deepcopy(missing)
            analysis_family[arm_id] = copy.deepcopy(missing)

    normalized = {
        "schema_version": panel_schema,
        "artifact_type": copy.deepcopy(artifact["artifact_type"]),
        "validation_state": copy.deepcopy(artifact["validation_state"]),
        "integrity": copy.deepcopy(_required_mapping(artifact, "integrity", "integrity")),
        "metadata": copy.deepcopy(metadata),
        "authorization": copy.deepcopy(panel_authorization),
        "summary": normalized_summary,
        "analysis": {
            "budget_marginals": copy.deepcopy(marginals),
            "family_coverage": copy.deepcopy(analysis_family),
        },
    }
    if "provenance" in artifact:
        normalized["provenance"] = copy.deepcopy(artifact["provenance"])

    # Apply the builder's existing fail-closed contract before returning.
    _validate_evidence(normalized)
    return normalized
