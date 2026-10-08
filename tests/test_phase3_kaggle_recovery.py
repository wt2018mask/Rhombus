"""Fail-closed branch triage without provider calls or production submission."""
import pytest

from rhombus.domain.kaggle_recovery import assess_kaggle_recovery


def flags(**kw):
    return {
        "receipt_verified": False,
        "archive_hashes_verified": False,
        "source_counts_verified": False,
        "source_digests_verified": False,
        **kw,
    }


def test_complete_requires_every_verification():
    result = assess_kaggle_recovery(provider_state="COMPLETE", evidence=flags())
    assert result["recovery_state"] == "COMPLETE_BUT_OUTPUTS_UNVERIFIED"
    verified = assess_kaggle_recovery(provider_state="COMPLETE", evidence=flags(
        receipt_verified=True, archive_hashes_verified=True,
        source_counts_verified=True, source_digests_verified=True,
    ))
    assert verified["recovery_state"] == "ARTIFACT_VERIFICATION_REPORTED_COMPLETE"
    assert verified["scientific_verdict"] == "UNKNOWN"
    assert verified["claim_authorized"] is False


@pytest.mark.parametrize("state", ["ERROR", "CANCELLED", "TIMEOUT"])
def test_terminal_failure_never_triggers_resubmission(state):
    result = assess_kaggle_recovery(provider_state=state, evidence=flags())
    assert result["provider_terminal"] is True
    assert result["resubmission_authorized"] is False
    assert result["partial_results_scientifically_qualified"] is False
    assert result["next_action"] == "CAPTURE_SANITIZED_LOGS_AND_VALIDATE_RECOVERABLE_FILES"


@pytest.mark.parametrize("state", ["RUNNING", "UNKNOWN", "STATUS_QUERY_ERROR"])
def test_heartbeat_or_status_errors_are_not_terminal(state):
    result = assess_kaggle_recovery(provider_state=state, evidence=flags())
    assert result["provider_terminal"] is False
    assert result["recovery_state"] == "PROVIDER_NOT_ATTESTED_TERMINAL"


def test_untrusted_flags_and_states_rejected():
    for bad in ({"receipt_verified": True}, flags(receipt_verified=1),
                {**flags(), "kernel_ref": "attacker/kernel"}):
        with pytest.raises(ValueError):
            assess_kaggle_recovery(provider_state="COMPLETE", evidence=bad)
    with pytest.raises(ValueError):
        assess_kaggle_recovery(provider_state="OTHER", evidence=flags())
