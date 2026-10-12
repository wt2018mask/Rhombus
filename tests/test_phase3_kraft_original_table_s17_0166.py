"""0166 first-party Kraft argyrodite Table S17 numeric Rbulk(T) falsification."""
import hashlib
import math
import sys
from types import SimpleNamespace
import numpy as np
import pytest
from scripts.science import obelix_kraft_original_tabular_impedance_0166 as z


def synthetic_page():
    xs=" ".join(f"{v:.2f}" for v in z.EXPECTED_COMPOSITIONS)
    thickness=" ".join(f"{x:.3f}" for x in (0.14,0.144,0.25,0.235,0.13,0.22,0.20,0.215,0.13,0.23))
    lines=["Table S 17: Values obtained from fitting of impedance spectra. "
           "Temperature dependant resistances R and quasi capacitances Q.",
           "Li6+xP1-xGexS5I "+xs,"thickness d /cm "+thickness,
           "Fitting results","Temperature / K Rbulk / Ohm"]
    for t in z.EXPECTED_T:
        rows=[]
        for n in range(10):
            e=0.14+n*0.008
            vals=math.exp(e/z.K_B_EV_PER_K*(1/t-1/298))*(1600/(n+1))
            rows.append(f"{vals:.6f}")
        lines.append(f"{t} "+" ".join(rows))
    lines+=["Quasi-Capacitances","Q(298 K) / pF cm2 10 20"]
    return "\n".join(lines)


def test_120_actual_type_temperature_cells_yield_positive_thermally_activated_R():
    tab=z.extract_table_s17(synthetic_page())
    assert tab["temperature_K"]==list(z.EXPECTED_T)
    assert tab["nominal_x"]==list(z.EXPECTED_COMPOSITIONS)
    report=z.physical_bulk_resistance_diagnostic(tab)
    assert report["raw_source_fit_resistance_values_read_NOT_REPUBLISHED"]==120
    assert report["duplicate_298K_Rbulk_records"]==10
    assert report["unique_temperatures_K"]==11
    assert report["Arrhenius_bulk_R_only_activation_Ea_eV_DIAGNOSTIC"]["median_logR_fit_R2"]>0.9999
    assert report["individual_true_sample_labels_qualified"]==0
    assert report["R_bulk_ohm_NOT_S_per_cm"] is True


def test_two_298K_lines_are_not_autonamed_independent_pellets():
    source=z.extract_table_s17(synthetic_page())
    result=z.physical_bulk_resistance_diagnostic(source)
    assert result["repeat_298K_rows_not_proven_independent_pellets"] is True
    assert result["electrode_area_for_each_original_table_column_verified"] is False
    assert result["correlated_phase_and_crystal_to_measured_pellet_verified"] is False


@pytest.mark.parametrize("bad",[
    lambda s:s.replace("Quasi-Capacitances","Other material"), 
    lambda s:s.replace("Table S 17","Other table"),
    lambda s:s.replace("298 ","299 ",1),
    lambda s:s.replace("0.60 0.70","0.66 0.70"),
    lambda s:s.replace("0.140 0.144","-0.140 0.144"),
])
def test_cannot_silently_accept_drift_or_missing_semantics(bad):
    with pytest.raises(ValueError):
        z.extract_table_s17(bad(synthetic_page()))


def test_bounded_original_pdf_identity_page_and_no_implicit_table_promotion(monkeypatch):
    class Page:
        def __init__(self,txt):self.txt=txt
        def extract_text(self):return self.txt
    class PDF:
        def __init__(self,_):
            self.pages=[Page("unrelated crystallography") for _ in range(23)]
            self.pages[19]=Page(synthetic_page())
    monkeypatch.setitem(sys.modules,"pypdf",SimpleNamespace(PdfReader=PDF))
    blob=b"%PDF-source-original-fixture-only"
    assert z.read_original_page(blob,strict_sha=hashlib.sha256(blob).hexdigest()).startswith("Table S 17")
    with pytest.raises(ValueError,match="SHA256"):
        z.read_original_page(blob,strict_sha="0"*64)


def test_duplicate_RT_rows_do_not_imply_sigma_without_geometry_even_if_R_declines():
    table=z.extract_table_s17(synthetic_page())
    result=z.physical_bulk_resistance_diagnostic(table)
    assert result["Arrhenius_bulk_R_only_activation_Ea_eV_DIAGNOSTIC"]["median"]>0
    assert result["inverse_R_or_bulk_R_direct_solid_ionic_conductivity_certified"] is False
