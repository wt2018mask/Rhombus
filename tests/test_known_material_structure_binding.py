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
    assert all(entry.artifact_state == StructureArtifactState.SOURCE_IDENTIFIED.value
               for entry in ledger.entries)


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
