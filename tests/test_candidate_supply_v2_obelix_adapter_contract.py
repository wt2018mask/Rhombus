"""Static RED contract for adapting a caller-supplied OBELiX checkout.

All checkouts in this file are synthetic temporary Git repositories. The
adapter's parser is injected; these tests do not require pymatgen or network.
"""

import copy
import hashlib
import importlib
import json
import shutil
import socket
import subprocess
import urllib.request

import pytest


ADAPTER_SCHEMA = "candidate-supply-v2-obelix-adapter-v1"
CSV_RELATIVE = "data/processed.csv"
CIF_RELATIVE = "data/randomized_cifs"
CONDUCTIVITY = "Ionic conductivity (S cm-1)"


def _config(**overrides):
    config = {
        "source_name": "synthetic-obelix",
        "source_namespace": "obelix",
        "source_schema_version": "synthetic-processed-csv-v1",
        "source_artifact_id": "synthetic-checkout",
        "processed_csv_relative_path": CSV_RELATIVE,
        "cif_dir_relative_path": CIF_RELATIVE,
        "id_column": "ID",
        "required_selection_columns": [],
        "adapter_config_identity": {
            "schema_version": "synthetic-adapter-config-v1",
            "content_sha256": "fixture-config-digest",
        },
    }
    config.update(overrides)
    return config


def _csv_bytes():
    return (
        f"ID,Composition,{CONDUCTIVITY}\n"
        "a,Li2O,0.1\n"
        "b,Li2S,99.0\n"
        "c,LiCl,1.5\n"
    ).encode("utf-8")


def _git(root, *args):
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _commit_fixture(root):
    _git(root, "add", ".")
    _git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
         "commit", "-m", "synthetic snapshot")


def _checkout(tmp_path, *, csv_bytes=None, cifs=None, git=True):
    root = tmp_path / "synthetic-obelix"
    cif_dir = root / CIF_RELATIVE
    cif_dir.mkdir(parents=True)
    if csv_bytes is not False:
        (root / CSV_RELATIVE).write_bytes(
            _csv_bytes() if csv_bytes is None else csv_bytes
        )
    for name, contents in (cifs if cifs is not None else {
        "a.cif": b"synthetic CIF a\n",
        "c.cif": b"synthetic CIF c\n",
    }).items():
        target = cif_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
    if git:
        _git(root, "init")
        _commit_fixture(root)
    return root


class _SyntheticStructure:
    def __init__(self, digest):
        self.structure_sha256 = digest
        self.is_ordered = True


def _parser(calls=None, *, fail_name=None):
    requested = calls if calls is not None else []

    def parse(path):
        requested.append(path)
        if path.name == fail_name:
            raise ValueError("synthetic parse failure with unstable details")
        return _SyntheticStructure(hashlib.sha256(path.read_bytes()).hexdigest())

    return parse, requested


def _builder():
    module = importlib.import_module(
        "rudeus.generation.candidate_supply_obelix_adapter"
    )
    return module.build_candidate_supply_v2_obelix_adapter


def _build(root, *, config=None, parser=None):
    selected_parser = parser
    if selected_parser is None:
        selected_parser, _ = _parser()
    return _builder()(
        root,
        adapter_config=_config() if config is None else config,
        parser=selected_parser,
    )


def _inventory_digest(entries):
    encoded = json.dumps(
        entries, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_obelix_adapter_module_and_api_exist():
    assert callable(_builder())


@pytest.mark.parametrize("root_kind", ["none", "empty", "missing"])
def test_explicit_valid_checkout_root_required(tmp_path, root_kind):
    root = {"none": None, "empty": "", "missing": tmp_path / "missing"}[root_kind]
    with pytest.raises((TypeError, ValueError, FileNotFoundError)):
        _build(root)


def test_omitting_checkout_root_is_not_ambient_cwd_fallback():
    parser, _ = _parser()
    with pytest.raises(TypeError):
        _builder()(adapter_config=_config(), parser=parser)


def test_processed_csv_is_required(tmp_path):
    root = _checkout(tmp_path, csv_bytes=False)
    with pytest.raises((ValueError, FileNotFoundError)):
        _build(root)


def test_id_column_is_required(tmp_path):
    root = _checkout(tmp_path, csv_bytes=b"other_field\na\n")
    with pytest.raises((TypeError, ValueError)):
        _build(root)


def test_duplicate_csv_ids_fail_closed(tmp_path):
    root = _checkout(tmp_path, csv_bytes=b"ID\na\na\n")
    with pytest.raises((TypeError, ValueError)):
        _build(root)


def test_optional_scientific_fields_remain_optional_and_preserved(tmp_path):
    root = _checkout(tmp_path, csv_bytes=b"ID\na\nb\n")
    adapter = _build(root)
    assert [row["source_id"] for row in adapter.source_rows] == ["a", "b"]
    assert all(CONDUCTIVITY not in row for row in adapter.source_rows)


def test_declared_selection_column_must_exist(tmp_path):
    root = _checkout(tmp_path, csv_bytes=b"ID\na\n")
    config = _config(required_selection_columns=[CONDUCTIVITY])
    with pytest.raises((TypeError, ValueError)):
        _build(root, config=config)


def test_source_rows_are_lexically_ordered_not_conductivity_ranked(tmp_path):
    root = _checkout(tmp_path)
    adapter = _build(root)
    assert [row["source_id"] for row in adapter.source_rows] == ["a", "b", "c"]
    assert [row[CONDUCTIVITY] for row in adapter.source_rows] == [
        "0.1", "99.0", "1.5"
    ]
    assert all(not row["source_id"].startswith("obelix:") for row in adapter.source_rows)


def test_git_commit_and_tree_are_bound_to_supplied_checkout(tmp_path):
    root = _checkout(tmp_path)
    snapshot = _build(root).source_snapshot
    assert snapshot["source_repository_commit"] == _git(root, "rev-parse", "HEAD")
    assert snapshot["source_repository_tree"] == _git(root, "rev-parse", "HEAD^{tree}")
    assert snapshot["source_name"] == "synthetic-obelix"
    assert snapshot["source_dataset"] == "obelix"
    assert snapshot["source_schema_version"] == _config()["source_schema_version"]
    assert snapshot["adapter_schema_version"] == ADAPTER_SCHEMA
    assert snapshot["source_data_identity"]["processed_csv_relative_path"] == CSV_RELATIVE
    assert snapshot["source_data_identity"]["cif_dir_relative_path"] == CIF_RELATIVE


def test_non_git_checkout_is_rejected(tmp_path):
    root = _checkout(tmp_path, git=False)
    with pytest.raises((TypeError, ValueError)):
        _build(root)


def test_checkout_without_commit_or_tree_is_rejected(tmp_path):
    root = _checkout(tmp_path, git=False)
    _git(root, "init")
    with pytest.raises((TypeError, ValueError)):
        _build(root)


def test_dirty_checkout_is_rejected_rather_than_certified_as_clean(tmp_path):
    root = _checkout(tmp_path)
    (root / CSV_RELATIVE).write_bytes(_csv_bytes() + b"d,LiF,0.4\n")
    with pytest.raises((TypeError, ValueError)):
        _build(root)


def test_processed_csv_sha256_binds_exact_bytes(tmp_path):
    root = _checkout(tmp_path)
    before = _build(root).source_snapshot["source_data_identity"]["processed_csv_sha256"]
    assert before == hashlib.sha256(_csv_bytes()).hexdigest()
    (root / CSV_RELATIVE).write_bytes(_csv_bytes().replace(b"a,Li2O,0.1", b"a,Li2O,0.10"))
    _commit_fixture(root)
    after = _build(root).source_snapshot["source_data_identity"]["processed_csv_sha256"]
    assert after != before


def test_cif_inventory_has_raw_id_relative_path_and_presence(tmp_path):
    root = _checkout(tmp_path)
    adapter = _build(root)
    inventory = {entry["source_id"]: entry for entry in adapter.cif_inventory}
    assert list(inventory) == ["a", "b", "c"]
    assert inventory["a"]["relative_path"] == f"{CIF_RELATIVE}/a.cif"
    assert inventory["a"]["cif_present"] is True
    assert inventory["b"]["relative_path"] is None
    assert inventory["b"]["cif_present"] is False
    assert inventory["a"]["source_row_present"] is True


def test_each_present_cif_has_exact_content_sha256(tmp_path):
    root = _checkout(tmp_path)
    inventory = {e["source_id"]: e for e in _build(root).cif_inventory}
    expected = hashlib.sha256((root / CIF_RELATIVE / "a.cif").read_bytes()).hexdigest()
    assert inventory["a"]["content_sha256"] == expected
    assert inventory["b"]["content_sha256"] is None


def test_cif_inventory_digest_uses_canonical_ordered_entries(tmp_path):
    root = _checkout(tmp_path)
    adapter = _build(root)
    digest = adapter.source_snapshot["source_data_identity"]["cif_inventory_sha256"]
    assert digest == _inventory_digest(adapter.cif_inventory)
    assert len(digest) == 64


def test_cif_content_change_changes_inventory_digest(tmp_path):
    root = _checkout(tmp_path)
    before = _build(root).source_snapshot["source_data_identity"]["cif_inventory_sha256"]
    (root / CIF_RELATIVE / "a.cif").write_bytes(b"different synthetic CIF a\n")
    _commit_fixture(root)
    after = _build(root).source_snapshot["source_data_identity"]["cif_inventory_sha256"]
    assert after != before


def test_cif_added_or_removed_changes_inventory_and_linkage(tmp_path):
    root = _checkout(tmp_path)
    before = _build(root)
    (root / CIF_RELATIVE / "b.cif").write_bytes(b"synthetic CIF b\n")
    _commit_fixture(root)
    after = _build(root)
    assert after.source_snapshot["source_data_identity"]["cif_inventory_sha256"] != (
        before.source_snapshot["source_data_identity"]["cif_inventory_sha256"]
    )
    assert before.source_rows[1]["structure_ref"] is None
    assert after.source_rows[1]["structure_ref"] == f"{CIF_RELATIVE}/b.cif"


def test_csv_id_with_and_without_cif_are_both_retained(tmp_path):
    root = _checkout(tmp_path)
    rows = _build(root).source_rows
    assert len(rows) == 3
    assert rows[0]["structure_ref"] == f"{CIF_RELATIVE}/a.cif"
    assert rows[1]["structure_ref"] is None


def test_orphan_cif_is_audited_but_not_turned_into_source_row(tmp_path):
    root = _checkout(tmp_path)
    (root / CIF_RELATIVE / "orphan.cif").write_bytes(b"orphan synthetic CIF\n")
    _commit_fixture(root)
    adapter = _build(root)
    assert [row["source_id"] for row in adapter.source_rows] == ["a", "b", "c"]
    orphan = next(e for e in adapter.cif_inventory if e["source_id"] == "orphan")
    assert orphan["source_row_present"] is False
    assert orphan["cif_present"] is True
    assert orphan["relative_path"] == f"{CIF_RELATIVE}/orphan.cif"


def test_multiple_cifs_for_same_raw_id_are_rejected(tmp_path):
    root = _checkout(tmp_path, cifs={
        "a.cif": b"first synthetic CIF\n",
        "alternate/a.cif": b"second synthetic CIF\n",
    })
    with pytest.raises((TypeError, ValueError)):
        _build(root)


def test_known_present_provider_uses_injected_parser_once(tmp_path):
    root = _checkout(tmp_path)
    parser, calls = _parser()
    adapter = _build(root, parser=parser)
    structure = adapter.structure_provider("obelix:a")
    assert structure.structure_sha256 == hashlib.sha256(b"synthetic CIF a\n").hexdigest()
    assert structure.is_ordered is True
    assert calls == [root / CIF_RELATIVE / "a.cif"]


def test_known_missing_provider_returns_none_without_parser_call(tmp_path):
    root = _checkout(tmp_path)
    parser, calls = _parser()
    adapter = _build(root, parser=parser)
    assert adapter.structure_provider("obelix:b") is None
    assert calls == []


def test_unknown_provider_identity_fails_closed(tmp_path):
    root = _checkout(tmp_path)
    parser, calls = _parser()
    adapter = _build(root, parser=parser)
    with pytest.raises((KeyError, ValueError)):
        adapter.structure_provider("obelix:unknown")
    assert calls == []


def test_parser_failure_remains_visible_to_preparation_layer(tmp_path):
    root = _checkout(tmp_path)
    parser, calls = _parser(fail_name="a.cif")
    adapter = _build(root, parser=parser)
    with pytest.raises(ValueError, match="synthetic parse failure"):
        adapter.structure_provider("obelix:a")
    assert calls == [root / CIF_RELATIVE / "a.cif"]


def test_adapter_construction_does_not_eagerly_parse_cifs(tmp_path):
    root = _checkout(tmp_path)
    parser, calls = _parser()
    _build(root, parser=parser)
    assert calls == []


def test_provider_requests_are_deterministic_and_have_no_hidden_retries(tmp_path):
    root = _checkout(tmp_path)
    parser, calls = _parser()
    adapter = _build(root, parser=parser)
    assert adapter.structure_provider("obelix:c").structure_sha256
    assert adapter.structure_provider("obelix:a").structure_sha256
    assert calls == [root / CIF_RELATIVE / "c.cif", root / CIF_RELATIVE / "a.cif"]


def test_absolute_checkout_root_does_not_enter_scientific_identity(tmp_path):
    first_root = _checkout(tmp_path / "first")
    second_root = tmp_path / "second" / "synthetic-obelix"
    second_root.parent.mkdir()
    shutil.copytree(first_root, second_root)
    first = _build(first_root)
    second = _build(second_root)
    assert first.source_rows == second.source_rows
    assert first.cif_inventory == second.cif_inventory
    assert first.source_snapshot == second.source_snapshot
    assert str(first_root) not in str(first.source_snapshot)
    assert str(second_root) not in str(second.source_snapshot)


def test_adapter_does_not_mutate_checkout_or_git_state(tmp_path):
    root = _checkout(tmp_path)
    head_before = _git(root, "rev-parse", "HEAD")
    csv_before = (root / CSV_RELATIVE).read_bytes()
    cif_before = (root / CIF_RELATIVE / "a.cif").read_bytes()
    parser, _ = _parser()
    adapter = _build(root, parser=parser)
    adapter.structure_provider("obelix:a")
    assert (root / CSV_RELATIVE).read_bytes() == csv_before
    assert (root / CIF_RELATIVE / "a.cif").read_bytes() == cif_before
    assert _git(root, "rev-parse", "HEAD") == head_before
    assert _git(root, "status", "--porcelain") == ""


def test_adapter_uses_no_network_or_git_fetch_clone(tmp_path, monkeypatch):
    root = _checkout(tmp_path)
    original_run = subprocess.run

    def guarded_run(command, *args, **kwargs):
        assert not any(str(part).lower() in {"fetch", "pull", "clone"} for part in command)
        return original_run(command, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "run", guarded_run)
        patch.setattr(socket, "create_connection", lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("unexpected network connection")
        ))
        patch.setattr(urllib.request, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("unexpected network request")
        ))
        adapter = _build(root)
    assert len(adapter.source_rows) == 3


def test_adapter_does_not_enter_preparation_or_runtime_layers(tmp_path, monkeypatch):
    root = _checkout(tmp_path)
    adapter_module = importlib.import_module(
        "rudeus.generation.candidate_supply_obelix_adapter"
    )
    forbidden = (
        "rudeus.generation.candidate_supply_source_preparation",
        "rudeus.generation.candidate_supply_source_universe",
        "rudeus.generation.fresh_parent_cohort",
        "rudeus.generation.scheduler", "rudeus.generation.generator",
        "rudeus.filters", "rudeus.mlip",
    )
    original_import = __import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith(forbidden):
            raise AssertionError("adapter entered a downstream layer")
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr("builtins.__import__", guarded_import)
        parser, _ = _parser()
        result = adapter_module.build_candidate_supply_v2_obelix_adapter(
            root, adapter_config=_config(), parser=parser,
        )
    assert len(result.source_rows) == 3


def test_adapter_output_feeds_preparation_without_provenance_reconstruction(tmp_path):
    root = _checkout(tmp_path)
    adapter = _build(root)
    preparation = importlib.import_module(
        "rudeus.generation.candidate_supply_source_preparation"
    )
    selection = {
        "source_namespace": "obelix",
        "source_id_field": "source_id",
        "structure_ref_field": "structure_ref",
        "ordering_rule": "PARENT_ID_LEXICAL",
        "eligibility_rule": {
            "require_source_row": True, "require_cif": True,
            "require_parse_success": True, "require_ordered_structure": False,
        },
        "selection_config_identity": {
            "schema_version": "synthetic-selection-v1",
            "content_sha256": "fixture-selection-digest",
        },
    }
    prepared = preparation.prepare_candidate_supply_v2_source_records(
        adapter.source_rows,
        source_snapshot=adapter.source_snapshot,
        structure_provider=adapter.structure_provider,
        selection_config=selection,
    )
    assert [r["parent_id"] for r in prepared["records"]] == [
        "obelix:a", "obelix:b", "obelix:c"
    ]
    assert prepared["records"][1]["ineligibility_reasons"] == ["CIF_MISSING"]


def test_equal_observational_count_does_not_certify_historical_identity(tmp_path):
    root = _checkout(tmp_path)
    historical_observational_count = 2
    adapter = _build(root)
    assert sum(e["cif_present"] for e in adapter.cif_inventory) == historical_observational_count
    assert adapter.source_snapshot.get("historical_universe_identity_verified") is not True
    assert adapter.adapter_provenance.get("historical_universe_identity_verified") is not True


def test_identical_checkout_and_config_yield_identical_evidence(tmp_path):
    root = _checkout(tmp_path)
    first = _build(root)
    second = _build(root)
    assert first.source_rows == second.source_rows
    assert first.source_snapshot == second.source_snapshot
    assert first.cif_inventory == second.cif_inventory
    assert first.adapter_provenance == second.adapter_provenance
    assert "timestamp" not in first.source_snapshot
    assert "uuid" not in first.source_snapshot


def test_adapter_config_is_immutable_and_nested_output_is_detached(tmp_path):
    root = _checkout(tmp_path)
    config = _config(required_selection_columns=[CONDUCTIVITY])
    original = copy.deepcopy(config)
    adapter = _build(root, config=config)
    assert config == original
    adapter.adapter_provenance["adapter_config"]["required_selection_columns"].append("other")
    assert config == original
