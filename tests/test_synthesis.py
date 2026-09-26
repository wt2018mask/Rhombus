from dataclasses import replace

import pytest

from rudeus.science.contracts import ClaimAssessment, Verdict, digest
from rudeus.science.negative_controls import NAssessment, NStatus
from rudeus.science.synthesis import SStatus, SynthesisAssessment, s_record, synthesize, verify_s_record
from rudeus.science.xcheck import XAssessment, XStatus


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


def x(status):
    conflict = (digest(["x-conflict", status]),) if status == XStatus.DISAGREEMENT else ()
    support = (digest(["x-support", status]),) if status == XStatus.AGREEMENT else ()
    return XAssessment(
        status=status,
        primary_model_hash=digest("primary-model"),
        cross_model_hash=digest("cross-model"),
        input_binding_hash=digest("binding"),
        comparison_spec_hash=digest("comparison"),
        primary_value=1.0,
        cross_value=1.0 if status == XStatus.AGREEMENT else 2.0,
        absolute_difference=0.0 if status == XStatus.AGREEMENT else 1.0,
        relative_difference=0.0 if status == XStatus.AGREEMENT else 0.5,
        reason_codes=(status.value,),
        supporting_evidence=support,
        conflicting_evidence=conflict,
        primary_verdict_changed=False,
    )


def n(status):
    conflict = (digest(["n-conflict", status]),) if status == NStatus.FALSIFIED else ()
    support = (digest(["n-support", status]),) if status == NStatus.CONTROL_PASSED else ()
    return NAssessment(
        status=status,
        target_claim_hash=digest("claim"),
        control_spec_hash=digest("control"),
        observation_hash=digest(["obs", status]),
        reason_codes=(status.value,),
        control_evidence=support or conflict,
        conflicting_evidence=conflict,
        target_verdict_changed=False,
    )


def test_s_consistent_support_never_upgrades_primary():
    p = primary(Verdict.UNKNOWN)
    out = synthesize(
        p,
        x_assessments=(x(XStatus.AGREEMENT),),
        n_assessments=(n(NStatus.CONTROL_PASSED),),
    )
    assert out.status == SStatus.CONSISTENT
    assert out.final_claim_verdict == Verdict.UNKNOWN
    assert out.primary_verdict_changed is False


def test_s_x_disagreement_forces_conflict_without_rewriting_primary():
    p = primary(Verdict.PASS)
    out = synthesize(p, x_assessments=(x(XStatus.DISAGREEMENT),))
    assert out.status == SStatus.CONFLICT
    assert out.primary_verdict == Verdict.PASS
    assert out.final_claim_verdict == Verdict.INDETERMINATE
    assert out.conflicting_evidence


def test_s_n_falsification_forces_conflict_without_rewriting_primary():
    p = primary(Verdict.PASS)
    out = synthesize(p, n_assessments=(n(NStatus.FALSIFIED),))
    assert out.status == SStatus.CONFLICT
    assert out.final_claim_verdict == Verdict.INDETERMINATE
    assert "n_falsified" in out.reason_codes


def test_s_fail_primary_is_never_upgraded_by_support():
    p = primary(Verdict.FAIL)
    out = synthesize(
        p,
        x_assessments=(x(XStatus.AGREEMENT),),
        n_assessments=(n(NStatus.CONTROL_PASSED),),
    )
    assert out.status == SStatus.CONSISTENT
    assert out.final_claim_verdict == Verdict.FAIL


def test_s_blocked_or_indeterminate_downstream_cannot_leave_pass_decisive():
    p = primary(Verdict.PASS)
    blocked = synthesize(
        p,
        x_assessments=(x(XStatus.BLOCKED_NOT_INDEPENDENT),),
    )
    assert blocked.status == SStatus.BLOCKED
    assert blocked.final_claim_verdict == Verdict.INDETERMINATE

    incomplete = synthesize(
        p,
        n_assessments=(n(NStatus.INDETERMINATE),),
    )
    assert incomplete.status == SStatus.INDETERMINATE
    assert incomplete.final_claim_verdict == Verdict.INDETERMINATE


def test_s_rejects_n_assessment_targeting_another_claim():
    bad = replace(n(NStatus.CONTROL_PASSED), target_claim_hash=digest("other"))
    with pytest.raises(ValueError, match="different claim"):
        synthesize(primary(), n_assessments=(bad,))


def test_s_record_replays_and_rejects_forged_resolution():
    p = primary(Verdict.PASS)
    record = s_record(p, x_assessments=(x(XStatus.DISAGREEMENT),))
    verified = verify_s_record(record)
    assert verified["status"] == "CONFLICT"
    assert verified["final_claim_verdict"] == "INDETERMINATE"
    assert len(verified["record_hash"]) == 64

    forged = dict(record)
    forged["assessment"] = dict(forged["assessment"])
    forged["assessment"]["status"] = "CONSISTENT"
    forged["assessment"]["final_claim_verdict"] = "PASS"
    with pytest.raises(ValueError, match="replay mismatch"):
        verify_s_record(forged)


def test_s_record_schema_and_stage_are_closed():
    record = s_record(primary(Verdict.UNKNOWN))
    wrong_stage = dict(record)
    wrong_stage["stage"] = "OUT"
    with pytest.raises(ValueError, match="invalid S record schema"):
        verify_s_record(wrong_stage)

    extra = dict(record)
    extra["latest"] = True
    with pytest.raises(ValueError, match="invalid S record schema"):
        verify_s_record(extra)


def test_synthesis_roundtrip_restores_enum_types():
    original = synthesize(primary(Verdict.UNKNOWN))
    restored = SynthesisAssessment.from_dict(original.to_dict())
    assert restored == original
    assert restored.status is SStatus.CONSISTENT
    assert restored.primary_verdict is Verdict.UNKNOWN
    assert restored.final_claim_verdict is Verdict.UNKNOWN
