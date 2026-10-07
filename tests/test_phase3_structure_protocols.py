from __future__ import annotations

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
        == "rhombus-composition-site-count-candidate-fingerprint-v1"
    )
    assert STRICT_STRUCTURE_EQUIVALENCE_PROTOCOL_ID == "pymatgen-structure-equivalence-v1"
    assert NEAR_DUPLICATE_PROTOCOL_ID == "pymatgen-structure-near-duplicate-v1"
