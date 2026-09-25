"""P3 quantitative transport calculation-core contract tests.

Contract-only tests.
No MD execution, no P2/P2.5 rerun, no schema.py modification.

The implementation under test is expected to provide pure numerical helpers
for:
- linear MSD-vs-time fitting -> self diffusion
- SI unit conversion
- Nernst-Einstein conductivity estimate
- Arrhenius temperature dependence
- Arrhenius extrapolation

Scientific definitions:
    D = slope(MSD) / 6          [3D Einstein relation]
    1 A^2 / ps = 1e-8 m^2 / s
    sigma_NE = n q^2 D / (k_B T)

Arrhenius:
    ln(D) = ln(D0) - Ea / (k_B T)

No helper may silently manufacture uncertainty or relabel an estimate
as experimental/true conductivity.
"""

import math

import numpy as np
import pytest

import rudeus.mlip.p3_transport as p3_transport


def test_a_linear_msd_fit_returns_self_diffusion_in_A2_per_ps():
    """D must come from the physical MSD slope, not log-log exponent."""
    time_ps = np.arange(1.0, 7.0)
    # MSD = 6 D t + intercept, D = 0.002 A^2/ps
    msd_A2 = 0.012 * time_ps + 0.25

    result = p3_transport.fit_self_diffusion(
        time_ps=time_ps,
        msd_A2=msd_A2,
    )

    assert result["fit_method"] == "linear_msd_vs_time"
    assert result["D_A2_per_ps"] == pytest.approx(0.002)
    assert result["D_m2_per_s"] == pytest.approx(2.0e-11)


def test_b_angstrom_ps_to_si_conversion_is_exact():
    assert p3_transport.diffusion_A2_per_ps_to_m2_per_s(1.0) == pytest.approx(
        1.0e-8
    )
    assert p3_transport.diffusion_A2_per_ps_to_m2_per_s(0.0012) == pytest.approx(
        1.2e-11
    )


def test_c_self_diffusion_requires_physical_time_units():
    time_ps = np.arange(1.0, 7.0)
    msd_A2 = 0.012 * time_ps

    with pytest.raises((ValueError, TypeError)):
        p3_transport.fit_self_diffusion(
            time_ps=time_ps,
            msd_A2=msd_A2,
            time_unit="frame",
        )


def test_d_nernst_einstein_is_explicitly_an_estimate():
    result = p3_transport.nernst_einstein_conductivity(
        D_m2_per_s=2.0e-11,
        carrier_density_per_m3=1.0e28,
        temperature_K=550.0,
        charge_number=1,
    )

    assert result["method"] == "nernst_einstein"
    assert result["claim_status"] == "estimate"
    assert result["value_S_per_m"] > 0.0
    assert result["temperature_K"] == pytest.approx(550.0)
    assert result["D_m2_per_s"] == pytest.approx(2.0e-11)
    assert result["carrier_density_per_m3"] == pytest.approx(1.0e28)


def test_e_nernst_einstein_uses_si_physical_constants():
    result = p3_transport.nernst_einstein_conductivity(
        D_m2_per_s=1.0e-10,
        carrier_density_per_m3=1.0e28,
        temperature_K=300.0,
        charge_number=1,
    )

    expected = (
        1.0e28
        * (1.602176634e-19 ** 2)
        * 1.0e-10
        / (1.380649e-23 * 300.0)
    )

    assert result["value_S_per_m"] == pytest.approx(expected, rel=1e-12)


def test_f_nernst_einstein_rejects_nonphysical_temperature():
    with pytest.raises((ValueError, TypeError)):
        p3_transport.nernst_einstein_conductivity(
            D_m2_per_s=1.0e-10,
            carrier_density_per_m3=1.0e28,
            temperature_K=0.0,
            charge_number=1,
        )


def test_g_arrhenius_fit_recovers_activation_energy():
    temperatures_K = np.array([500.0, 600.0, 700.0, 800.0])
    Ea_eV = 0.25
    D0 = 1.0e-7
    k_B_eV_per_K = 8.617333262145e-5

    D_values = D0 * np.exp(
        -Ea_eV / (k_B_eV_per_K * temperatures_K)
    )

    result = p3_transport.fit_arrhenius(
        temperatures_K=temperatures_K,
        values=D_values,
        value_name="D_m2_per_s",
    )

    assert result["model"] == "arrhenius"
    assert result["available"] is True
    assert result["activation_energy_eV"] == pytest.approx(
        Ea_eV, rel=1e-6
    )
    assert result["prefactor"] == pytest.approx(D0, rel=1e-6)


def test_h_arrhenius_requires_positive_transport_values():
    with pytest.raises((ValueError, TypeError)):
        p3_transport.fit_arrhenius(
            temperatures_K=np.array([500.0, 600.0, 700.0]),
            values=np.array([1.0e-10, 0.0, 2.0e-10]),
            value_name="D_m2_per_s",
        )


def test_i_arrhenius_fit_preserves_per_temperature_uncertainty():
    temperatures_K = np.array([500.0, 600.0, 700.0, 800.0])
    values = np.array([1e-12, 3e-12, 8e-12, 2e-11])
    ci = [
        [0.8e-12, 1.2e-12],
        [2.4e-12, 3.6e-12],
        [6.4e-12, 9.6e-12],
        [1.6e-11, 2.4e-11],
    ]

    result = p3_transport.fit_arrhenius(
        temperatures_K=temperatures_K,
        values=values,
        value_name="D_m2_per_s",
        uncertainty_ci=ci,
    )

    assert result["fit_diagnostics"]["uncertainty_method"] is not None
    assert result["fit_diagnostics"]["n_points"] == 4


def test_j_arrhenius_extrapolation_is_explicitly_extrapolated():
    fit = {
        "model": "arrhenius",
        "available": True,
        "activation_energy_eV": 0.25,
        "prefactor": 1.0e-7,
    }

    result = p3_transport.extrapolate_arrhenius(
        fit=fit,
        target_temperature_K=300.0,
        source_temperature_range_K=[500.0, 800.0],
        quantity="D_m2_per_s",
    )

    assert result["available"] is True
    assert result["status"] == "EXTRAPOLATED"
    assert result["target_temperature_K"] == pytest.approx(300.0)
    assert result["source_temperature_range_K"] == [500.0, 800.0]
    assert result["extrapolation_distance_K"] == pytest.approx(200.0)


def test_k_extrapolation_inside_supported_range_is_not_labeled_extrapolated():
    fit = {
        "model": "arrhenius",
        "available": True,
        "activation_energy_eV": 0.25,
        "prefactor": 1.0e-7,
    }

    result = p3_transport.extrapolate_arrhenius(
        fit=fit,
        target_temperature_K=650.0,
        source_temperature_range_K=[500.0, 800.0],
        quantity="D_m2_per_s",
    )

    assert result["status"] != "EXTRAPOLATED"


def test_l_invalid_arrhenius_input_does_not_fabricate_extrapolation():
    result = p3_transport.extrapolate_arrhenius(
        fit={
            "model": "arrhenius",
            "available": False,
        },
        target_temperature_K=300.0,
        source_temperature_range_K=[500.0, 800.0],
        quantity="D_m2_per_s",
    )

    assert result["available"] is False
    assert "value" not in result

def test_block_bootstrap_self_diffusion_returns_ci():
    from rudeus.mlip.p3_transport import block_bootstrap_self_diffusion

    n_frames = 100
    n_ions = 2

    rng = np.random.default_rng(1234)
    increments = rng.normal(
        scale=0.5,
        size=(n_frames - 1, n_ions, 3),
    )
    positions = np.zeros((n_frames, n_ions, 3), dtype=float)
    positions[1:] = np.cumsum(increments, axis=0)

    result = block_bootstrap_self_diffusion(
        positions,
        fit_window_fraction=(0.3, 0.9),
        block_origins=10,
        n_bootstrap=100,
        ci_level=0.68,
        seed=2505,
        min_blocks=4,
    )

    assert result["status"] == "sufficient"
    assert result["method"] == "block_bootstrap_origins"
    assert result["ci_level"] == 0.68
    assert len(result["D_A2_per_ps_ci"]) == 2
    assert result["D_A2_per_ps_ci"][0] <= result["D_A2_per_ps_ci"][1]
    assert result["D_A2_per_ps_ci"][0] >= 0.0
