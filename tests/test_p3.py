"""P3 quantitative-transport contract tests.

Contract-only tests. These tests intentionally define the P3 result shape
before the P3 implementation exists.

Scientific rules:
  - P2/P2.5 state and evidence are immutable.
  - P3 quantitative transport is additive.
  - self diffusion is not conductivity.
  - Nernst-Einstein conductivity is explicitly an estimate.
  - collective transport may be unavailable when evidence is insufficient.
  - Arrhenius fitting is descriptive/model-based, never itself a verdict.
  - extrapolated values are explicitly marked as extrapolated.
  - multi-temperature provenance is content-addressed per trajectory.
"""

import copy

import pytest

from rudeus.schema import (
    CandidateMaterial,
    DynamicState,
    EvidenceEvent,
    ExistenceState,
    TransportState,
)


# ---------------------------------------------------------------------------
# Contract fixtures
# ---------------------------------------------------------------------------

def _p2_p25_baseline():
    """Minimal representative P2/P2.5 result fields that P3 must preserve."""
    return {
        "candidate_material_id": "mat-test-001",
        "batch_id": "batch-test-001",
        "parent_id": "parent-test-001",
        "p2_dynamic_state": "PASS",
        "p2_verdict": "PASS",
        "temperature_K": 550.0,
        "temperature_source": "p2_protocol",
        "target_species": "Li",
        "transport_state": "DIFFUSIVE",
        "p25_verdict": "DIFFUSIVE",
        "transport_claim_status": "provisional",
        "provenance": {
            "p2_result_path": "data/batches/p2/batch-test-001.json",
            "trajectory_artifact_path": "data/batches/p2_traj/batch-test-001.npz",
            "trajectory_artifact_sha256": "sha-p2-traj",
            "artifact_format_version": "p2-traj-v1",
            "p2_config_hash": "p2-config-hash",
            "p2_protocol_version": "p2-adaptive-v1-provisional",
            "p2_seed": 123,
            "p25_config_hash": "p25-config-hash",
            "p25_version": "p25-f3-v1-provisional",
        },
        "transport": {
            "n_mobile_ions": 4,
            "n_frames": 100,
            "log_slope": 1.0,
            "tail_alpha2": 0.1,
        },
        "sufficiency": {
            "n_mobile_ions": 4,
            "n_production_frames": 100,
            "n_valid_lags": 40,
            "n_origin_blocks": 20,
        },
        "diagnostics": {
            "unwrapped": True,
            "unwrap_method": "p2.unwrap_trajectory",
        },
        "evidence_events": [
            {
                "level": "P2.5",
                "method": "f3_mobile_ion_msd_alpha2_block_bootstrap",
                "artifact_hash": "sha-p2-traj",
            }
        ],
    }


def _p3_namespace():
    """Representative P3 quantitative namespace from the frozen contract."""
    return {
        "self_diffusion": {
            "species": "Li",
            "D_A2_per_ps": 0.0012,
            "D_m2_per_s": 1.2e-11,
            "fit_method": "einstein_msd_linear_fit",
            "fit_window": [0.3, 0.9],
            "uncertainty": {
                "method": "block_bootstrap",
                "ci_level": 0.68,
                "D_A2_per_ps_ci": [0.0008, 0.0017],
            },
            "n_mobile_ions": 4,
            "n_frames": 100,
            "n_valid_lags": 40,
        },
        "conductivity_estimate": {
            "method": "nernst_einstein",
            "value_S_per_m": 0.12,
            "temperature_K": 550.0,
            "carrier_density_per_m3": 1.0e28,
            "D_m2_per_s": 1.2e-11,
            "uncertainty": {
                "method": "propagated_block_bootstrap",
                "ci_level": 0.68,
                "value_S_per_m_ci": [0.08, 0.17],
            },
            "claim_status": "estimate",
        },
        "collective_transport": {
            "available": False,
            "status": "INSUFFICIENT",
        },
        "temperature_dependence": {
            "temperatures_K": [550.0, 650.0, 750.0],
            "diffusion_points": [
                {
                    "temperature_K": 550.0,
                    "D_m2_per_s": 1.2e-11,
                    "uncertainty": {
                        "method": "block_bootstrap",
                        "ci_level": 0.68,
                        "D_m2_per_s_ci": [0.8e-11, 1.7e-11],
                    },
                },
                {
                    "temperature_K": 650.0,
                    "D_m2_per_s": 4.0e-10,
                    "uncertainty": {
                        "method": "block_bootstrap",
                        "ci_level": 0.68,
                        "D_m2_per_s_ci": [3.0e-10, 5.2e-10],
                    },
                },
                {
                    "temperature_K": 750.0,
                    "D_m2_per_s": 1.1e-9,
                    "uncertainty": {
                        "method": "block_bootstrap",
                        "ci_level": 0.68,
                        "D_m2_per_s_ci": [0.8e-9, 1.5e-9],
                    },
                },
            ],
            "conductivity_points": [],
            "fit": {
                "model": "arrhenius",
                "available": True,
                "activation_energy_eV": 0.42,
                "activation_energy_ci_eV": [0.34, 0.51],
                "prefactor": 1.0e-5,
                "fit_diagnostics": {
                    "status": "SUPPORTED_BY_DATA",
                },
            },
        },
        "extrapolation": {
            "target_temperature_K": 300.0,
            "available": True,
            "quantity": "D_m2_per_s",
            "value": 1.0e-12,
            "uncertainty": {
                "ci_level": 0.68,
                "value_ci": [0.4e-12, 2.0e-12],
            },
            "source_temperature_range_K": [550.0, 750.0],
            "extrapolation_distance_K": 250.0,
            "model": "arrhenius",
            "status": "EXTRAPOLATED",
        },
    }


def _p3_result():
    result = _p2_p25_baseline()
    result["quantitative_transport"] = _p3_namespace()
    result["provenance"] = {
        **result["provenance"],
        "p25_result_paths": [
            "data/batches/p25/batch-550.json",
            "data/batches/p25/batch-650.json",
            "data/batches/p25/batch-750.json",
        ],
        "trajectory_artifacts": [
            {
                "temperature_K": 550.0,
                "path": "data/batches/p2_traj/batch-550.npz",
                "sha256": "sha-550",
            },
            {
                "temperature_K": 650.0,
                "path": "data/batches/p2_traj/batch-650.npz",
                "sha256": "sha-650",
            },
            {
                "temperature_K": 750.0,
                "path": "data/batches/p2_traj/batch-750.npz",
                "sha256": "sha-750",
            },
        ],
        "p2_config_hashes": ["p2-550", "p2-650", "p2-750"],
        "p25_config_hashes": ["p25-550", "p25-650", "p25-750"],
        "p3_config_hash": "p3-config-hash",
        "p3_version": "p3-quantitative-transport-v1-provisional",
    }
    return result


# ---------------------------------------------------------------------------
# A. P2/P2.5 immutability
# ---------------------------------------------------------------------------

def test_a_p2_p25_fields_are_preserved():
    baseline = _p2_p25_baseline()
    result = _p3_result()

    protected = [
        "candidate_material_id",
        "batch_id",
        "parent_id",
        "p2_dynamic_state",
        "p2_verdict",
        "temperature_K",
        "temperature_source",
        "target_species",
        "transport_state",
        "p25_verdict",
        "transport_claim_status",
        "transport",
        "sufficiency",
        "diagnostics",
    ]

    for key in protected:
        assert result[key] == baseline[key], f"protected field changed: {key}"


def test_a_p3_does_not_upgrade_transport_state():
    result = _p3_result()

    assert result["transport_state"] == TransportState.DIFFUSIVE.value
    assert result["p25_verdict"] == TransportState.DIFFUSIVE.value
    assert result["transport_state"] != "P3_PASS"


# ---------------------------------------------------------------------------
# B. exact P3 namespace
# ---------------------------------------------------------------------------

def test_b_quantitative_transport_has_exact_required_sections():
    qt = _p3_result()["quantitative_transport"]

    assert set(qt) == {
        "self_diffusion",
        "conductivity_estimate",
        "collective_transport",
        "temperature_dependence",
        "extrapolation",
    }


# ---------------------------------------------------------------------------
# C. self diffusion
# ---------------------------------------------------------------------------

def test_c_self_diffusion_has_explicit_units_and_uncertainty():
    sd = _p3_result()["quantitative_transport"]["self_diffusion"]

    assert sd["species"] == "Li"
    assert "D_A2_per_ps" in sd
    assert "D_m2_per_s" in sd
    assert sd["D_m2_per_s"] == pytest.approx(
        sd["D_A2_per_ps"] * 1.0e-8
    )

    assert sd["uncertainty"]["ci_level"] == 0.68
    assert len(sd["uncertainty"]["D_A2_per_ps_ci"]) == 2
    assert sd["uncertainty"]["D_A2_per_ps_ci"][0] <= sd["D_A2_per_ps"]
    assert sd["D_A2_per_ps"] <= sd["uncertainty"]["D_A2_per_ps_ci"][1]


def test_c_self_diffusion_is_not_named_conductivity():
    qt = _p3_result()["quantitative_transport"]

    assert "conductivity" not in qt["self_diffusion"]
    assert "sigma_S_per_m" not in qt["self_diffusion"]


# ---------------------------------------------------------------------------
# D. Nernst-Einstein conductivity estimate
# ---------------------------------------------------------------------------

def test_d_nernst_einstein_is_explicitly_an_estimate():
    ce = _p3_result()["quantitative_transport"]["conductivity_estimate"]

    assert ce["method"] == "nernst_einstein"
    assert ce["claim_status"] == "estimate"
    assert ce["value_S_per_m"] >= 0.0
    assert ce["D_m2_per_s"] >= 0.0
    assert ce["temperature_K"] > 0.0

    assert "experimental_conductivity" not in ce
    assert "measured_conductivity" not in ce


def test_d_conductivity_estimate_has_uncertainty():
    ce = _p3_result()["quantitative_transport"]["conductivity_estimate"]

    uncertainty = ce["uncertainty"]
    assert uncertainty["ci_level"] == 0.68
    lo, hi = uncertainty["value_S_per_m_ci"]
    assert lo <= ce["value_S_per_m"] <= hi


# ---------------------------------------------------------------------------
# E. collective transport
# ---------------------------------------------------------------------------

def test_e_collective_transport_can_be_insufficient_without_fabrication():
    ct = _p3_result()["quantitative_transport"]["collective_transport"]

    assert ct["available"] is False
    assert ct["status"] == "INSUFFICIENT"
    assert "sigma_S_per_m" not in ct
    assert "uncertainty" not in ct


def test_e_collective_transport_when_available_requires_definition():
    ct = {
        "available": True,
        "status": "SUFFICIENT",
        "method": "collective_charge_displacement_einstein",
        "sigma_S_per_m": 0.08,
        "uncertainty": {
            "method": "block_bootstrap",
            "ci_level": 0.68,
            "sigma_S_per_m_ci": [0.05, 0.12],
        },
        "charge_displacement_definition": (
            "sum_i q_i [r_i(t)-r_i(0)] for mobile Li ions"
        ),
        "n_frames": 100,
        "n_mobile_ions": 4,
    }

    assert ct["available"] is True
    assert ct["charge_displacement_definition"]
    lo, hi = ct["uncertainty"]["sigma_S_per_m_ci"]
    assert lo <= ct["sigma_S_per_m"] <= hi


# ---------------------------------------------------------------------------
# F. temperature dependence / Arrhenius
# ---------------------------------------------------------------------------

def test_f_temperature_dependence_keeps_per_temperature_uncertainty():
    td = _p3_result()["quantitative_transport"]["temperature_dependence"]

    temps = td["temperatures_K"]
    points = td["diffusion_points"]

    assert len(temps) == len(points)
    assert all(point["temperature_K"] in temps for point in points)

    for point in points:
        assert point["D_m2_per_s"] >= 0.0
        assert point["uncertainty"]["ci_level"] == 0.68
        lo, hi = point["uncertainty"]["D_m2_per_s_ci"]
        assert lo <= point["D_m2_per_s"] <= hi


def test_f_arrhenius_is_model_analysis_not_transport_verdict():
    fit = _p3_result()["quantitative_transport"]["temperature_dependence"]["fit"]

    assert fit["model"] == "arrhenius"
    assert fit["available"] is True
    assert "activation_energy_eV" in fit
    assert "fit_diagnostics" in fit

    # No P3-specific PASS/FAIL verdict is permitted in the Arrhenius block.
    assert "verdict" not in fit
    assert "transport_state" not in fit


# ---------------------------------------------------------------------------
# G. extrapolation
# ---------------------------------------------------------------------------

def test_g_extrapolation_is_explicitly_marked():
    ex = _p3_result()["quantitative_transport"]["extrapolation"]

    assert ex["available"] is True
    assert ex["status"] == "EXTRAPOLATED"
    assert ex["target_temperature_K"] == 300.0
    assert ex["model"] == "arrhenius"
    assert ex["source_temperature_range_K"] == [550.0, 750.0]
    assert ex["extrapolation_distance_K"] == 250.0


def test_g_extrapolation_is_not_presented_as_measured():
    ex = _p3_result()["quantitative_transport"]["extrapolation"]

    assert ex["status"] != "MEASURED"
    assert "measured" not in ex
    assert "experimental" not in ex


# ---------------------------------------------------------------------------
# H. provenance
# ---------------------------------------------------------------------------

def test_h_multi_temperature_provenance_is_per_temperature():
    provenance = _p3_result()["provenance"]

    artifacts = provenance["trajectory_artifacts"]

    assert len(artifacts) == 3
    assert [a["temperature_K"] for a in artifacts] == [550.0, 650.0, 750.0]
    assert all(a["path"] for a in artifacts)
    assert all(a["sha256"] for a in artifacts)
    assert len({a["sha256"] for a in artifacts}) == 3


def test_h_p3_provenance_has_own_version_and_config_hash():
    provenance = _p3_result()["provenance"]

    assert provenance["p3_config_hash"]
    assert provenance["p3_version"].startswith("p3-")


# ---------------------------------------------------------------------------
# I. EvidenceEvent compatibility
# ---------------------------------------------------------------------------

def test_i_p3_evidence_event_is_append_only_and_schema_compatible():
    candidate = CandidateMaterial(
        material_id="mat-test-001",
        formula="Li-test",
        existence_state=ExistenceState.PLAUSIBLE,
        dynamic_state=DynamicState.PASS,
        transport_state=TransportState.DIFFUSIVE,
    )

    p25 = EvidenceEvent(
        level="P2.5",
        method="f3_mobile_ion_msd_alpha2_block_bootstrap",
        conditions={"transport_claim_status": "provisional"},
        uncertainty=None,
        source="p25-test",
        artifact_hash="sha-p25",
        model_or_data_version="p25-f3-v1-provisional",
    )
    p3 = EvidenceEvent(
        level="P3",
        method="quantitative_transport_v1",
        conditions={
            "D_m2_per_s": 1.2e-11,
            "D_ci": [0.8e-10, 1.7e-10],
            "sigma_NE_claim_status": "estimate",
        },
        uncertainty=None,
        source="p3-test",
        artifact_hash="sha-p3",
        model_or_data_version="p3-quantitative-transport-v1-provisional",
    )

    candidate.add_evidence(p25)
    candidate.add_evidence(p3)

    assert len(candidate.evidence_log) == 2
    assert candidate.evidence_log[0].level == "P2.5"
    assert candidate.evidence_log[1].level == "P3"
    assert candidate.evidence_log[0].artifact_hash == "sha-p25"
    assert candidate.evidence_log[1].artifact_hash == "sha-p3"


# ---------------------------------------------------------------------------
# J. contract-level semantic guards
# ---------------------------------------------------------------------------

def test_j_p3_namespace_is_additive_to_p2_p25_result():
    result = _p3_result()
    baseline = _p2_p25_baseline()

    protected = [
        "candidate_material_id",
        "batch_id",
        "parent_id",
        "p2_dynamic_state",
        "p2_verdict",
        "temperature_K",
        "temperature_source",
        "target_species",
        "transport_state",
        "p25_verdict",
        "transport_claim_status",
        "transport",
        "sufficiency",
        "diagnostics",
        "evidence_events",
    ]

    for key in protected:
        assert result[key] == baseline[key]

    assert set(result) >= set(baseline)
    assert "quantitative_transport" in result
    assert len(result["provenance"]) > len(baseline["provenance"])


def test_j_contract_fixture_does_not_mutate_when_copied():
    original = _p3_result()
    copied = copy.deepcopy(original)

    copied["quantitative_transport"]["self_diffusion"]["D_m2_per_s"] = 999.0

    assert (
        original["quantitative_transport"]["self_diffusion"]["D_m2_per_s"]
        != 999.0
    )
