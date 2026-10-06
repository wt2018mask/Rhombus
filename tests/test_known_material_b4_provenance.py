"""B4 provenance closure tests."""
from rudeus.science.known_material_artifact_curation import load_artifact_retention_index
from rudeus.science.known_material_b3_split import B3SplitFreeze, B3SplitMember
from rudeus.science.known_material_b4_provenance import audit_b4_provenance


H = "1" * 64


def _canonical_member_ids():
    return (
        "libh4-phase-transition-pair",
        "llzo-tetragonal-undoped",
        "lialo2-gamma",
        "li2s-microcrystalline",
        "llzo-cubic-al-stabilized",
        "li3n-crystalline",
    )


def _freeze():
    return B3SplitFreeze(
        freeze_version="known-material-b3-split-freeze-v1",
        authorization_hash=H,
        assignment_method="ROLE_STRATIFIED_TRUTH_BUNDLE_HASH_ASCENDING",
        members=tuple(
            B3SplitMember(
                benchmark_id=value,
                split="DEV" if i % 2 == 0 else "HELD_OUT",
                truth_bundle_hash=f"{i + 2:064x}",
            )
            for i, value in enumerate(_canonical_member_ids())
        ),
    )


def test_current_retention_index_blocks_only_missing_tetragonal_llzo():
    index = load_artifact_retention_index(
        __import__("pathlib").Path(
            "data/benchmarks/known_material/artifact_retention_index_v1.json"
        )
    )
    audit = audit_b4_provenance(_freeze(), index)
    assert audit.missing_material_keys == ("llzo-tetragonal-undoped",)
    assert audit.ingress_materialization_authorized is False
    assert set(audit.retained_material_keys) == set(_canonical_member_ids()) - {
        "llzo-tetragonal-undoped"
    }
