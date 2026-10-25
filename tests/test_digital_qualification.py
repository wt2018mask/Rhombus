"""Adversarial digital claim semantics, not synthetic atomistic validation."""
import pytest

from rhombus.qualification.digital import assess_pilot_claims


def assessment(**overrides):
    args = dict(candidate_id="fixture", protocol_hash="1" * 64,
                artifact_hashes=("2" * 64,), source_verified=True, numerically_replayed=True)
    return assess_pilot_claims(**(args | overrides))


def claims(result):
    return {r["claim_id"].split(":")[-1]: r["verdict"] for r in result["claim_vector"]["claims"]}


def test_numerical_success_does_not_qualify_material_or_transport():
    r = assessment(); c = claims(r)
    assert c["source_and_structure_identity"] == c["numerical_protocol_compliance"] == "PASS"
    assert all(c[k] == "UNKNOWN" for k in ("model_applicability", "simulation_convergence",
                                          "transport_claim_support", "uncertainty"))
    assert r["claim_vector"]["verdict"] == "UNKNOWN"
    assert r["qualification"] == "ABSTAIN" and not r["qualified_survivor"]


def test_physical_experiment_is_not_a_required_digital_claim():
    r = assessment()
    assert len(claims(r)) == 6
    assert not any("P0_0" in k or "physical_confirmation" in k for k in claims(r))
    assert r["physical_experimental_confirmation"] == "NOT_ASSESSED_OUTSIDE_REQUIRED_DIGITAL_SCOPE"


@pytest.mark.parametrize("key", ["source_verified", "numerically_replayed"])
def test_real_predicate_failure_remains_failed_instead_of_hidden_unknown(key):
    r = assessment(**{key: False})
    assert r["claim_vector"]["verdict"] == "FAIL"
    assert not r["qualified_survivor"]


@pytest.mark.parametrize("changes", [{"source_verified": 1}, {"numerically_replayed": "true"},
                                       {"candidate_id": " "}, {"artifact_hashes": ()}])
def test_invalid_or_unbound_claim_inputs_rejected(changes):
    with pytest.raises(ValueError): assessment(**changes)


def test_evidence_and_claim_ids_are_repeatable_and_bound_to_candidate_protocol():
    a = assessment(); b = assessment()
    assert a == b
    assert a["claim_vector"]["profile_hash"] != assessment(candidate_id="different")["claim_vector"]["profile_hash"]
    assert a["claim_vector"]["profile_hash"] != assessment(protocol_hash="3" * 64)["claim_vector"]["profile_hash"]
