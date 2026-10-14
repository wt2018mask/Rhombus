"""Adversarial original-manuscript, publication isolation and false GO tests."""
import math
import pytest
from scripts.science import original_cross_paper_transfer_0169 as m
from scripts.science import original_sulfide_measurement_table_0166 as y


def figure_text():
    nums = ("8.06·10-5 S/cm for 250 oC, 2.28·10-4 S/cm for 300 oC, "
            "7.98·10-4 S/cm for 350 oC, 1.15·10-3 S/cm for 400 oC, "
            "1.38·10-3 S/cm for 450 oC, 1.65·10-3 S/cm for 500 oC, "
            "2.58·10-3 S/cm for 550 oC, and 1.41·10-3 S/cm for 600 oC")
    return ("Figure 4. The room temperature ionic conductivities of the samples "
            "prepared by annealing at various temperatures are " + nums +
            ", respectively. The result differs from decomposition above 550 C.")


def test_parser_requires_original_article_exact_all_eight_numbers():
    t, s = m.parse_yu_figure4_text("DOI: 10.1039/C9TA02126D Li6PS5Br", figure_text())
    assert t == list(m.YU_T)
    assert s == list(m.YU_SIGMA_S_CM)
    assert m.parse_yu_figure4_text(
        "DOI 10.1039/C9TA02126D Li6PS5Br",
        figure_text().replace("·", "\uf0d7")
    ) == (t, s)


@pytest.mark.parametrize("cover,page", [
    ("10.1039/C9TA02126X Li6PS5Br", figure_text()),
    ("10.1039/C9TA02126D Li6PS5Br", figure_text().replace("2.58·10-3", "2.59·10-3")),
    ("10.1039/C9TA02126D Li6PS5Br", figure_text().replace("600 oC", "650 oC")),
    ("10.1039/C9TA02126D Li6PS5Br", figure_text().replace("respectively", "approximately")),
    ("10.1039/C9TA02126D Li6PS5Br", figure_text().replace("Figure 4.", "Table 7.")),
])
def test_fail_closed_on_source_or_measurement_drift(cover,page):
    with pytest.raises(ValueError):
        m.parse_yu_figure4_text(cover,page)


def test_cross_paper_alternating_full_paper_holdout_is_not_rowwise_cv():
    yt = list(y.EXPECTED_PROCESS_T_C)
    ys = [v/1000 for v in y.EXPECTED_SIGMA_MSCM]
    ut, us = list(m.YU_T), list(m.YU_SIGMA_S_CM)
    forward = m.fixed_paper_model(yt,ys,ut,us)
    reverse = m.fixed_paper_model(ut,us,yt,ys)
    assert forward["train_conditions"] == 6
    assert forward["heldout_paper_conditions"] == 8
    assert forward["median_train_paper_constant_log10MAE"] == 0.37480574
    assert forward["process_temperature_OLS_train_paper_log10MAE"] == 0.20572061
    assert reverse["train_conditions"] == 8
    assert reverse["heldout_paper_conditions"] == 6
    assert reverse["median_train_paper_constant_log10MAE"] == 0.37793339
    assert reverse["process_temperature_OLS_train_paper_log10MAE"] == 0.22463230
    assert forward["no_target_paper_labels_fitted"] and reverse["no_pooled_rowwise_random_split"]
    # A withheld publication's changed labels cannot alter its predicted OLS fit,
    # but SHOULD change its error. This is a negative leakage control.
    altered = [v * 10 for v in us]
    altered_score = m.fixed_paper_model(yt, ys, ut, altered)
    assert math.isclose(
        altered_score["train_paper_temperature_slope_log10_Scm_per_C"],
        forward["train_paper_temperature_slope_log10_Scm_per_C"]
    )
    assert altered_score["process_temperature_OLS_train_paper_log10MAE"] != forward[
        "process_temperature_OLS_train_paper_log10MAE"
    ]


@pytest.mark.parametrize("broken", [
    ([250,250,350], [1e-3,2e-3,3e-3]),
    ([250,300,350], [1e-3,0,3e-3]),
    ([250,300,350], [1e-3,float("nan"),3e-3]),
])
def test_bad_train_rows_rejected(broken):
    with pytest.raises(ValueError):
        m.fixed_paper_model(broken[0], broken[1], [300,400,500], [1e-3,2e-3,3e-3])
