"""Generic known-material artifact curation tests."""
import json
from pathlib import Path

import pytest

from rudeus.science.known_material_artifact_curation import (
    ARTIFACT_REGISTRY_VERSION,
    ArtifactKind,
    ArtifactRegistry,
    ArtifactRetentionReceipt,
    CurationScope,
    adapter_for,
    apply_structure_retention_receipt,
    build_curation_plan,
    load_registry,
)
from rudeus.science.known_material_structure_binding import (
    StructureArtifactState,
    StructureBindingLedger,
)


REGISTRY = Path("data/benchmarks/known_material/artifact_registry_v1.json")
LEDGER = Path("data/benchmarks/known_material/b2_structure_binding_v1.json")


def registry():
    return load_registry(REGISTRY)


def ledger():
    return StructureBindingLedger.from_dict(
        json.loads(LEDGER.read_text(encoding="utf-8"))
    )


def test_registry_is_data_driven_and_versioned():
    value = registry()
    assert value.registry_version == ARTIFACT_REGISTRY_VERSION
    assert value.entries
    assert len({entry.artifact_key for entry in value.entries}) == len(value.entries)
    assert all(entry.material_key for entry in value.entries)
    assert all(entry.source_adapter for entry in value.entries)


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
        ledger(),
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
        build_curation_plan(registry(), ledger(), scope=scope, selector=None)


def test_unresolved_scope_is_derived_from_ledger_state():
    original = ledger()
    plan = build_curation_plan(
        registry(),
        original,
        scope=CurationScope.UNRESOLVED.value,
    )
    assert len(plan.artifact_keys) == 1

    binding = next(
        entry for entry in original.entries
        if entry.material_key == "llzo-cubic-al-stabilized"
    )
    receipt = ArtifactRetentionReceipt(
        receipt_version="known-material-artifact-receipt-v1",
        artifact_key=plan.artifact_keys[0],
        material_key=binding.material_key,
        artifact_kind=ArtifactKind.REFERENCE_STRUCTURE.value,
        source_adapter="cod-cif-v1",
        source_id=binding.source_id,
        pinned_locator=binding.artifact_locator,
        license_id="CC0-1.0",
        artifact_sha256="0" * 64,
        byte_count=1,
        retained_path=(
            "data/benchmarks/known_material/structures/cod/"
            "7215448-r176453.cif"
        ),
        validation_summary={"test": True},
    )
    retained = apply_structure_retention_receipt(original, receipt)
    plan_after = build_curation_plan(
        registry(),
        retained,
        scope=CurationScope.UNRESOLVED.value,
    )
    assert plan_after.artifact_keys == ()


def test_generic_receipt_promotes_structure_without_removing_science_blockers():
    original = ledger()
    binding = next(
        entry for entry in original.entries
        if entry.material_key == "llzo-cubic-al-stabilized"
    )
    entry = registry().entries[0]
    receipt = ArtifactRetentionReceipt(
        receipt_version="known-material-artifact-receipt-v1",
        artifact_key=entry.artifact_key,
        material_key=entry.material_key,
        artifact_kind=entry.artifact_kind,
        source_adapter=entry.source_adapter,
        source_id=binding.source_id,
        pinned_locator=binding.artifact_locator,
        license_id="CC0-1.0",
        artifact_sha256="1" * 64,
        byte_count=9264,
        retained_path=entry.retained_path,
        validation_summary={"source_verified": True},
    )
    updated = apply_structure_retention_receipt(original, receipt)
    after = next(
        item for item in updated.entries
        if item.material_key == entry.material_key
    )
    assert after.artifact_state == StructureArtifactState.ARTIFACT_RETAINED.value
    assert after.artifact_sha256 == "1" * 64
    assert after.retained_path == entry.retained_path
    assert "artifact_not_yet_retained_and_hashed" not in after.blockers
    assert "fractional_Li_Al_occupancy_execution_policy_required" in after.blockers
    assert not updated.b2_structure_closure_authorized


def test_unknown_adapter_fails_closed():
    with pytest.raises(ValueError, match="unsupported artifact source adapter"):
        adapter_for("not-a-real-adapter")


def test_registry_paths_cannot_escape_repository():
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    raw["entries"][0]["retained_path"] = "../../escape.cif"
    with pytest.raises(ValueError, match="repository-relative"):
        ArtifactRegistry.from_dict(raw)
