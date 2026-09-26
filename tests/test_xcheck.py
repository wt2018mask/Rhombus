from dataclasses import replace

import pytest

from rudeus.science.contracts import digest
from rudeus.science.xcheck import (
    XAssessment,
    XComparisonSpec,
    XInputBinding,
    XModelIdentity,
    XStatus,
    assess_x,
    independent_models,
)


def model(name, family, checkpoint, implementation):
    return XModelIdentity(
        model_name=name,
        model_family=family,
        checkpoint_sha256=digest(checkpoint),
        code_revision=digest(["code", name]),
        implementation_id=implementation,
    )


def binding():
    return XInputBinding(
        candidate_id="candidate",
        structure_sha256=digest("structure"),
        protocol_hash=digest("protocol"),
        quantity="D_self",
        units="m2/s",
        conditions={"temperature_K": 550.0, "species": "Li"},
    )


def criterion():
    return XComparisonSpec(
        quantity="D_self",
        units="m2/s",
        relative_tolerance=0.25,
        justification="PROVISIONAL X contract test criterion only",
    )


def test_x_independence_fails_closed_on_same_checkpoint_family_or_implementation():
    primary = model("primary", "family-a", "checkpoint-a", "impl-a")

    ok, reasons = independent_models(
        primary, model("cross", "family-b", "checkpoint-b", "impl-b"))
    assert ok is True and reasons == ()

    same_checkpoint = replace(
        model("cross", "family-b", "checkpoint-b", "impl-b"),
        checkpoint_sha256=primary.checkpoint_sha256,
    )
    ok, reasons = independent_models(primary, same_checkpoint)
    assert ok is False and "same_checkpoint" in reasons

    ok, reasons = independent_models(
        primary, model("cross", "family-a", "checkpoint-b", "impl-b"))
    assert ok is False and "same_model_family" in reasons

    ok, reasons = independent_models(
        primary, model("cross", "family-b", "checkpoint-b", "impl-a"))
    assert ok is False and "same_implementation" in reasons


def test_x_agreement_records_support_but_never_changes_primary_verdict():
    primary = model("primary", "family-a", "checkpoint-a", "impl-a")
    cross = model("cross", "family-b", "checkpoint-b", "impl-b")
    b = binding()
    p_ref, x_ref = digest("primary-evidence"), digest("cross-evidence")

    out = assess_x(
        primary_model=primary,
        cross_model=cross,
        primary_binding=b,
        cross_binding=b,
        comparison=criterion(),
        primary_value=1.0e-9,
        cross_value=0.9e-9,
        primary_evidence_hash=p_ref,
        cross_evidence_hash=x_ref,
    )

    assert out.status == XStatus.AGREEMENT
    assert out.primary_verdict_changed is False
    assert out.supporting_evidence == (p_ref, x_ref)
    assert out.conflicting_evidence == ()
    assert XAssessment.from_dict(out.to_dict()) == out


def test_x_disagreement_is_preserved_as_conflicting_evidence():
    primary = model("primary", "family-a", "checkpoint-a", "impl-a")
    cross = model("cross", "family-b", "checkpoint-b", "impl-b")
    b = binding()
    p_ref, x_ref = digest("primary-evidence"), digest("cross-evidence")

    out = assess_x(
        primary_model=primary,
        cross_model=cross,
        primary_binding=b,
        cross_binding=b,
        comparison=criterion(),
        primary_value=1.0e-9,
        cross_value=0.2e-9,
        primary_evidence_hash=p_ref,
        cross_evidence_hash=x_ref,
    )

    assert out.status == XStatus.DISAGREEMENT
    assert out.supporting_evidence == ()
    assert out.conflicting_evidence == (p_ref, x_ref)
    assert out.primary_verdict_changed is False


def test_x_scope_mismatch_and_missing_value_are_not_decisive():
    primary = model("primary", "family-a", "checkpoint-a", "impl-a")
    cross = model("cross", "family-b", "checkpoint-b", "impl-b")
    b = binding()

    mismatch = replace(b, protocol_hash=digest("different-protocol"))
    out = assess_x(
        primary_model=primary,
        cross_model=cross,
        primary_binding=b,
        cross_binding=mismatch,
        comparison=criterion(),
        primary_value=1.0,
        cross_value=1.0,
    )
    assert out.status == XStatus.BLOCKED_SCOPE_MISMATCH

    missing = assess_x(
        primary_model=primary,
        cross_model=cross,
        primary_binding=b,
        cross_binding=b,
        comparison=criterion(),
        primary_value=1.0,
        cross_value=None,
    )
    assert missing.status == XStatus.INDETERMINATE


def test_x_same_family_cannot_masquerade_as_independent_agreement():
    primary = model("primary", "mace", "checkpoint-a", "mace-adapter")
    cross = model("cross", "mace", "checkpoint-b", "other-adapter")
    b = binding()

    out = assess_x(
        primary_model=primary,
        cross_model=cross,
        primary_binding=b,
        cross_binding=b,
        comparison=criterion(),
        primary_value=1.0,
        cross_value=1.0,
    )

    assert out.status == XStatus.BLOCKED_NOT_INDEPENDENT
    assert "same_model_family" in out.reason_codes
    assert out.supporting_evidence == ()
    assert out.primary_verdict_changed is False
