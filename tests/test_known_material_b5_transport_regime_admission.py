import json
from pathlib import Path

from rhombus.transport import assess_transport_regime_admission


def test_transport_regime_admission_is_fail_closed_and_transport_neutral():
    ok = assess_transport_regime_admission(
        finite_temperature_stability_verdict="PASS",
        authoritative_stability_verdict=True,
        trajectory_sha256="a" * 64,
        numerical_abort=None,
    )
    assert ok["admission_status"] == "ELIGIBLE"
    assert ok["capability"] == "classify_transport_regime"
    assert ok["scientific_claim"] is None
    assert ok["transport_state"] is None

    bad = assess_transport_regime_admission(
        finite_temperature_stability_verdict="FAIL",
        authoritative_stability_verdict=True,
        trajectory_sha256="a" * 64,
        numerical_abort=None,
    )
    assert bad["admission_status"] == "NOT_ELIGIBLE"
    assert "finite_temperature_stability_not_pass" in bad["reasons"]


def test_known_material_transport_regime_authorization_is_exact():
    row = json.loads(Path(
        "data/benchmarks/known_material/b5_transport_regime_authorization_v1.json"
    ).read_text(encoding="utf-8"))

    assert row["capability"] == "classify_transport_regime"
    assert row["admission_contract_version"] == "transport-regime-admission-v1"

    authorized = row["authorized"]
    assert len(authorized) == 1
    gamma = authorized[0]
    assert gamma["batch_id"] == "df4431260652d2ea"
    assert gamma["finite_temperature_stability_verdict"] == "PASS"
    assert gamma["authoritative_stability_verdict"] is True
    assert gamma["numerical_abort"] is None
    assert gamma["trajectory_sha256"] == (
        "b68c805b8f69bb2346ad3f5337cf5df64d9dd0c882af74bed397dcc00af34f02"
    )
    assert gamma["admission_status"] == "ELIGIBLE"

    excluded = {
        (x["material_key"], x["component_label"]): x["reason"]
        for x in row["excluded"]
    }
    assert excluded[("libh4-phase-transition-pair", "hexagonal")] == (
        "finite_temperature_stability_FAIL"
    )
    assert excluded[("libh4-phase-transition-pair", "orthorhombic")] == (
        "finite_temperature_stability_FAIL"
    )
    assert excluded[("llzo-cubic-al-stabilized", "ensemble")] == (
        "upstream_static_validation_INDETERMINATE"
    )

    interp = row["interpretation"]
    assert interp["transport_claim_authorized"] is False
    assert interp["diffusion_claim_authorized"] is False
    assert interp["conductivity_claim_authorized"] is False
    assert interp["qualification_claim_authorized"] is False


def test_gamma_authorization_matches_generic_admission_contract():
    row = json.loads(Path(
        "data/benchmarks/known_material/b5_transport_regime_authorization_v1.json"
    ).read_text(encoding="utf-8"))
    gamma = row["authorized"][0]
    decision = assess_transport_regime_admission(
        finite_temperature_stability_verdict=gamma[
            "finite_temperature_stability_verdict"
        ],
        authoritative_stability_verdict=gamma[
            "authoritative_stability_verdict"
        ],
        trajectory_sha256=gamma["trajectory_sha256"],
        numerical_abort=gamma["numerical_abort"],
    )
    assert decision["admission_status"] == gamma["admission_status"]
