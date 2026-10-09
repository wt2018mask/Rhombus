from __future__ import annotations

import json
from pathlib import Path

from pymatgen.core import Lattice, Structure

from rhombus.domain import (
    CANDIDATE_FINGERPRINT_PROTOCOL_ID,
    NEAR_DUPLICATE_PROTOCOL_ID,
    STRICT_STRUCTURE_EQUIVALENCE_PROTOCOL_ID,
    near_duplicate_structure,
    strict_structure_equivalent,
    structure_candidate_fingerprint_sha256,
)


def _nacl(a: float = 4.0) -> Structure:
    return Structure(
        Lattice.cubic(a),
        ["Na", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    )


def test_candidate_fingerprint_is_only_a_safe_coarse_bucket() -> None:
    base = _nacl(4.0)
    scaled = _nacl(4.4)

    assert len(structure_candidate_fingerprint_sha256(base)) == 64
    assert (
        structure_candidate_fingerprint_sha256(base)
        == structure_candidate_fingerprint_sha256(scaled)
    )
    assert strict_structure_equivalent(base, scaled) is False


def test_strict_structure_equivalence_accepts_site_reordering() -> None:
    base = _nacl()
    reordered = Structure(
        base.lattice,
        ["Cl", "Na"],
        [[0.5, 0.5, 0.5], [0, 0, 0]],
    )

    assert strict_structure_equivalent(base, reordered) is True


def test_near_duplicate_allows_scale_but_strict_does_not() -> None:
    base = _nacl(4.0)
    scaled = _nacl(4.4)

    assert strict_structure_equivalent(base, scaled) is False
    assert near_duplicate_structure(base, scaled) is True


def test_structure_matchers_fail_closed_on_composition_change() -> None:
    base = _nacl()
    changed = Structure(
        base.lattice,
        ["K", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    )

    assert strict_structure_equivalent(base, changed) is False
    assert near_duplicate_structure(base, changed) is False


def test_protocol_ids_are_explicit() -> None:
    assert (
        CANDIDATE_FINGERPRINT_PROTOCOL_ID
        == "rhombus-reduced-composition-candidate-fingerprint-v2"
    )
    assert STRICT_STRUCTURE_EQUIVALENCE_PROTOCOL_ID == "pymatgen-structure-equivalence-v1"
    assert NEAR_DUPLICATE_PROTOCOL_ID == "pymatgen-structure-near-duplicate-v1"


def test_structure_protocol_evidence_remains_fail_closed() -> None:
    root = Path(__file__).resolve().parents[1]
    evidence = json.loads(
        (root / "data/development/phase3_structure_protocol_executors_v1.json")
        .read_text(encoding="utf-8")
    )

    assert evidence["comparison_protocol_id"] == "wbm-exposure-comparison-v2"
    assert evidence["candidate_fingerprint"]["authoritative_exact_match"] is False
    assert evidence["strict_structure_equivalence"]["authoritative_exact_match"] is True
    assert evidence["prototype_group"]["upstream_commit"] == (
        "26d3a19073df8cb303c7e4849a0d65e74746d9eb"
    )
    assert evidence["prototype_group"]["runtime_source_env"] == (
        "RHOMBUS_MATBENCH_PROTOCOL_SOURCE_DIR"
    )
    assert evidence["prototype_group"]["wheel_status"] == (
        "NOT_AUTHORITATIVE_REFERENCE_SOURCE_WYCKOFF_FILES_OMITTED"
    )
    assert evidence["authorization"]["build_production_salex_membership_index"] is False
    assert evidence["authorization"]["execute_exposure_audit"] is False
    assert evidence["authorization"]["unseen_generalization_claim"] is False



def test_near_candidate_bucket_covers_primitive_and_supercell_site_counts() -> None:
    base = _nacl(5.0)
    supercell = base.copy()
    supercell.make_supercell([2, 1, 1])
    assert len(base) == 2
    assert len(supercell) == 4
    # Exact matching explicitly requires identical input site counts.
    assert strict_structure_equivalent(base, supercell) is False
    # Near matching normalizes primitive cells and must not be screened
    # out by an extra site-count requirement in the candidate bucket.
    assert near_duplicate_structure(base, supercell) is True
    assert structure_candidate_fingerprint_sha256(base) == (
        structure_candidate_fingerprint_sha256(supercell)
    )


def test_composition_only_protocol_differs_from_historical_v1_site_count_bucket() -> None:
    import hashlib
    base = _nacl()
    old = {
        "protocol_id": "rhombus-composition-site-count-candidate-fingerprint-v1",
        "composition_key": base.composition.element_composition.reduced_formula,
        "site_count": len(base),
    }
    old_hash = hashlib.sha256(
        json.dumps(old, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert old_hash != structure_candidate_fingerprint_sha256(base)



def test_active_v2_candidate_protocol_append_only_erratum_keeps_old_verified_observation():
    root = Path(__file__).resolve().parents[1]
    fresh = json.loads(
        (root / "data/development/phase3_candidate_fingerprint_prefilter_soundness_v2.json")
        .read_text(encoding="utf-8")
    )
    erratum = json.loads(
        (root / "data/development/phase3_salex_v1_candidate_prefilter_scope_erratum_v1.json")
        .read_text(encoding="utf-8")
    )
    original = json.loads(
        (root / "data/development/phase3_salex_preserved_source_overlap_union_observation_v1.json")
        .read_text(encoding="utf-8")
    )
    assert fresh["active_candidate_fingerprint_protocol_id"] == CANDIDATE_FINGERPRINT_PROTOCOL_ID
    assert fresh["sha256_payload"].keys() == {"protocol_id", "composition_key"}
    assert erratum["positive_detected_v1"]["distinct_union"] == 1946
    assert original["wbms"]["distinct_positive_source_overlap_union"] == 1946
    assert erratum["scientific_authorization"]["historical_v1_near_completeness_claim"] is False
    assert fresh["migration"]["old_v1_wbm_sqlite_reuse_authorized"] is False
    assert fresh["migration"]["no_new_production_run_performed"] is True
