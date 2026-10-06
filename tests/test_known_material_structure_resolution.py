"""Generic scientific structure resolution tests."""
from dataclasses import replace
from pathlib import Path

import pytest

from rudeus.science.known_material_artifact_curation import (
    ARTIFACT_INDEX_VERSION,
    ARTIFACT_RECEIPT_VERSION,
    ARTIFACT_REGISTRY_VERSION,
    ArtifactRegistry,
    ArtifactRegistryEntry,
    ArtifactRetentionIndex,
    ArtifactRetentionReceipt,
    load_registry,
    load_retention_index,
)
from rudeus.science.known_material_representation_policy import (
    REPRESENTATION_EVIDENCE_LEDGER_VERSION,
    REPRESENTATION_POLICY_VERSION,
    RepresentationEvidenceDisposition,
    RepresentationEvidenceLedger,
    RepresentationPolicyEvidence,
    RepresentationPolicyKind,
    RepresentationPolicyRegistry,
    RepresentationPolicySpec,
    load_representation_evidence_ledger,
    load_representation_policy_registry,
)
from rudeus.science.known_material_structure_resolution import (
    STRUCTURE_RESOLUTION_LEDGER_VERSION,
    STRUCTURE_RESOLUTION_VERSION,
    ResolutionMode,
    ResolutionStatus,
    StructureResolutionManifest,
    StructureResolutionSpec,
    load_structure_resolution_manifest,
    resolve_structure_case,
    resolve_structure_manifest,
)


DATA_ROOT = Path("data/benchmarks/known_material")


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


def policy_registry(*, required=(), optional=()):
    return RepresentationPolicyRegistry(
        registry_version=REPRESENTATION_POLICY_VERSION,
        policies=(
            RepresentationPolicySpec(
                policy_id="policy-v1",
                policy_kind=RepresentationPolicyKind.EXACT.value,
                applicable_modes=("DIRECT", "PHASE_SET", "ENSEMBLE"),
                required_inputs=required,
                optional_inputs=optional,
                forbidden_shortcuts=("silent_proxy",),
                rationale=("test policy",),
            ),
        ),
    )


def policy_evidence(input_key, sha="3" * 64):
    return RepresentationPolicyEvidence(
        policy_id="policy-v1",
        input_key=input_key,
        disposition=RepresentationEvidenceDisposition.SATISFIED.value,
        provenance_hash=sha,
        evidence_refs=("artifact:test-policy",),
        payload={"strategy": "explicit"},
        rationale=("test evidence",),
    )


def policy_ledger(*items):
    return RepresentationEvidenceLedger(
        ledger_version=REPRESENTATION_EVIDENCE_LEDGER_VERSION,
        entries=items,
    )


def spec(
    *,
    mode="DIRECT",
    keys=("a",),
    material="m1",
    required=(),
    blockers=(),
    reference_conditions=None,
):
    return StructureResolutionSpec(
        resolution_key="case",
        material_key=material,
        chemistry_family="family",
        mode=mode,
        artifact_keys=keys,
        phase_identity="phase",
        composition_identity="Li1",
        representation_policy_id="policy-v1",
        reference_conditions=(
            reference_conditions
            if reference_conditions is not None
            else {"temperature_K": 300}
        ),
        required_policy_inputs=required,
        scientific_blockers=blockers,
    )


def resolve(case, reg, idx, *, policies=None, evidence=None):
    return resolve_structure_case(
        case,
        reg,
        idx,
        policy_registry=policies or policy_registry(),
        policy_evidence_ledger=evidence or policy_ledger(),
    )


def test_direct_case_becomes_ready_only_after_artifact_and_policy_evidence():
    a = entry("a")
    case = spec()
    policies = policy_registry(required=("ordered_realization_policy",))

    missing = resolve(case, registry(a), index(), policies=policies)
    assert missing.status == ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value
    assert missing.requested_artifact_keys == ("a",)
    assert missing.retained_artifact_keys == ()
    assert missing.artifact_hashes == ()
    assert missing.missing_artifact_keys == ("a",)
    assert missing.unresolved_requirements == ()

    retained = index(receipt(a, "1" * 64))
    policy_blocked = resolve(case, registry(a), retained, policies=policies)
    assert policy_blocked.status == ResolutionStatus.BLOCKED_POLICY.value
    assert policy_blocked.requested_artifact_keys == ("a",)
    assert policy_blocked.retained_artifact_keys == ("a",)
    assert policy_blocked.missing_artifact_keys == ()
    assert policy_blocked.unresolved_requirements == (
        "ordered_realization_policy",
    )

    ready = resolve(
        case,
        registry(a),
        retained,
        policies=policies,
        evidence=policy_ledger(
            policy_evidence("ordered_realization_policy")
        ),
    )
    assert ready.status == ResolutionStatus.READY.value
    assert ready.requested_artifact_keys == ("a",)
    assert ready.retained_artifact_keys == ("a",)
    assert ready.missing_artifact_keys == ()
    assert ready.artifact_hashes == ("1" * 64,)


def test_phase_set_reports_partial_retention_without_corrupting_alignment():
    low = entry("low")
    high = entry("high")
    case = spec(
        mode=ResolutionMode.PHASE_SET.value,
        keys=("low", "high"),
        reference_conditions={
            "phase_condition_mapping": {
                "low": {"artifact_key": "low", "temperature_scope": "low"},
                "high": {"artifact_key": "high", "temperature_scope": "high"},
            }
        },
    )
    partial = resolve(
        case,
        registry(low, high),
        index(receipt(low, "1" * 64)),
    )
    assert partial.status == ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value
    assert partial.requested_artifact_keys == ("low", "high")
    assert partial.retained_artifact_keys == ("low",)
    assert partial.artifact_hashes == ("1" * 64,)
    assert partial.missing_artifact_keys == ("high",)


def test_phase_set_supports_multiple_artifacts_for_one_material():
    low = entry("low")
    high = entry("high")
    case = spec(
        mode=ResolutionMode.PHASE_SET.value,
        keys=("low", "high"),
        reference_conditions={
            "phase_condition_mapping": {
                "low": {"artifact_key": "low", "temperature_scope": "low"},
                "high": {"artifact_key": "high", "temperature_scope": "high"},
            }
        },
    )
    resolved = resolve(
        case,
        registry(low, high),
        index(receipt(low, "1" * 64), receipt(high, "2" * 64)),
    )
    assert resolved.status == ResolutionStatus.READY.value
    assert resolved.requested_artifact_keys == ("low", "high")
    assert resolved.retained_artifact_keys == ("low", "high")
    assert resolved.artifact_hashes == ("1" * 64, "2" * 64)
    assert resolved.missing_artifact_keys == ()


def test_ensemble_supports_multiple_realizations_without_material_specific_code():
    a = entry("r1")
    b = entry("r2")
    case = spec(
        mode=ResolutionMode.ENSEMBLE.value,
        keys=("r1", "r2"),
    )
    policies = policy_registry(required=("ensemble_weight_policy",))
    retained = index(receipt(a, "1" * 64), receipt(b, "2" * 64))

    blocked = resolve(
        case,
        registry(a, b),
        retained,
        policies=policies,
    )
    assert blocked.status == ResolutionStatus.BLOCKED_POLICY.value
    assert blocked.retained_artifact_keys == ("r1", "r2")
    assert blocked.missing_artifact_keys == ()

    ready = resolve(
        case,
        registry(a, b),
        retained,
        policies=policies,
        evidence=policy_ledger(policy_evidence("ensemble_weight_policy")),
    )
    assert ready.status == ResolutionStatus.READY.value


def test_unrepresentable_control_is_explicit_not_silently_coerced():
    case = spec(
        mode=ResolutionMode.UNREPRESENTABLE.value,
        keys=(),
        blockers=("periodic_bulk_cannot_encode_required_microstructure",),
    )
    resolved = resolve(case, registry(entry("unused")), index())
    assert resolved.status == ResolutionStatus.UNREPRESENTABLE.value
    assert resolved.requested_artifact_keys == ()
    assert resolved.retained_artifact_keys == ()
    assert resolved.missing_artifact_keys == ()
    assert resolved.scientific_blockers


def test_cross_material_artifact_binding_fails_closed():
    foreign = entry("foreign", material="m2")
    with pytest.raises(ValueError, match="cross-binds"):
        resolve(spec(keys=("foreign",)), registry(foreign), index())


def test_unknown_registry_artifact_fails_closed():
    with pytest.raises(ValueError, match="outside registry"):
        resolve(spec(keys=("missing",)), registry(entry("a")), index())


def test_unknown_representation_policy_fails_after_artifact_is_present():
    a = entry("a")
    case = replace(spec(), representation_policy_id="missing-policy")
    with pytest.raises(ValueError, match="unknown representation policy"):
        resolve(
            case,
            registry(a),
            index(receipt(a, "1" * 64)),
        )


def test_direct_mode_rejects_multiple_artifacts():
    with pytest.raises(ValueError, match="exactly one artifact"):
        spec(mode=ResolutionMode.DIRECT.value, keys=("a", "b"))


def test_phase_set_requires_at_least_two_artifacts_and_exact_mapping():
    with pytest.raises(ValueError, match="at least two artifacts"):
        spec(
            mode=ResolutionMode.PHASE_SET.value,
            keys=("a",),
            reference_conditions={
                "phase_condition_mapping": {
                    "a": {"artifact_key": "a"},
                }
            },
        )

    with pytest.raises(ValueError, match="cover exactly"):
        spec(
            mode=ResolutionMode.PHASE_SET.value,
            keys=("a", "b"),
            reference_conditions={
                "phase_condition_mapping": {
                    "a": {"artifact_key": "a"},
                    "wrong": {"artifact_key": "c"},
                }
            },
        )


def test_manifest_is_data_driven_and_accepts_multiple_modes():
    direct = spec()
    phase_set = replace(
        direct,
        resolution_key="phase-set",
        mode=ResolutionMode.PHASE_SET.value,
        artifact_keys=("a", "b"),
        reference_conditions={
            "phase_condition_mapping": {
                "a": {"artifact_key": "a", "temperature_scope": "low"},
                "b": {"artifact_key": "b", "temperature_scope": "high"},
            }
        },
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


def test_bulk_manifest_resolution_preserves_case_order_and_statuses():
    a = entry("a")
    b = entry("b")
    cases = StructureResolutionManifest(
        structure_resolution_version=STRUCTURE_RESOLUTION_VERSION,
        specs=(
            spec(),
            replace(
                spec(),
                resolution_key="second",
                artifact_keys=("b",),
            ),
        ),
    )
    resolved = resolve_structure_manifest(
        cases,
        registry(a, b),
        index(receipt(a, "1" * 64)),
        policy_registry=policy_registry(),
        policy_evidence_ledger=policy_ledger(),
    )
    assert resolved.ledger_version == STRUCTURE_RESOLUTION_LEDGER_VERSION
    assert tuple(item.resolution_key for item in resolved.cases) == (
        "case",
        "second",
    )
    assert tuple(item.status for item in resolved.cases) == (
        ResolutionStatus.READY.value,
        ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value,
    )


def test_canonical_structure_cases_follow_retention_and_policy_state():
    manifest = load_structure_resolution_manifest(
        DATA_ROOT / "structure_resolution_manifest_v1.json"
    )
    retention = load_retention_index(
        DATA_ROOT / "artifact_retention_index_v1.json"
    )
    resolved = resolve_structure_manifest(
        manifest,
        load_registry(DATA_ROOT / "artifact_registry_v1.json"),
        retention,
        policy_registry=load_representation_policy_registry(
            DATA_ROOT / "representation_policy_registry_v1.json"
        ),
        policy_evidence_ledger=load_representation_evidence_ledger(
            DATA_ROOT / "representation_evidence_ledger_v1.json"
        ),
    )
    by_material = {item.material_key: item for item in resolved.cases}
    assert set(by_material) == {
        "llzo-cubic-al-stabilized",
        "li2s-microcrystalline",
        "li3n-crystalline",
        "lialo2-gamma",
        "libh4-phase-transition-pair",
    }

    retained_keys = {item.artifact_key for item in retention.receipts}

    llzo = by_material["llzo-cubic-al-stabilized"]
    assert llzo.status == ResolutionStatus.BLOCKED_POLICY.value
    assert llzo.missing_artifact_keys == ()
    assert llzo.retained_artifact_keys == (
        "reference-structure:llzo-cubic-al-stabilized:cod:7215448@176453",
    )
    assert llzo.artifact_hashes == (
        "db5f259f418edca7111136c0bc3a48b7f7cccde87411d54c48ebf71821217eec",
    )
    assert llzo.unresolved_requirements == (
        "fractional_occupancy_execution_strategy",
    )

    libh4 = by_material["libh4-phase-transition-pair"]
    libh4_keys = (
        "reference-structure:libh4-phase-transition-pair:"
        "cod:1504402@latest-freeze-v1",
        "reference-structure:libh4-phase-transition-pair:"
        "cod:1504403@latest-freeze-v1",
    )
    if all(key in retained_keys for key in libh4_keys):
        assert libh4.status == ResolutionStatus.READY.value
        assert libh4.missing_artifact_keys == ()
        assert libh4.retained_artifact_keys == libh4_keys
        assert libh4.unresolved_requirements == ()
        assert libh4.scientific_blockers == ()
    else:
        assert libh4.status == ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value
        assert set(libh4.missing_artifact_keys) == {
            key for key in libh4_keys if key not in retained_keys
        }

    li2s = by_material["li2s-microcrystalline"]
    li2s_key = (
        "reference-structure:li2s-microcrystalline:"
        "cod:9009060@latest-freeze-v1"
    )
    if li2s_key in retained_keys:
        assert li2s.status == ResolutionStatus.READY.value
        assert li2s.missing_artifact_keys == ()
        assert li2s.retained_artifact_keys == (li2s_key,)
        assert li2s.unresolved_requirements == ()
        assert li2s.scientific_blockers == ()
    else:
        assert li2s.status == ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value
        assert li2s.missing_artifact_keys == (li2s_key,)
        assert li2s.retained_artifact_keys == ()

    gamma = by_material["lialo2-gamma"]
    gamma_key = "reference-structure:lialo2-gamma:cod:1008166@latest-freeze-v1"
    if gamma_key in retained_keys:
        assert gamma.status == ResolutionStatus.READY.value
        assert gamma.missing_artifact_keys == ()
        assert gamma.retained_artifact_keys == (gamma_key,)
        assert gamma.unresolved_requirements == ()
        assert gamma.scientific_blockers == ()
    else:
        assert gamma.status == ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value
        assert gamma.missing_artifact_keys == (gamma_key,)
        assert gamma.retained_artifact_keys == ()

    li3n = by_material["li3n-crystalline"]
    li3n_key = (
        "reference-structure:li3n-crystalline:"
        "literature-reconstruction:alpha-v1"
    )
    if li3n_key in retained_keys:
        assert li3n.status == ResolutionStatus.READY.value
        assert li3n.missing_artifact_keys == ()
        assert li3n.retained_artifact_keys == (li3n_key,)
        assert li3n.unresolved_requirements == ()
        assert li3n.scientific_blockers == ()
    else:
        assert li3n.status == ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value
        assert li3n.missing_artifact_keys == (li3n_key,)
        assert li3n.retained_artifact_keys == ()
