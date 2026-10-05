"""Representation-policy registry and evidence-gating tests."""
import json
from pathlib import Path

import pytest

from rudeus.science.known_material_representation_policy import (
    REPRESENTATION_EVIDENCE_LEDGER_VERSION,
    REPRESENTATION_POLICY_VERSION,
    RepresentationEvidenceDisposition,
    RepresentationEvidenceLedger,
    RepresentationPolicyEvidence,
    RepresentationPolicyKind,
    RepresentationPolicyRegistry,
    RepresentationPolicySpec,
    RepresentationPolicyStatus,
    load_representation_evidence_ledger,
    load_representation_policy_registry,
    resolve_representation_policy,
    validate_representation_evidence_ledger,
)


REGISTRY = Path(
    "data/benchmarks/known_material/representation_policy_registry_v1.json"
)
EVIDENCE = Path(
    "data/benchmarks/known_material/representation_evidence_ledger_v1.json"
)


def policy(
    *,
    policy_id="policy-v1",
    modes=("DIRECT", "ENSEMBLE"),
    required=("strategy",),
    optional=("bias_assessment",),
):
    return RepresentationPolicySpec(
        policy_id=policy_id,
        policy_kind=RepresentationPolicyKind.FRACTIONAL_OCCUPANCY.value,
        applicable_modes=modes,
        required_inputs=required,
        optional_inputs=optional,
        forbidden_shortcuts=("silent_ordering",),
        rationale=("explicit representation required",),
    )


def registry(*policies):
    return RepresentationPolicyRegistry(
        registry_version=REPRESENTATION_POLICY_VERSION,
        policies=policies or (policy(),),
    )


def evidence(
    *,
    policy_id="policy-v1",
    input_key="strategy",
    disposition=RepresentationEvidenceDisposition.SATISFIED.value,
    sha="1" * 64,
):
    return RepresentationPolicyEvidence(
        policy_id=policy_id,
        input_key=input_key,
        disposition=disposition,
        provenance_hash=sha,
        evidence_refs=("artifact:policy-evidence",),
        payload={"strategy": "enumerated-ensemble"},
        rationale=("reviewed representation choice",),
    )


def ledger(*entries):
    return RepresentationEvidenceLedger(
        ledger_version=REPRESENTATION_EVIDENCE_LEDGER_VERSION,
        entries=entries,
    )


def test_canonical_policy_registry_is_material_agnostic():
    reg = load_representation_policy_registry(REGISTRY)
    raw = REGISTRY.read_text(encoding="utf-8").lower()

    assert reg.registry_version == REPRESENTATION_POLICY_VERSION
    assert {item.policy_id for item in reg.policies} == {
        "fractional-occupancy-explicit-v1",
        "exact-ordered-full-occupancy-v1",
    }
    assert "llzo" not in raw
    assert "li10gep2s12" not in raw
    assert "li6ps5cl" not in raw


def test_exact_ordered_policy_needs_no_synthetic_representation_evidence():
    reg = load_representation_policy_registry(REGISTRY)
    evidence_ledger = load_representation_evidence_ledger(EVIDENCE)

    resolved = resolve_representation_policy(
        policy_id="exact-ordered-full-occupancy-v1",
        resolution_mode="DIRECT",
        registry=reg,
        evidence_ledger=evidence_ledger,
    )

    assert resolved.status == RepresentationPolicyStatus.SATISFIED.value
    assert resolved.required_inputs == ()
    assert resolved.evidence_hashes == ()


def test_canonical_evidence_ledger_starts_empty_and_versioned():
    evidence_ledger = load_representation_evidence_ledger(EVIDENCE)
    assert evidence_ledger.ledger_version == REPRESENTATION_EVIDENCE_LEDGER_VERSION
    assert evidence_ledger.entries == ()


def test_policy_identity_alone_never_satisfies_required_evidence():
    resolved = resolve_representation_policy(
        policy_id="policy-v1",
        resolution_mode="DIRECT",
        registry=registry(),
        evidence_ledger=ledger(),
    )
    assert resolved.status == RepresentationPolicyStatus.BLOCKED_MISSING_EVIDENCE.value
    assert resolved.required_inputs == ("strategy",)
    assert resolved.missing_inputs == ("strategy",)
    assert resolved.satisfied_inputs == ()
    assert resolved.evidence_hashes == ()


def test_satisfied_policy_requires_evidence_record_not_raw_string():
    item = evidence()
    resolved = resolve_representation_policy(
        policy_id="policy-v1",
        resolution_mode="DIRECT",
        registry=registry(),
        evidence_ledger=ledger(item),
    )
    assert resolved.status == RepresentationPolicyStatus.SATISFIED.value
    assert resolved.satisfied_inputs == ("strategy",)
    assert resolved.missing_inputs == ()
    assert resolved.rejected_inputs == ()
    assert resolved.evidence_hashes == (item.content_hash,)


def test_rejected_evidence_blocks_policy():
    item = evidence(
        disposition=RepresentationEvidenceDisposition.REJECTED.value,
    )
    resolved = resolve_representation_policy(
        policy_id="policy-v1",
        resolution_mode="DIRECT",
        registry=registry(),
        evidence_ledger=ledger(item),
    )
    assert (
        resolved.status
        == RepresentationPolicyStatus.BLOCKED_REJECTED_EVIDENCE.value
    )
    assert resolved.rejected_inputs == ("strategy",)


def test_satisfied_evidence_requires_refs_and_payload():
    with pytest.raises(ValueError, match="requires refs and payload"):
        RepresentationPolicyEvidence(
            policy_id="policy-v1",
            input_key="strategy",
            disposition=RepresentationEvidenceDisposition.SATISFIED.value,
            provenance_hash="1" * 64,
            evidence_refs=(),
            payload={},
        )


def test_unknown_policy_fails_closed():
    with pytest.raises(ValueError, match="unknown representation policy"):
        resolve_representation_policy(
            policy_id="missing",
            resolution_mode="DIRECT",
            registry=registry(),
            evidence_ledger=ledger(),
        )


def test_incompatible_mode_fails_closed():
    with pytest.raises(ValueError, match="incompatible"):
        resolve_representation_policy(
            policy_id="policy-v1",
            resolution_mode="PHASE_SET",
            registry=registry(),
            evidence_ledger=ledger(),
        )


def test_case_specific_requirement_must_be_declared_by_policy():
    with pytest.raises(ValueError, match="not declared by policy"):
        resolve_representation_policy(
            policy_id="policy-v1",
            resolution_mode="DIRECT",
            registry=registry(),
            evidence_ledger=ledger(),
            additional_required_inputs=("material_specific_escape_hatch",),
        )


def test_optional_declared_input_can_be_promoted_to_case_requirement():
    resolved = resolve_representation_policy(
        policy_id="policy-v1",
        resolution_mode="DIRECT",
        registry=registry(),
        evidence_ledger=ledger(
            evidence(),
            evidence(input_key="bias_assessment", sha="2" * 64),
        ),
        additional_required_inputs=("bias_assessment",),
    )
    assert resolved.status == RepresentationPolicyStatus.SATISFIED.value
    assert resolved.required_inputs == ("strategy", "bias_assessment")


def test_global_ledger_validation_rejects_orphan_policy():
    orphan = evidence(policy_id="missing")
    with pytest.raises(ValueError, match="unknown policy"):
        validate_representation_evidence_ledger(registry(), ledger(orphan))


def test_global_ledger_validation_rejects_undeclared_input():
    typo = evidence(input_key="stratgey")
    with pytest.raises(ValueError, match="not declared by policy"):
        validate_representation_evidence_ledger(registry(), ledger(typo))


def test_policy_registry_rejects_duplicate_policy_ids():
    p = policy()
    with pytest.raises(ValueError, match="unique policy ids"):
        RepresentationPolicyRegistry(
            registry_version=REPRESENTATION_POLICY_VERSION,
            policies=(p, p),
        )


def test_evidence_ledger_rejects_duplicate_policy_input_pairs():
    item = evidence()
    with pytest.raises(ValueError, match="unique policy/input pairs"):
        ledger(item, item)


def test_policy_registry_json_contains_forbidden_shortcuts():
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    item = raw["policies"][0]
    assert "silent_occupancy_rounding" in item["forbidden_shortcuts"]
    assert (
        "single_ordered_proxy_without_declared_ensemble_or_justification"
        in item["forbidden_shortcuts"]
    )
