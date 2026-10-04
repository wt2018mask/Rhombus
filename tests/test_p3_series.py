"""Synthetic P3 aggregation tests; no MD or historical cohort execution."""
from copy import deepcopy
from dataclasses import replace

import pytest

from rudeus.science.claims import QualificationRecord
from rudeus.science.contracts import (AcceptanceRegion, ClaimSpec, Observation,
                                      ObservableType, Uncertainty, digest)
from rudeus.science.p3_series import analyze_p3_series


def replicate(temperature, D, point_id, replica_id, *, candidate="candidate",
              protocol=None, frame="simulation_cell", uncertainty=True):
    protocol = protocol or digest("p3-protocol")
    trajectory = digest([point_id, replica_id])
    source = {"candidate_material_id": candidate, "target_species": "Li",
              "temperature_K": temperature, "transport_state": "DIFFUSIVE"}
    obs = Observation(quantity="D_self", units="m2/s", value=D, species=("Li",),
        conditions={"candidate_id": candidate, "temperature_K": temperature,
                    "reference_frame": frame}, reference_frame=frame,
        data_support={"trajectory_sha256": trajectory}, estimator="free_intercept_OLS_MSD",
        estimator_version="p3-test", protocol_hash=protocol, artifact_hashes=(trajectory,),
        observable_type=ObservableType.DERIVED)
    unc = Uncertainty(observation_hash=obs.content_hash,
        method="diagnostic_blocks" if uncertainty else None,
        unavailable_reasons=("coverage_not_qualified",) if uncertainty else
                            ("resampling_protocol_unresolved",))
    record = {"observation": obs.to_dict(), "uncertainty": unc.to_dict()}
    result = {**source,
        "quantitative_transport": {"self_diffusion": {"D_m2_per_s": D},
            "conductivity_estimate": {"available": False, "claim_status": "estimate"},
            "collective_transport": {"available": False, "status": "INSUFFICIENT"}},
        "p3_scientific_record": record,
        "p3_provenance": {"scientific_record_hash": digest(record),
            "p25_result_hash": digest(source), "p3_config_hash": protocol,
            "trajectory_sha256": trajectory}}
    return {"temperature_point_id": point_id, "replicate_id": replica_id,
            "p3_result": result}


def series():
    k = 8.617333262145e-5
    return [replicate(t, 1e-7 * __import__("math").exp(-.25 / (k*t)), f"T{t}", "r1")
            for t in (500., 600., 700., 800.)]


def test_single_and_two_temperatures_remain_insufficient():
    for inputs in (series()[:1], series()[:2]):
        report = analyze_p3_series(inputs)
        assert report["temperature_dependence"]["fit"]["status"] == "INSUFFICIENT_TEMPERATURES"
        assert report["assessment"]["verdict"] == "UNKNOWN"


def test_synthetic_arrhenius_preserves_replicates_and_extrapolation():
    inputs = series()
    exact = analyze_p3_series(inputs)
    assert exact["temperature_dependence"]["fit"]["activation_energy_eV"] == pytest.approx(.25)
    second = replicate(500., inputs[0]["p3_result"]["quantitative_transport"]["self_diffusion"]["D_m2_per_s"] * 1.1,
                       "T500.0", "r2")
    inputs.append(second)
    report = analyze_p3_series(inputs, target_temperature_K=300.)
    assert report["temperature_points"][0]["replicate_ids"] == ["r1", "r2"]
    assert report["temperature_points"][0]["replicate_spread_m2_per_s"] is not None
    assert report["temperature_points"][0]["uncertainty_bounds"] is None
    assert len(report["replicates"]) == 5
    assert len(report["temperature_dependence"]["conductivity_points"]) == 5
    assert not any(p["actual_conductivity_qualified"] for p in
                   report["temperature_dependence"]["conductivity_points"])
    fit = report["temperature_dependence"]["fit"]
    assert fit["available"] and len(fit["fit_diagnostics"]["residuals_log_D"]) == 4
    assert fit["fit_diagnostics"]["regime_qualification"] != "QUALIFIED"
    assert report["extrapolation"]["status"] == "EXTRAPOLATED"
    assert report["extrapolation"]["uncertainty"]["value_ci"] is None
    assert report["assessment"]["verdict"] == "UNKNOWN"


@pytest.mark.parametrize("change", [
    lambda p: p.update(replicate_id=""),
    lambda p: p["p3_result"].update(candidate_material_id="other"),
    lambda p: p["p3_result"]["p3_provenance"].update(p3_config_hash=digest("other")),
    lambda p: p["p3_result"]["p3_scientific_record"]["observation"].update(reference_frame="lab"),
    lambda p: p.update(temperature_point_id="T500.0"),
])
def test_identity_and_binding_mismatches_are_rejected(change):
    inputs = series()[:2]
    bad = deepcopy(inputs[1])
    change(bad)
    with pytest.raises(ValueError):
        analyze_p3_series([inputs[0], bad])


def test_duplicate_replicate_and_tampered_p25_binding_are_rejected():
    first = series()[0]
    with pytest.raises(ValueError, match="replicate identity"):
        analyze_p3_series([first, deepcopy(first)])
    tampered = deepcopy(first)
    tampered["p3_result"]["p3_provenance"]["p25_result_hash"] = digest("wrong")
    with pytest.raises(ValueError, match="P2.5 payload binding"):
        analyze_p3_series([tampered])


def test_missing_uncertainty_and_non_arrhenius_residuals_stay_unqualified():
    inputs = [replicate(t, D, f"T{t}", "r1", uncertainty=False)
              for t, D in ((500., 1e-12), (600., 9e-12), (700., 2e-12))]
    report = analyze_p3_series(inputs)
    assert report["temperature_dependence"]["fit"]["available"]
    assert max(abs(x) for x in report["temperature_dependence"]["fit"]["fit_diagnostics"]["residuals_log_D"]) > 0
    assert report["uncertainty"]["bounds"] is None
    assert report["assessment"]["verdict"] == "UNKNOWN"


def test_held_out_binding_requires_exact_estimator_method_population_and_checks():
    inputs = series()
    initial = analyze_p3_series(inputs)
    spec = replace(ClaimSpec.from_dict(initial["claim_spec"]),
        acceptance=AcceptanceRegion(kind="interval", lower=.1, upper=.4,
                                    justification="PROVISIONAL synthetic criterion"),
        uncertainty_requirements={"held_out_coverage": "required"})
    observation = Observation.from_dict(initial["observation"])
    cert = QualificationRecord(protocol_hash=initial["series_hash"],
        estimator=observation.estimator, estimator_version=observation.estimator_version,
        uncertainty_method="held_out_interval", uncertainty_method_version="v1",
        nominal_coverage=.9, scope=spec.scope, evidence_hashes=(digest("synthetic held-out"),),
        requirements_hash=digest(spec.uncertainty_requirements), status="QUALIFIED")
    uncertainty = Uncertainty(observation_hash=observation.content_hash,
        method="held_out_interval", method_version="v1", nominal_coverage=.9,
        bounds=(.2, .3), calibration_reference=cert.content_hash,
        unavailable_reasons=())
    checks = {name: True for name in (spec.assumptions + spec.applicability_requirements +
                                      spec.sufficiency_requirements + spec.independence_requirements)}
    report = analyze_p3_series(inputs, claim_spec=spec, activation_uncertainty=uncertainty,
        qualification_registry={cert.content_hash: cert}, checks=checks)
    assert report["calibration_applicability"]["status"] == "APPLICABLE"
    assert report["calibration_applicability"]["held_out_evidence_hashes"] == list(cert.evidence_hashes)
    assert report["assessment"]["verdict"] == "PASS"
    wrong = replace(cert, estimator_version="wrong")
    unresolved = analyze_p3_series(inputs, claim_spec=spec, activation_uncertainty=uncertainty,
        qualification_registry={cert.content_hash: wrong}, checks=checks)
    assert unresolved["calibration_applicability"]["status"] != "APPLICABLE"
    assert unresolved["assessment"]["verdict"] == "INDETERMINATE"


def test_nondiffusive_input_cannot_be_aggregated():
    bad = series()[0]
    bad["p3_result"]["transport_state"] = "NONDIFFUSIVE"
    with pytest.raises(ValueError, match="NONDIFFUSIVE"):
        analyze_p3_series([bad])
