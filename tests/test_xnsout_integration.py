from rudeus.science.contracts import ClaimAssessment, Verdict, digest
from rudeus.science.negative_controls import (
    NControlSpec,
    NObservation,
    NStatus,
    assess_n,
)
from rudeus.science.output import OUTDisposition, build_output
from rudeus.science.synthesis import SStatus, synthesize
from rudeus.science.xcheck import (
    XComparisonSpec,
    XInputBinding,
    XModelIdentity,
    XObservation,
    XStatus,
    assess_x_observations,
)


def primary(verdict=Verdict.PASS):
    return ClaimAssessment(
        claim_id="claim",
        claim_hash=digest("claim"),
        protocol_hash=digest("protocol"),
        verdict=verdict,
        assumptions={},
        applicability={},
        statistical_sufficiency={},
        reason_codes=("primary",),
        supporting_evidence=(digest("primary-evidence"),),
        conflicting_evidence=(),
        unresolved_requirements=(),
    )


def x_inputs(cross_value):
    primary_model = XModelIdentity(
        model_name="primary",
        model_family="mace",
        checkpoint_sha256=digest("primary-checkpoint"),
        code_revision=digest("primary-code"),
        implementation_id="primary-adapter",
        training_data_id="mptrj-2022.9",
    )
    cross_model = XModelIdentity(
        model_name="cross",
        model_family="independent-family",
        checkpoint_sha256=digest("cross-checkpoint"),
        code_revision=digest("cross-code"),
        implementation_id="cross-adapter",
        training_data_id="independent-cross-training-v1",
    )
    binding = XInputBinding(
        candidate_id="candidate",
        structure_sha256=digest("structure"),
        protocol_hash=digest("protocol"),
        quantity="D_self",
        units="m2/s",
        conditions={"temperature_K": 550.0, "species": "Li"},
    )
    comparison = XComparisonSpec(
        quantity="D_self",
        units="m2/s",
        relative_tolerance=0.25,
        justification="PROVISIONAL integration criterion",
    )
    primary_obs = XObservation(
        model_hash=primary_model.content_hash,
        input_binding_hash=binding.content_hash,
        quantity=binding.quantity,
        units=binding.units,
        value=1.0e-9,
        evidence_hash=digest("primary-x-evidence"),
        estimator_id="primary-estimator",
    )
    cross_obs = XObservation(
        model_hash=cross_model.content_hash,
        input_binding_hash=binding.content_hash,
        quantity=binding.quantity,
        units=binding.units,
        value=cross_value,
        evidence_hash=digest(["cross-x-evidence", cross_value]),
        estimator_id="cross-estimator",
    )
    return primary_model, cross_model, binding, comparison, primary_obs, cross_obs


def x_assessment(cross_value):
    pm, cm, binding, comparison, po, xo = x_inputs(cross_value)
    return assess_x_observations(
        primary_model=pm,
        cross_model=cm,
        primary_binding=binding,
        cross_binding=binding,
        comparison=comparison,
        primary_observation=po,
        cross_observation=xo,
    )


def n_assessment(observed):
    spec = NControlSpec(
        control_id="known-negative",
        target_claim_hash=digest("claim"),
        protocol_hash=digest("n-protocol"),
        control_kind="known_negative_transport",
        expected=False,
        scope={"quantity": "decisive_diffusion", "domain": "synthetic-negative"},
        justification="PROVISIONAL integration control",
    )
    obs = NObservation(
        control_id=spec.control_id,
        protocol_hash=spec.protocol_hash,
        observed=observed,
        scope=spec.scope,
        evidence_hashes=(digest(["n-evidence", observed]),),
        producer_identity="synthetic-negative-v1",
    )
    return assess_n(spec, obs)


def test_xnsout_consistent_path_preserves_primary_pass_without_upgrading():
    x = x_assessment(0.9e-9)
    n = n_assessment(False)

    assert x.status == XStatus.AGREEMENT
    assert n.status == NStatus.CONTROL_PASSED

    s = synthesize(primary(Verdict.PASS), x_assessments=(x,), n_assessments=(n,))
    out = build_output(s)

    assert s.status == SStatus.CONSISTENT
    assert s.final_claim_verdict == Verdict.PASS
    assert s.primary_verdict_changed is False
    assert out.disposition == OUTDisposition.SUPPORTED
    assert out.claim_verdict == Verdict.PASS


def test_xnsout_x_disagreement_propagates_to_conflicted_output():
    x = x_assessment(0.2e-9)
    n = n_assessment(False)

    assert x.status == XStatus.DISAGREEMENT

    s = synthesize(primary(Verdict.PASS), x_assessments=(x,), n_assessments=(n,))
    out = build_output(s)

    assert s.status == SStatus.CONFLICT
    assert s.final_claim_verdict == Verdict.INDETERMINATE
    assert s.conflicting_evidence
    assert out.disposition == OUTDisposition.CONFLICTED
    assert out.claim_verdict == Verdict.INDETERMINATE


def test_xnsout_n_falsification_propagates_to_conflicted_output():
    x = x_assessment(0.9e-9)
    n = n_assessment(True)

    assert n.status == NStatus.FALSIFIED

    s = synthesize(primary(Verdict.PASS), x_assessments=(x,), n_assessments=(n,))
    out = build_output(s)

    assert s.status == SStatus.CONFLICT
    assert s.final_claim_verdict == Verdict.INDETERMINATE
    assert "n_falsified" in s.reason_codes
    assert out.disposition == OUTDisposition.CONFLICTED


def test_xnsout_unknown_primary_cannot_be_promoted_by_clean_downstream_evidence():
    x = x_assessment(0.9e-9)
    n = n_assessment(False)

    s = synthesize(primary(Verdict.UNKNOWN), x_assessments=(x,), n_assessments=(n,))
    out = build_output(s)

    assert s.status == SStatus.CONSISTENT
    assert s.final_claim_verdict == Verdict.UNKNOWN
    assert out.disposition == OUTDisposition.UNRESOLVED
    assert out.claim_verdict == Verdict.UNKNOWN


def test_xnsout_fail_primary_cannot_be_rescued_by_clean_downstream_evidence():
    x = x_assessment(0.9e-9)
    n = n_assessment(False)

    s = synthesize(primary(Verdict.FAIL), x_assessments=(x,), n_assessments=(n,))
    out = build_output(s)

    assert s.status == SStatus.CONSISTENT
    assert s.final_claim_verdict == Verdict.FAIL
    assert out.disposition == OUTDisposition.NOT_SUPPORTED
    assert out.claim_verdict == Verdict.FAIL
