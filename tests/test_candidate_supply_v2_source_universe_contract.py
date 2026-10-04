"""RED contract for a prospective, explicit Candidate Supply v2 source universe.

These synthetic records are prepared inputs, not an OBELiX acquisition fixture.
The future builder validates records; it does not read or parse source data.
"""

import builtins
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path

import pytest


SCHEMA = "candidate-supply-v2-source-universe-v1"
_DEFAULT = object()
CORE_KEYS = (
    "schema_version",
    "source_snapshot",
    "selection_config",
    "considered_records",
    "eligible_parent_ids",
    "counts",
)


def _source_identity():
    return {
        "source_dataset": "obelix",
        "source_schema_version": "synthetic-obelix-snapshot-v1",
        "source_artifact_id": "synthetic-snapshot",
        "source_repository_commit": "fixture-commit-a",
        "source_repository_tree": "fixture-tree-a",
        "source_data_identity": {
            "processed_rows_sha256": "fixture-rows-digest-a",
            "cif_inventory_sha256": "fixture-cif-digest-a",
        },
    }


def _selection_config():
    return {
        "ordering_rule": "PARENT_ID_LEXICAL",
        "eligibility_rule": {
            "require_source_row": True,
            "require_cif": True,
            "require_parse_success": True,
            "require_ordered_structure": False,
        },
        "selection_config_identity": {
            "schema_version": "synthetic-selection-v1",
            "content_sha256": "fixture-selection-digest-a",
        },
    }


def _records():
    return [
        {
            "parent_id": "obelix:a",
            "source_dataset": "obelix",
            "source_ref": "a",
            "source_row_present": True,
            "cif_present": True,
            "parse_state": "SUCCESS",
            "parse_error": None,
            "structure_sha256": "fixture-structure-a",
            "structure_ordered": True,
            "eligible": True,
            "ineligibility_reasons": [],
            "provenance": {"row": {"ref": "a"}},
        },
        {
            "parent_id": "obelix:b",
            "source_dataset": "obelix",
            "source_ref": "b",
            "source_row_present": True,
            "cif_present": True,
            "parse_state": "FAILED",
            "parse_error": "synthetic parser failure",
            "structure_sha256": None,
            "structure_ordered": None,
            "eligible": False,
            "ineligibility_reasons": ["CIF_PARSE_FAILED"],
            "provenance": {"row": {"ref": "b"}},
        },
        {
            "parent_id": "obelix:c",
            "source_dataset": "obelix",
            "source_ref": "c",
            "source_row_present": True,
            "cif_present": False,
            "parse_state": "NOT_ATTEMPTED",
            "parse_error": None,
            "structure_sha256": None,
            "structure_ordered": None,
            "eligible": False,
            "ineligibility_reasons": ["CIF_MISSING"],
            "provenance": {"row": {"ref": "c"}},
        },
        {
            "parent_id": "obelix:d",
            "source_dataset": "obelix",
            "source_ref": "d",
            "source_row_present": True,
            "cif_present": True,
            "parse_state": "SUCCESS",
            "parse_error": None,
            "structure_sha256": "fixture-structure-d",
            "structure_ordered": False,
            "eligible": True,
            "ineligibility_reasons": [],
            "provenance": {"row": {"ref": "d"}},
        },
    ]


def _builder():
    module = importlib.import_module(
        "rudeus.generation.candidate_supply_source_universe"
    )
    return module.build_candidate_supply_v2_source_universe_manifest


def _build(records=_DEFAULT, *, source=_DEFAULT, config=_DEFAULT):
    return _builder()(
        _records() if records is _DEFAULT else records,
        source_identity=_source_identity() if source is _DEFAULT else source,
        selection_config=_selection_config() if config is _DEFAULT else config,
    )


def _canonical_sha256(manifest):
    # The derived fresh-cohort projection and digest are not hashed into
    # themselves. The core includes the complete ordered evidence and rules.
    core = {key: manifest[key] for key in CORE_KEYS}
    encoded = json.dumps(
        core, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _nested_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _nested_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nested_keys(child)


def test_source_universe_api_exists():
    assert callable(_builder())


@pytest.mark.parametrize("records", [None, [], {"n_considered": 321}])
def test_explicit_nonempty_source_records_required(records):
    with pytest.raises((TypeError, ValueError)):
        _build(records=records)


def test_duplicate_canonical_parent_ids_rejected():
    records = _records()
    duplicate = copy.deepcopy(records[0])
    duplicate["source_ref"] = "different-row"
    records.insert(1, duplicate)
    with pytest.raises((TypeError, ValueError)):
        _build(records=records)


@pytest.mark.parametrize(
    "missing_field",
    ["source_dataset", "source_repository_commit", "source_repository_tree",
     "source_data_identity", "source_schema_version"],
)
def test_explicit_immutable_source_snapshot_identity_required(missing_field):
    source = _source_identity()
    del source[missing_field]
    with pytest.raises((TypeError, ValueError)):
        _build(source=source)


@pytest.mark.parametrize("config", [None, {}])
def test_explicit_selection_semantics_required(config):
    with pytest.raises((TypeError, ValueError)):
        _build(config=config)


@pytest.mark.parametrize("missing_field", ["schema_version", "content_sha256"])
def test_selection_config_identity_is_required(missing_field):
    config = _selection_config()
    del config["selection_config_identity"][missing_field]
    with pytest.raises((TypeError, ValueError)):
        _build(config=config)


def test_identical_inputs_produce_identical_canonical_content_identity():
    first = _build()
    second = _build()
    assert first == second
    assert first["schema_version"] == SCHEMA
    assert first["source_snapshot"] == _source_identity()
    assert first["selection_config"] == _selection_config()
    assert first["content_sha256"] == _canonical_sha256(first)
    assert len(first["content_sha256"]) == 64
    assert "created_at" not in first and "uuid" not in first


def test_source_snapshot_change_changes_content_identity():
    changed = _source_identity()
    changed["source_repository_tree"] = "fixture-tree-b"
    assert _build(source=changed)["content_sha256"] != _build()["content_sha256"]


@pytest.mark.parametrize("record_index,field,value", [
    (0, "structure_sha256", "different-structure"),
    (1, "parse_error", "different parser evidence"),
    (1, "provenance", {"row": {"ref": "different-source-row"}}),
])
def test_ordered_record_evidence_change_changes_content_identity(
    record_index, field, value
):
    records = _records()
    records[record_index][field] = value
    assert _build(records)["content_sha256"] != _build()["content_sha256"]


def test_declared_selection_semantics_change_changes_content_identity():
    config = _selection_config()
    config["eligibility_rule"]["require_ordered_structure"] = True
    records = _records()
    records[3]["eligible"] = False
    records[3]["ineligibility_reasons"] = ["STRUCTURE_NOT_ORDERED"]
    assert _build(records, config=config)["content_sha256"] != _build()["content_sha256"]


def test_declared_lexical_order_is_preserved_not_reordered():
    manifest = _build()
    assert [r["parent_id"] for r in manifest["considered_records"]] == [
        "obelix:a", "obelix:b", "obelix:c", "obelix:d"
    ]
    assert manifest["eligible_parent_ids"] == ["obelix:a", "obelix:d"]
    assert manifest["selection_config"]["ordering_rule"] == "PARENT_ID_LEXICAL"


def test_input_order_violating_declared_order_is_rejected():
    records = _records()
    records[0], records[1] = records[1], records[0]
    with pytest.raises((TypeError, ValueError)):
        _build(records)


def test_parse_success_and_parse_failure_remain_distinct():
    records = _build()["considered_records"]
    assert records[0]["parse_state"] == "SUCCESS"
    assert records[0]["structure_sha256"] == "fixture-structure-a"
    assert records[1]["cif_present"] is True
    assert records[1]["parse_state"] == "FAILED"
    assert records[1]["parse_error"] == "synthetic parser failure"
    assert records[1]["ineligibility_reasons"] == ["CIF_PARSE_FAILED"]
    assert records[2]["source_row_present"] is True
    assert records[2]["cif_present"] is False
    assert records[2]["parse_state"] == "NOT_ATTEMPTED"


def test_considered_source_records_and_eligible_subset_are_distinct():
    manifest = _build()
    assert len(manifest["considered_records"]) == 4
    assert manifest["eligible_parent_ids"] == ["obelix:a", "obelix:d"]
    assert [r["parent_id"] for r in manifest["considered_records"] if not r["eligible"]] == [
        "obelix:b", "obelix:c"
    ]
    assert manifest["considered_records"][3]["structure_ordered"] is False
    assert manifest["considered_records"][3]["eligible"] is True


def test_source_row_absence_is_distinct_from_cif_and_parse_state():
    records = _records()
    records[2]["source_row_present"] = False
    records[2]["ineligibility_reasons"] = ["SOURCE_ROW_MISSING", "CIF_MISSING"]
    retained = _build(records)["considered_records"][2]
    assert retained["source_row_present"] is False
    assert retained["cif_present"] is False
    assert retained["parse_state"] == "NOT_ATTEMPTED"
    assert retained["ineligibility_reasons"] == ["SOURCE_ROW_MISSING", "CIF_MISSING"]


def test_counts_are_derived_from_explicit_records():
    manifest = _build()
    assert manifest["counts"] == {
        "n_considered": 4,
        "n_parse_success": 2,
        "n_parse_failure": 1,
        "n_eligible": 2,
    }
    assert manifest["counts"]["n_considered"] == len(manifest["considered_records"])
    assert manifest["counts"]["n_eligible"] == len(manifest["eligible_parent_ids"])


def test_caller_cannot_inject_contradictory_counts():
    config = _selection_config()
    config["n_eligible"] = 321
    with pytest.raises((TypeError, ValueError)):
        _build(config=config)


def test_caller_declared_eligibility_must_match_explicit_rule():
    records = _records()
    records[1]["eligible"] = True  # Failed parse cannot satisfy this rule.
    records[1]["ineligibility_reasons"] = []
    with pytest.raises((TypeError, ValueError)):
        _build(records)


def test_historical_count_alone_cannot_define_source_universe():
    with pytest.raises((TypeError, ValueError)):
        _build(records={"historical_perturbable_count": 321},
               source={"historical_perturbable_count": 321})


def test_equal_historical_count_is_comparison_only_not_identity():
    records = [_records()[0], _records()[3]]
    config = _selection_config()
    config["historical_comparison"] = {"historical_perturbable_count": 2}
    manifest = _build(records, config=config)
    assert manifest["counts"]["n_eligible"] == 2
    assert manifest["selection_config"]["historical_comparison"] == {
        "historical_perturbable_count": 2
    }
    assert manifest.get("historical_universe_identity_verified") is not True
    assert manifest["source_identity"].get("historical_universe_identity_verified") is not True


def test_inputs_are_not_mutated_and_nested_output_is_detached():
    records, source, config = _records(), _source_identity(), _selection_config()
    before = copy.deepcopy((records, source, config))
    manifest = _build(records, source=source, config=config)
    assert (records, source, config) == before
    manifest["considered_records"][0]["provenance"]["row"]["ref"] = "output-only"
    manifest["source_snapshot"]["source_data_identity"]["cif_inventory_sha256"] = "output-only"
    manifest["selection_config"]["eligibility_rule"]["require_cif"] = False
    assert (records, source, config) == before


def test_builder_does_not_acquire_source_data_or_parse_files(monkeypatch):
    builder = _builder()  # Import before trapping builder-time I/O.

    def forbidden(*_args, **_kwargs):
        raise AssertionError("source acquisition or filesystem access in pure builder")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(os, "scandir", forbidden)
        result = builder(
            _records(), source_identity=_source_identity(),
            selection_config=_selection_config(),
        )
    assert result["counts"]["n_considered"] == 4


def test_builder_does_not_enter_scheduler_generator_or_science(monkeypatch):
    builder = _builder()
    original_import = builtins.__import__
    forbidden_names = (
        "rudeus.generation.scheduler", "rudeus.generation.generator",
        "rudeus.filters", "rudeus.mlip", "pymatgen",
    )

    def guarded_import(name, *args, **kwargs):
        if name.startswith(forbidden_names):
            raise AssertionError("pure source-universe builder entered execution/science")
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", guarded_import)
        result = builder(
            _records(), source_identity=_source_identity(),
            selection_config=_selection_config(),
        )
    assert result["counts"]["n_eligible"] == 2


def test_manifest_contains_no_ranking_or_runtime_authorization():
    manifest = _build()
    forbidden = {
        "rank", "ranking", "score", "winner", "top_n", "exploration",
        "exploitation", "fresh_parent_ids", "excluded_parent_ids",
        "generation_authorized", "scheduler_activated", "p1_eligible",
    }
    assert forbidden.isdisjoint(_nested_keys(manifest))


def test_source_identity_can_bind_future_fresh_parent_cohort_without_selecting_it():
    manifest = _build()
    identity = manifest["source_identity"]
    assert identity["source_dataset"] == "obelix"
    assert identity["source_schema_version"] == _source_identity()["source_schema_version"]
    assert identity["source_artifact_id"] == "synthetic-snapshot"
    assert identity["content_sha256"] == manifest["content_sha256"]
    assert identity["ordered_parent_ids"] == manifest["eligible_parent_ids"]
    assert "fresh_parent_ids" not in manifest
