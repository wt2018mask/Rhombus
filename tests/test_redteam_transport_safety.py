"""RT-P2-01/02: invalid inputs must never produce scientific support."""
import numpy as np
import pytest

from rudeus.mlip.p3_transport import fit_arrhenius, nernst_einstein_conductivity


@pytest.mark.parametrize("temperatures", [
    [300, 300], [300, 400, 300], [300, 300 + 1e-9],
    [300, 300.0004], [1e308, 1e308], [1e-320, 2e-320],
    [300, np.nan], [300, np.inf], [0, 400], [300], [],
])
def test_arrhenius_rejects_degenerate_design(temperatures):
    with pytest.raises(ValueError):
        fit_arrhenius(temperatures_K=temperatures,
                      values=[1e-10] * len(temperatures), value_name="D")


@pytest.mark.parametrize("values", [[1, np.nan], [1, np.inf], [0, 1], [-1, 1], [1]])
def test_arrhenius_rejects_invalid_values(values):
    with pytest.raises(ValueError):
        fit_arrhenius(temperatures_K=[300, 600], values=values, value_name="D")


def test_arrhenius_rejects_nonfinite_prefactor():
    with pytest.raises(ValueError):
        fit_arrhenius(temperatures_K=[300, 600], values=[1e-300, 1e300], value_name="D")


@pytest.mark.parametrize("charge", [1.9, 1.0, True, False, "1", 0, np.nan, np.inf, None, 1+0j])
def test_charge_is_strict_nonzero_integer(charge):
    with pytest.raises(ValueError):
        nernst_einstein_conductivity(D_m2_per_s=1e-10, carrier_density_per_m3=1e28,
                                    temperature_K=300, charge_number=charge)


@pytest.mark.parametrize("charge", [-3, -1, 1, 2, np.int64(2)])
def test_integer_charge_preserves_squared_formula(charge):
    result = nernst_einstein_conductivity(D_m2_per_s=1e-10,
        carrier_density_per_m3=1e28, temperature_K=300, charge_number=charge)
    expected = 1e28 * (int(charge) * 1.602176634e-19)**2 * 1e-10 / (1.380649e-23 * 300)
    assert result["value_S_per_m"] == pytest.approx(expected, rel=1e-12)
    assert result["claim_status"] == "estimate"


def test_valid_arrhenius_order_and_temperature_scale_preserved():
    for temperatures in ([800, 500, 700, 600], [2, 4, 6]):
        t = np.array(temperatures, dtype=float)
        energy = 0.0001 if max(t) < 10 else 0.25
        values = 1e-7 * np.exp(-energy / (8.617333262145e-5 * t))
        result = fit_arrhenius(temperatures_K=t, values=values, value_name="D")
        assert result["activation_energy_eV"] == pytest.approx(energy)
        assert result["prefactor"] == pytest.approx(1e-7, rel=1e-8)
