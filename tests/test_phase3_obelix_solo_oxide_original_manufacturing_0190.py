"""0190 adversarial first-party source, measurement and choice tests."""
import pytest

from scripts.science import obelix_solo_oxide_original_manufacturing_0190 as m


def article(values=None, header="total Ionic conductivity (25 °C)/S cm−1",
            doi=m.DOI, routes=True):
    values = m.AUTHOR_TOTAL if values is None else values
    cells = "".join(
        "<tr><td>" + key + "</td><td>" + f"{v:.2e}" +
        "</td><td>0.50</td></tr>" for key, v in values.items())
    science = ("These high entropy lithium garnets use both mono-step and dual-step "
               "synthesis, described by the authors." if routes else
               "These garnets were synthesized by a laboratory.")
    return (f'<article><front><article-meta><article-id pub-id-type="doi">{doi}</article-id>'
            f'<article-id pub-id-type="pmc">{m.PMC[3:]}</article-id></article-meta></front>'
            f'<body><p>{science}</p></body><floats-group><table-wrap><label>Table 2.</label>'
            f'<caption><p>Measured Ionic Conductivity and Calculated Activation Energy</p></caption>'
            f'<table><tr><th>sample</th><th>{header}</th><th>bulk activation energy</th></tr>'
            f'{cells}</table></table-wrap></floats-group></article>').encode()


def test_exact_original_source_and_manufacturing_descriptor():
    rows, meta = m.read_author_table(article())
    assert len(rows) == 8 and meta["source_conditions"] == 8
    assert {r["manufacturing_route"] for r in rows} == {"DUAL_STEP", "MONO_STEP"}
    for i in range(4):
        assert rows[i]["nominal_formula"] == rows[i + 4]["nominal_formula"]
    assert rows[1]["conductivity_S_cm"] == pytest.approx(4.57e-5)
    assert rows[5]["conductivity_S_cm"] == pytest.approx(1.75e-4)
    assert all(r["temperature_C"] == 25 for r in rows)


def test_exact_source_authentication_and_target_guard():
    with pytest.raises(ValueError):
        m.read_author_table(article(doi="10.1021/fake"))
    with pytest.raises(ValueError):
        m.read_author_table(article(header="bulk Ionic conductivity (25 °C)/S cm−1"))
    with pytest.raises(ValueError):
        m.read_author_table(article(header="total Ionic conductivity (30 °C)/S cm−1"))
    with pytest.raises(ValueError):
        m.read_author_table(article(header="total Ionic conductivity (25 °C)/mS cm−1"))
    with pytest.raises(ValueError):
        m.read_author_table(article(routes=False))


def test_missing_swapped_or_mutated_measurement_denied():
    values = dict(m.AUTHOR_TOTAL)
    values["MS2"] = 8.54e-5
    with pytest.raises(ValueError):
        m.read_author_table(article(values=values))
    values = dict(m.AUTHOR_TOTAL)
    values.pop("DS2")
    with pytest.raises(ValueError):
        m.read_author_table(article(values=values))
    with pytest.raises(ValueError):
        m.read_author_table(article().replace(b"DS4", b"DS3"))


def test_complete_scientific_notation_and_security():
    assert m.conductivity_cell("1.41 × 10−4") == pytest.approx(1.41e-4)
    assert m.conductivity_cell("4.57x10-5") == pytest.approx(4.57e-5)
    for bad in ("<script>", "1.2x10-4 leftovers", "NaN", "Infinity", "0", "-1"):
        with pytest.raises(ValueError):
            m.conductivity_cell(bad)
    with pytest.raises(ValueError):
        m.read_author_table(
            b'<!DOCTYPE article [<!ENTITY m "bad">]><article>&m;</article>')


def test_original_label_population_and_source_doi_is_new_to_0188():
    from scripts.science.obelix_solo_oxide_five_doi_0188 import ALL_DOIS
    from scripts.science.obelix_real_grouped_oof_0146 import _composition
    from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
    assert m.DOI not in ALL_DOIS
    assert len(m.FORMULAS) == 4
    assert len(set(_composition(f)[0] for f in m.FORMULAS)) == 4
    assert all(_family_proxy(_composition(f)[1]) == "O_ONLY" for f in m.FORMULAS)


def test_source_specific_numeric_acs_table_label_requires_anchored_caption():
    # Original ACS JATS uses <label>2</label>, unlike prior MDPI/RSC deposits.
    xml = article().replace(b"<label>Table 2.</label>", b"<label>2</label>")
    rows, meta = m.read_author_table(xml)
    assert len(rows) == 8 and meta["original_table_number"] == 2
    corrupt = xml.replace(
        b"Measured Ionic Conductivity and Calculated Activation Energy",
        b"Unrelated Density Table",
    )
    with pytest.raises(ValueError, match="table"):
        m.read_author_table(corrupt)
