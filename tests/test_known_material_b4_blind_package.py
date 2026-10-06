"""B4 blind execution package tests."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from rudeus.science.known_material_artifact_curation import (
    load_registry,
    load_retention_index,
)
from rudeus.science.known_material_b2_coverage import (
    load_cataloged_truth_bundles,
    load_truth_bundle_catalog,
)
from rudeus.science.known_material_b3_split import (
    authorize_b3_split,
    freeze_b3_split_from_truth_bundles,
)
from rudeus.science.known_material_b4_blind_package import (
    build_b4_blind_execution_package,
)
from rudeus.science.known_material_b4_blinding_amendment import (
    build_b4_blind_identity_amendment,
)
from rudeus.science.known_material_representation_policy import (
    load_representation_evidence_ledger,
    load_representation_policy_registry,
)
from rudeus.science.known_material_sample_size import load_sample_size_assessment
from rudeus.science.known_material_structure_resolution import (
    ResolutionStatus,
    StructureResolutionLedger,
    load_structure_resolution_manifest,
    resolve_structure_manifest,
)
from rudeus.science.known_material_truth import KnownMaterialTruthBundle
from tests.test_known_material_b2_coverage import canonical_audit


ROOT = Path("data/benchmarks/known_material")
PROTOCOL_HASH = "6cb6579cdddaaf4d4fb93ca71828832eb741e31c749fbcff54bce9ab85351369"
CUBIC_LLZO_EXECUTION_HASH = (
    "0ce55065f464292b34919e31bab12947cddea8c26bf2521323fd3f8714d5e475"
)
TRUTH_FILES = (
    "li2s-microcrystalline-v1.json",
    "li3n-crystalline-v1.json",
    "lialo2-gamma-v1.json",
    "libh4-phase-transition-pair-v1.json",
    "llzo-cubic-al-stabilized-v1.json",
    "llzo-tetragonal-undoped-v1.json",
)


def _freeze():
    catalog = load_truth_bundle_catalog(ROOT / "truth_bundle_catalog_v1.json")
    bundles = load_cataloged_truth_bundles(catalog, repo_root=Path("."))
    return freeze_b3_split_from_truth_bundles(
        authorize_b3_split(
            canonical_audit(),
            load_sample_size_assessment(ROOT / "sample_size_assessment_v1.json"),
        ),
        bundles,
    )


def _protocol_map():
    result = {}
    for name in TRUTH_FILES:
        bundle = KnownMaterialTruthBundle.from_dict(
            json.loads((ROOT / "truth_bundles" / name).read_text(encoding="utf-8"))
        )
        result[bundle.content_hash] = bundle.benchmark_protocol_hash
    return result


def _test_amendment(freeze):
    opaque = {
        member.benchmark_id: f"km-pkg{index:05d}"
        for index, member in enumerate(freeze.members)
    }
    return build_b4_blind_identity_amendment(
        freeze,
        opaque_ids_by_legacy_id=opaque,
        protocol_hash_by_truth_bundle_hash=_protocol_map(),
    )


def _structure_ledger():
    return resolve_structure_manifest(
        load_structure_resolution_manifest(ROOT / "structure_resolution_manifest_v1.json"),
        load_registry(ROOT / "artifact_registry_v1.json"),
        load_retention_index(ROOT / "artifact_retention_index_v1.json"),
        policy_registry=load_representation_policy_registry(
            ROOT / "representation_policy_registry_v1.json"
        ),
        policy_evidence_ledger=load_representation_evidence_ledger(
            ROOT / "representation_evidence_ledger_v1.json"
        ),
    )


def test_blind_package_exposes_only_four_visible_fields_and_no_legacy_ids():
    freeze = _freeze()
    amendment = _test_amendment(freeze)
    package = build_b4_blind_execution_package(
        freeze, amendment, _structure_ledger()
    )

    assert len(package.execution_payloads) == 6
    assert all(
        tuple(payload) == (
            "benchmark_id",
            "split",
            "structure_hash",
            "benchmark_protocol_hash",
        )
        for payload in package.execution_payloads
    )
    serialized = json.dumps(package.execution_payloads, sort_keys=True)
    assert all(member.benchmark_id not in serialized for member in freeze.members)
    assert all(member.truth_bundle_hash not in serialized for member in freeze.members)
    assert {payload["benchmark_protocol_hash"] for payload in package.execution_payloads} == {
        PROTOCOL_HASH
    }
    assert sum(payload["split"] == "DEV" for payload in package.execution_payloads) == 3
    assert sum(payload["split"] == "HELD_OUT" for payload in package.execution_payloads) == 3


def test_blind_package_uses_mode_correct_composite_structure_hashes():
    freeze = _freeze()
    amendment = _test_amendment(freeze)
    ledger = _structure_ledger()
    package = build_b4_blind_execution_package(freeze, amendment, ledger)

    opaque_by_legacy = {
        item.legacy_benchmark_id: item.opaque_benchmark_id
        for item in amendment.bindings
    }
    ingress_by_id = {item.benchmark_id: item for item in package.ingresses}
    case_by_material = {item.material_key: item for item in ledger.cases}

    cubic = ingress_by_id[opaque_by_legacy["llzo-cubic-al-stabilized"]]
    assert cubic.structure_hash == CUBIC_LLZO_EXECUTION_HASH
    assert cubic.structure_hash not in case_by_material[
        "llzo-cubic-al-stabilized"
    ].artifact_hashes

    libh4_case = case_by_material["libh4-phase-transition-pair"]
    libh4 = ingress_by_id[opaque_by_legacy["libh4-phase-transition-pair"]]
    assert libh4.structure_hash not in set(libh4_case.artifact_hashes)
    assert len(libh4.structure_hash) == 64

    li3n_case = case_by_material["li3n-crystalline"]
    li3n = ingress_by_id[opaque_by_legacy["li3n-crystalline"]]
    assert li3n.structure_hash == li3n_case.artifact_hashes[0]


def test_blind_package_rejects_non_ready_frozen_member():
    freeze = _freeze()
    amendment = _test_amendment(freeze)
    ledger = _structure_ledger()
    cases = list(ledger.cases)
    target = next(
        index
        for index, item in enumerate(cases)
        if item.material_key == "llzo-cubic-al-stabilized"
    )
    cases[target] = replace(
        cases[target],
        status=ResolutionStatus.BLOCKED_POLICY.value,
        unresolved_requirements=("synthetic-blocker",),
    )
    blocked = StructureResolutionLedger(
        ledger_version=ledger.ledger_version,
        cases=tuple(cases),
    )

    with pytest.raises(ValueError, match="READY structure cases"):
        build_b4_blind_execution_package(freeze, amendment, blocked)
