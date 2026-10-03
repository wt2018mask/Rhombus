"""Static RED contract for explicit Candidate Supply v2 source preparation.

Fixtures are synthetic. The future preparation API receives source rows and an
injected provider; it must not acquire real source data itself.
"""

import builtins
import copy
import importlib
import os
from pathlib import Path
import urllib.request

import pytest


PREPARATION_SCHEMA = "candidate-supply-v2-source-record-preparation-v1"
_DEFAULT = object()


def _snapshot():
    return {
        "source_name": "synthetic-obelix",
        "source_dataset": "obelix",
        "source_schema_version": "synthetic-source-v1",
        "source_artifact_id": "synthetic-snapshot",
        "source_repository_commit": "fixture-commit",
        "source_repository_tree": "fixture-tree",
        "source_data_identity": {
            "rows_sha256": "fixture-rows-hash",
            "structure_index_sha256": "fixture-structure-index-hash",
        },
    }


def _selection_config(**overrides):
    config = {
        "source_namespace": "obelix",
        "source_id_field": "source_id",
        "structure_ref_field": "structure_ref",
        "ordering_rule": "PARENT_ID_LEXICAL",
        "eligibility_rule": {
            "require_source_row": True,
            "require_cif": True,
            "require_parse_success": True,
            "require_ordered_structure": False,
        },
        "selection_config_identity": {
            "schema_version": "synthetic-preparation-rules-v1",
            "content_sha256": "fixture-selection-hash",
        },
    }
    config.update(overrides)
    return config


def _source_rows():
    # Supplied in declared canonical lexical order, independent of conductivity.
    return [
        {
            "source_id": "a",
            "conductivity": 0.1,
            "structure_ref": "cif/a.cif",
            "row_metadata": {"origin": "row-a"},
        },
        {
            "source_id": "b",
            "conductivity": 99.0,
            "structure_ref": "cif/b.cif",
            "row_metadata": {"origin": "row-b"},
        },
        {
            "source_id": "c",
            "conductivity": 1.5,
            "structure_ref": None,
            "row_metadata": {"origin": "row-c"},
        },
    ]


class _SyntheticStructure:
    def __init__(self, digest, *, is_ordered=True):
        self.structure_sha256 = digest
        self.is_ordered = is_ordered
        self.arbitrary_internal_object = object()


def _provider(requested=None, *, failures=(), missing=()):
    calls = requested if requested is not None else []
    failures = set(failures)
    missing = set(missing)

    def provide(parent_id):
        calls.append(parent_id)
        if parent_id in failures:
            raise ValueError("provider fixture parse failure; details are unstable")
        if parent_id in missing:
            return None
        suffix = parent_id.split(":", 1)[1]
        return _SyntheticStructure(
            f"synthetic-structure-{suffix}", is_ordered=(suffix != "b")
        )

    return provide, calls


def _preparer():
    module = importlib.import_module(
        "rudeus.generation.candidate_supply_source_preparation"
    )
    return module.prepare_candidate_supply_v2_source_records


def _prepare(rows=_DEFAULT, *, snapshot=_DEFAULT, provider=_DEFAULT, config=_DEFAULT):
    selected_rows = _source_rows() if rows is _DEFAULT else rows
    selected_provider = provider
    if selected_provider is _DEFAULT:
        selected_provider, _ = _provider()
    return _preparer()(
        selected_rows,
        source_snapshot=_snapshot() if snapshot is _DEFAULT else snapshot,
        structure_provider=selected_provider,
        selection_config=_selection_config() if config is _DEFAULT else config,
    )


def test_source_record_preparation_api_exists():
    assert callable(_preparer())


@pytest.mark.parametrize("rows", [None, [], {"n_rows": 3}])
def test_explicit_source_rows_required(rows):
    with pytest.raises((TypeError, ValueError)):
        _prepare(rows=rows)


@pytest.mark.parametrize("snapshot", [None, {}])
def test_explicit_source_snapshot_required(snapshot):
    with pytest.raises((TypeError, ValueError)):
        _prepare(snapshot=snapshot)


@pytest.mark.parametrize("config", [None, {}])
def test_explicit_selection_configuration_required(config):
    with pytest.raises((TypeError, ValueError)):
        _prepare(config=config)


def test_injected_structure_provider_required():
    with pytest.raises((TypeError, ValueError)):
        _prepare(provider=None)


def test_canonical_parent_id_uses_explicit_namespace_and_raw_id():
    prepared = _prepare()
    assert [row["parent_id"] for row in prepared["records"]] == [
        "obelix:a", "obelix:b", "obelix:c"
    ]
    assert [row["source_ref"] for row in prepared["records"]] == ["a", "b", "c"]
    assert prepared["selection_config"]["source_namespace"] == "obelix"


def test_namespace_is_required_instead_of_silently_invented():
    config = _selection_config()
    del config["source_namespace"]
    with pytest.raises((TypeError, ValueError)):
        _prepare(config=config)


@pytest.mark.parametrize(
    "rows",
    [
        [dict(_source_rows()[0]), dict(_source_rows()[0])],
        [
            {**_source_rows()[0], "source_id": "obelix:a"},
            {**_source_rows()[1], "source_id": "a"},
        ],
    ],
)
def test_duplicate_raw_or_canonical_parent_identity_rejected(rows):
    with pytest.raises((TypeError, ValueError)):
        _prepare(rows=rows)


def test_structure_present_and_parse_success_are_retained_as_facts():
    prepared = _prepare()
    first = prepared["records"][0]
    assert first["structure_state"] == "STRUCTURE_PRESENT"
    assert first["cif_present"] is True
    assert first["parse_state"] == "SUCCESS"
    assert first["structure_sha256"] == "synthetic-structure-a"
    assert first["structure_ordered"] is True
    assert first["eligible"] is True
    assert first["ineligibility_reasons"] == []


def test_structure_present_and_parse_failure_remain_auditable():
    provider, calls = _provider(failures={"obelix:b"})
    prepared = _prepare(provider=provider)
    failed = prepared["records"][1]
    assert failed["structure_state"] == "STRUCTURE_PRESENT"
    assert failed["cif_present"] is True
    assert failed["parse_state"] == "FAILED"
    assert failed["parse_error"] == "PARSE_FAILED"
    assert failed["eligible"] is False
    assert failed["ineligibility_reasons"] == ["CIF_PARSE_FAILED"]
    assert calls == ["obelix:a", "obelix:b"]


def test_missing_structure_is_retained_without_provider_lookup():
    provider, calls = _provider()
    prepared = _prepare(provider=provider)
    missing = prepared["records"][2]
    assert missing["structure_state"] == "STRUCTURE_MISSING"
    assert missing["cif_present"] is False
    assert missing["parse_state"] == "NOT_ATTEMPTED"
    assert missing["eligible"] is False
    assert missing["ineligibility_reasons"] == ["CIF_MISSING"]
    assert calls == ["obelix:a", "obelix:b"]


def test_linked_structure_provider_miss_is_explicitly_missing():
    provider, calls = _provider(missing={"obelix:b"})
    prepared = _prepare(provider=provider)
    missing = prepared["records"][1]
    assert missing["structure_state"] == "STRUCTURE_MISSING"
    assert missing["cif_present"] is False
    assert missing["parse_state"] == "NOT_ATTEMPTED"
    assert missing["ineligibility_reasons"] == ["CIF_MISSING"]
    assert calls == ["obelix:a", "obelix:b"]


def test_selection_config_controls_ordered_structure_eligibility():
    config = _selection_config()
    config["eligibility_rule"]["require_ordered_structure"] = True
    prepared = _prepare(config=config)
    second = prepared["records"][1]
    assert second["parse_state"] == "SUCCESS"
    assert second["structure_ordered"] is False
    assert second["eligible"] is False
    assert second["ineligibility_reasons"] == ["STRUCTURE_NOT_ORDERED"]


def test_ineligible_records_keep_specific_reasons_and_selection_failure():
    config = _selection_config()
    config["eligibility_rule"]["require_ordered_structure"] = True
    prepared = _prepare(config=config)
    assert prepared["records"][1]["ineligibility_reasons"] == [
        "STRUCTURE_NOT_ORDERED"
    ]
    assert all(
        (row["eligible"] and not row["ineligibility_reasons"])
        or (not row["eligible"] and row["ineligibility_reasons"])
        for row in prepared["records"]
    )


def test_every_input_row_is_accounted_for_in_order():
    rows = _source_rows()
    prepared = _prepare(rows)
    assert len(prepared["records"]) == len(rows)
    assert [r["source_ref"] for r in prepared["records"]] == [
        row["source_id"] for row in rows
    ]


def test_identical_inputs_produce_deterministic_prepared_output():
    first = _prepare()
    second = _prepare()
    assert first == second
    assert first["schema_version"] == PREPARATION_SCHEMA
    assert "timestamp" not in first and "uuid" not in first


def test_provider_requests_follow_canonical_order_once_each():
    provider, calls = _provider()
    _prepare(provider=provider)
    assert calls == ["obelix:a", "obelix:b"]
    assert len(calls) == len(set(calls))


def test_provider_receives_only_known_linked_parent_identities():
    provider, calls = _provider()
    _prepare(provider=provider)
    assert set(calls) == {"obelix:a", "obelix:b"}
    assert "obelix:unknown" not in calls
    assert "obelix:c" not in calls


def test_valid_declared_order_is_preserved_and_invalid_order_rejected():
    assert [r["parent_id"] for r in _prepare()["records"]] == [
        "obelix:a", "obelix:b", "obelix:c"
    ]
    rows = _source_rows()
    rows[0], rows[1] = rows[1], rows[0]
    with pytest.raises((TypeError, ValueError)):
        _prepare(rows)


def test_unsupported_ordering_rule_rejected():
    config = _selection_config()
    config["ordering_rule"] = "HISTORICAL_OBELIX_ORDER"
    with pytest.raises((TypeError, ValueError)):
        _prepare(config=config)


def test_output_order_does_not_rank_by_conductivity():
    prepared = _prepare()
    assert [r["parent_id"] for r in prepared["records"]] == [
        "obelix:a", "obelix:b", "obelix:c"
    ]
    assert [r["provenance"]["source_row"]["conductivity"] for r in prepared["records"]] == [
        0.1, 99.0, 1.5
    ]


def test_source_snapshot_provenance_is_retained():
    snapshot = _snapshot()
    prepared = _prepare(snapshot=snapshot)
    assert prepared["source_snapshot"] == snapshot
    assert prepared["source_identity"] == snapshot


def test_inputs_are_immutable_and_nested_outputs_detached():
    rows, snapshot, config = _source_rows(), _snapshot(), _selection_config()
    before = copy.deepcopy((rows, snapshot, config))
    prepared = _prepare(rows, snapshot=snapshot, config=config)
    assert (rows, snapshot, config) == before
    prepared["records"][0]["provenance"]["source_row"]["row_metadata"]["origin"] = "changed"
    prepared["source_snapshot"]["source_data_identity"]["rows_sha256"] = "changed"
    prepared["selection_config"]["eligibility_rule"]["require_cif"] = False
    assert (rows, snapshot, config) == before


def test_provider_structure_objects_do_not_leak_into_prepared_records():
    prepared = _prepare()
    first = prepared["records"][0]
    assert first["structure_sha256"] == "synthetic-structure-a"
    assert first["structure_ordered"] is True
    assert all(not isinstance(value, _SyntheticStructure) for value in first.values())


def test_no_filesystem_or_network_acquisition_besides_injected_provider(monkeypatch):
    preparer = _preparer()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("preparation performed ambient filesystem/network access")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(os, "scandir", forbidden)
        patch.setattr(urllib.request, "urlopen", forbidden)
        prepared = preparer(
            _source_rows(), source_snapshot=_snapshot(),
            structure_provider=lambda parent_id: _SyntheticStructure(
                f"hash-{parent_id.rsplit(':', 1)[-1]}"
            ) if parent_id != "obelix:c" else None,
            selection_config=_selection_config(),
        )
    assert len(prepared["records"]) == 3


def test_no_scheduler_generator_or_freshness_imports(monkeypatch):
    preparer = _preparer()
    original_import = builtins.__import__
    forbidden_prefixes = (
        "rudeus.generation.scheduler", "rudeus.generation.generator",
        "rudeus.generation.fresh_parent_cohort",
        "rudeus.generation.candidate_supply_activation",
    )

    def guarded_import(name, *args, **kwargs):
        if name.startswith(forbidden_prefixes):
            raise AssertionError("preparation entered scheduler/generation/freshness")
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", guarded_import)
        prepared = preparer(
            _source_rows(), source_snapshot=_snapshot(),
            structure_provider=lambda parent_id: _SyntheticStructure(
                f"hash-{parent_id.rsplit(':', 1)[-1]}"
            ) if parent_id != "obelix:c" else None,
            selection_config=_selection_config(),
        )
    assert len(prepared["records"]) == 3


def test_prepared_records_are_accepted_by_source_universe_manifest_contract():
    prepared = _prepare()
    universe = importlib.import_module(
        "rudeus.generation.candidate_supply_source_universe"
    )
    manifest = universe.build_candidate_supply_v2_source_universe_manifest(
        prepared["records"], source_identity=prepared["source_identity"],
        selection_config=prepared["selection_config"],
    )
    assert manifest["counts"]["n_considered"] == 3
    assert manifest["eligible_parent_ids"] == ["obelix:a", "obelix:b"]


def test_historical_321_is_not_a_preparation_acceptance_criterion():
    rows = _source_rows()
    prepared = _prepare(rows)
    assert len(prepared["records"]) == len(rows)
    assert all("321" not in str(value) for value in prepared["records"])
