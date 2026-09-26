from dataclasses import replace

import pytest

from rudeus.science.contracts import digest
from rudeus.science.negative_controls import (
    NAssessment,
    NControlSpec,
    NObservation,
    NStatus,
    assess_n,
    n_record,
    verify_n_record,
)


def spec():
    return NControlSpec(
        control_id="caged-zero-diffusion",
        target_claim_hash=digest("target-claim"),
        protocol_hash=digest("n-protocol"),
        control_kind="known_negative_transport",
        expected=False,
        scope={"quantity": "decisive_diffusion", "domain": "synthetic-caged"},
        justification="PROVISIONAL N contract test control only",
    )


def observation(value):
    s = spec()
    return NObservation(
        control_id=s.control_id,
        protocol_hash=s.protocol_hash,
        observed=value,
        scope=s.scope,
        evidence_hashes=(digest(["evidence", value]),),
        producer_identity="synthetic-caged-generator-v1",
    )


def test_n_passed_control_never_upgrades_target_claim():
    s = spec()
    obs = observation(False)

    out = assess_n(s, obs)

    assert out.status == NStatus.CONTROL_PASSED
    assert out.target_verdict_changed is False
    assert out.conflicting_evidence == ()
    assert out.control_evidence == obs.evidence_hashes
    assert NAssessment.from_dict(out.to_dict()) == out


def test_n_violated_negative_control_is_falsification_evidence():
    s = spec()
    obs = observation(True)

    out = assess_n(s, obs)

    assert out.status == NStatus.FALSIFIED
    assert out.target_verdict_changed is False
    assert out.conflicting_evidence == obs.evidence_hashes
    assert "negative_control_violated" in out.reason_codes


def test_n_missing_or_scope_mismatched_control_is_not_decisive():
    s = spec()

    missing = assess_n(s, None)
    assert missing.status == NStatus.INDETERMINATE

    mismatched = replace(
        observation(False),
        protocol_hash=digest("other-protocol"),
    )
    blocked = assess_n(s, mismatched)
    assert blocked.status == NStatus.BLOCKED_SCOPE_MISMATCH
    assert blocked.target_verdict_changed is False


def test_n_unavailable_outcome_remains_indeterminate():
    s = spec()
    obs = observation(None)

    out = assess_n(s, obs)

    assert out.status == NStatus.INDETERMINATE
    assert out.conflicting_evidence == ()
    assert out.control_evidence == obs.evidence_hashes


def test_n_record_replays_and_rejects_forged_falsification():
    s = spec()
    obs = observation(False)
    record = n_record(s, obs)

    verified = verify_n_record(record)
    assert verified["status"] == "CONTROL_PASSED"
    assert verified["target_verdict_changed"] is False
    assert len(verified["record_hash"]) == 64

    forged = dict(record)
    forged["assessment"] = dict(forged["assessment"])
    forged["assessment"]["status"] = "FALSIFIED"
    forged["assessment"]["conflicting_evidence"] = list(obs.evidence_hashes)

    with pytest.raises(ValueError, match="replay mismatch"):
        verify_n_record(forged)


def test_n_record_schema_and_stage_are_closed():
    s = spec()
    record = n_record(s, observation(False))

    wrong_stage = dict(record)
    wrong_stage["stage"] = "X"
    with pytest.raises(ValueError, match="invalid N record schema"):
        verify_n_record(wrong_stage)

    extra = dict(record)
    extra["latest"] = True
    with pytest.raises(ValueError, match="invalid N record schema"):
        verify_n_record(extra)
