"""Generic model-domain snapshot contract tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from rudeus.science.known_material_model_domain import (
    MACE_DOMAIN_ADAPTER,
    MODEL_DOMAIN_INDEX_VERSION,
    MODEL_DOMAIN_REGISTRY_VERSION,
    MODEL_DOMAIN_SNAPSHOT_VERSION,
    ModelDomainIndex,
    ModelDomainRegistryEntry,
    check_model_domain,
    deterministic_unsupported_atomic_number,
    extract_model_domain_snapshot,
    load_model_domain_index,
    load_model_domain_registry,
    load_model_domain_snapshot,
    plan_model_domain_entries,
    persist_model_domain_index,
    retain_model_domain_snapshot,
    verify_model_domain_repository_state,
)


ROOT = Path("data/benchmarks/known_material")
REGISTRY = ROOT / "model_domain_registry_v1.json"
INDEX = ROOT / "model_domain_snapshot_index_v1.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synthetic_entry(
    checkpoint_sha256: str,
    *,
    expected_element_count: int | None = 3,
) -> ModelDomainRegistryEntry:
    return ModelDomainRegistryEntry(
        domain_key="mlip-domain:test-model",
        model_id="test-model",
        source_adapter=MACE_DOMAIN_ADAPTER,
        checkpoint_url="https://example.com/test.model",
        checkpoint_sha256=checkpoint_sha256,
        expected_element_count=expected_element_count,
        package_constraint="mace-torch==0.3.16",
        snapshot_path=(
            "data/benchmarks/known_material/model_domains/test-model.json"
        ),
        evidence_refs=("fixture:test-model",),
    )


def test_canonical_registry_is_pinned_and_snapshot_index_starts_empty():
    registry = load_model_domain_registry(REGISTRY)
    index = load_model_domain_index(INDEX)

    assert registry.registry_version == MODEL_DOMAIN_REGISTRY_VERSION
    assert len(registry.entries) == 1
    entry = registry.entries[0]
    assert entry.domain_key == "mlip-domain:medium-mpa-0"
    assert entry.model_id == "medium-mpa-0"
    assert entry.checkpoint_sha256 == (
        "75428afe3a1d7d8062e19bcaabd5c433"
        "623cabf308242ec9fb493e38604fb638"
    )
    assert entry.expected_element_count == 89
    assert entry.package_constraint == "mace-torch==0.3.16"

    assert index.index_version == MODEL_DOMAIN_INDEX_VERSION
    assert index.entries == ()


def test_extract_snapshot_uses_checkpoint_domain_not_hardcoded_species(tmp_path):
    payload = b"synthetic-checkpoint"
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(payload)
    entry = synthetic_entry(_sha(payload))

    calls = []

    def loader(path):
        calls.append(path)
        return (8, 1, 3), "mace-torch", "0.3.16"

    snapshot = extract_model_domain_snapshot(
        entry,
        checkpoint_path=checkpoint,
        loader=loader,
    )

    assert calls == [checkpoint]
    assert snapshot.snapshot_version == MODEL_DOMAIN_SNAPSHOT_VERSION
    assert snapshot.model_atomic_number_order == (8, 1, 3)
    assert snapshot.supported_atomic_numbers == (1, 3, 8)
    assert snapshot.supported_symbols == ("H", "Li", "O")
    assert snapshot.element_count == 3
    assert 2 in snapshot.unsupported_atomic_numbers_1_to_118
    assert deterministic_unsupported_atomic_number(snapshot) == 2


def test_extract_snapshot_rejects_checkpoint_hash_mismatch(tmp_path):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"wrong")
    entry = synthetic_entry("1" * 64)

    with pytest.raises(ValueError, match="checkpoint hash mismatch"):
        extract_model_domain_snapshot(
            entry,
            checkpoint_path=checkpoint,
            loader=lambda _: ((1, 3, 8), "mace-torch", "0.3.16"),
        )


def test_extract_snapshot_rejects_unpinned_runtime_package_version(tmp_path):
    payload = b"synthetic-checkpoint"
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(payload)
    entry = synthetic_entry(_sha(payload))

    with pytest.raises(ValueError, match="extractor package mismatch"):
        extract_model_domain_snapshot(
            entry,
            checkpoint_path=checkpoint,
            loader=lambda _: ((1, 3, 8), "mace-torch", "0.3.15"),
        )


def test_extract_snapshot_rejects_declared_element_count_mismatch(tmp_path):
    payload = b"synthetic-checkpoint"
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(payload)
    entry = synthetic_entry(_sha(payload), expected_element_count=4)

    with pytest.raises(ValueError, match="element count mismatch"):
        extract_model_domain_snapshot(
            entry,
            checkpoint_path=checkpoint,
            loader=lambda _: ((1, 3, 8), "mace-torch", "0.3.16"),
        )


def test_domain_check_returns_unknown_for_unsupported_species(tmp_path):
    payload = b"synthetic-checkpoint"
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(payload)
    snapshot = extract_model_domain_snapshot(
        synthetic_entry(_sha(payload)),
        checkpoint_path=checkpoint,
        loader=lambda _: ((1, 3, 8), "mace-torch", "0.3.16"),
    )

    supported = check_model_domain(snapshot, (1, 8))
    assert supported.supported is True
    assert supported.disposition == "SUPPORTED_BY_MODEL_DOMAIN"
    assert supported.unsupported_atomic_numbers == ()

    unsupported = check_model_domain(snapshot, (1, 2))
    assert unsupported.supported is False
    assert unsupported.disposition == "UNKNOWN_MODEL_DOMAIN_UNSUPPORTED"
    assert unsupported.unsupported_atomic_numbers == (2,)
    assert unsupported.reason_codes == ("MODEL_DOMAIN_UNSUPPORTED_SPECIES",)


def test_retention_is_idempotent_and_repository_verifiable(tmp_path):
    payload = b"synthetic-checkpoint"
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(payload)
    entry = synthetic_entry(_sha(payload))
    snapshot = extract_model_domain_snapshot(
        entry,
        checkpoint_path=checkpoint,
        loader=lambda _: ((1, 3, 8), "mace-torch", "0.3.16"),
    )
    index = ModelDomainIndex(
        index_version=MODEL_DOMAIN_INDEX_VERSION,
        entries=(),
    )

    retained = retain_model_domain_snapshot(
        entry=entry,
        snapshot=snapshot,
        index=index,
        repo_root=tmp_path,
    )
    retained_again = retain_model_domain_snapshot(
        entry=entry,
        snapshot=snapshot,
        index=retained,
        repo_root=tmp_path,
    )
    assert retained_again == retained

    index_path = tmp_path / "index.json"
    persist_model_domain_index(retained, index_path)
    loaded_snapshot = load_model_domain_snapshot(
        tmp_path / entry.snapshot_path
    )
    assert loaded_snapshot.content_hash == snapshot.content_hash

    registry = type(load_model_domain_registry(REGISTRY))(
        registry_version=MODEL_DOMAIN_REGISTRY_VERSION,
        entries=(entry,),
    )
    assert verify_model_domain_repository_state(
        registry,
        retained,
        repo_root=tmp_path,
    ) == (entry.domain_key,)


def test_repository_verifier_rejects_snapshot_byte_tampering(tmp_path):
    payload = b"synthetic-checkpoint"
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(payload)
    entry = synthetic_entry(_sha(payload))
    snapshot = extract_model_domain_snapshot(
        entry,
        checkpoint_path=checkpoint,
        loader=lambda _: ((1, 3, 8), "mace-torch", "0.3.16"),
    )
    retained = retain_model_domain_snapshot(
        entry=entry,
        snapshot=snapshot,
        index=ModelDomainIndex(
            index_version=MODEL_DOMAIN_INDEX_VERSION,
            entries=(),
        ),
        repo_root=tmp_path,
    )
    target = tmp_path / entry.snapshot_path
    target.write_bytes(target.read_bytes() + b" ")

    registry = type(load_model_domain_registry(REGISTRY))(
        registry_version=MODEL_DOMAIN_REGISTRY_VERSION,
        entries=(entry,),
    )
    with pytest.raises(ValueError, match="file SHA256 mismatch"):
        verify_model_domain_repository_state(
            registry,
            retained,
            repo_root=tmp_path,
        )


def test_retention_refuses_conflicting_snapshot_bytes(tmp_path):
    payload = b"synthetic-checkpoint"
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(payload)
    entry = synthetic_entry(_sha(payload))
    snapshot = extract_model_domain_snapshot(
        entry,
        checkpoint_path=checkpoint,
        loader=lambda _: ((1, 3, 8), "mace-torch", "0.3.16"),
    )
    target = tmp_path / entry.snapshot_path
    target.parent.mkdir(parents=True)
    target.write_text('{"conflict": true}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="conflicting model-domain snapshot"):
        retain_model_domain_snapshot(
            entry=entry,
            snapshot=snapshot,
            index=ModelDomainIndex(
                index_version=MODEL_DOMAIN_INDEX_VERSION,
                entries=(),
            ),
            repo_root=tmp_path,
        )


def test_planner_supports_bulk_unresolved_and_domain_scopes():
    registry = load_model_domain_registry(REGISTRY)
    empty = load_model_domain_index(INDEX)

    assert plan_model_domain_entries(
        registry, empty, scope="unresolved"
    ) == registry.entries
    assert plan_model_domain_entries(
        registry, empty, scope="all"
    ) == registry.entries
    assert plan_model_domain_entries(
        registry,
        empty,
        scope="domain",
        selector="mlip-domain:medium-mpa-0",
    ) == registry.entries

    with pytest.raises(ValueError, match="requires selector"):
        plan_model_domain_entries(registry, empty, scope="domain")


def test_model_domain_paths_are_git_trackable_but_unrelated_data_stays_ignored():
    registry = load_model_domain_registry(REGISTRY)
    paths = [
        str(INDEX),
        str(REGISTRY),
        *(entry.snapshot_path for entry in registry.entries),
    ]
    for path in paths:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", path],
            check=False,
        )
        assert result.returncode == 1, f"benchmark path is ignored: {path}"

    unrelated = subprocess.run(
        [
            "git",
            "check-ignore",
            "--no-index",
            "-q",
            "data/unrelated-model-checkpoint.bin",
        ],
        check=False,
    )
    assert unrelated.returncode == 0


def test_snapshot_workflow_installs_p0_runtime_before_failure_control_regression():
    workflow = Path(
        ".github/workflows/known-material-model-domain-snapshot.yml"
    ).read_text(encoding="utf-8")
    install = (
        "python -m pip install -c scripts/ci/constraints.txt "
        "torch mace-torch ase pymatgen smact pyyaml pytest"
    )
    assert install in workflow
    assert workflow.index(install) < workflow.index(
        "tests/test_known_material_failure_control_execution.py"
    )

    constraints = Path("scripts/ci/constraints.txt").read_text(encoding="utf-8")
    assert "smact==4.0.2" in constraints
