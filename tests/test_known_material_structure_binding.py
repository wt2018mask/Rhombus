"""B2 exact-structure binding ledger tests."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from rudeus.science.known_material_structure_binding import (
    LicenseDisposition,
    StructureArtifactBinding,
    StructureArtifactState,
    StructureBindingLedger,
)


DATA = Path("data/benchmarks/known_material/b2_structure_binding_v1.json")


def load():
    return StructureBindingLedger.from_dict(json.loads(DATA.read_text(encoding="utf-8")))


def test_structure_ledger_is_pre_b3_and_not_closed_yet():
    ledger = load()
    assert not ledger.b2_structure_closure_authorized
    assert not ledger.dev_held_out_assignment_authorized
    assert not ledger.pipeline_execution_authorized
    assert not ledger.production_search_authorized
    allowed_pre_b3_states = {
        StructureArtifactState.SOURCE_IDENTIFIED.value,
        StructureArtifactState.ARTIFACT_RETAINED.value,
        StructureArtifactState.HASHED_AND_VALIDATED.value,
    }
    assert all(
        entry.artifact_state in allowed_pre_b3_states
        for entry in ledger.entries
    )
    assert any(
        entry.artifact_state != StructureArtifactState.HASHED_AND_VALIDATED.value
        for entry in ledger.entries
    )
    assert all(
        entry.artifact_state != StructureArtifactState.HASHED_AND_VALIDATED.value
        for entry in ledger.entries
    )


def test_every_b2_universe_material_has_one_structure_binding():
    universe = json.loads(Path(
        "data/benchmarks/known_material/b2_universe_intake_v1.json"
    ).read_text(encoding="utf-8"))
    ledger = load()
    assert {entry.material_key for entry in ledger.entries} == {
        item["material_key"] for item in universe["entries"]
    }


def test_source_identified_cannot_claim_repo_retention():
    entry = load().entries[0]
    with pytest.raises(ValueError, match="cannot claim retained path"):
        replace(entry, retained_path="data/benchmarks/known_material/structures/lgps.cif")


def test_unverified_remote_artifact_cannot_be_retained():
    entry = load().entries[0]
    with pytest.raises(ValueError, match="cannot be retained"):
        replace(
            entry,
            artifact_state=StructureArtifactState.ARTIFACT_RETAINED.value,
            retained_path="data/benchmarks/known_material/structures/lgps.cif",
        )


def test_validated_structure_requires_hash_rights_and_zero_blockers():
    entry = load().entries[0]
    with pytest.raises(ValueError, match="retained artifact and SHA256"):
        replace(
            entry,
            artifact_state=StructureArtifactState.HASHED_AND_VALIDATED.value,
            blockers=(),
        )
    with pytest.raises(ValueError, match="verified redistribution rights"):
        replace(
            entry,
            artifact_state=StructureArtifactState.HASHED_AND_VALIDATED.value,
            artifact_sha256="0" * 64,
            retained_path="data/benchmarks/known_material/structures/lgps.cif",
            blockers=(),
        )


def test_ledger_cannot_claim_closure_until_all_entries_validated():
    ledger = load()
    with pytest.raises(ValueError, match="closure flag"):
        replace(ledger, b2_structure_closure_authorized=True)


def test_lgps_binding_points_to_primary_single_crystal_cif_but_stays_unretained():
    entry = next(
        item for item in load().entries
        if item.material_key == "lgps-tetragonal-li10gep2s12"
    )
    assert entry.source_id == "doi:10.1039/C3CP51985F"
    assert entry.artifact_locator.endswith("c3cp51985f.cif")
    assert entry.license_disposition == LicenseDisposition.REMOTE_ONLY_UNVERIFIED.value
    assert entry.artifact_sha256 is None
    assert entry.retained_path is None


def test_disorder_and_microstructure_risks_are_explicit():
    entries = {entry.material_key: entry for entry in load().entries}
    assert "partial Li occupancies" in entries[
        "lgps-tetragonal-li10gep2s12"
    ].disorder_representation
    assert "ordered proxy cannot silently replace" in entries[
        "li6ps5cl-argyrodite"
    ].disorder_representation
    assert "cannot silently encode nanopore" in entries[
        "li3ps4-nanoporous-beta"
    ].disorder_representation


def test_li2s_binding_uses_public_cod_bulk_phase_without_microstructure_claim():
    entry = next(
        item for item in load().entries
        if item.material_key == "li2s-microcrystalline"
    )
    assert entry.composition_identity == "Li2S"
    assert "Fm-3m" in entry.phase_identity
    assert entry.source_id == (
        "cod:9009060@sha256:"
        "ff1d7eeb11f6d91c3adb7af92c8b6cfc938f9c9f412e26bd4187a021de7470b0"
    )
    assert entry.source_kind == "PUBLIC_DOMAIN_DATABASE"
    assert entry.artifact_locator.endswith("/9009060.cif")
    assert entry.license_disposition == "VERIFIED_REDISTRIBUTABLE"
    assert entry.artifact_state == StructureArtifactState.HASHED_AND_VALIDATED.value
    assert entry.artifact_sha256 == (
        "ff1d7eeb11f6d91c3adb7af92c8b6cfc938f9c9f412e26bd4187a021de7470b0"
    )
    assert entry.retained_path == (
        "data/benchmarks/known_material/structures/cod/"
        "9009060-latest-freeze-v1.cif"
    )
    assert entry.blockers == ()
    assert "microstructure" in entry.disorder_representation.lower()


def test_cubic_llzo_binding_is_scientific_state_not_retention_state():
    entry = next(
        item for item in load().entries
        if item.material_key == "llzo-cubic-al-stabilized"
    )
    assert entry.composition_identity == "Al0.196La3Li6.06O12Zr2"
    assert entry.phase_identity == "Al-stabilized cubic LLZO, Ia-3d (No. 230), 300 K"
    assert entry.source_id == "cod:7215448@176453"
    assert entry.source_kind == "PUBLIC_DOMAIN_DATABASE"
    assert entry.artifact_locator.endswith("/7215448.cif@176453")
    assert entry.license_disposition == "VERIFIED_REDISTRIBUTABLE"

    # Mechanical retention is tracked in artifact_retention_index_v1.json.
    # The scientific binding ledger must not infer readiness merely because
    # the corresponding file happens to exist in the working tree.
    assert entry.artifact_state == StructureArtifactState.SOURCE_IDENTIFIED.value
    assert entry.artifact_sha256 is None
    assert entry.retained_path is None
    assert "artifact_not_yet_retained_and_hashed" in entry.blockers
    assert "fractional_Li_Al_occupancy_execution_policy_required" in entry.blockers
