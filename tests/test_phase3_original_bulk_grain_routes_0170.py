"""0170 source-binding + forbidden bulk/total scientific promotion."""
import math
import pytest
from scripts.science import original_bulk_grain_routes_0170 as m


def fake():
    cover="Final journal publication 10.1039/c7ta05031c Li6PS5Br"
    methods=("Stainless-steel disks were attached on both faces of the "
             "10 mm diameter powder pellets. Annealed at 300 C for 5 hours, "
             "subsequently ball milled at 450 rpm for 4 hours.")
    page=("These result in bulk and grain boundary resistances of (924.8 ± 16.58) "
          "and (3.02 ± 0.64) x 10^6 Ohm for Li6PS5Br, (516.8 ± 32.28) "
          "and (619.9 ± 22.26) Ohm for AN-Li6PS5Br and (381.7 ± 10.81) "
          "and (686.8 ± 35.88) Ohm for AN-BM-Li6PS5Br. "
          "The corresponding room temperature bulk conductivities are "
          "6.20 x 10-4 S cm-1, 1.11 x 10-3 S cm-1 and "
          "1.38 x 10-3 S cm-1 for Li6PS5Br, AN-Li6PS5Br and "
          "AN-BM-Li6PS5Br respectively. The annealing process increases conductivity.")
    return cover,methods,page


def test_original_source_bound_three_bulk_state_values():
    d=m.check_original_paragraph(*fake())
    assert d["exact_author_bulk_and_grain_source_values_verified"]
    assert d["author_measured_room_temperature_but_exact_numeric_T_not_verified"]
    assert d["sample_numbers_pellet_phase_and_thickness_unattested"]


@pytest.mark.parametrize("idx,a,b",[
    (0,"c7ta05031c","c7ta05032c"),
    (1,"10 mm diameter","11 mm diameter"),
    (1,"450 rpm","540 rpm"),
    (2,"924.8","924.9"),
    (2,"3.02","3.01"),
    (2,"10^6","10^5"),
    (2,"1.11 x 10-3","1.11 x 10-2"),
    (2,"room temperature bulk conductivities","room temperature total conductivities"),
])
def test_source_drift_or_wrong_quantity_rejected(idx,a,b):
    args=list(fake());args[idx]=args[idx].replace(a,b)
    with pytest.raises(ValueError):
        m.check_original_paragraph(*args)


def test_authentic_bulk_grain_ratios_and_NO_fake_total_measurements():
    v=m.physical_unit_audit()
    assert v["source_processing_pathways"]==3
    assert v["is_third_numeric_anneal_temp_transfer_paper"] is False
    assert v["nominal_series_proxy_ranking_annealed_above_re_milled"] is True
    assert v["bulk_sigma_ranking_re_milled_above_annealed"] is True
    assert v["resistance_only_endpoint_bands_overlap"] is True
    assert v["proxy_NOT_author_published_sigma_total"] is True
    assert v["actual_author_reported_total_sigma_S_per_cm_certified"] is False
    assert math.isclose(v["initial_milled_grain_to_bulk_resistance_ratio"],3265.570934,abs_tol=2e-6)
    assert math.isclose(v["annealed_nominal_series_transport_proxy_S_per_cm"],0.00050466086,abs_tol=1e-9)
    assert math.isclose(v["re_milled_nominal_series_transport_proxy_S_per_cm"],0.00049297707,abs_tol=1e-9)


@pytest.mark.parametrize("mod",[
    {"bulk":(0.0,516.8,381.7)},
    {"gb":(3.02e6,-1.0,686.8)},
    {"sigma":(6.2e-4,1.11e-3,float("nan"))},
    {"delta_gb":(0.64e6,22.26,686.8)},
    {"bulk":(924.8,516.8)},
])
def test_invalid_or_unqualified_physical_inputs_fail(mod):
    with pytest.raises(ValueError):
        m.physical_unit_audit(**mod)


def test_different_paper_and_training_temperature_dont_invent_three_temps():
    assert m.STATES == (
        "BALL_MILLED","ANNEALED_300C_5H","ANNEALED_RE_MILLED_450RPM_4H"
    )
    assert len(m.STATES)==3
    assert len(m.BULK_SIGMA_SCM)==3
