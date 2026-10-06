"""B4 executable-readiness gate tests."""
from pathlib import Path

from rudeus.science.known_material_artifact_curation import load_registry, load_retention_index
from rudeus.science.known_material_b4_readiness import audit_b4_executable_readiness
from rudeus.science.known_material_representation_policy import (
    load_representation_evidence_ledger,
    load_representation_policy_registry,
)
from rudeus.science.known_material_structure_resolution import (
    load_structure_resolution_manifest,
    resolve_structure_manifest,
)


DATA_ROOT = Path("data/benchmarks/known_material")


def test_current_canonical_readiness_authorizes_all_frozen_members():
    ledger = resolve_structure_manifest(
        load_structure_resolution_manifest(DATA_ROOT / "structure_resolution_manifest_v1.json"),
        load_registry(DATA_ROOT / "artifact_registry_v1.json"),
        load_retention_index(DATA_ROOT / "artifact_retention_index_v1.json"),
        policy_registry=load_representation_policy_registry(
            DATA_ROOT / "representation_policy_registry_v1.json"
        ),
        policy_evidence_ledger=load_representation_evidence_ledger(
            DATA_ROOT / "representation_evidence_ledger_v1.json"
        ),
    )
    audit = audit_b4_executable_readiness(ledger)

    assert audit.ready_material_keys == (
        "li2s-microcrystalline",
        "li3n-crystalline",
        "lialo2-gamma",
        "libh4-phase-transition-pair",
        "llzo-cubic-al-stabilized",
        "llzo-tetragonal-undoped",
    )
    assert audit.blocked_material_keys == ()
    assert audit.blind_execution_authorized is True
