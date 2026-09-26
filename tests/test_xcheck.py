from dataclasses import replace

import pytest

from rudeus.science.contracts import digest
from rudeus.science.xcheck import (
    XAssessment,
    XComparisonSpec,
    XInputBinding,
    XModelIdentity,
    XObservation,
    XStatus,
    assess_x,
    assess_x_observations,
    independent_models,
    verify_x_record,
    x_record,
)


def model(name, family, checkpoint, implementation):
    return XModelIdentity(
        model_name=name,
        model_family=family,
        checkpoint_sha256=digest(checkpoint),
        code_revision=digest(["code", name]),
        implementation_id=implementation,
        training_data_id="train-" + family,
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


def test_x_observation_binding_rejects_model_or_input_rebinding():
    primary = model("primary", "family-a", "checkpoint-a", "impl-a")
    cross = model("cross", "family-b", "checkpoint-b", "impl-b")
    b = binding()

    p_obs = XObservation(
        model_hash=primary.content_hash,
        input_binding_hash=b.content_hash,
        quantity=b.quantity,
        units=b.units,
        value=1.0e-9,
        evidence_hash=digest("p-evidence"),
        estimator_id="primary-estimator-v1",
    )
    x_obs = XObservation(
        model_hash=cross.content_hash,
        input_binding_hash=b.content_hash,
        quantity=b.quantity,
        units=b.units,
        value=0.9e-9,
        evidence_hash=digest("x-evidence"),
        estimator_id="cross-estimator-v1",
    )

    out = assess_x_observations(
        primary_model=primary,
        cross_model=cross,
        primary_binding=b,
        cross_binding=b,
        comparison=criterion(),
        primary_observation=p_obs,
        cross_observation=x_obs,
    )
    assert out.status == XStatus.AGREEMENT

    with pytest.raises(ValueError, match="cross observation model binding mismatch"):
        assess_x_observations(
            primary_model=primary,
            cross_model=cross,
            primary_binding=b,
            cross_binding=b,
            comparison=criterion(),
            primary_observation=p_obs,
            cross_observation=replace(x_obs, model_hash=primary.content_hash),
        )

    other_binding = replace(b, protocol_hash=digest("other-protocol"))
    with pytest.raises(ValueError, match="cross observation input binding mismatch"):
        assess_x_observations(
            primary_model=primary,
            cross_model=cross,
            primary_binding=b,
            cross_binding=other_binding,
            comparison=criterion(),
            primary_observation=p_obs,
            cross_observation=x_obs,
        )


def test_x_observation_roundtrip_preserves_evidence_identity():
    primary = model("primary", "family-a", "checkpoint-a", "impl-a")
    b = binding()
    obs = XObservation(
        model_hash=primary.content_hash,
        input_binding_hash=b.content_hash,
        quantity=b.quantity,
        units=b.units,
        value=None,
        evidence_hash=digest("raw-model-output"),
        estimator_id="adapter-v1",
    )
    assert XObservation.from_dict(obs.to_dict()) == obs
    assert obs.evidence_hash == digest("raw-model-output")


def test_x_record_replays_exactly_and_rejects_forged_assessment():
    primary = model("primary", "family-a", "checkpoint-a", "impl-a")
    cross = model("cross", "family-b", "checkpoint-b", "impl-b")
    b = binding()
    p_obs = XObservation(
        model_hash=primary.content_hash,
        input_binding_hash=b.content_hash,
        quantity=b.quantity,
        units=b.units,
        value=1.0e-9,
        evidence_hash=digest("primary-evidence"),
        estimator_id="primary-v1",
    )
    x_obs = XObservation(
        model_hash=cross.content_hash,
        input_binding_hash=b.content_hash,
        quantity=b.quantity,
        units=b.units,
        value=0.95e-9,
        evidence_hash=digest("cross-evidence"),
        estimator_id="cross-v1",
    )

    record = x_record(
        primary_model=primary,
        cross_model=cross,
        primary_binding=b,
        cross_binding=b,
        comparison=criterion(),
        primary_observation=p_obs,
        cross_observation=x_obs,
    )
    verified = verify_x_record(record)
    assert verified["scientific_status"] == "AGREEMENT"
    assert verified["primary_verdict_changed"] is False
    assert len(verified["record_hash"]) == 64

    forged = dict(record)
    forged["assessment"] = dict(forged["assessment"])
    forged["assessment"]["status"] = "DISAGREEMENT"
    with pytest.raises(ValueError, match="replay mismatch"):
        verify_x_record(forged)


def test_x_record_schema_is_closed_and_stage_is_bound():
    primary = model("primary", "family-a", "checkpoint-a", "impl-a")
    cross = model("cross", "family-b", "checkpoint-b", "impl-b")
    b = binding()
    p_obs = XObservation(
        model_hash=primary.content_hash,
        input_binding_hash=b.content_hash,
        quantity=b.quantity,
        units=b.units,
        value=1.0,
        evidence_hash=digest("primary-evidence"),
        estimator_id="primary-v1",
    )
    x_obs = replace(
        p_obs,
        model_hash=cross.content_hash,
        evidence_hash=digest("cross-evidence"),
        estimator_id="cross-v1",
    )
    record = x_record(
        primary_model=primary,
        cross_model=cross,
        primary_binding=b,
        cross_binding=b,
        comparison=criterion(),
        primary_observation=p_obs,
        cross_observation=x_obs,
    )

    wrong_stage = dict(record)
    wrong_stage["stage"] = "N"
    with pytest.raises(ValueError, match="invalid X record schema"):
        verify_x_record(wrong_stage)

    extra = dict(record)
    extra["mutable_latest"] = True
    with pytest.raises(ValueError, match="invalid X record schema"):
        verify_x_record(extra)
