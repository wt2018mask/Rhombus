"""Pure validation and authorization boundary for a candidate-supply policy."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping


_POLICY_SCHEMA = "candidate-supply-v2-scheduler-policy-v1"
_PARETO_SCHEMA = "candidate-supply-v2-pareto-report-v1"
_ACTIVATION_SCHEMA = "candidate-supply-v2-scheduler-activation-v1"
_LANES = ("EXPLORATION", "EXPLOITATION")
_AUTHORIZATION = (
    "scheduler_activation_authorized",
    "operator_superiority_authorized",
    "optimal_budget_authorized",
    "downstream_diffusion_claim_authorized",
)
_SCIENTIFIC_AUTHORIZATION = (
    "operator_superiority_authorized",
    "optimal_budget_authorized",
    "downstream_diffusion_claim_authorized",
)
_IDENTITY_FIELDS = (
    "schema_version",
    "content_sha256",
    "source_pareto_report_schema_version",
    "source_diagnostic_config_hash",
)


def _mapping(value, name):
    if not isinstance(value, Mapping):
        raise ValueError(f"invalid {name}: expected a mapping")
    return value


def _nonempty_string(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid {name}: expected a non-empty string")
    return value


def _policy_digest(policy_artifact):
    canonical = json.dumps(
        policy_artifact,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_policy(policy_artifact):
    policy = _mapping(policy_artifact, "policy artifact")
    if policy.get("schema_version") != _POLICY_SCHEMA:
        raise ValueError("unsupported or missing scheduler policy schema")
    if policy.get("artifact_type") != "CANDIDATE_SUPPLY_POLICY":
        raise ValueError("invalid scheduler policy artifact_type")
    if policy.get("validation_state") != "PRE_ACTIVATION":
        raise ValueError("policy is not a pre-activation artifact")

    authorization = _mapping(policy.get("authorization"), "policy authorization")
    if set(authorization) != set(_AUTHORIZATION):
        raise ValueError("policy authorization schema mismatch")
    if any(type(authorization.get(key)) is not bool for key in _AUTHORIZATION):
        raise ValueError("policy authorization values must be booleans")
    if authorization["scheduler_activation_authorized"] is not False:
        raise ValueError("pre-activation policy must not authorize scheduler execution")
    if any(authorization[key] is not False for key in _SCIENTIFIC_AUTHORIZATION):
        raise ValueError("policy cannot authorize scientific claims")

    source = _mapping(policy.get("source"), "policy source")
    if source.get("pareto_report_schema_version") != _PARETO_SCHEMA:
        raise ValueError("unsupported or missing source Pareto report schema")
    _nonempty_string(source.get("diagnostic_config_hash"), "diagnostic config hash")
    arm_order = source.get("arm_order")
    if (not isinstance(arm_order, list) or not arm_order
            or any(not isinstance(arm, str) or not arm for arm in arm_order)
            or len(set(arm_order)) != len(arm_order)):
        raise ValueError("invalid policy source arm order")
    eligibility = _mapping(source.get("lane_eligibility"), "lane eligibility")
    if set(eligibility) != set(_LANES):
        raise ValueError("source lane eligibility schema mismatch")
    for lane in _LANES:
        lane_eligibility = _mapping(eligibility[lane], f"{lane} eligibility")
        if set(lane_eligibility) != set(arm_order) or any(
            type(lane_eligibility[arm]) is not bool for arm in arm_order
        ):
            raise ValueError(f"invalid {lane} eligibility evidence")

    configuration = _mapping(policy.get("configuration"), "policy configuration")
    total = configuration.get("total_allocation_units")
    if type(total) is not int or total < 0:
        raise ValueError("invalid total allocation units")
    configured_quotas = _mapping(configuration.get("lane_quotas"), "lane quotas")
    if set(configured_quotas) != set(_LANES):
        raise ValueError("lane quota schema mismatch")
    quotas = {}
    for lane in _LANES:
        quota = configured_quotas[lane]
        if type(quota) is not int or quota < 0:
            raise ValueError(f"invalid {lane} quota")
        quotas[lane] = quota
    if sum(quotas.values()) != total:
        raise ValueError("overall allocation conservation mismatch")

    lanes = _mapping(policy.get("lanes"), "policy lanes")
    if set(lanes) != set(_LANES):
        raise ValueError("policy lane schema mismatch")
    for lane in _LANES:
        lane_record = _mapping(lanes[lane], f"{lane} lane")
        if lane_record.get("quota") != quotas[lane] or type(
            lane_record.get("quota")
        ) is not int:
            raise ValueError(f"{lane} lane quota mismatch")
        participants = lane_record.get("participants")
        if (not isinstance(participants, list)
                or any(not isinstance(arm, str) for arm in participants)
                or len(set(participants)) != len(participants)):
            raise ValueError(f"invalid {lane} participants")
        allocations = _mapping(lane_record.get("allocations"), f"{lane} allocations")
        if set(allocations) != set(participants):
            raise ValueError(f"{lane} participants and allocation arms differ")
        if any(arm not in arm_order for arm in allocations):
            raise ValueError(f"unknown arm in {lane} allocations")
        if any(not eligibility[lane][arm] for arm in participants):
            raise ValueError(f"ineligible arm participates in {lane}")
        for arm, units in allocations.items():
            if type(units) is not int or units <= 0:
                raise ValueError(f"invalid allocation units for {lane} {arm}")
        if sum(allocations.values()) != quotas[lane]:
            raise ValueError(f"{lane} allocation conservation mismatch")

    limitations = _mapping(policy.get("limitations"), "policy limitations")
    for key in _SCIENTIFIC_AUTHORIZATION:
        if limitations.get(key) is True:
            raise ValueError("policy limitations cannot authorize scientific claims")
    evidence = _mapping(policy.get("evidence"), "policy evidence")
    _mapping(evidence.get("budget_marginals"), "budget marginals")
    _mapping(evidence.get("pareto_evidence_limitations"),
             "Pareto evidence limitations")
    _mapping(evidence.get("report_limitations"), "report limitations")

    return policy, source, total, quotas, lanes, limitations


def _validate_activation_request(policy, source, activation_request):
    request = _mapping(activation_request, "activation request")
    if set(request) != {"activation_requested", "source_policy_identity"}:
        raise ValueError("activation request schema mismatch")
    if request.get("activation_requested") is not True:
        raise ValueError("explicit activation request is required")

    identity = _mapping(request.get("source_policy_identity"),
                        "source policy identity")
    if set(identity) != set(_IDENTITY_FIELDS):
        raise ValueError("source policy identity schema mismatch")
    expected_identity = {
        "schema_version": _POLICY_SCHEMA,
        "content_sha256": _policy_digest(policy),
        "source_pareto_report_schema_version": source[
            "pareto_report_schema_version"
        ],
        "source_diagnostic_config_hash": source["diagnostic_config_hash"],
    }
    for field in _IDENTITY_FIELDS:
        if identity.get(field) != expected_identity[field]:
            raise ValueError(f"activation request policy identity mismatch: {field}")


def build_candidate_supply_v2_scheduler_activation(
    policy_artifact,
    *,
    activation_request,
):
    """Build a deterministic activated plan without executing scheduler work."""

    policy, source, total, quotas, lanes, limitations = _validate_policy(
        policy_artifact
    )
    _validate_activation_request(policy, source, activation_request)

    activated_authorization = {
        "scheduler_activation_authorized": True,
        "operator_superiority_authorized": False,
        "optimal_budget_authorized": False,
        "downstream_diffusion_claim_authorized": False,
    }
    activated_limitations = copy.deepcopy(dict(limitations))
    if "scheduler_activation_authorized" in activated_limitations:
        activated_limitations["scheduler_activation_authorized"] = True

    return {
        "schema_version": _ACTIVATION_SCHEMA,
        "artifact_type": "CANDIDATE_SUPPLY_SCHEDULER_ACTIVATION",
        "validation_state": "ACTIVATED",
        "source_policy_identity": copy.deepcopy(
            activation_request["source_policy_identity"]
        ),
        "source": copy.deepcopy(dict(source)),
        "activation_request": copy.deepcopy(dict(activation_request)),
        "lanes": copy.deepcopy(dict(lanes)),
        "total_allocation_units": total,
        "authorization": activated_authorization,
        "limitations": activated_limitations,
        "evidence": copy.deepcopy(dict(policy["evidence"])),
    }
