"""Pure, fail-closed translation of scheduler activation into a runtime plan.

This module describes allocated work only. It never schedules or generates
materials; execution remains a separate, explicitly authorized operation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping


_ACTIVATION_SCHEMA = "candidate-supply-v2-scheduler-activation-v1"
_POLICY_SCHEMA = "candidate-supply-v2-scheduler-policy-v1"
_PARETO_SCHEMA = "candidate-supply-v2-pareto-report-v1"
_PLAN_SCHEMA = "candidate-supply-v2-scheduler-runtime-plan-v1"
_LANES = ("EXPLORATION", "EXPLOITATION")
_ARMS = (
    "BASELINE_GAUSSIAN",
    "BOUNDED_GAUSSIAN_A8",
    "GAUSSIAN_LOCAL_D4",
    "GAUSSIAN_LOCAL_D8",
    "GAUSSIAN_LOCAL_D16",
)
_UNIT_SEMANTICS = "ONE_OPERATOR_PARENT_CHILD_REQUEST"
_PARENT_ASSIGNMENT_RULE = "DETERMINISTIC_HASH_BREADTH_FIRST_V1"
_PARENT_ASSIGNMENT_DOMAIN = (
    "rhombus.candidate-supply-v2.parent-assignment/"
    "DETERMINISTIC_HASH_BREADTH_FIRST_V1"
)
_CANONICAL_PARENT_ID = re.compile(r"^[a-z][a-z0-9_-]*:[a-z0-9][a-z0-9._-]*$")
_SCIENTIFIC_AUTHORIZATION = (
    "operator_superiority_authorized",
    "optimal_budget_authorized",
    "downstream_diffusion_claim_authorized",
)


def _mapping(value, label):
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _digest(value):
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _canonical_sha256(value, label):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 identity")
    return value


def _parent_permutation(parent_ids, cohort_identity, policy_identity):
    def rank(parent_id):
        return _digest({
            "domain": _PARENT_ASSIGNMENT_DOMAIN,
            "cohort_canonical_content_identity": cohort_identity,
            "policy_canonical_content_identity": policy_identity,
            "canonical_parent_id": parent_id,
        })

    return sorted(parent_ids, key=lambda parent_id: (rank(parent_id), parent_id))


def _expected_operator_identity(arm, target_species):
    if arm == "BASELINE_GAUSSIAN":
        return {
            "operator_name": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "parameters": {"mobile_ion": target_species, "sigma_A_provisional": 0.30},
        }
    if arm == "BOUNDED_GAUSSIAN_A8":
        return {
            "operator_name": "mobile-ion-displace-clearance",
            "operator_version": "mobile-ion-displace-clearance-v1",
            "parameters": {
                "mobile_ion": target_species,
                "sigma_A_provisional": 0.30,
                "max_attempts": 8,
            },
        }
    budget = {"GAUSSIAN_LOCAL_D4": 4, "GAUSSIAN_LOCAL_D8": 8,
              "GAUSSIAN_LOCAL_D16": 16}.get(arm)
    if budget is not None:
        return {
            "operator_name": "mobile-ion-local-clearance-gaussian-radius",
            "operator_version": "mobile-ion-local-clearance-gaussian-radius-v1",
            "parameters": {
                "mobile_ion": target_species,
                "sigma_A_provisional": 0.30,
                "max_direction_trials": budget,
            },
        }
    raise ValueError(f"unsupported activated arm: {arm}")


def _validate_activation(activation):
    activation = _mapping(activation, "activation artifact")
    if activation.get("schema_version") != _ACTIVATION_SCHEMA:
        raise ValueError("unsupported activation schema")
    if activation.get("artifact_type") != "CANDIDATE_SUPPLY_SCHEDULER_ACTIVATION":
        raise ValueError("invalid activation artifact type")
    if activation.get("validation_state") != "ACTIVATED":
        raise ValueError("activation artifact is not activated")

    auth = _mapping(activation.get("authorization"), "authorization")
    if auth.get("scheduler_activation_authorized") is not True:
        raise ValueError("scheduler activation is not authorized")
    if any(auth.get(field) is not False for field in _SCIENTIFIC_AUTHORIZATION):
        raise ValueError("scientific superiority/downstream claims must remain unauthorized")

    source = _mapping(activation.get("source"), "activation source")
    if source.get("pareto_report_schema_version") != _PARETO_SCHEMA:
        raise ValueError("unsupported Pareto source schema")
    _text(source.get("diagnostic_config_hash"), "diagnostic config hash")
    arm_order = source.get("arm_order")
    if arm_order != list(_ARMS):
        raise ValueError("unsupported or noncanonical activated arm order")

    policy_identity = _mapping(
        activation.get("source_policy_identity"), "source policy identity"
    )
    if policy_identity.get("schema_version") != _POLICY_SCHEMA:
        raise ValueError("unsupported source policy schema")
    for field in ("content_sha256", "source_diagnostic_config_hash"):
        _text(policy_identity.get(field), f"source policy {field}")
    if policy_identity.get("source_pareto_report_schema_version") != _PARETO_SCHEMA:
        raise ValueError("source policy Pareto schema mismatch")
    if policy_identity["source_diagnostic_config_hash"] != source["diagnostic_config_hash"]:
        raise ValueError("source policy diagnostic identity mismatch")

    lanes = _mapping(activation.get("lanes"), "activation lanes")
    if set(lanes) != set(_LANES):
        raise ValueError("activation lane schema mismatch")
    clean_lanes = {}
    total = 0
    for lane in _LANES:
        record = _mapping(lanes[lane], f"{lane} lane")
        quota = record.get("quota")
        if type(quota) is not int or quota < 0:
            raise ValueError(f"invalid {lane} quota")
        participants = record.get("participants")
        if (not isinstance(participants, list) or
                len(set(participants)) != len(participants) or
                any(arm not in _ARMS for arm in participants)):
            raise ValueError(f"invalid {lane} participants")
        allocations = _mapping(record.get("allocations"), f"{lane} allocations")
        if set(allocations) != set(participants):
            raise ValueError(f"{lane} allocation/participant mismatch")
        if any(type(value) is not int or value < 0 for value in allocations.values()):
            raise ValueError(f"invalid {lane} allocation value")
        if sum(allocations.values()) != quota:
            raise ValueError(f"{lane} quota conservation mismatch")
        clean_lanes[lane] = {"quota": quota, "participants": copy.deepcopy(participants),
                             "allocations": copy.deepcopy(dict(allocations))}
        total += quota
    if type(activation.get("total_allocation_units")) is not int or activation[
        "total_allocation_units"
    ] != total:
        raise ValueError("total allocation conservation mismatch")
    return source, policy_identity, clean_lanes, total


def build_candidate_supply_v2_scheduler_runtime_plan(
    activation_artifact, *, runtime_config
):
    """Validate activation and return a deterministic, non-executing work plan."""
    source, policy_identity, lanes, total = _validate_activation(activation_artifact)
    config = _mapping(runtime_config, "runtime config")

    activation_identity = _mapping(config.get("activation_identity"), "activation identity")
    expected_activation_identity = {
        "schema_version": _ACTIVATION_SCHEMA,
        "content_sha256": _digest(activation_artifact),
    }
    if dict(activation_identity) != expected_activation_identity:
        raise ValueError("activation content identity mismatch")

    cohort = _mapping(config.get("parent_cohort_identity"), "parent cohort identity")
    cohort_id = _text(cohort.get("cohort_id"), "cohort id")
    parent_ids = cohort.get("ordered_parent_ids")
    if (not isinstance(parent_ids, list) or not parent_ids or
            any(not isinstance(parent_id, str) or
                _CANONICAL_PARENT_ID.fullmatch(parent_id) is None
                for parent_id in parent_ids) or
            len(set(parent_ids)) != len(parent_ids)):
        raise ValueError("invalid ordered parent cohort")
    if parent_ids != sorted(parent_ids):
        raise ValueError("ordered parent cohort must use canonical lexical ordering")
    cohort_identity = _canonical_sha256(
        cohort.get("canonical_content_sha256"), "cohort canonical content identity"
    )
    parent_count = cohort.get("parent_count")
    if type(parent_count) is not int or parent_count != len(parent_ids):
        raise ValueError("parent cohort count does not reconcile")
    if type(config.get("root_seed")) is not int:
        raise ValueError("root_seed must be an integer")
    generation_hash = _text(config.get("generation_config_hash"), "generation config hash")
    target_species = _text(config.get("target_species"), "target species")

    registry = _mapping(config.get("operator_registry"), "operator registry")
    if set(registry) != set(_ARMS):
        raise ValueError("operator registry must map every supported arm exactly once")
    identities = []
    for arm in _ARMS:
        identity = _mapping(registry[arm], f"{arm} operator identity")
        expected = _expected_operator_identity(arm, target_species)
        if dict(identity) != expected:
            raise ValueError(f"invalid executable operator identity for {arm}")
        identities.append(_digest(identity))
    if len(set(identities)) != len(identities):
        raise ValueError("ambiguous executable operator mapping")

    mapping = _mapping(config.get("allocation_unit_mapping"), "allocation unit mapping")
    if mapping.get("semantics") != _UNIT_SEMANTICS:
        raise ValueError("allocation unit semantics must be explicit")
    if type(mapping.get("children_per_work_item")) is not int or mapping[
        "children_per_work_item"
    ] != 1:
        raise ValueError("each allocation unit must request exactly one child")
    policy_digest = _canonical_sha256(
        policy_identity.get("content_sha256"), "source policy canonical content identity"
    )
    parent_order = _parent_permutation(parent_ids, cohort_identity, policy_digest)
    allocation_units = []
    for lane in _LANES:
        for arm in _ARMS:
            for unit_index in range(lanes[lane]["allocations"].get(arm, 0)):
                allocation_units.append((lane, arm, unit_index))

    work_items = []
    for index, (lane, arm, unit_index) in enumerate(allocation_units):
        parent_id = parent_order[index % len(parent_order)]
        parent_index = parent_ids.index(parent_id)
        seed = config["root_seed"] + parent_index
        operator_identity = copy.deepcopy(dict(registry[arm]))
        allocation_unit_id = _digest({
            "domain": "rhombus.candidate-supply-v2.allocation-unit/v1",
            "policy_canonical_content_identity": policy_digest,
            "lane": lane,
            "arm_id": arm,
            "unit_index": unit_index,
        })
        seed_material = {
            "parent_id": parent_id,
            "seed": seed,
            "operator_name": operator_identity["operator_name"],
            "operator_version": operator_identity["operator_version"],
            "generation_config_hash": generation_hash,
            "allocation_unit_id": allocation_unit_id,
        }
        work_item_identity = _digest([
            activation_identity,
            policy_digest,
            cohort_identity,
            allocation_unit_id,
            lane,
            arm,
            operator_identity,
            parent_id,
            _PARENT_ASSIGNMENT_RULE,
        ])
        work_items.append({
            "work_item_id": f"{index:06d}-{work_item_identity[:16]}",
            "work_item_index": index,
            "allocation_unit_id": allocation_unit_id,
            "allocation_unit_index": unit_index,
            "lane": lane,
            "arm_id": arm,
            "parent_id": parent_id,
            "seed": seed,
            "seed_material": seed_material,
            "operator_rng_identity": _digest(seed_material),
            "operator_identity": operator_identity,
            "allocation_unit_semantics": _UNIT_SEMANTICS,
            "parent_assignment_rule": _PARENT_ASSIGNMENT_RULE,
            "parent_cohort_identity": {
                "cohort_id": cohort_id,
                "canonical_content_sha256": cohort_identity,
                "parent_count": parent_count,
            },
            "source_activation_identity": copy.deepcopy(dict(activation_identity)),
            "source_policy_identity": copy.deepcopy(dict(policy_identity)),
            "source_diagnostic_config_hash": source["diagnostic_config_hash"],
        })

    supplied_items = mapping.get("work_items")
    if supplied_items is not None and supplied_items != work_items:
        raise ValueError("caller work_items do not match derived runtime-plan work items")

    plan = {
        "schema_version": _PLAN_SCHEMA,
        "artifact_type": "CANDIDATE_SUPPLY_V2_SCHEDULER_RUNTIME_PLAN",
        "execution_performed": False,
        "source_activation_identity": copy.deepcopy(dict(activation_identity)),
        "source_policy_identity": copy.deepcopy(dict(policy_identity)),
        "source_diagnostic_config_hash": source["diagnostic_config_hash"],
        "parent_cohort_identity": {
            "cohort_id": cohort_id,
            "canonical_content_sha256": cohort_identity,
            "parent_count": parent_count,
            "ordered_parent_ids": copy.deepcopy(parent_ids),
        },
        "parent_assignment": {
            "rule": _PARENT_ASSIGNMENT_RULE,
            "domain": _PARENT_ASSIGNMENT_DOMAIN,
            "parent_permutation": parent_order,
        },
        "root_seed": config["root_seed"],
        "generation_config_hash": generation_hash,
        "lanes": copy.deepcopy(lanes),
        "total_allocation_units": total,
        "allocation_unit_mapping": {
            "semantics": _UNIT_SEMANTICS,
            "children_per_work_item": 1,
        },
        "work_items": work_items,
        "authorization": copy.deepcopy(dict(activation_artifact["authorization"])),
    }
    plan["manifest_identity"] = _digest(plan)
    return plan
