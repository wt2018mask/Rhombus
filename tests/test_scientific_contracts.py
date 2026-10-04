from dataclasses import replace
import pytest

from rudeus.science.contracts import (
    ClaimSpec, Observation, AcceptanceRegion, ObservableType, Uncertainty, digest,
)
from rudeus.science.claims import QualificationRecord, evaluate_claim, final_claim_vector
from rudeus.execution.contracts import TaskSpec, ExecutionError, FailureClass, classify_failure


def claim():
    # Artificial PROVISIONAL decision boundaries: contract tests, not calibration.
    return ClaimSpec(claim_id="D-positive", protocol_hash=digest("protocol"), estimand="D",
                     units="m2/s", scope={"temperature_K": 500}, assumptions=("stationary",),
                     applicability_requirements=(), sufficiency_requirements=("sampling",),
                     admissible_evidence=("derived_quantity",), independence_requirements=(),
                     provenance_identity=digest("source"), acceptance=AcceptanceRegion(
                         kind="interval", lower=1, upper=3, justification="synthetic test only"),
                     uncertainty_requirements={"registered_test": "synthetic fixture only"})


def observation(spec):
    return Observation(quantity="D", units="m2/s", value=2, species=("Li",),
                       conditions={"temperature_K": 500}, reference_frame="simulation_cell",
                       data_support={"frames": 100}, estimator="test", estimator_version="v1",
                       protocol_hash=spec.protocol_hash, artifact_hashes=(digest("artifact"),),
                       observable_type=ObservableType.DERIVED)


def certificate(spec):
    return QualificationRecord(protocol_hash=spec.protocol_hash, estimator="test",
                               uncertainty_method="test", nominal_coverage=0.9, scope=spec.scope,
                               evidence_hashes=(digest("validation"),),
                               estimator_version="v1", uncertainty_method_version="v1",
                               requirements_hash=digest(spec.uncertainty_requirements), status="QUALIFIED")


def test_deep_immutability_and_finite_serialization():
    spec = claim()
    with pytest.raises(TypeError):
        spec.scope["temperature_K"] = 900
    with pytest.raises(ValueError):
        replace(observation(spec), value=float("nan"))
    assert digest(spec.to_dict()) == spec.content_hash


@pytest.mark.parametrize("bounds,expected", [((1, 3), "PASS"), ((4, 5), "FAIL"),
                                            ((0, 2), "INDETERMINATE"), ((0, 1), "INDETERMINATE")])
def test_closed_confidence_region_semantics(bounds, expected):
    spec = claim()
    cert = certificate(spec)
    uncertainty = Uncertainty(method="test", method_version="v1", nominal_coverage=0.9,
                              observation_hash=observation(spec).content_hash,
                              bounds=bounds, calibration_reference=cert.content_hash,
                              unavailable_reasons=())
    result = evaluate_claim(spec, observation(spec), uncertainty,
                            checks={"stationary": True, "sampling": True},
                            qualification_registry={cert.content_hash: cert})
    assert result.verdict == expected


def test_worker_cannot_self_certify_and_missing_criteria_never_pass():
    spec = claim()
    u = Uncertainty(method="test", nominal_coverage=0.9, bounds=(1, 2), qualification="QUALIFIED",
                    unavailable_reasons=())
    assert evaluate_claim(spec, observation(spec), u, checks={"stationary": True,
                          "sampling": True}).verdict == "INDETERMINATE"
    assert evaluate_claim(replace(spec, acceptance=None), observation(spec)).verdict == "UNKNOWN"
    assert evaluate_claim(spec, None).verdict == "UNKNOWN"
    assert final_claim_vector((), ())['verdict'] == "UNKNOWN"


def test_conjunction_rejects_missing_and_conflicting_assessments():
    spec = claim()
    assessed = evaluate_claim(spec, observation(spec))
    assert final_claim_vector((spec,), (assessed, assessed))["verdict"] == "INDETERMINATE"
    fail = replace(assessed, verdict="FAIL", reason_codes=("synthetic failure",))
    assert final_claim_vector((spec,), (assessed, fail))["verdict"] == "INDETERMINATE"
    second = replace(spec, claim_id="missing")
    assert final_claim_vector((spec, second), (fail,))["verdict"] == "FAIL"


def task(**overrides):
    values = dict(candidate_id="candidate", stage="P3", protocol_hash=digest("p"),
                  config={"fit_window_ps": None}, input_artifact_hashes=(), dependencies=(),
                  code_revision="revision", resource_requirements={"kind": "analysis"},
                  expected_outputs=("result.json",), retry_policy={"max_attempts": 2})
    values.update(overrides)
    return TaskSpec(**values)


def test_task_identity_and_failure_separation():
    first = task()
    assert first.task_id == replace(first, resource_requirements={"kind": "analysis", "memory": 2}).task_id
    assert first.task_id != replace(first, seed=1).task_id
    assert first.task_id != replace(first, config={"fit_window_ps": [1, 2]}).task_id
    with pytest.raises(ValueError):
        task(config={"backend": "local"})
    assert classify_failure(TimeoutError()) == FailureClass.TIMEOUT
    assert classify_failure(ExecutionError("preempted", "INFRASTRUCTURE")) == FailureClass.INFRASTRUCTURE
