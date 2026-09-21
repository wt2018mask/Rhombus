"""Executable trajectory -> observation -> uncertainty -> assessment contract."""
from dataclasses import replace
import copy
import hashlib
import json
import subprocess
import sys

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science.contracts import (AcceptanceRegion, ClaimAssessment, ClaimSpec,
                                      Observation, Uncertainty, UNRESOLVED, canonical_bytes, digest)
from rudeus.science.p3 import P3Protocol, analyze_p3, main
from rudeus.science.statistics import ResamplingSpec
from tests.test_scientific_transport import bound_inputs
from tests.test_scientific_contracts import claim, observation, certificate
from rudeus.science.claims import evaluate_claim


def protocol():
    # Explicit PROVISIONAL synthetic experiment parameters, not production gates.
    return P3Protocol(target_species="Li", lag_steps=tuple(range(1, 9)),
                      fit_window_ps=(.1, .8), reference_frame="simulation_cell",
                      reconstruction={"coordinate_convention": "wrapped_cartesian_primary_cell",
                                      "periodic_directions": [True, True, True], "cell_origin_A": [0, 0, 0]},
                      resampling=ResamplingSpec(block_origins=9, min_blocks_provisional=2,
                          n_resamples=12, nominal_coverage_provisional=.68, seed=12,
                          replica_scheme="single_trajectory_no_replica_resampling",
                          joint_quantities=("D:Li",)))


def test_verified_slice_roundtrips_and_preserves_primary_estimator(tmp_path):
    p2, p25 = bound_inputs(tmp_path)
    before = canonical_bytes([p2, p25])
    proto = protocol()
    assert P3Protocol.from_dict(proto.to_dict()) == proto
    result = analyze_p3(p2, p25, proto, artifact_root=tmp_path, timestamp="fixed")
    assert canonical_bytes([p2, p25]) == before
    assert all(result[k] == v for k, v in p25["result"].items())
    record = result["p3_scientific_record"]
    obs = Observation.from_dict(record["observation"])
    unc = Uncertainty.from_dict(record["uncertainty"])
    spec = ClaimSpec.from_dict(record["claim_spec"])
    assessment = ClaimAssessment.from_dict(record["assessment"])
    assert unc.observation_hash == obs.content_hash
    assert assessment.claim_hash == spec.content_hash
    assert assessment.verdict == "UNKNOWN" and spec.acceptance is None
    assert unc.qualification == UNRESOLVED and unc.bounds is None
    assert "origin_pool_differs_from_point_estimator" in unc.unavailable_reasons
    assert obs.sample_counts["origins_per_lag"] == tuple(range(79, 71, -1))
    assert obs.dependence_counts["effective_independent_samples"] is None
    diagnostic = result["quantitative_transport"]["self_diffusion"]["resampling_diagnostic"]
    assert diagnostic["intervals"]["D:Li"] is not None
    assert diagnostic["used_origins"] == 72
    assert result["p3_provenance"]["scientific_record_hash"] == digest(record)
    assert result == analyze_p3(p2, p25, proto, artifact_root=tmp_path, timestamp="fixed")
    no_bootstrap = analyze_p3(p2, p25, replace(proto, resampling=None), artifact_root=tmp_path,
                              timestamp="fixed")
    assert no_bootstrap["p3_scientific_record"]["observation"]["value"] == obs.value


def test_explicit_criterion_cannot_qualify_diagnostic_or_insufficient_sampling(tmp_path):
    p2, p25 = bound_inputs(tmp_path)
    proto = protocol()
    result = analyze_p3(p2, p25, proto, artifact_root=tmp_path, timestamp="fixed")
    spec = ClaimSpec.from_dict(result["p3_scientific_record"]["claim_spec"])
    spec = replace(spec, acceptance=AcceptanceRegion(kind="interval", lower=0,
                   justification="PROVISIONAL synthetic test only"),
                   uncertainty_requirements={"qualification": "required"})
    assert ClaimSpec.from_dict(spec.to_dict()) == spec
    assessed = analyze_p3(p2, p25, proto, artifact_root=tmp_path, timestamp="fixed", claim_spec=spec)
    assert assessed["p3_scientific_record"]["assessment"]["verdict"] == "INDETERMINATE"
    short = replace(proto, lag_steps=(100, 200))
    insufficient = analyze_p3(p2, p25, short, artifact_root=tmp_path, timestamp="fixed")
    assert insufficient["p3_scientific_record"]["observation"] is None
    assert insufficient["p3_scientific_record"]["assessment"]["verdict"] == "UNKNOWN"
    assert "insufficient_frames_for_requested_lags" in insufficient["p3_assessment"]["reason_codes"]


@pytest.mark.parametrize("field,value", [("p2_seed", 999), ("p2_protocol_version", "different"),
                                        ("artifact_format_version", "different")])
def test_cross_document_provenance_tampering_is_integrity_failure(tmp_path, field, value):
    p2, p25 = bound_inputs(tmp_path)
    p25["result"]["provenance"][field] = value
    with pytest.raises(ExecutionError) as exc:
        analyze_p3(p2, p25, protocol(), artifact_root=tmp_path, timestamp="fixed")
    assert exc.value.failure_class == "INTEGRITY"


def test_corrupt_missing_and_already_analyzed_artifacts_do_not_become_material_fail(tmp_path):
    p2, p25 = bound_inputs(tmp_path)
    result = analyze_p3(p2, p25, protocol(), artifact_root=tmp_path, timestamp="fixed")
    with pytest.raises(ExecutionError, match="refusing overwrite"):
        analyze_p3(p2, result, protocol(), artifact_root=tmp_path, timestamp="fixed")
    artifact = tmp_path / "trajectory.npz"
    artifact.write_bytes(b"interrupted upload")
    for _ in range(2):
        with pytest.raises(ExecutionError) as exc:
            analyze_p3(p2, p25, protocol(), artifact_root=tmp_path, timestamp="fixed")
        assert exc.value.failure_class == "INTEGRITY"
        artifact.unlink(missing_ok=True)
    assert p2["result"]["p2_verdict"] == "PASS"


def test_numerical_failure_remains_execution_failure(tmp_path, monkeypatch):
    p2, p25 = bound_inputs(tmp_path)
    before = copy.deepcopy(p25)
    def fail(*args, **kwargs):
        raise FloatingPointError("injected numerical failure")
    monkeypatch.setattr("rudeus.science.p3.analyze_trajectory", fail)
    with pytest.raises(ExecutionError) as exc:
        analyze_p3(p2, p25, protocol(), artifact_root=tmp_path, timestamp="fixed")
    assert exc.value.failure_class == "NUMERICAL"
    assert p25 == before


def test_confidence_set_cannot_be_rebound_to_another_observation_or_method_version():
    spec = claim()
    obs = observation(spec)
    cert = certificate(spec)
    unc = Uncertainty(method="test", method_version="v1", nominal_coverage=.9, bounds=(1, 2),
                      observation_hash=obs.content_hash, calibration_reference=cert.content_hash,
                      unavailable_reasons=())
    kwargs = dict(checks={"stationary": True, "sampling": True},
                  qualification_registry={cert.content_hash: cert})
    assert evaluate_claim(spec, obs, unc, **kwargs).verdict == "PASS"
    assert evaluate_claim(spec, replace(obs, value=9), unc, **kwargs).verdict == "INDETERMINATE"
    assert evaluate_claim(spec, obs, replace(unc, method_version="v2"), **kwargs).verdict == "INDETERMINATE"


def test_unresolved_uncertainty_criterion_and_historical_fail_stay_uninterpreted(tmp_path):
    spec = replace(claim(), uncertainty_requirements=None)
    assert evaluate_claim(spec, observation(spec)).verdict == "UNKNOWN"
    p2, p25 = bound_inputs(tmp_path)
    p2["result"]["p2_verdict"] = p25["result"]["p2_verdict"] = "FAIL"
    p2["result"]["dynamic_state"] = p25["result"]["p2_dynamic_state"] = "FAIL"
    p2["result"]["reasons"] = ["numerical-failure historical label"]
    before = canonical_bytes([p2, p25])
    result = analyze_p3(p2, p25, protocol(), artifact_root=tmp_path, timestamp="fixed")
    assert canonical_bytes([p2, p25]) == before
    assert result["p2_verdict"] == "FAIL"
    assert result["p3_scientific_record"]["assessment"]["verdict"] == "UNKNOWN"
    assert result["p3_scientific_record"]["observation"] is None
    assert "legacy_p2_interpretation" not in result["p3_assessment"]


def test_cli_executes_real_slice_and_refuses_overwrite(tmp_path, capsys):
    p2, p25 = bound_inputs(tmp_path)
    for name, value in (("p2", p2), ("p25", p25), ("protocol", protocol().to_dict())):
        (tmp_path / f"{name}.json").write_bytes(canonical_bytes(value))
    protected = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}
    output = tmp_path / "p3.json"
    args = ["--p2", str(tmp_path/"p2.json"), "--p25", str(tmp_path/"p25.json"),
            "--protocol", str(tmp_path/"protocol.json"), "--artifact-root", str(tmp_path),
            "--timestamp", "fixed", "--output", str(output)]
    completed = subprocess.run([sys.executable, "-B", "-m", "rudeus.science.p3", *args],
                               capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["scientific_verdict"] == "UNKNOWN"
    original = output.read_bytes()
    assert main(args) == 0
    assert output.read_bytes() == original
    args[args.index("fixed")] = "changed"
    assert main(args) == 1
    assert output.read_bytes() == original
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["failure_class"] == "INTEGRITY"
    assert {name: hashlib.sha256((tmp_path/name).read_bytes()).hexdigest() for name in protected} == protected
    assert not list(tmp_path.glob(".p3-pending-*"))
