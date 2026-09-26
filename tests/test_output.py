from dataclasses import replace

import pytest

from rudeus.science.contracts import Verdict, digest
from rudeus.science.output import (
    OUTDisposition,
    ResearchOutput,
    build_output,
    out_record,
    verify_out_record,
)
from rudeus.science.synthesis import SStatus, SynthesisAssessment


def synthesis(status=SStatus.CONSISTENT, verdict=Verdict.PASS,
              conflicting=(), unresolved=()):
    return SynthesisAssessment(
        status=status,
        primary_claim_hash=digest("claim"),
        primary_assessment_hash=digest("assessment"),
        primary_verdict=verdict,
        x_assessment_hashes=(digest("x"),),
        n_assessment_hashes=(digest("n"),),
        reason_codes=("test",),
        supporting_evidence=(digest("support"),),
        conflicting_evidence=conflicting,
        unresolved_requirements=unresolved,
        final_claim_verdict=verdict,
        primary_verdict_changed=False,
    )


def test_out_supported_only_for_consistent_pass():
    out = build_output(synthesis())
    assert out.disposition == OUTDisposition.SUPPORTED
    assert out.claim_verdict == Verdict.PASS
    assert "registered scope" in out.summary
    assert ResearchOutput.from_dict(out.to_dict()) == out


def test_out_unknown_and_indeterminate_remain_unresolved():
    unknown = build_output(synthesis(verdict=Verdict.UNKNOWN))
    indeterminate = build_output(synthesis(
        status=SStatus.INDETERMINATE,
        verdict=Verdict.INDETERMINATE,
        unresolved=("coverage",),
    ))
    assert unknown.disposition == OUTDisposition.UNRESOLVED
    assert indeterminate.disposition == OUTDisposition.UNRESOLVED
    assert "unresolved scientific requirements remain" in indeterminate.caveats


def test_out_fail_remains_not_supported():
    out = build_output(synthesis(verdict=Verdict.FAIL))
    assert out.disposition == OUTDisposition.NOT_SUPPORTED
    assert out.claim_verdict == Verdict.FAIL


def test_out_conflict_cannot_be_presented_as_supported():
    conflict = synthesis(
        status=SStatus.CONFLICT,
        verdict=Verdict.INDETERMINATE,
        conflicting=(digest("conflict"),),
    )
    out = build_output(conflict)
    assert out.disposition == OUTDisposition.CONFLICTED
    assert "No positive scientific conclusion is authorized." in out.summary

    with pytest.raises(ValueError, match="conflicted synthesis"):
        replace(out, disposition=OUTDisposition.SUPPORTED)


def test_out_conflicting_evidence_forces_conflicted_even_if_status_were_wrong():
    base = synthesis(verdict=Verdict.INDETERMINATE)
    with pytest.raises(ValueError, match="conflicting evidence"):
        ResearchOutput(
            synthesis_hash=base.content_hash,
            synthesis_status=SStatus.INDETERMINATE,
            claim_verdict=Verdict.INDETERMINATE,
            disposition=OUTDisposition.UNRESOLVED,
            headline="x",
            summary="y",
            supporting_evidence=(),
            conflicting_evidence=(digest("conflict"),),
            unresolved_requirements=(),
            caveats=(),
            machine_readable={},
        )


def test_out_record_replays_and_rejects_forged_positive_language():
    s = synthesis(
        status=SStatus.CONFLICT,
        verdict=Verdict.INDETERMINATE,
        conflicting=(digest("conflict"),),
    )
    record = out_record(s)
    verified = verify_out_record(record)
    assert verified["disposition"] == "CONFLICTED"
    assert verified["claim_verdict"] == "INDETERMINATE"
    assert len(verified["record_hash"]) == 64

    forged = dict(record)
    forged["output"] = dict(forged["output"])
    forged["output"]["headline"] = "Claim supported"
    with pytest.raises(ValueError, match="OUT replay mismatch"):
        verify_out_record(forged)


def test_out_record_schema_and_stage_are_closed():
    record = out_record(synthesis(verdict=Verdict.UNKNOWN))
    wrong_stage = dict(record)
    wrong_stage["stage"] = "S"
    with pytest.raises(ValueError, match="invalid OUT record schema"):
        verify_out_record(wrong_stage)

    extra = dict(record)
    extra["mutable_latest"] = True
    with pytest.raises(ValueError, match="invalid OUT record schema"):
        verify_out_record(extra)


def test_output_roundtrip_restores_enum_types():
    original = build_output(synthesis(verdict=Verdict.UNKNOWN))
    restored = ResearchOutput.from_dict(original.to_dict())
    assert restored == original
    assert restored.synthesis_status is SStatus.CONSISTENT
    assert restored.claim_verdict is Verdict.UNKNOWN
    assert restored.disposition is OUTDisposition.UNRESOLVED
