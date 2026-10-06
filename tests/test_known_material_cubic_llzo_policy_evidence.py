"""Cubic Al-LLZO representation-policy evidence tests."""
from fractions import Fraction
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_policy_evidence import (
    build_cubic_llzo_fractional_occupancy_policy_evidence,
)
from rudeus.science.known_material_representation_policy import (
    RepresentationEvidenceLedger,
    RepresentationPolicyStatus,
    load_representation_policy_registry,
    resolve_representation_policy,
    validate_representation_evidence_ledger,
)


ROOT = Path("data/benchmarks/known_material")
CIF = ROOT / "structures/cod/7215448-r176453.cif"
SOURCE_HASH = "db5f259f418edca7111136c0bc3a48b7f7cccde87411d54c48ebf71821217eec"


def test_cubic_llzo_policy_evidence_satisfies_fractional_occupancy_strategy_for_ensemble():
    strategy, execution, entry = build_cubic_llzo_fractional_occupancy_policy_evidence(
        CIF,
        source_artifact_hash=SOURCE_HASH,
    )
    registry = load_representation_policy_registry(
        ROOT / "representation_policy_registry_v1.json"
    )
    ledger = RepresentationEvidenceLedger(
        ledger_version="known-material-representation-evidence-ledger-v1",
        entries=(entry,),
    )
    validate_representation_evidence_ledger(registry, ledger)
    resolution = resolve_representation_policy(
        policy_id="fractional-occupancy-explicit-v1",
        resolution_mode="ENSEMBLE",
        registry=registry,
        evidence_ledger=ledger,
    )

    assert resolution.status == RepresentationPolicyStatus.SATISFIED.value
    assert resolution.missing_inputs == ()
    assert strategy.composition_preserved is True
    assert strategy.occupancy_statistics_preserved is True
    assert execution.mode == "ENSEMBLE"
    assert execution.visible_structure_hash == entry.payload["execution_structure_hash"]


def test_cubic_llzo_policy_evidence_preserves_exact_rational_weights_as_source_of_truth():
    _, execution, entry = build_cubic_llzo_fractional_occupancy_policy_evidence(
        CIF,
        source_artifact_hash=SOURCE_HASH,
    )
    fractions = tuple(
        Fraction(numerator, denominator)
        for numerator, denominator in entry.payload["exact_weight_fractions"]
    )

    assert sum(fractions, Fraction(0, 1)) == 1
    assert tuple(component.weight for component in execution.components) == fractions
    assert entry.payload["declared_marginal_occupancies"] == {
        "Li1": "0.54",
        "Al1": "0.06530",
        "Li2": "0.37",
    }


def test_cubic_llzo_policy_evidence_does_not_claim_unresolved_correlations():
    strategy, _, entry = build_cubic_llzo_fractional_occupancy_policy_evidence(
        CIF,
        source_artifact_hash=SOURCE_HASH,
    )

    assert "DOES_NOT_RESOLVE_CORRELATIONS" in entry.payload["correlation_scope"]
    assert any("no such correlation claim" in item for item in strategy.bias_assessment)
