"""Immutable B3 split-freeze tests."""
from dataclasses import replace
from pathlib import Path

import pytest

from rudeus.science.known_material_b3_split import (
    authorize_b3_split,
    freeze_b3_split,
    freeze_b3_split_from_truth_bundles,
    load_b3_split_authorization,
    load_b3_split_freeze,
)
from rudeus.science.known_material_b2_coverage import (
    load_cataloged_truth_bundles,
    load_truth_bundle_catalog,
)
from rudeus.science.known_material_sample_size import load_sample_size_assessment
from tests.test_known_material_b2_coverage import canonical_audit


ROOT = Path("data/benchmarks/known_material")

ROLE_HASHES = {
    "POSITIVE": (
        ("li3n-crystalline", "9a890dc1b315ecfb5bb3cce851983544938cd7f547d076e709cb1aa8e1f90b7b"),
        ("llzo-cubic-al-stabilized", "42d5c8e94dd8f474cf47c6d2ca33cb4cba9cbb8db863a091004e08b9bcb33765"),
    ),
    "NEGATIVE": (
        ("li2s-microcrystalline", "cb4ebd30697a8258fb35b1efa0284795a5937c0f6cc56cc64d2de702fda93210"),
        ("lialo2-gamma", "8550f760233dfae15dc5c85966ab2b09073ed513b59c13d05f9d8f078d96df8b"),
    ),
    "BORDERLINE": (
        ("libh4-phase-transition-pair", "83e6116fb6b87389661aa8651f5fb91dd770b97f09a827d3b4f77dc8e12ffb0c"),
        ("llzo-tetragonal-undoped", "f8bae9e25e6d765d7df09ea248434b76e848731c1438f5ff135aec3e6f134ebb"),
    ),
}


def _authorization():
    return load_b3_split_authorization(ROOT / "b3_split_authorization_v1.json")


def _derived_authorization():
    return authorize_b3_split(
        canonical_audit(),
        load_sample_size_assessment(ROOT / "sample_size_assessment_v1.json"),
    )


def test_canonical_b3_transition_records_are_content_addressed_and_match_derivation():
    authorization = _authorization()
    freeze = load_b3_split_freeze(ROOT / "b3_split_freeze_v1.json")
    catalog = load_truth_bundle_catalog(ROOT / "truth_bundle_catalog_v1.json")
    bundles = load_cataloged_truth_bundles(catalog, repo_root=Path("."))

    assert authorization == _derived_authorization()
    assert authorization.content_hash == (
        "6a5920309685d5fc5f084480dece901816ec6d649c0cb600680566f3a50b3d94"
    )
    assert freeze.authorization_hash == authorization.content_hash
    assert freeze.content_hash == (
        "749c3c15db813a5bc4602f4095089a84951687315192694ca7880ddf97e32cea"
    )
    assert freeze == freeze_b3_split_from_truth_bundles(authorization, bundles)


def test_canonical_split_is_role_stratified_deterministic_and_immutable():
    freeze = load_b3_split_freeze(ROOT / "b3_split_freeze_v1.json")
    assert freeze == freeze_b3_split(_authorization(), ROLE_HASHES)
    observed = {member.benchmark_id: member.split for member in freeze.members}
    assert observed == {
        "libh4-phase-transition-pair": "DEV",
        "llzo-tetragonal-undoped": "HELD_OUT",
        "lialo2-gamma": "DEV",
        "li2s-microcrystalline": "HELD_OUT",
        "llzo-cubic-al-stabilized": "DEV",
        "li3n-crystalline": "HELD_OUT",
    }
    assert sum(member.split == "DEV" for member in freeze.members) == 3
    assert sum(member.split == "HELD_OUT" for member in freeze.members) == 3
    assert freeze.authorization_hash == _authorization().content_hash


def test_split_assignment_does_not_depend_on_input_order():
    reversed_inputs = {
        role: tuple(reversed(values)) for role, values in ROLE_HASHES.items()
    }
    assert freeze_b3_split(_authorization(), reversed_inputs) == freeze_b3_split(
        _authorization(), ROLE_HASHES
    )


def test_split_freeze_rejects_cohort_growth_or_role_loss():
    authorization = _authorization()
    grown = dict(ROLE_HASHES)
    grown["POSITIVE"] = grown["POSITIVE"] + (
        ("future-positive", "0" * 64),
    )
    with pytest.raises(ValueError, match="exactly two"):
        freeze_b3_split(authorization, grown)

    missing = dict(ROLE_HASHES)
    missing.pop("BORDERLINE")
    with pytest.raises(ValueError, match="positive/negative/borderline"):
        freeze_b3_split(authorization, missing)


def test_catalog_driven_freeze_matches_historical_frozen_membership():
    catalog = load_truth_bundle_catalog(ROOT / "truth_bundle_catalog_v1.json")
    bundles = load_cataloged_truth_bundles(catalog, repo_root=Path("."))
    derived = freeze_b3_split_from_truth_bundles(_authorization(), bundles)
    expected = load_b3_split_freeze(ROOT / "b3_split_freeze_v1.json")

    assert derived == expected
