"""Contract for explicit, evidence-backed fresh parent cohorts."""

import copy
import importlib

import pytest


SCHEMA = "candidate-supply-v2-fresh-parent-cohort-v1"


def _parents():
    from rudeus.generation.generator import ParentRecord

    return [
        ParentRecord(
            parent_id=f"obelix:{suffix}",
            source_dataset="obelix",
            source_ref=suffix,
            composition="LiFePO4",
            structure=None,
            structure_sha256=f"structure-digest-{suffix}",
            conductivity=conductivity,
            chemical_family="oxide",
            perturbable=False,
            provenance={"source": "synthetic-fixture", "nested": {"ref": suffix}},
        )
        for suffix, conductivity in (("a", 0.1), ("b", 9.0), ("c", 0.5))
    ]


def _source_identity():
    return {
        "source_dataset": "obelix",
        "source_schema_version": "synthetic-parent-source-v1",
        "source_artifact_id": "synthetic-source-fixture",
        "content_sha256": "source-universe-digest-fixture",
        "ordered_parent_ids": ["obelix:a", "obelix:b", "obelix:c"],
    }


def _exclusions(*, wave_status="UNRESOLVED", diagnostic_ids=None, wave_ids=None):
    return [
        {
            "cohort_id": "diagnostic-72",
            "kind": "DIAGNOSTIC_TOURNAMENT",
            "status": "COMPLETE",
            "ordered_parent_ids": list(
                diagnostic_ids if diagnostic_ids is not None
                else ["obelix:diagnostic-only"]
            ),
            "source_identity": {"artifact": "diagnostic-panel-fixture"},
        },
        {
            "cohort_id": "ordered-expansion-wave1",
            "kind": "HISTORICAL_GENERATION",
            "status": wave_status,
            "ordered_parent_ids": list(
                wave_ids if wave_ids is not None
                else ["obelix:wave1-only"]
            ) if wave_status == "COMPLETE" else [],
            "source_identity": {"artifact": "wave1-records-fixture"},
        },
    ]


def _cohort_config(parent_ids=None):
    return {
        "cohort_id": "synthetic-fresh-cohort-v1",
        "ordered_parent_ids": list(parent_ids or ["obelix:b", "obelix:a"]),
        "required_exclusion_sources": [
            "diagnostic-72", "ordered-expansion-wave1"
        ],
        "selection_rule": {
            "policy_id": "caller-supplied-ordered-parent-ids-v1",
            "description": "Use the explicit ordered IDs supplied by the caller.",
        },
        "selection_config_identity": {
            "schema_version": "fresh-cohort-selection-config-v1",
            "content_sha256": "selection-config-digest-fixture",
        },
    }


def _builder():
    module = importlib.import_module(
        "rudeus.generation.fresh_parent_cohort"
    )
    return module.build_candidate_supply_v2_fresh_parent_cohort_manifest


def _build(parents=None, *, exclusions=None, config=None, source=None):
    return _builder()(
        parents if parents is not None else _parents(),
        source_identity=source if source is not None else _source_identity(),
        exclusion_evidence=(
            exclusions if exclusions is not None else _exclusions()
        ),
        cohort_config=config if config is not None else _cohort_config(),
    )


def test_fresh_parent_cohort_manifest_api_exists():
    assert callable(_builder())


def test_duplicate_selected_parent_ids_fail_closed():
    with pytest.raises((TypeError, ValueError)):
        _build(config=_cohort_config(["obelix:a", "obelix:a"]))


def test_selected_parent_absent_from_bound_source_fails_closed():
    with pytest.raises((TypeError, ValueError)):
        _build(config=_cohort_config(["obelix:not-in-source"]))


def test_overlap_with_complete_diagnostic_72_exclusion_fails_closed():
    exclusions = _exclusions(diagnostic_ids=["obelix:b"])
    with pytest.raises((TypeError, ValueError)):
        _build(exclusions=exclusions)


def test_overlap_with_complete_historical_use_exclusion_fails_closed():
    exclusions = _exclusions(wave_status="COMPLETE")
    exclusions[1]["ordered_parent_ids"] = ["obelix:b"]
    with pytest.raises((TypeError, ValueError)):
        _build(exclusions=exclusions)


def test_unresolved_exclusion_evidence_is_visible_and_not_fully_verified():
    manifest = _build()
    assert manifest["freshness"]["verification_state"] == "UNRESOLVED"
    assert manifest["freshness"]["freshness_fully_verified"] is False
    assert manifest["exclusion_evidence"][1]["cohort_id"] == "ordered-expansion-wave1"
    assert manifest["exclusion_evidence"][1]["status"] == "UNRESOLVED"


@pytest.mark.parametrize("status", ["PARTIAL", "UNRESOLVED"])
def test_incomplete_required_source_cannot_certify_full_freshness(status):
    manifest = _build(exclusions=_exclusions(wave_status=status))
    assert manifest["freshness"]["verification_state"] == status
    assert manifest["freshness"]["freshness_fully_verified"] is False


def test_missing_required_source_is_visible_and_prevents_verification():
    manifest = _build(exclusions=_exclusions()[:1])
    assert manifest["freshness"]["verification_state"] == "PARTIAL"
    assert manifest["freshness"]["freshness_fully_verified"] is False
    assert manifest["freshness"]["missing_required_exclusion_sources"] == [
        "ordered-expansion-wave1"
    ]


def test_required_source_policy_must_be_explicit_and_nonempty():
    for required in (None, []):
        config = _cohort_config()
        if required is None:
            config.pop("required_exclusion_sources")
        else:
            config["required_exclusion_sources"] = required
        with pytest.raises((TypeError, ValueError)):
            _build(config=config)


def test_complete_generic_sources_verify_without_historical_output_labels():
    config = _cohort_config()
    exclusions = _exclusions(wave_status="COMPLETE", diagnostic_ids=["obelix:c"])
    manifest = _build(exclusions=exclusions, config=config)
    assert manifest["freshness"]["verification_state"] == "VERIFIED"
    assert manifest["freshness"]["freshness_fully_verified"] is True
    assert manifest["freshness"]["required_exclusion_sources"] == config[
        "required_exclusion_sources"
    ]
    assert {item["cohort_id"] for item in manifest["exclusion_evidence"]} == {
        "diagnostic-72", "ordered-expansion-wave1"
    }


def test_required_exclusion_sources_accept_arbitrary_explicit_identities():
    exclusions = _exclusions(wave_status="COMPLETE")
    config = _cohort_config()
    for item, name in zip(exclusions, ("source-alpha", "source-beta")):
        item["cohort_id"] = name
    config["required_exclusion_sources"] = ["source-alpha", "source-beta"]
    manifest = _build(exclusions=exclusions, config=config)
    assert manifest["freshness"]["freshness_fully_verified"] is True
    assert manifest["freshness"]["required_exclusion_sources"] == [
        "source-alpha", "source-beta"
    ]


def test_optional_incomplete_evidence_remains_visible_without_becoming_required():
    exclusions = _exclusions(wave_status="COMPLETE")
    exclusions.append({
        "cohort_id": "optional-historical-note",
        "status": "UNRESOLVED",
        "kind": "HISTORICAL_NOTE",
        "source_identity": {"artifact": "optional-note-fixture"},
    })
    manifest = _build(exclusions=exclusions)
    assert manifest["freshness"]["freshness_fully_verified"] is True
    assert manifest["exclusion_evidence"][-1] == exclusions[-1]


def test_five_downstream_outputs_do_not_require_a_five_parent_cohort():
    exclusions = _exclusions(wave_status="COMPLETE", diagnostic_ids=["obelix:c"])
    exclusions.append({
        "cohort_id": "five-output-lineage",
        "kind": "DOWNSTREAM_CHILD_LINEAGE",
        "status": "COMPLETE",
        "child_output_count": 5,
        "child_rows": [
            {"child_material_id": f"child-{index}", "parent_id": "obelix:c"}
            for index in range(5)
        ],
        "ordered_parent_ids": ["obelix:c"],
        "source_identity": {"artifact": "five-output-fixture"},
    })
    manifest = _build(exclusions=exclusions)
    assert manifest["freshness"]["freshness_fully_verified"] is True
    assert manifest["exclusion_evidence"][-1]["child_output_count"] == 5
    assert manifest["exclusion_evidence"][-1]["ordered_parent_ids"] == ["obelix:c"]


def test_thirteen_child_outputs_can_trace_to_seven_source_parents():
    parent_ids = ["obelix:a", "obelix:c"] + [
        f"obelix:used-{index}" for index in range(5)
    ]
    child_rows = [
        {"child_material_id": f"child-{index}",
         "parent_id": parent_ids[index % len(parent_ids)]}
        for index in range(13)
    ]
    exclusions = _exclusions(wave_status="COMPLETE")
    exclusions.append({
        "cohort_id": "thirteen-output-lineage",
        "kind": "DOWNSTREAM_CHILD_LINEAGE",
        "status": "COMPLETE",
        "child_output_count": len(child_rows),
        "child_rows": child_rows,
        "ordered_parent_ids": parent_ids,
        "source_identity": {"artifact": "thirteen-output-fixture"},
    })
    assert len(child_rows) == 13
    assert len({row["parent_id"] for row in child_rows}) == 7
    assert len(parent_ids) == 7
    with pytest.raises((TypeError, ValueError), match="overlap COMPLETE exclusion"):
        _build(exclusions=exclusions)

    config = _cohort_config(["obelix:b"])
    manifest = _build(exclusions=exclusions, config=config)
    assert manifest["freshness"]["freshness_fully_verified"] is True
    assert manifest["exclusion_evidence"][-1]["child_output_count"] == 13
    assert len(manifest["exclusion_evidence"][-1]["ordered_parent_ids"]) == 7


def test_complete_lineage_parent_evidence_must_match_child_rows():
    exclusions = _exclusions(wave_status="COMPLETE")
    exclusions.append({
        "cohort_id": "child-lineage",
        "kind": "DOWNSTREAM_CHILD_LINEAGE",
        "status": "COMPLETE",
        "child_output_count": 2,
        "child_rows": [
            {"child_material_id": "child-1", "parent_id": "obelix:a"},
            {"child_material_id": "child-2", "parent_id": "obelix:a"},
        ],
        "ordered_parent_ids": ["obelix:c"],
        "source_identity": {"artifact": "lineage-fixture"},
    })
    with pytest.raises((TypeError, ValueError), match="lineage"):
        _build(exclusions=exclusions, config=_cohort_config(["obelix:b"]))


def test_aggregate_unselected_count_alone_cannot_certify_a_cohort():
    config = _cohort_config()
    config["aggregate_unselected_count"] = 249
    config.pop("ordered_parent_ids")
    with pytest.raises((TypeError, ValueError)):
        _build(config=config)


def test_explicit_ordered_parent_identity_is_preserved():
    config = _cohort_config(["obelix:c", "obelix:a"])
    manifest = _build(config=config)
    assert manifest["ordered_parent_ids"] == ["obelix:c", "obelix:a"]
    assert manifest["parent_count"] == 2


def test_same_explicit_inputs_produce_identical_manifest_identity():
    parents, source = _parents(), _source_identity()
    exclusions, config = _exclusions(), _cohort_config()
    first = _build(parents, source=source, exclusions=exclusions, config=config)
    second = _build(parents, source=source, exclusions=exclusions, config=config)
    assert first == second
    assert first["manifest_identity"] == second["manifest_identity"]


def test_manifest_binds_source_universe_identity():
    source = _source_identity()
    manifest = _build(source=source)
    assert manifest["source_identity"] == source
    assert manifest["source_identity"]["content_sha256"] == source["content_sha256"]
    assert manifest["manifest_identity"] != ""
    changed_source = _source_identity()
    changed_source["content_sha256"] = "different-source-digest"
    assert _build(source=changed_source)["manifest_identity"] != manifest[
        "manifest_identity"
    ]


def test_explicit_selection_rule_and_config_identity_are_preserved():
    config = _cohort_config()
    manifest = _build(config=config)
    assert manifest["selection"]["rule"] == config["selection_rule"]
    assert manifest["selection"]["config_identity"] == config[
        "selection_config_identity"
    ]


def test_selection_does_not_rank_by_conductivity_or_operator_performance():
    config = _cohort_config(["obelix:a", "obelix:c"])
    manifest = _build(config=config)
    assert manifest["ordered_parent_ids"] == config["ordered_parent_ids"]
    assert not ({"winner", "ranked_parents", "best_parent", "score"}
                & set(manifest))


def test_source_exclusions_and_config_are_immutable_and_manifest_detached():
    parents, source = _parents(), _source_identity()
    exclusions, config = _exclusions(), _cohort_config()
    before = copy.deepcopy((parents, source, exclusions, config))
    manifest = _build(parents, source=source, exclusions=exclusions, config=config)
    manifest["source_identity"]["content_sha256"] = "mutated-output"
    manifest["exclusion_evidence"][0]["source_identity"]["artifact"] = "mutated"
    manifest["freshness"]["required_exclusion_sources"][0] = "mutated"
    manifest["parents"][0]["provenance"]["nested"]["ref"] = "mutated"
    assert (parents, source, exclusions, config) == before


def test_manifest_construction_has_no_scheduler_generator_or_acquisition_side_effects(
    monkeypatch,
):
    from rudeus.generation import generator, scheduler
    from rudeus.mlip import make_batches

    def forbidden(*args, **kwargs):
        raise AssertionError("manifest construction invoked external/runtime work")

    monkeypatch.setattr(scheduler, "schedule_candidate_supply_v2", forbidden)
    monkeypatch.setattr(scheduler, "execute_candidate_supply_v2_for_parent", forbidden)
    monkeypatch.setattr(scheduler, "execute_candidate_supply_v2_cohort", forbidden)
    monkeypatch.setattr(generator, "generate_children", forbidden)
    monkeypatch.setattr(generator, "op_displace", forbidden)
    monkeypatch.setattr(generator, "op_mobile_ion_displace_v2", forbidden)
    monkeypatch.setattr(make_batches, "retrieve_obelix_parents", forbidden)
    _build()


def test_unresolved_freshness_does_not_authorize_runtime_generation():
    manifest = _build()
    assert manifest["freshness"]["freshness_fully_verified"] is False
    assert manifest["authorization"]["runtime_generation_authorized"] is False


def test_verified_freshness_does_not_authorize_runtime_generation():
    manifest = _build(exclusions=_exclusions(wave_status="COMPLETE"))
    assert manifest["freshness"]["freshness_fully_verified"] is True
    assert manifest["authorization"]["runtime_generation_authorized"] is False
