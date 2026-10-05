"""Generic scientific structure resolution tests."""
from dataclasses import replace

import pytest

from rudeus.science.known_material_artifact_curation import (
    ARTIFACT_INDEX_VERSION,
    ARTIFACT_RECEIPT_VERSION,
    ARTIFACT_REGISTRY_VERSION,
    ArtifactRegistry,
    ArtifactRegistryEntry,
    ArtifactRetentionIndex,
    ArtifactRetentionReceipt,
)
from rudeus.science.known_material_structure_resolution import (
    STRUCTURE_RESOLUTION_VERSION,
    ResolutionMode,
    ResolutionStatus,
    StructureResolutionManifest,
    StructureResolutionSpec,
    resolve_structure_case,
)


def entry(key, material="m1"):
    return ArtifactRegistryEntry(
        artifact_key=key,
        material_key=material,
        chemistry_family="family",
        artifact_kind="REFERENCE_STRUCTURE",
        source_adapter="cod-cif-v1",
        source_config={"cod_id": "7215448", "revision": 1},
        validation={
            "expected_formula": "Li1",
            "expected_space_group_number": 1,
        },
        retained_path=f"data/benchmarks/known_material/structures/cod/{key}.cif",
        receipt_path=f"data/benchmarks/known_material/receipts/{key}.json",
    )


def receipt(item, sha):
    return ArtifactRetentionReceipt(
        receipt_version=ARTIFACT_RECEIPT_VERSION,
        artifact_key=item.artifact_key,
        material_key=item.material_key,
        artifact_kind=item.artifact_kind,
        source_adapter=item.source_adapter,
        source_id="cod:7215448@1",
        pinned_locator="https://www.crystallography.net/cod/7215448.cif@1",
        license_id="CC0-1.0",
        artifact_sha256=sha,
        byte_count=10,
        retained_path=item.retained_path,
        validation_summary={"verified": True},
    )


def registry(*items):
    return ArtifactRegistry(
        registry_version=ARTIFACT_REGISTRY_VERSION,
        entries=items,
    )


def index(*items):
    return ArtifactRetentionIndex(
        index_version=ARTIFACT_INDEX_VERSION,
        receipts=items,
    )


def spec(*, mode="DIRECT", keys=("a",), material="m1", required=(), blockers=()):
    return StructureResolutionSpec(
        resolution_key="case",
        material_key=material,
        chemistry_family="family",
        mode=mode,
        artifact_keys=keys,
        phase_identity="phase",
        composition_identity="Li1",
        representation_policy_id="policy-v1",
        reference_conditions={"temperature_K": 300},
        required_policy_inputs=required,
        scientific_blockers=blockers,
    )


def test_direct_case_becomes_ready_only_after_artifact_and_policy_are_satisfied():
    a = entry("a")
    case = spec(required=("ordered_realization_policy",))
    missing = resolve_structure_case(case, registry(a), index())
    assert missing.status == ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value

    retained = index(receipt(a, "1" * 64))
    policy_blocked = resolve_structure_case(case, registry(a), retained)
    assert policy_blocked.status == ResolutionStatus.BLOCKED_POLICY.value
    assert policy_blocked.unresolved_requirements == ("ordered_realization_policy",)

    ready = resolve_structure_case(
        case,
        registry(a),
        retained,
        satisfied_policy_inputs=("ordered_realization_policy",),
    )
    assert ready.status == ResolutionStatus.READY.value
    assert ready.artifact_hashes == ("1" * 64,)


def test_phase_set_supports_multiple_artifacts_for_one_material():
    low = entry("low")
    high = entry("high")
    case = spec(
        mode=ResolutionMode.PHASE_SET.value,
        keys=("low", "high"),
    )
    resolved = resolve_structure_case(
        case,
        registry(low, high),
        index(receipt(low, "1" * 64), receipt(high, "2" * 64)),
    )
    assert resolved.status == ResolutionStatus.READY.value
    assert resolved.artifact_keys == ("low", "high")
    assert resolved.artifact_hashes == ("1" * 64, "2" * 64)


def test_ensemble_supports_multiple_realizations_without_material_specific_code():
    a = entry("r1")
    b = entry("r2")
    case = spec(
        mode=ResolutionMode.ENSEMBLE.value,
        keys=("r1", "r2"),
        required=("ensemble_weight_policy",),
    )
    blocked = resolve_structure_case(
        case,
        registry(a, b),
        index(receipt(a, "1" * 64), receipt(b, "2" * 64)),
    )
    assert blocked.status == ResolutionStatus.BLOCKED_POLICY.value

    ready = resolve_structure_case(
        case,
        registry(a, b),
        index(receipt(a, "1" * 64), receipt(b, "2" * 64)),
        satisfied_policy_inputs=("ensemble_weight_policy",),
    )
    assert ready.status == ResolutionStatus.READY.value


def test_unrepresentable_control_is_explicit_not_silently_coerced():
    case = spec(
        mode=ResolutionMode.UNREPRESENTABLE.value,
        keys=(),
        blockers=("periodic_bulk_cannot_encode_required_microstructure",),
    )
    resolved = resolve_structure_case(case, registry(entry("unused")), index())
    assert resolved.status == ResolutionStatus.UNREPRESENTABLE.value
    assert resolved.artifact_keys == ()
    assert resolved.scientific_blockers


def test_cross_material_artifact_binding_fails_closed():
    foreign = entry("foreign", material="m2")
    with pytest.raises(ValueError, match="cross-binds"):
        resolve_structure_case(spec(keys=("foreign",)), registry(foreign), index())


def test_unknown_registry_artifact_fails_closed():
    with pytest.raises(ValueError, match="outside registry"):
        resolve_structure_case(spec(keys=("missing",)), registry(entry("a")), index())


def test_direct_mode_rejects_multiple_artifacts():
    with pytest.raises(ValueError, match="exactly one artifact"):
        spec(mode=ResolutionMode.DIRECT.value, keys=("a", "b"))


def test_manifest_is_data_driven_and_accepts_multiple_modes():
    direct = spec()
    phase_set = replace(
        direct,
        resolution_key="phase-set",
        mode=ResolutionMode.PHASE_SET.value,
        artifact_keys=("a", "b"),
    )
    ensemble = replace(
        direct,
        resolution_key="ensemble",
        mode=ResolutionMode.ENSEMBLE.value,
        artifact_keys=("a", "b"),
    )
    unrepresentable = replace(
        direct,
        resolution_key="unrepresentable",
        mode=ResolutionMode.UNREPRESENTABLE.value,
        artifact_keys=(),
        scientific_blockers=("scope_not_representable",),
    )
    manifest = StructureResolutionManifest(
        structure_resolution_version=STRUCTURE_RESOLUTION_VERSION,
        specs=(direct, phase_set, ensemble, unrepresentable),
    )
    assert {item.mode for item in manifest.specs} == {
        "DIRECT", "PHASE_SET", "ENSEMBLE", "UNREPRESENTABLE"
    }
