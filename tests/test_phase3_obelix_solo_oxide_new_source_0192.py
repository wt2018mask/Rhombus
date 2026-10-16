"""0192 negative real-source gates and paired public-source inventory."""
import pytest
from scripts.science import obelix_solo_oxide_new_source_0192 as s

def xml(first=None,second=None,unit="S cm−1",doi=s.SOURCE_DOI,method="mother powder"):
    a=s.SIX_HOUR_VALUES_1050 if first is None else first
    b=s.SIX_HOUR_VALUES_1100 if second is None else second
    def fmt(v):return ", ".join(f"{z:.3f}" for z in v[:-1])+", and "+f"{v[-1]:.3f}"
    p=("EIS measurement results revealed that the radius of the semicircle was reduced almost by half. "
       "The total ionic conductivities were increased from "+fmt(a)+" × 10−4 "+unit+
       " to "+fmt(b)+" × 10−4 "+unit+
       " for LLZO, Ta0.6LLZO, Ta0.4Ga0.067LLZO, Ta0.2Ga0.133LLZO, and Ga0.2LLZO.")
    return (f'<article><front><article-meta><article-id pub-id-type="doi">{doi}</article-id>'
            '<article-id pub-id-type="pmc">9773338</article-id></article-meta></front>'
            f'<body><p>Measured total conductivity at room temperature at 1050 °C or 1100 °C for 6 h or 12 h; {method} used 12 h.</p>'
            '<p>Electrochemical impedance spectroscopy (EIS) measurements were performed at room temperature.</p>'
            f'<p>{p}</p></body><floats-group><table-wrap><label>1</label>'
            '<caption><p>Lattice Parameters and Ionic Conductivities of Pure, Monodoped, and Codoped LLZO</p></caption>'
            '<table>'+''.join('<tr><td>author</td><td>data</td></tr>' for _ in range(11))+
            '</table></table-wrap></floats-group></article>').encode()

def test_correct_source_data_and_temperature_pair_identity():
    x,meta=s.original_six_hour_conditions(xml())
    assert len(x)==10 and len({r[2] for r in x})==5
    assert x[0][3:5]==(1050,360) and x[5][3:5]==(1100,360)
    assert x[0][5]==pytest.approx(1.7e-6) and x[-1][5]==pytest.approx(7.13e-5)
    assert meta["twelve_hour_powder_covered_conditions_quarantined"]==10
    assert meta["actual_EIS_temperature"]=="ROOM_TEMPERATURE_NUMERIC_UNSPECIFIED"
    assert meta["strict_numeric_25C_admitted"] is False

def test_corrupted_doi_source_units_source_values_or_process_denied():
    with pytest.raises(ValueError):s.original_six_hour_conditions(xml(doi="10.1000/incorrect"))
    with pytest.raises(ValueError):s.original_six_hour_conditions(xml(unit="S m−1"))
    a=list(s.SIX_HOUR_VALUES_1050);a[2]=0.486
    with pytest.raises(ValueError):s.original_six_hour_conditions(xml(first=a))
    with pytest.raises(ValueError):s.original_six_hour_conditions(xml(method="unknown cover"))
    with pytest.raises(ValueError):s.original_six_hour_conditions(xml().replace(b"performed at room temperature",b"performed at exactly 25 Celsius"))
    with pytest.raises(ValueError):s.original_six_hour_conditions(xml().replace(b"Ionic Conductivities",b"Density Controls"))
    with pytest.raises(ValueError):s.original_six_hour_conditions(b'<!DOCTYPE article [<!ENTITY x "bad">]><article>&x;</article>')

def test_original_heldout_family_and_explicit_simple_rule():
    from scripts.science.obelix_real_grouped_oof_0146 import _composition
    from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
    from scripts.science.obelix_solo_oxide_five_doi_0188 import ALL_DOIS
    assert s.SOURCE_DOI not in ALL_DOIS
    assert len({_composition(f)[0] for f in s.FORMULAS})==5
    assert all(_family_proxy(_composition(f)[1])=="O_ONLY" for f in s.FORMULAS)
    assert all(b>a for a,b in zip(s.SIX_HOUR_VALUES_1050,s.SIX_HOUR_VALUES_1100))
