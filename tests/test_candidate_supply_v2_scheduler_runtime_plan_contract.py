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
            "content_sha256": "a" * 64,
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


def _operator_registry(target_species="Li"):
    return {
        "BASELINE_GAUSSIAN": {
            "operator_name": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "parameters": {"mobile_ion": target_species, "sigma_A_provisional": 0.30},
        },
        "BOUNDED_GAUSSIAN_A8": {
            "operator_name": "mobile-ion-displace-clearance",
            "operator_version": "mobile-ion-displace-clearance-v1",
            "parameters": {
                "mobile_ion": target_species,
                "sigma_A_provisional": 0.30,
                "max_attempts": 8,
            },
        },
        **{
            f"GAUSSIAN_LOCAL_D{budget}": {
                "operator_name": "mobile-ion-local-clearance-gaussian-radius",
                "operator_version": "mobile-ion-local-clearance-gaussian-radius-v1",
                "parameters": {
                    "mobile_ion": target_species,
                    "sigma_A_provisional": 0.30,
                    "max_direction_trials": budget,
                },
            }
            for budget in (4, 8, 16)
        },
    }


def _runtime_config(activation, parent_ids=None, target_species="Li"):
    parent_ids = parent_ids or ["synthetic:parent-a", "synthetic:parent-b"]
    return {
        "activation_identity": {
            "schema_version": activation["schema_version"],
            "content_sha256": _digest(activation),
        },
        "parent_cohort_identity": {
            "cohort_id": "fresh-synthetic-cohort-v1",
            "canonical_content_sha256": _digest({
                "cohort_id": "fresh-synthetic-cohort-v1",
                "ordered_parent_ids": parent_ids,
            }),
            "parent_count": len(parent_ids),
            "ordered_parent_ids": parent_ids,
        },
        "root_seed": 73,
        "generation_config_hash": "generation-config-fixture",
        "target_species": target_species,
        "operator_registry": _operator_registry(target_species),
        "allocation_unit_mapping": {
            "semantics": ALLOCATION_UNIT_SEMANTICS,
            "children_per_work_item": 1,
        },
    }


def _set_lane_allocations(activation, exploration, exploitation):
    allocations = {
        "EXPLORATION": exploration,
        "EXPLOITATION": exploitation,
    }
    for lane, arm_allocations in allocations.items():
        ordered = {arm: arm_allocations.get(arm, 0) for arm in ARM_ORDER}
        activation["lanes"][lane] = {
            "quota": sum(ordered.values()),
            "participants": [arm for arm in ARM_ORDER if ordered[arm] > 0],
            "allocations": {arm: units for arm, units in ordered.items() if units > 0},
        }
    activation["total_allocation_units"] = sum(
        activation["lanes"][lane]["quota"] for lane in LANES
    )
    return activation


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
    assert plan["manifest_identity"] == _digest(
        {key: value for key, value in plan.items() if key != "manifest_identity"}
    )
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


def test_runtime_plan_target_species_is_explicit_and_species_neutral():
    activation = _activation_fixture()
    config = _runtime_config(activation, target_species="Na")
    plan = _build(activation, config)
    assert all(
        item["operator_identity"]["parameters"]["mobile_ion"] == "Na"
        for item in plan["work_items"]
    )

    missing_species = _runtime_config(activation)
    del missing_species["target_species"]
    with pytest.raises(ValueError, match="target species"):
        _build(activation, missing_species)


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


def test_parent_assignment_is_derived_without_caller_work_items():
    activation = _activation_fixture()
    config = _runtime_config(activation)

    assert "work_items" not in config["allocation_unit_mapping"]
    plan = _build(activation, config)
    assert len(plan["work_items"]) == activation["total_allocation_units"]
    assert all(item["parent_id"] in config["parent_cohort_identity"][
        "ordered_parent_ids"] for item in plan["work_items"])


def test_hash_breadth_first_assignment_covers_breadth_before_parent_reuse():
    activation = _set_lane_allocations(
        _activation_fixture(),
        {"BASELINE_GAUSSIAN": 7},
        {},
    )
    parents = ["synthetic:parent-a", "synthetic:parent-b", "synthetic:parent-c"]
    config = _runtime_config(activation, parents)
    plan = _build(activation, config)

    assigned = [item["parent_id"] for item in plan["work_items"]]
    counts = {parent: assigned.count(parent) for parent in parents}
    assert sorted(counts.values()) == [2, 2, 3]
    assert len(set(assigned[:3])) == 3
    assert plan["parent_assignment"]["rule"] == (
        "DETERMINISTIC_HASH_BREADTH_FIRST_V1"
    )
    assert plan["parent_assignment"]["parent_permutation"][:3] == assigned[:3]


def test_fewer_units_than_parents_selects_hash_permuted_breadth_without_reuse():
    activation = _set_lane_allocations(
        _activation_fixture(),
        {"BASELINE_GAUSSIAN": 3},
        {},
    )
    parents = [f"synthetic:parent-{letter}" for letter in "abcde"]
    plan = _build(activation, _runtime_config(activation, parents))
    assigned = [item["parent_id"] for item in plan["work_items"]]

    assert len(assigned) == 3
    assert len(set(assigned)) == 3
    assert set(assigned).issubset(parents)
    assert sum(parent not in assigned for parent in parents) == 2
    assert all(count == 1 for count in (assigned.count(parent) for parent in assigned))
    assert assigned == plan["parent_assignment"]["parent_permutation"][:3]


def test_assignment_and_runtime_identity_are_deterministic_for_identical_inputs():
    activation = _activation_fixture()
    config = _runtime_config(activation)
    first = _build(activation, config)
    second = _build(activation, config)

    assert first["parent_assignment"] == second["parent_assignment"]
    assert first["work_items"] == second["work_items"]
    assert first["manifest_identity"] == second["manifest_identity"]


def test_cohort_identity_is_bound_into_assignment_and_plan_identity():
    activation = _activation_fixture()
    config = _runtime_config(activation)
    first = _build(activation, config)
    changed = copy.deepcopy(config)
    changed["parent_cohort_identity"]["canonical_content_sha256"] = "b" * 64
    second = _build(activation, changed)

    assert first["parent_assignment"]["parent_permutation"] != second[
        "parent_assignment"]["parent_permutation"
    ] or first["manifest_identity"] != second["manifest_identity"]
    assert first["manifest_identity"] != second["manifest_identity"]


def test_policy_identity_is_bound_into_assignment_and_plan_identity():
    activation = _activation_fixture()
    config = _runtime_config(activation)
    first = _build(activation, config)
    changed_activation = copy.deepcopy(activation)
    changed_activation["source_policy_identity"]["content_sha256"] = "c" * 64
    changed_config = _runtime_config(changed_activation)
    second = _build(changed_activation, changed_config)

    assert first["parent_assignment"]["parent_permutation"] != second[
        "parent_assignment"]["parent_permutation"
    ] or first["manifest_identity"] != second["manifest_identity"]
    assert first["manifest_identity"] != second["manifest_identity"]


@pytest.mark.parametrize(
    "parent_ids, parent_count",
    [
        (["synthetic:parent-a", "synthetic:parent-a"], 2),
        (["synthetic:parent-A"], 1),
        (["synthetic:parent-a", "synthetic:parent-b"], 3),
        (["synthetic:parent-b", "synthetic:parent-a"], 2),
    ],
)
def test_invalid_parent_cohort_fails_closed(parent_ids, parent_count):
    activation = _activation_fixture()
    config = _runtime_config(activation, parent_ids)
    config["parent_cohort_identity"]["parent_count"] = parent_count
    with pytest.raises((TypeError, ValueError)):
        _build(activation, config)


def test_caller_work_items_are_only_an_exact_assertion_path():
    activation = _activation_fixture()
    config = _runtime_config(activation)
    expected = _build(activation, config)
    asserted = copy.deepcopy(config)
    asserted["allocation_unit_mapping"]["work_items"] = expected["work_items"]
    assert _build(activation, asserted) == expected

    asserted["allocation_unit_mapping"]["work_items"][0]["parent_id"] = (
        "synthetic:parent-b"
        if asserted["allocation_unit_mapping"]["work_items"][0]["parent_id"]
        == "synthetic:parent-a" else "synthetic:parent-a"
    )
    with pytest.raises((TypeError, ValueError), match="do not match derived"):
        _build(activation, asserted)


def test_assignment_preserves_arm_and_lane_unit_counts():
    activation = _activation_fixture()
    plan = _build(activation, _runtime_config(activation))

    assert len(plan["work_items"]) == activation["total_allocation_units"]
    for lane in LANES:
        assert sum(item["lane"] == lane for item in plan["work_items"]) == (
            activation["lanes"][lane]["quota"]
        )
        for arm, count in activation["lanes"][lane]["allocations"].items():
            assert sum(item["lane"] == lane and item["arm_id"] == arm
                       for item in plan["work_items"]) == count
