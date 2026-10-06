"""Generic known-material artifact curation tests."""
import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from pymatgen.core import Structure

import rudeus.science.known_material_artifact_curation as curation_module
from rudeus.science.known_material_artifact_curation import (
    ARTIFACT_INDEX_VERSION,
    ARTIFACT_RECEIPT_VERSION,
    ARTIFACT_REGISTRY_VERSION,
    ARTIFACT_VERIFICATION_VERSION,
    ArtifactKind,
    ArtifactRegistry,
    ArtifactRetentionIndex,
    ArtifactRetentionReceipt,
    CurationScope,
    adapter_for,
    apply_retention_receipt,
    build_curation_plan,
    load_registry,
    load_retention_index,
    verify_retention_repository_state,
)


REGISTRY = Path("data/benchmarks/known_material/artifact_registry_v1.json")
INDEX = Path("data/benchmarks/known_material/artifact_retention_index_v1.json")


def registry():
    return load_registry(REGISTRY)


def repository_index():
    return load_retention_index(INDEX)


def empty_index():
    return ArtifactRetentionIndex(
        index_version=ARTIFACT_INDEX_VERSION,
        receipts=(),
    )


def receipt_for(
    entry,
    *,
    sha="0" * 64,
    byte_count=9264,
    retained_path=None,
):
    return ArtifactRetentionReceipt(
        receipt_version=ARTIFACT_RECEIPT_VERSION,
        artifact_key=entry.artifact_key,
        material_key=entry.material_key,
        artifact_kind=entry.artifact_kind,
        source_adapter=entry.source_adapter,
        source_id="cod:7215448@176453",
        pinned_locator="https://www.crystallography.net/cod/7215448.cif@176453",
        license_id="CC0-1.0",
        artifact_sha256=sha,
        byte_count=byte_count,
        retained_path=retained_path or entry.retained_path,
        validation_summary={"source_verified": True},
    )


def test_registry_and_retention_index_are_versioned_data_contracts():
    reg = registry()
    idx = repository_index()
    assert reg.registry_version == ARTIFACT_REGISTRY_VERSION
    assert idx.index_version == ARTIFACT_INDEX_VERSION
    assert reg.entries
    assert len({entry.artifact_key for entry in reg.entries}) == len(reg.entries)
    assert len({receipt.artifact_key for receipt in idx.receipts}) == len(idx.receipts)
    assert {receipt.artifact_key for receipt in idx.receipts}.issubset(
        {entry.artifact_key for entry in reg.entries}
    )


@pytest.mark.parametrize(
    ("scope", "selector"),
    [
        (CurationScope.UNRESOLVED.value, None),
        (CurationScope.ALL.value, None),
        (CurationScope.MATERIAL.value, "llzo-cubic-al-stabilized"),
        (CurationScope.FAMILY.value, "oxide-garnet"),
        (CurationScope.SOURCE.value, "cod-cif-v1"),
    ],
)
def test_planner_supports_macro_scopes_without_material_code_changes(scope, selector):
    plan = build_curation_plan(
        registry(),
        empty_index(),
        scope=scope,
        selector=selector,
    )
    assert plan.artifact_keys
    assert (
        "reference-structure:llzo-cubic-al-stabilized:cod:7215448@176453"
        in plan.artifact_keys
    )


@pytest.mark.parametrize(
    "scope",
    [
        CurationScope.MATERIAL.value,
        CurationScope.FAMILY.value,
        CurationScope.SOURCE.value,
    ],
)
def test_selected_scopes_require_selector(scope):
    with pytest.raises(ValueError, match="requires a selector"):
        build_curation_plan(registry(), empty_index(), scope=scope, selector=None)


def test_unresolved_scope_is_driven_by_artifact_key_not_material_identity():
    reg = registry()
    entry = reg.entries[0]
    retained = apply_retention_receipt(empty_index(), receipt_for(entry))
    plan = build_curation_plan(
        reg,
        retained,
        scope=CurationScope.UNRESOLVED.value,
    )
    assert set(plan.artifact_keys) == {
        "reference-structure:li2s-microcrystalline:cod:9009060@latest-freeze-v1",
        "reference-structure:li3n-crystalline:literature-reconstruction:alpha-v1",
        "reference-structure:lialo2-gamma:cod:1008166@latest-freeze-v1",
        "reference-structure:libh4-phase-transition-pair:cod:1504402@latest-freeze-v1",
        "reference-structure:libh4-phase-transition-pair:cod:1504403@latest-freeze-v1",
        "reference-structure:llzo-tetragonal-undoped:literature-reconstruction:awaka-2009-nd-v1",
    }


def test_latest_freeze_cod_adapter_freezes_exact_bytes_without_revision_claim(
    tmp_path,
    monkeypatch,
):
    entry = next(
        item for item in registry().entries
        if item.source_adapter == "cod-cif-latest-freeze-v1"
    )
    payload = b"""data_9009060
_cod_database_code 9009060
_chemical_formula_sum 'Li2 S'
_space_group_IT_number 225
loop_
_atom_site_label
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Li1 0.25 0.25 0.25
S1 0.0 0.0 0.0
"""
    monkeypatch.setattr(curation_module, "_download", lambda url: payload)

    receipt = adapter_for(entry.source_adapter).retain(
        entry,
        repo_root=tmp_path,
    )

    expected_sha = hashlib.sha256(payload).hexdigest()
    assert receipt.source_id == f"cod:9009060@sha256:{expected_sha}"
    assert receipt.pinned_locator.endswith("/9009060.cif")
    assert receipt.artifact_sha256 == expected_sha
    assert receipt.validation_summary["revision"] == "UNASSERTED"
    assert receipt.validation_summary["retention_policy"] == (
        "latest-uri-freeze-by-sha256-v1"
    )
    assert (tmp_path / entry.retained_path).read_bytes() == payload


def test_literature_structure_adapter_is_offline_deterministic(tmp_path):
    entry = next(
        item for item in registry().entries
        if item.source_adapter == "literature-ordered-cif-v1"
    )
    first = adapter_for(entry.source_adapter).retain(entry, repo_root=tmp_path)
    payload = (tmp_path / entry.retained_path).read_bytes()
    second = adapter_for(entry.source_adapter).retain(entry, repo_root=tmp_path)

    assert first.content_hash == second.content_hash
    assert first.artifact_sha256 == hashlib.sha256(payload).hexdigest()
    assert first.validation_summary["publisher_bytes_retained"] is False
    assert first.validation_summary["expected_space_group_number"] == 191
    assert set(first.validation_summary["source_ids"]) == {
        "doi:10.1016/0022-5088(76)90263-0",
        "doi:10.1016/j.ssc.2009.09.029",
    }
    text = payload.decode("utf-8")
    assert "_space_group_IT_number 191" in text
    assert "_chemical_formula_sum 'Li3 N'" in text
    assert "Li1 Li 0 0 0.5 1" in text


def test_asymmetric_literature_structure_adapter_reconstructs_tetragonal_llzo(
    tmp_path,
):
    entry = next(
        item for item in registry().entries
        if item.source_adapter == "literature-asymmetric-cif-v1"
    )
    receipt = adapter_for(entry.source_adapter).retain(
        entry,
        repo_root=tmp_path,
    )
    payload = (tmp_path / entry.retained_path).read_bytes()

    assert receipt.artifact_sha256 == hashlib.sha256(payload).hexdigest()
    assert receipt.validation_summary["publisher_bytes_retained"] is False
    assert receipt.validation_summary["formula_units_z"] == 8
    assert receipt.validation_summary["expected_space_group_number"] == 142

    text = payload.decode("utf-8")
    assert "_cell_formula_units_Z 8" in text
    assert "_atom_site_symmetry_multiplicity" in text
    assert "Li3 Li 32 g 0.0806 0.0857 0.8041 1" in text
    assert "O1 O 32 g -0.0338 0.0548 0.1524 1" in text

    structure = Structure.from_str(text, fmt="cif")
    assert len(structure) == 192
    assert structure.composition.reduced_formula == "Li7La3Zr2O12"


def test_retention_index_is_idempotent_for_identical_receipt():
    entry = registry().entries[0]
    receipt = receipt_for(entry)
    first = apply_retention_receipt(empty_index(), receipt)
    second = apply_retention_receipt(first, receipt)
    assert second.content_hash == first.content_hash
    assert len(second.receipts) == 1


def test_retention_index_rejects_conflicting_bytes_for_same_artifact_key():
    entry = registry().entries[0]
    first = apply_retention_receipt(
        empty_index(),
        receipt_for(entry, sha="1" * 64),
    )
    with pytest.raises(ValueError, match="artifact key conflicts"):
        apply_retention_receipt(first, receipt_for(entry, sha="2" * 64))


def test_retention_index_supports_multiple_artifacts_for_one_material():
    base = registry().entries[0]
    second_entry = replace(
        base,
        artifact_key=base.artifact_key + ":second-phase",
        retained_path=(
            "data/benchmarks/known_material/structures/cod/"
            "7215448-r176453-second-phase.cif"
        ),
        receipt_path=(
            "data/benchmarks/known_material/receipts/artifacts/"
            "second-phase.json"
        ),
    )
    first = apply_retention_receipt(
        empty_index(),
        receipt_for(base, sha="1" * 64),
    )
    second_receipt = ArtifactRetentionReceipt(
        receipt_version=ARTIFACT_RECEIPT_VERSION,
        artifact_key=second_entry.artifact_key,
        material_key=second_entry.material_key,
        artifact_kind=ArtifactKind.REFERENCE_STRUCTURE.value,
        source_adapter=second_entry.source_adapter,
        source_id="cod:7215448@176453",
        pinned_locator="https://www.crystallography.net/cod/7215448.cif@176453",
        license_id="CC0-1.0",
        artifact_sha256="2" * 64,
        byte_count=9000,
        retained_path=second_entry.retained_path,
        validation_summary={"phase": "second"},
    )
    retained = apply_retention_receipt(first, second_receipt)
    assert len(retained.receipts) == 2
    assert {item.material_key for item in retained.receipts} == {
        "llzo-cubic-al-stabilized"
    }


def test_future_material_can_be_added_by_registry_data_only():
    base = registry().entries[0]
    future = replace(
        base,
        artifact_key="reference-structure:future-material:cod:7654321@2",
        material_key="future-material",
        chemistry_family="future-family",
        source_config={"cod_id": "7654321", "revision": 2},
        retained_path=(
            "data/benchmarks/known_material/structures/cod/"
            "7654321-r2.cif"
        ),
        receipt_path=(
            "data/benchmarks/known_material/receipts/artifacts/"
            "reference-structure-future-material-cod-7654321-r2.json"
        ),
    )
    expanded = ArtifactRegistry(
        registry_version=ARTIFACT_REGISTRY_VERSION,
        entries=(base, future),
    )
    material_plan = build_curation_plan(
        expanded,
        empty_index(),
        scope=CurationScope.MATERIAL.value,
        selector="future-material",
    )
    family_plan = build_curation_plan(
        expanded,
        empty_index(),
        scope=CurationScope.FAMILY.value,
        selector="future-family",
    )
    all_plan = build_curation_plan(
        expanded,
        empty_index(),
        scope=CurationScope.ALL.value,
    )
    assert material_plan.artifact_keys == (future.artifact_key,)
    assert family_plan.artifact_keys == (future.artifact_key,)
    assert future.artifact_key in all_plan.artifact_keys


def test_post_curation_verifier_checks_index_bytes_and_persisted_receipt(tmp_path):
    entry = registry().entries[0]
    payload = b"retained-structure-bytes"
    digest = hashlib.sha256(payload).hexdigest()
    receipt = receipt_for(
        entry,
        sha=digest,
        byte_count=len(payload),
    )
    idx = apply_retention_receipt(empty_index(), receipt)

    artifact_path = tmp_path / entry.retained_path
    receipt_path = tmp_path / entry.receipt_path
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(payload)
    receipt_path.write_text(
        json.dumps(receipt.to_dict(), sort_keys=True),
        encoding="utf-8",
    )

    report = verify_retention_repository_state(
        registry(),
        idx,
        repo_root=tmp_path,
    )
    assert report.verification_version == ARTIFACT_VERIFICATION_VERSION
    assert report.checked_artifact_keys == (entry.artifact_key,)


def test_post_curation_verifier_rejects_orphaned_retained_files(tmp_path):
    entry = registry().entries[0]
    payload = b"orphaned-structure"
    digest = hashlib.sha256(payload).hexdigest()
    receipt = receipt_for(
        entry,
        sha=digest,
        byte_count=len(payload),
    )
    artifact_path = tmp_path / entry.retained_path
    receipt_path = tmp_path / entry.receipt_path
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(payload)
    receipt_path.write_text(
        json.dumps(receipt.to_dict(), sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not indexed"):
        verify_retention_repository_state(
            registry(),
            empty_index(),
            repo_root=tmp_path,
        )


def test_post_curation_verifier_rejects_modified_bytes(tmp_path):
    entry = registry().entries[0]
    expected = b"expected"
    receipt = receipt_for(
        entry,
        sha=hashlib.sha256(expected).hexdigest(),
        byte_count=len(expected),
    )
    idx = apply_retention_receipt(empty_index(), receipt)

    artifact_path = tmp_path / entry.retained_path
    receipt_path = tmp_path / entry.receipt_path
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(b"tampered")
    receipt_path.write_text(
        json.dumps(receipt.to_dict(), sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="SHA256 mismatch"):
        verify_retention_repository_state(
            registry(),
            idx,
            repo_root=tmp_path,
        )


def test_unknown_adapter_fails_closed():
    with pytest.raises(ValueError, match="unsupported artifact source adapter"):
        adapter_for("not-a-real-adapter")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("retained_path", "../../escape.cif", "repository-relative"),
        ("retained_path", "README.md", "structure root"),
        ("receipt_path", "receipt.json", "receipt root"),
    ],
)
def test_registry_paths_are_confined(field, value, message):
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    raw["entries"][0][field] = value
    with pytest.raises(ValueError, match=message):
        ArtifactRegistry.from_dict(raw)


def test_workflow_contains_no_material_allowlist():
    workflow = Path(
        ".github/workflows/known-material-artifact-curation.yml"
    ).read_text(encoding="utf-8")
    assert "llzo-cubic-al-stabilized" not in workflow
    assert "material_key:" not in workflow
    assert "scope:" in workflow
    assert "selector:" in workflow


def test_curation_workflow_separates_preflight_mutation_and_post_verification():
    workflow = Path(
        ".github/workflows/known-material-artifact-curation.yml"
    ).read_text(encoding="utf-8")
    preflight = workflow.index("Run pre-curation focused regression")
    mutate = workflow.index("Curate selected artifacts")
    verify = workflow.index("Verify persisted curation state")
    commit = workflow.index("Commit verified data on curation branch")
    assert preflight < mutate < verify < commit


def test_registry_outputs_are_git_trackable_under_repository_policy():
    paths = {
        INDEX.as_posix(),
        *(
            path
            for entry in registry().entries
            for path in (entry.retained_path, entry.receipt_path)
        ),
    }
    for path in sorted(paths):
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", path],
            check=False,
        )
        assert result.returncode == 1, f"curated benchmark path is ignored: {path}"


def test_repository_policy_keeps_unrelated_data_ignored():
    result = subprocess.run(
        [
            "git",
            "check-ignore",
            "--no-index",
            "-q",
            "data/unrelated-heavy-artifact.bin",
        ],
        check=False,
    )
    assert result.returncode == 0
