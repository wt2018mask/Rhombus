"""0194 author-source identity, counterexample and applicability tests."""
import pytest
from scripts.science import obelix_solo_oxide_author_te_hotpress_0194 as m

def fixture(values=None,doi=m.DOI,header="Total ionic conductivity σ (25 °C) [S cm−1]"):
    v=m.AUTHOR if values is None else values
    rows=""
    for i,t in enumerate(m.TEMPS):
        cells="".join("<td>"+f"{x:.2e}".replace("e-","x10-")+"</td>" for x in v[i])
        rows+=f"<tr><td>{t} °C</td>{cells}</tr>"
    return (f'<html><head><meta name="citation_doi" content="{doi}"/></head><body>'
        '<h1>Hexavalent Ions Insertion in Garnet</h1>'
        '<p>Authors Campanella, Zhu, Girard: total ionic conductivity of hot-pressed samples.</p>'
        f'<table><caption>Original Table 2. {header}</caption>'
        '<tr><th>Temperature</th><th>Te0.1</th><th>Te0.25</th><th>Te0.375</th>'
        '<th>Te0.5</th><th>Al-LLZO</th><th>Ta-LLZO</th></tr>'
        +rows+'</table></body></html>').encode()

def test_author_18_conditions_and_650C_nonmonotonic_counterexample():
    d=m.evaluate(m.original_html(fixture()))
    assert d["author_conditions"]==18 and d["nominal_series_count"]==6
    assert d["nonmonotonic_series"]==["Te0.1"]
    assert d["always_hottest_successes"]==5
    assert d["always_hottest_failures"]==1
    assert d["rows"][0]["best_source_temp_C"]==650
    assert d["rows"][0]["25C_TOTAL_S_cm"][2]==pytest.approx(1.45e-5)

def test_first_party_DOI_and_target_temperature_required():
    for kw in ({"doi":"10.1002/wrong"},{"header":"Total ionic conductivity σ (30 °C) [S cm−1]"},
               {"header":"Total ionic conductivity σ (25 °C) [mS cm−1]"}):
        with pytest.raises(ValueError):m.original_html(fixture(**kw))

def test_mutation_and_double_table_must_fail():
    v=[list(row) for row in m.AUTHOR]
    v[1][0]=1.11e-5
    with pytest.raises(ValueError):m.original_html(fixture(values=v))
    with pytest.raises(ValueError):m.original_html(fixture().replace(b"650",b"680"))
    f=fixture()
    duplicate=f.replace(b"</body>",f[f.find(b"<table>"):f.find(b"</table>")+8]+b"</body>")
    with pytest.raises(ValueError):m.original_html(duplicate)

def test_invalid_scientific_notation_rejected():
    assert m.conductivity("1,76×10−5")==pytest.approx(1.76e-5)
    for cell in ("NaN","1.76 mS/cm","1.76e5","1.76x10-5 noise","0","-1"):
        with pytest.raises(ValueError):m.conductivity(cell)

def test_physical_science_NO_GO_and_0191_outside_domain():
    d=m.evaluate(m.original_html(fixture()))
    assert not d["0191_process_model_compatible"]
    assert d["0191_model_route_abstentions"]==6
    assert not d["model_choice_outperformance_proven"]
    assert d["original_OBELiX_official_TEST_121_unread"]
    assert not d["scientific_GO"] and not d["production_enabled"]
    assert all(d[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))
