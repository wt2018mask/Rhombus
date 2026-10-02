"""Deterministic, non-authorizing allocation plan from Pareto evidence."""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping


_LANES = ("EXPLORATION", "EXPLOITATION")
_SUPPORTED_PARETO_REPORT_SCHEMA_VERSION = "candidate-supply-v2-pareto-report-v1"
_AUTHORIZATION = (
    "scheduler_activation_authorized",
    "operator_superiority_authorized",
    "optimal_budget_authorized",
    "downstream_diffusion_claim_authorized",
)
_SOURCE_AUTHORIZATION = (
    "scheduler_activation", "p1_eligibility", "operator_superiority",
    "automatic_promotion", "sigma_selection", "budget_selection",
    "parent_exclusion", "chemistry_exclusion",
    "downstream_diffusion_claim", "threshold_modification",
)


def _mapping(value, name):
    if not isinstance(value, Mapping):
        raise ValueError(f"invalid {name}: expected a mapping")
    return value


def _all_false(mapping, keys, name):
    missing = [key for key in keys if key not in mapping]
    if missing:
        raise ValueError(f"{name} authorization keys missing: {', '.join(missing)}")
    if any(value is not False for value in mapping.values()):
        raise ValueError(f"{name} authorization must remain all false")


def _positive_identity(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing or invalid source identity: {name}")
    return value


def _integer(value, name, *, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"invalid {name}: expected integer >= {minimum}")
    return value


def _validate_inputs(report, config):
    report = _mapping(report, "Pareto report")
    config = _mapping(config, "policy_config")
    if report.get("artifact_type") != "OBSERVATIONAL_DIAGNOSTIC":
        raise ValueError("invalid Pareto report artifact_type")
    if report.get("validation_state") != "RECONCILED":
        raise ValueError("Pareto report is not validated/reconciled")
    schema = _positive_identity(report.get("schema_version"), "Pareto report schema")
    if schema != _SUPPORTED_PARETO_REPORT_SCHEMA_VERSION:
        raise ValueError(f"unsupported Pareto report schema: {schema}")
    source = _mapping(report.get("source"), "Pareto report source")
    if (source.get("artifact_type") != "OBSERVATIONAL_DIAGNOSTIC"
            or source.get("validation_state") != "RECONCILED"):
        raise ValueError("invalid Pareto report source provenance")
    diagnostic_hash = _positive_identity(
        source.get("diagnostic_config_hash"), "diagnostic_config_hash"
    )
    order = source.get("configured_arm_order")
    if (not isinstance(order, list) or not order
            or any(not isinstance(item, str) or not item for item in order)
            or len(set(order)) != len(order)):
        raise ValueError("invalid source configured arm order")

    evidence = _mapping(report.get("pareto_evidence"), "Pareto evidence")
    if evidence.get("artifact_type") != "OBSERVATIONAL_DIAGNOSTIC":
        raise ValueError("invalid Pareto evidence artifact type")
    _all_false(_mapping(evidence.get("authorization"), "Pareto evidence"),
               _SOURCE_AUTHORIZATION, "Pareto evidence")
    _all_false(_mapping(report.get("authorization"), "report"),
               _AUTHORIZATION, "Pareto report")
    limits = _mapping(report.get("limitations"), "report limitations")
    if any(value is True for value in limits.values()
           if "authorized" in str(value).lower()):
        raise ValueError("report limitation indicates authorization")

    arm_order = evidence.get("arm_order")
    if arm_order != order:
        raise ValueError("Pareto evidence arm order does not match source identity")
    arms = evidence.get("arms")
    if not isinstance(arms, list) or [row.get("arm_id") for row in arms
                                     if isinstance(row, Mapping)] != order:
        raise ValueError("Pareto report arm rows do not match source arm order")
    arm_by_id = {}
    for row in arms:
        _mapping(row, "Pareto arm")
        eligibility = _mapping(row.get("lane_eligibility"), "lane eligibility")
        for lane in _LANES:
            if type(eligibility.get(lane)) is not bool:
                raise ValueError(f"invalid lane eligibility for {row.get('arm_id')} {lane}")
        arm_by_id[row["arm_id"]] = row
    return report, config, schema, source, diagnostic_hash, order, evidence, limits, arm_by_id


def _apportion(quota, weights, minimum=0):
    """Largest-remainder integer apportionment, with lexical tie-breaking."""
    ids = sorted(weights)
    if not ids:
        if quota:
            raise ValueError("required lane has no eligible arms")
        return {}
    if quota < minimum * len(ids):
        raise ValueError("quota cannot satisfy minimum exploration representation")
    allocation = {arm_id: minimum for arm_id in ids}
    remaining = quota - minimum * len(ids)
    total = sum(weights.values())
    if total <= 0 or not math.isfinite(total):
        raise ValueError("eligible lane has no positive allocation weight")
    exact = {arm_id: remaining * weights[arm_id] / total for arm_id in ids}
    for arm_id in ids:
        whole = math.floor(exact[arm_id])
        allocation[arm_id] += whole
    left = quota - sum(allocation.values())
    order = sorted(ids, key=lambda arm_id: (-(exact[arm_id] % 1), arm_id))
    for arm_id in order[:left]:
        allocation[arm_id] += 1
    return {arm_id: units for arm_id, units in allocation.items() if units > 0}


def _arm_weights(lane, eligible, arms, config):
    supplied = _mapping(config["lane_weights"].get(lane), f"{lane} lane weights")
    weights = {}
    for arm_id in eligible:
        weight = supplied.get(arm_id)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise ValueError(f"missing/invalid configured weight for {lane} {arm_id}")
        weight = float(weight)
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError(f"invalid configured weight for {lane} {arm_id}")
        if lane == "EXPLOITATION":
            dims = _mapping(arms[arm_id].get("dimensions"), f"dimensions for {arm_id}")
            yield_dims = _mapping(dims.get("yield"), f"yield for {arm_id}")
            coverage_dims = _mapping(dims.get("parent_coverage"), f"coverage for {arm_id}")
            evidence_values = []
            for field in config["exploitation_evidence_fields"]:
                if field == "useful_over_attempted":
                    value = yield_dims.get(field)
                elif field == "useful_parent_coverage":
                    useful = coverage_dims.get(field)
                    attempted = coverage_dims.get("attempted_eligible_parents")
                    value = (useful / attempted if type(useful) is int
                             and type(attempted) is int and attempted > 0 else None)
                else:
                    raise ValueError(f"unsupported exploitation evidence field: {field}")
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value) or value < 0):
                    raise ValueError(f"missing/invalid exploitation evidence: {field}")
                evidence_values.append(float(value))
            weight *= sum(evidence_values) / len(evidence_values)
        weights[arm_id] = weight
    return weights


def build_candidate_supply_v2_scheduler_policy(pareto_report, *, policy_config):
    """Build a deterministic allocation plan; never activates or runs a scheduler."""
    (report, config, schema, source, diagnostic_hash, arm_order, evidence,
     limitations, arms) = _validate_inputs(pareto_report, policy_config)

    total = _integer(config.get("total_allocation_units"), "total allocation units")
    quotas = _mapping(config.get("lane_quotas"), "lane quotas")
    if set(quotas) != set(_LANES):
        raise ValueError("lane quotas must specify exactly EXPLORATION and EXPLOITATION")
    quotas = {lane: _integer(quotas[lane], f"{lane} quota") for lane in _LANES}
    if sum(quotas.values()) != total:
        raise ValueError("quota conservation mismatch")
    minimum = _integer(config.get("minimum_exploration_units_per_participant"),
                       "minimum exploration units per participant")
    for name in ("only_lane_eligible_arms", "allow_unallocated_reserve"):
        if type(config.get(name)) is not bool:
            raise ValueError(f"invalid policy config {name}")
    if config["allow_unallocated_reserve"]:
        raise ValueError("reserve allocation semantics are not defined by this policy contract")
    if config.get("empty_lane_behavior") != "ERROR":
        raise ValueError("empty lanes must fail closed")
    if config.get("rounding_rule") != "LARGEST_REMAINDER_ARM_ID_ASCENDING":
        raise ValueError("unsupported deterministic rounding rule")
    if config.get("marginal_evidence_handling") != "PRESERVE_DIRECTIONAL_NO_BUDGET_SELECTION":
        raise ValueError("marginals must be preserved without budget selection")
    evidence_fields = config.get("exploitation_evidence_fields")
    if (not isinstance(evidence_fields, list) or not evidence_fields
            or "useful_over_attempted" not in evidence_fields
            or "useful_parent_coverage" not in evidence_fields
            or any("novel" in str(field).lower() and "useful" not in str(field).lower()
                   for field in evidence_fields)):
        raise ValueError("exploitation requires useful yield and useful-parent coverage evidence")

    lanes = {}
    eligibility_source = {}
    for lane in _LANES:
        eligible = [arm_id for arm_id in arm_order
                    if arms[arm_id]["lane_eligibility"][lane]]
        if not eligible:
            raise ValueError(f"required lane {lane} has no eligible arms")
        if config["only_lane_eligible_arms"]:
            participants = eligible
        else:
            participants = list(arm_order)
        if any(not arms[arm_id]["lane_eligibility"][lane] for arm_id in participants):
            raise ValueError(f"ineligible arm included in {lane}")
        weights = _arm_weights(lane, participants, arms, config)
        minimum_for_lane = minimum if lane == "EXPLORATION" else 0
        allocations = _apportion(quotas[lane], weights, minimum_for_lane)
        lanes[lane] = {
            "quota": quotas[lane],
            "participants": [arm_id for arm_id in arm_order if arm_id in allocations],
            "allocations": {arm_id: allocations[arm_id] for arm_id in arm_order
                            if arm_id in allocations},
        }
        eligibility_source[lane] = {
            arm_id: arms[arm_id]["lane_eligibility"][lane] for arm_id in arm_order
        }

    if sum(lane["quota"] for lane in lanes.values()) != total:
        raise ValueError("lane quota does not equal total units")
    for lane in _LANES:
        if sum(lanes[lane]["allocations"].values()) != lanes[lane]["quota"]:
            raise ValueError(f"{lane} allocation does not conserve its quota")

    marginals = copy.deepcopy(evidence.get("budget_marginals"))
    if not isinstance(marginals, Mapping):
        raise ValueError("missing or malformed directional budget marginals")
    return {
        "schema_version": "candidate-supply-v2-scheduler-policy-v1",
        "artifact_type": "CANDIDATE_SUPPLY_POLICY",
        "validation_state": "PRE_ACTIVATION",
        "source": {
            "pareto_report_schema_version": schema,
            "diagnostic_config_hash": diagnostic_hash,
            "arm_order": copy.deepcopy(arm_order),
            "lane_eligibility": eligibility_source,
        },
        "configuration": copy.deepcopy(dict(config)),
        "lanes": lanes,
        "authorization": {key: False for key in _AUTHORIZATION},
        "limitations": copy.deepcopy(dict(limitations)),
        "evidence": {
            "pareto_relations": copy.deepcopy(evidence.get("pareto_relations")),
            "budget_marginals": dict(marginals),
            "report_limitations": copy.deepcopy(dict(limitations)),
            "per_arm": {
                arm_id: {
                    "useful_over_attempted": copy.deepcopy(
                        arms[arm_id].get("dimensions", {}).get("yield", {}).get(
                            "useful_over_attempted")
                    ),
                    "useful_parent_coverage": copy.deepcopy(
                        arms[arm_id].get("dimensions", {}).get("parent_coverage", {}).get(
                            "useful_parent_coverage")
                    ),
                    "native_effort_value": copy.deepcopy(
                        arms[arm_id].get("dimensions", {}).get("native_effort", {}).get("value")
                    ),
                    "native_effort_unit": copy.deepcopy(
                        arms[arm_id].get("dimensions", {}).get("native_effort", {}).get("unit")
                    ),
                }
                for arm_id in arm_order
            },
            "incomparable_effort_units_preserved": True,
        },
    }
