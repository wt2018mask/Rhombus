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
                else ["obelix:c"]
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
        "ordered_parent_ids": list(
            parent_ids if parent_ids is not None else ["obelix:a", "obelix:b"]
        ),
        "required_exclusion_sources": [
            "diagnostic-72", "ordered-expansion-wave1"
        ],
        "selection_rule": {
            "policy_id": "eligible-minus-complete-exclusions-lexical-v1",
            "description": "Derive eligible IDs minus COMPLETE exclusions in lexical order.",
        },
        "selection_config_identity": {
            "schema_version": "fresh-cohort-selection-config-v1",
            "content_sha256": "selection-config-digest-fixture",
        },
    }


def _source_universe_mapping_records():
    """JSON-shaped records as emitted by candidate_supply_source_universe."""
    records = []
    for suffix, eligible in (
        ("a", True), ("b", True), ("c", True), ("d", True), ("e", False)
    ):
        records.append({
            "parent_id": f"obelix:{suffix}",
            "source_dataset": "obelix",
            "source_ref": suffix,
            "source_row_present": True,
            "cif_present": eligible,
            "parse_state": "SUCCESS" if eligible else "NOT_ATTEMPTED",
            "parse_error": None,
            "structure_sha256": f"structure-{suffix}" if eligible else None,
            "structure_ordered": True if eligible else None,
            "eligible": eligible,
            "ineligibility_reasons": [] if eligible else ["CIF_MISSING"],
            "provenance": {"source": "source-universe-fixture", "row": suffix},
        })
    return records


def _source_universe_mapping_identity():
    return {
        "source_dataset": "obelix",
        "source_schema_version": "synthetic-obelix-snapshot-v1",
        "source_artifact_id": "synthetic-source-universe-fixture",
        "content_sha256": "source-universe-digest-fixture",
        "ordered_parent_ids": [f"obelix:{suffix}" for suffix in "abcd"],
    }


def _derived_cohort_config(*, parent_ids=None, required=None):
    config = {
        "cohort_id": "synthetic-derived-cohort-v1",
        "required_exclusion_sources": list(required or ["required-complete"]),
        "selection_rule": {
            "policy_id": "eligible-minus-complete-exclusions-lexical-v1",
            "description": "Derive eligible IDs minus supplied COMPLETE evidence in lexical order.",
        },
        "selection_config_identity": {
            "schema_version": "fresh-cohort-selection-config-v1",
            "content_sha256": "selection-config-digest-fixture",
        },
    }
    if parent_ids is not None:
        config["ordered_parent_ids"] = list(parent_ids)
    return config


def _derived_exclusions():
    return [
        {
            "cohort_id": "required-complete",
            "status": "COMPLETE",
            "kind": "HISTORICAL_GENERATION",
            "ordered_parent_ids": ["obelix:b"],
            "source_identity": {"artifact": "required-complete-fixture"},
        },
        {
            "cohort_id": "optional-complete",
            "status": "COMPLETE",
            "kind": "PRIOR_USE",
            "ordered_parent_ids": ["obelix:d"],
            "source_identity": {"artifact": "optional-complete-fixture"},
        },
        {
            "cohort_id": "optional-partial",
            "status": "PARTIAL",
            "kind": "HISTORICAL_NOTE",
            "ordered_parent_ids": ["obelix:a", "obelix:e"],
            "source_identity": {"artifact": "optional-partial-fixture"},
        },
    ]


def _build_derived(records=None, *, exclusions=None, config=None, source=None):
    return _builder()(
        records if records is not None else _source_universe_mapping_records(),
        source_identity=(
            source if source is not None else _source_universe_mapping_identity()
        ),
        exclusion_evidence=(
            exclusions if exclusions is not None else _derived_exclusions()
        ),
        cohort_config=(config if config is not None else _derived_cohort_config()),
    )


def _build_three_parent_evidence_case(exclusions):
    records = _source_universe_mapping_records()[:3]
    source = _source_universe_mapping_identity()
    source["ordered_parent_ids"] = ["obelix:a", "obelix:b", "obelix:c"]
    config = _derived_cohort_config(
        required=[item["cohort_id"] for item in exclusions]
    )
    return _build_derived(
        records=records,
        exclusions=exclusions,
        config=config,
        source=source,
    )


def _complete_lineage_for_b():
    return {
        "cohort_id": "lineage-b",
        "kind": "DOWNSTREAM_CHILD_LINEAGE",
        "status": "COMPLETE",
        "child_output_count": 1,
        "child_rows": [{"child_material_id": "child-b", "parent_id": "obelix:b"}],
        "ordered_parent_ids": ["obelix:b"],
        "source_identity": {"artifact": "lineage-b-fixture"},
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
    manifest = _build(exclusions=exclusions)
    assert manifest["ordered_parent_ids"] == ["obelix:a", "obelix:b"]
    assert manifest["freshness"]["freshness_fully_verified"] is True
    assert manifest["exclusion_evidence"][-1]["status"] == "COMPLETE"
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


def test_aggregate_unselected_count_does_not_define_derived_membership():
    config = _cohort_config()
    config["aggregate_unselected_count"] = 249
    config.pop("ordered_parent_ids")
    manifest = _build(config=config)
    assert manifest["ordered_parent_ids"] == ["obelix:a", "obelix:b"]


def test_explicit_ordered_parent_identity_asserts_derived_membership():
    config = _cohort_config(["obelix:a", "obelix:b"])
    manifest = _build(config=config)
    assert manifest["ordered_parent_ids"] == ["obelix:a", "obelix:b"]
    assert manifest["parent_count"] == 2

    with pytest.raises(ValueError, match="does not match derived membership"):
        _build(config=_cohort_config(["obelix:c", "obelix:a"]))


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
    config = _cohort_config(["obelix:a", "obelix:b"])
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


def test_source_universe_mapping_records_derive_cohort_without_caller_ids():
    manifest = _build_derived()

    assert manifest["ordered_parent_ids"] == ["obelix:a", "obelix:c"]
    assert manifest["parent_count"] == 2
    assert [parent["parent_id"] for parent in manifest["parents"]] == [
        "obelix:a", "obelix:c"
    ]
    assert manifest["freshness"]["verification_state"] == "VERIFIED"
    assert manifest["authorization"]["runtime_generation_authorized"] is False


def test_optional_complete_source_excludes_its_ids():
    manifest = _build_derived()

    assert "obelix:d" not in manifest["ordered_parent_ids"]
    assert manifest["exclusion_evidence"][1]["cohort_id"] == "optional-complete"


def test_partial_source_is_visible_but_not_used_as_exclusion():
    manifest = _build_derived()

    assert "obelix:a" in manifest["ordered_parent_ids"]
    assert "obelix:e" not in manifest["ordered_parent_ids"]
    assert manifest["exclusion_evidence"][2]["status"] == "PARTIAL"


def test_explicit_ordered_ids_are_only_an_assertion_of_derived_membership():
    manifest = _build_derived(
        config=_derived_cohort_config(parent_ids=["obelix:a", "obelix:c"])
    )
    assert manifest["ordered_parent_ids"] == ["obelix:a", "obelix:c"]

    with pytest.raises((TypeError, ValueError), match="derived"):
        _build_derived(
            config=_derived_cohort_config(parent_ids=["obelix:a", "obelix:c", "obelix:d"])
        )


def test_derived_mapping_cohort_is_deterministic_and_uses_lexical_order():
    first = _build_derived()
    second = _build_derived()

    assert first["ordered_parent_ids"] == second["ordered_parent_ids"]
    assert first["manifest_identity"] == second["manifest_identity"]
    assert first["ordered_parent_ids"] == sorted(first["ordered_parent_ids"])


def test_mapping_parent_id_rejects_source_ref_mismatch():
    records = _source_universe_mapping_records()
    records[0]["source_ref"] = "different"

    with pytest.raises(ValueError, match="canonical"):
        _build_derived(records=records)


def test_mapping_parent_id_rejects_source_dataset_mismatch():
    records = _source_universe_mapping_records()
    records[0]["source_dataset"] = "other"

    with pytest.raises(ValueError, match="canonical"):
        _build_derived(records=records)


def test_mapping_parent_dataset_must_match_bound_source_dataset():
    source = _source_universe_mapping_identity()
    source["source_dataset"] = "other"

    with pytest.raises(ValueError, match="bound source dataset"):
        _build_derived(source=source)


@pytest.mark.parametrize(
    "kind", ["DIAGNOSTIC_TOURNAMENT", "HISTORICAL_GENERATION", "PRIOR_USE"]
)
def test_complete_prior_use_kind_excludes_its_parent_ids(kind):
    evidence = [{
        "cohort_id": "prior-use-b",
        "kind": kind,
        "status": "COMPLETE",
        "ordered_parent_ids": ["obelix:b"],
        "source_identity": {"artifact": "prior-use-b-fixture"},
    }]

    manifest = _build_three_parent_evidence_case(evidence)

    assert manifest["ordered_parent_ids"] == ["obelix:a", "obelix:c"]


def test_complete_downstream_lineage_is_visible_but_does_not_exclude_parent():
    lineage = _complete_lineage_for_b()

    manifest = _build_three_parent_evidence_case([lineage])

    assert manifest["ordered_parent_ids"] == ["obelix:a", "obelix:b", "obelix:c"]
    assert manifest["exclusion_evidence"] == [lineage]


def test_lineage_and_independent_complete_exclusion_exclude_parent_once():
    lineage = _complete_lineage_for_b()
    exclusion = {
        "cohort_id": "historical-use-b",
        "kind": "HISTORICAL_GENERATION",
        "status": "COMPLETE",
        "ordered_parent_ids": ["obelix:b"],
        "source_identity": {"artifact": "historical-use-b-fixture"},
    }

    manifest = _build_three_parent_evidence_case([lineage, exclusion])

    assert manifest["ordered_parent_ids"] == ["obelix:a", "obelix:c"]
    assert manifest["exclusion_evidence"] == [lineage, exclusion]


def test_complete_historical_note_is_not_exclusion_authoritative():
    evidence = [{
        "cohort_id": "note-b",
        "kind": "HISTORICAL_NOTE",
        "status": "COMPLETE",
        "ordered_parent_ids": ["obelix:b"],
        "source_identity": {"artifact": "note-b-fixture"},
    }]

    manifest = _build_three_parent_evidence_case(evidence)

    assert "obelix:b" in manifest["ordered_parent_ids"]
    assert manifest["exclusion_evidence"] == evidence


def test_full_source_universe_records_accept_ineligible_ids_outside_eligible_identity():
    records = _source_universe_mapping_records()[:3]
    records[2].update({
        "cif_present": False,
        "parse_state": "NOT_ATTEMPTED",
        "structure_sha256": None,
        "structure_ordered": None,
        "eligible": False,
        "ineligibility_reasons": ["CIF_MISSING"],
    })
    source = _source_universe_mapping_identity()
    source["ordered_parent_ids"] = ["obelix:a", "obelix:b"]
    exclusions = [{
        "cohort_id": "no-prior-use",
        "kind": "PRIOR_USE",
        "status": "COMPLETE",
        "ordered_parent_ids": [],
        "source_identity": {"artifact": "empty-prior-use-fixture"},
    }]

    manifest = _build_derived(
        records=records,
        source=source,
        exclusions=exclusions,
        config=_derived_cohort_config(required=["no-prior-use"]),
    )

    assert manifest["ordered_parent_ids"] == ["obelix:a", "obelix:b"]
    assert "obelix:c" not in manifest["ordered_parent_ids"]
    assert all(parent["eligible"] for parent in manifest["parents"])


def test_eligible_source_record_outside_bound_eligible_identity_is_rejected():
    records = _source_universe_mapping_records()[:2]
    source = _source_universe_mapping_identity()
    source["ordered_parent_ids"] = ["obelix:a"]
    exclusions = [{
        "cohort_id": "no-prior-use",
        "kind": "PRIOR_USE",
        "status": "COMPLETE",
        "ordered_parent_ids": [],
        "source_identity": {"artifact": "empty-prior-use-fixture"},
    }]

    with pytest.raises(ValueError, match="outside bound source universe"):
        _build_derived(
            records=records,
            source=source,
            exclusions=exclusions,
            config=_derived_cohort_config(required=["no-prior-use"]),
        )


def test_certified_summary_lineage_is_preserved_without_child_rows_or_exclusion():
    lineage = {
        "cohort_id": "old-13",
        "kind": "DOWNSTREAM_CHILD_LINEAGE",
        "status": "COMPLETE",
        "classification": "LINEAGE",
        "lineage_validation_scope": "SUMMARY_ONLY",
        "output_count": 13,
        "distinct_source_parent_count": 2,
        "source_parent_ids": ["obelix:a", "obelix:b"],
        "evidence_paths": ["detached/old-13-summary.json"],
        "source_identity": {"artifact": "certified-exclusion-report", "source_id": "old-13"},
    }
    no_prior_use = {
        "cohort_id": "no-prior-use",
        "kind": "PRIOR_USE",
        "status": "COMPLETE",
        "ordered_parent_ids": [],
        "source_identity": {"artifact": "empty-prior-use-fixture"},
    }
    evidence = [lineage, no_prior_use]
    config = _derived_cohort_config(required=["no-prior-use"])

    manifest = _build_derived(exclusions=evidence, config=config)
    repeated = _build_derived(exclusions=evidence, config=config)

    preserved = manifest["exclusion_evidence"][0]
    assert "child_rows" not in preserved
    assert preserved == lineage
    assert preserved["classification"] == "LINEAGE"
    assert preserved["source_parent_ids"] == ["obelix:a", "obelix:b"]
    assert preserved["output_count"] == 13
    assert manifest["ordered_parent_ids"] == [
        "obelix:a", "obelix:b", "obelix:c", "obelix:d"
    ]
    assert repeated["manifest_identity"] == manifest["manifest_identity"]


def test_full_child_row_lineage_still_uses_deep_validation_without_exclusion():
    lineage = _complete_lineage_for_b()
    no_prior_use = {
        "cohort_id": "no-prior-use",
        "kind": "PRIOR_USE",
        "status": "COMPLETE",
        "ordered_parent_ids": [],
        "source_identity": {"artifact": "empty-prior-use-fixture"},
    }

    manifest = _build_three_parent_evidence_case([lineage, no_prior_use])

    assert manifest["ordered_parent_ids"] == ["obelix:a", "obelix:b", "obelix:c"]
    assert manifest["exclusion_evidence"][0] == lineage
