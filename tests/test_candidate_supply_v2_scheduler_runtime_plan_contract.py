"""RED contract for translating scheduler activation into a pure runtime plan."""

import copy
import hashlib
import importlib
import json

import pytest


ACTIVATION_SCHEMA = "candidate-supply-v2-scheduler-activation-v1"
POLICY_SCHEMA = "candidate-supply-v2-scheduler-policy-v1"
PARETO_SCHEMA = "candidate-supply-v2-pareto-report-v1"
ARM_ORDER = (
    "BASELINE_GAUSSIAN",
    "BOUNDED_GAUSSIAN_A8",
    "GAUSSIAN_LOCAL_D4",
    "GAUSSIAN_LOCAL_D8",
    "GAUSSIAN_LOCAL_D16",
)
LANES = ("EXPLORATION", "EXPLOITATION")
ALLOCATION_UNIT_SEMANTICS = "ONE_OPERATOR_PARENT_CHILD_REQUEST"


def _digest(value):
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _activation_fixture():
    allocations = {lane: {arm: 1 for arm in ARM_ORDER} for lane in LANES}
    return {
        "schema_version": ACTIVATION_SCHEMA,
        "artifact_type": "CANDIDATE_SUPPLY_SCHEDULER_ACTIVATION",
        "validation_state": "ACTIVATED",
        "source_policy_identity": {
            "schema_version": POLICY_SCHEMA,
            "content_sha256": "policy-content-digest-fixture",
            "source_pareto_report_schema_version": PARETO_SCHEMA,
            "source_diagnostic_config_hash": "diagnostic-config-fixture",
        },
        "source": {
            "pareto_report_schema_version": PARETO_SCHEMA,
            "diagnostic_config_hash": "diagnostic-config-fixture",
            "arm_order": list(ARM_ORDER),
        },
        "activation_request": {"activation_requested": True},
        "lanes": {
            lane: {
                "quota": 5,
                "participants": list(ARM_ORDER),
                "allocations": dict(allocations[lane]),
            }
            for lane in LANES
        },
        "total_allocation_units": 10,
        "authorization": {
            "scheduler_activation_authorized": True,
            "operator_superiority_authorized": False,
            "optimal_budget_authorized": False,
            "downstream_diffusion_claim_authorized": False,
        },
        "limitations": {
            "observational_only": True,
            "full_structural_diversity_available": False,
            "operator_superiority_authorized": False,
            "optimal_budget_authorized": False,
            "downstream_diffusion_claim_authorized": False,
        },
        "evidence": {
            "incomparable_effort_units_preserved": True,
            "per_arm": {
                arm: {
                    "diversity": {
                        "evidence_state": "PARTIAL",
                        "distinct_structural_outcomes": {
                            "state": "MISSING",
                            "value": None,
                        },
                    },
                    "native_effort_unit": (
                        "PER_SITE_DIRECTION_TRIALS"
                        if arm.startswith("GAUSSIAN_LOCAL_")
                        else "COMPLETE_GAUSSIAN_PROPOSAL_ATTEMPTS"
                    ),
                }
                for arm in ARM_ORDER
            },
        },
    }


def _operator_registry():
    return {
        "BASELINE_GAUSSIAN": {
            "operator_name": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "parameters": {"mobile_ion": "Li", "sigma_A_provisional": 0.30},
        },
        "BOUNDED_GAUSSIAN_A8": {
            "operator_name": "mobile-ion-displace-clearance",
            "operator_version": "mobile-ion-displace-clearance-v1",
            "parameters": {
                "mobile_ion": "Li",
                "sigma_A_provisional": 0.30,
                "max_attempts": 8,
            },
        },
        **{
            f"GAUSSIAN_LOCAL_D{budget}": {
                "operator_name": "mobile-ion-local-clearance-gaussian-radius",
                "operator_version": "mobile-ion-local-clearance-gaussian-radius-v1",
                "parameters": {
                    "mobile_ion": "Li",
                    "sigma_A_provisional": 0.30,
                    "max_direction_trials": budget,
                },
            }
            for budget in (4, 8, 16)
        },
    }


def _runtime_config(activation):
    parent_ids = ["synthetic:parent-a", "synthetic:parent-b"]
    work_items = []
    for lane in LANES:
        for arm in ARM_ORDER:
            work_items.append({
                "lane": lane,
                "arm_id": arm,
                "parent_id": parent_ids[len(work_items) % len(parent_ids)],
            })
    return {
        "activation_identity": {
            "schema_version": activation["schema_version"],
            "content_sha256": _digest(activation),
        },
        "parent_cohort_identity": {
            "cohort_id": "fresh-synthetic-cohort-v1",
            "ordered_parent_ids": parent_ids,
        },
        "root_seed": 73,
        "generation_config_hash": "generation-config-fixture",
        "operator_registry": _operator_registry(),
        "allocation_unit_mapping": {
            "semantics": ALLOCATION_UNIT_SEMANTICS,
            "children_per_work_item": 1,
            "work_items": work_items,
        },
    }


def _builder():
    module = importlib.import_module(
        "rudeus.generation.candidate_supply_runtime_plan"
    )
    return module.build_candidate_supply_v2_scheduler_runtime_plan


def _build(activation=None, runtime_config=None):
    activation = activation or _activation_fixture()
    runtime_config = runtime_config or _runtime_config(activation)
    return _builder()(activation, runtime_config=runtime_config)


def test_preactivation_policy_is_not_accepted_as_runtime_authority():
    policy_like = _activation_fixture()
    policy_like["schema_version"] = POLICY_SCHEMA
    policy_like["validation_state"] = "PRE_ACTIVATION"
    with pytest.raises((TypeError, ValueError)):
        _build(policy_like)


def test_missing_activation_authorization_fails_closed():
    activation = _activation_fixture()
    del activation["authorization"]["scheduler_activation_authorized"]
    with pytest.raises((TypeError, ValueError)):
        _build(activation)


def test_false_scheduler_activation_authorization_fails_closed():
    activation = _activation_fixture()
    activation["authorization"]["scheduler_activation_authorized"] = False
    with pytest.raises((TypeError, ValueError)):
        _build(activation)


@pytest.mark.parametrize(
    "field",
    [
        "operator_superiority_authorized",
        "optimal_budget_authorized",
        "downstream_diffusion_claim_authorized",
    ],
)
def test_scientific_authorization_true_fails_closed(field):
    activation = _activation_fixture()
    activation["authorization"][field] = True
    with pytest.raises((TypeError, ValueError)):
        _build(activation)


@pytest.mark.parametrize("schema_change", ["missing", "unsupported"])
def test_missing_or_malformed_activation_schema_fails_closed(schema_change):
    activation = _activation_fixture()
    config = _runtime_config(activation)
    if schema_change == "missing":
        del activation["schema_version"]
    else:
        activation["schema_version"] = "candidate-supply-v2-scheduler-activation-v99"
        config = _runtime_config(activation)
    with pytest.raises((TypeError, ValueError)):
        _build(activation, config)


def test_activation_content_identity_mismatch_fails_closed():
    activation = _activation_fixture()
    config = _runtime_config(activation)
    config["activation_identity"]["content_sha256"] = "0" * 64
    with pytest.raises((TypeError, ValueError)):
        _build(activation, config)


def test_lane_allocation_conservation_mismatch_fails_closed():
    activation = _activation_fixture()
    activation["lanes"]["EXPLORATION"]["allocations"][ARM_ORDER[0]] = 2
    config = _runtime_config(activation)
    config["activation_identity"]["content_sha256"] = _digest(activation)
    with pytest.raises((TypeError, ValueError)):
        _build(activation, config)


def test_unknown_activated_arm_fails_closed():
    activation = _activation_fixture()
    lane = activation["lanes"]["EXPLORATION"]
    lane["allocations"]["UNKNOWN_ARM"] = 1
    lane["participants"].append("UNKNOWN_ARM")
    lane["quota"] += 1
    activation["total_allocation_units"] += 1
    config = _runtime_config(activation)
    config["activation_identity"]["content_sha256"] = _digest(activation)
    config["allocation_unit_mapping"]["work_items"].append({
        "lane": "EXPLORATION",
        "arm_id": "UNKNOWN_ARM",
        "parent_id": "synthetic:parent-a",
    })
    with pytest.raises((TypeError, ValueError)):
        _build(activation, config)


def test_missing_executable_arm_mapping_fails_closed():
    activation = _activation_fixture()
    config = _runtime_config(activation)
    del config["operator_registry"]["GAUSSIAN_LOCAL_D4"]
    with pytest.raises((TypeError, ValueError)):
        _build(activation, config)


def test_ambiguous_executable_operator_mapping_fails_closed():
    activation = _activation_fixture()
    config = _runtime_config(activation)
    config["operator_registry"]["BOUNDED_GAUSSIAN_A8"] = copy.deepcopy(
        config["operator_registry"]["BASELINE_GAUSSIAN"]
    )
    with pytest.raises((TypeError, ValueError)):
        _build(activation, config)


def test_missing_runtime_config_fails_closed():
    with pytest.raises((TypeError, ValueError)):
        _builder()(_activation_fixture())


def test_missing_explicit_parent_cohort_identity_fails_closed():
    activation = _activation_fixture()
    config = _runtime_config(activation)
    del config["parent_cohort_identity"]
    with pytest.raises((TypeError, ValueError)):
        _build(activation, config)


@pytest.mark.parametrize(
    "mapping_change",
    [
        ("semantics", "UNSPECIFIED_UNITS"),
        ("children_per_work_item", 2),
    ],
)
def test_allocation_unit_meaning_must_be_explicit_and_one_child(mapping_change):
    activation = _activation_fixture()
    config = _runtime_config(activation)
    key, value = mapping_change
    config["allocation_unit_mapping"][key] = value
    with pytest.raises((TypeError, ValueError)):
        _build(activation, config)


def test_valid_runtime_config_preserves_exact_lane_allocations_and_provenance():
    activation = _activation_fixture()
    config = _runtime_config(activation)
    plan = _build(activation, config)

    assert plan["lanes"]["EXPLORATION"]["allocations"] == {
        arm: 1 for arm in ARM_ORDER
    }
    assert plan["lanes"]["EXPLOITATION"]["allocations"] == {
        arm: 1 for arm in ARM_ORDER
    }
    assert plan["lanes"]["EXPLORATION"]["quota"] == 5
    assert plan["lanes"]["EXPLOITATION"]["quota"] == 5
    assert plan["total_allocation_units"] == 10
    assert plan["allocation_unit_mapping"]["semantics"] == (
        ALLOCATION_UNIT_SEMANTICS
    )
    assert plan["allocation_unit_mapping"]["children_per_work_item"] == 1
    assert plan["parent_cohort_identity"] == config["parent_cohort_identity"]
    assert plan["generation_config_hash"] == config["generation_config_hash"]
    assert len(plan["work_items"]) == 10
    assert {item["lane"] for item in plan["work_items"]} == set(LANES)
    assert all("arm_id" in item and "operator_identity" in item
               and "parent_id" in item and "seed_material" in item
               for item in plan["work_items"])
    for lane in LANES:
        planned_counts = {
            arm: sum(
                item["lane"] == lane and item["arm_id"] == arm
                for item in plan["work_items"]
            )
            for arm in ARM_ORDER
        }
        assert planned_counts == plan["lanes"][lane]["allocations"]
    for item in plan["work_items"]:
        assert item["operator_identity"] == config["operator_registry"][
            item["arm_id"]
        ]
        assert item["allocation_unit_semantics"] == ALLOCATION_UNIT_SEMANTICS
    assert plan["source_activation_identity"]["content_sha256"] == _digest(
        activation
    )
    assert plan["source_policy_identity"] == activation["source_policy_identity"]
    assert plan["source_diagnostic_config_hash"] == (
        activation["source"]["diagnostic_config_hash"]
    )


def test_every_work_item_carries_enclosing_source_provenance():
    activation = _activation_fixture()
    plan = _build(activation, _runtime_config(activation))

    assert plan["work_items"]
    for item in plan["work_items"]:
        assert item["source_activation_identity"] == plan[
            "source_activation_identity"
        ]
        assert item["source_policy_identity"] == plan["source_policy_identity"]
        assert item["source_diagnostic_config_hash"] == plan[
            "source_diagnostic_config_hash"
        ]


def test_runtime_plan_and_seed_material_are_deterministic_for_same_inputs():
    activation = _activation_fixture()
    config = _runtime_config(activation)
    first = _build(activation, config)
    second = _build(activation, config)

    assert first == second
    assert [item["seed_material"] for item in first["work_items"]] == [
        item["seed_material"] for item in second["work_items"]
    ]


def test_activation_and_runtime_config_are_immutable_and_plan_is_detached():
    activation = _activation_fixture()
    config = _runtime_config(activation)
    before_activation = copy.deepcopy(activation)
    before_config = copy.deepcopy(config)
    plan = _build(activation, config)

    assert activation == before_activation
    assert config == before_config

    plan["lanes"]["EXPLORATION"]["allocations"][ARM_ORDER[0]] += 1
    plan["source_policy_identity"]["content_sha256"] = "mutated-plan-copy"
    plan["work_items"][0]["operator_identity"]["operator_version"] = "mutated"
    assert activation == before_activation
    assert config == before_config


def test_runtime_plan_construction_has_no_scheduler_or_generation_side_effects(
    monkeypatch,
):
    from rudeus.generation import generator, scheduler

    def forbidden(*args, **kwargs):
        raise AssertionError("runtime-plan construction invoked runtime work")

    monkeypatch.setattr(scheduler, "schedule_candidate_supply_v2", forbidden)
    monkeypatch.setattr(scheduler, "execute_candidate_supply_v2_for_parent", forbidden)
    monkeypatch.setattr(scheduler, "execute_candidate_supply_v2_cohort", forbidden)
    monkeypatch.setattr(generator, "generate_children", forbidden)
    monkeypatch.setattr(generator, "op_displace", forbidden)
    monkeypatch.setattr(generator, "op_mobile_ion_displace_v2", forbidden)
    monkeypatch.setattr(generator, "op_mobile_ion_displace_clearance_v1", forbidden)
    monkeypatch.setattr(
        generator, "op_mobile_ion_local_clearance_gaussian_radius_v1", forbidden
    )

    _build()
