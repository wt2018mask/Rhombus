"""0188 hostile author original source and held out source-group tests."""
import pytest
from scripts.science import obelix_solo_oxide_five_doi_0188 as m

def article(doi,pmc,number,rows):
    science="We prepared Li6.4Al0.2La3Zr2O12 garnet and measured total conductivity by EIS at 25 °C."
    table="<table-wrap><label>Table "+str(number)+".</label><caption><p>Total and bulk ionic conductivity</p></caption><table>"
    table+="".join("<tr>"+"".join("<td>"+str(cell)+"</td>" for cell in row)+"</tr>" for row in rows)
    table+="</table></table-wrap>"
    return (f'<article><front><article-meta><article-id pub-id-type="doi">{doi}</article-id>'
            f'<article-id pub-id-type="pmc">{pmc[3:]}</article-id></article-meta></front>'
            f'<body><p>{science}</p></body><floats-group>{table}</floats-group></article>').encode()

def test_2018_original_total_column_aligned_and_mutations_denied():
    source=article(m.DOI18,"PMC9079727",3,[["Sample","σ total (S/cm)","σ bulk (S/cm)"]]+
         [[label,f"{value:.2e}","1e-3"] for label,value in zip(m.S18,m.T18)])
    rows,meta=m.original_2018(source)
    assert len(rows)==5 and rows[3][3]==pytest.approx(2.10e-4)
    assert meta["original_table_number"]==3
    with pytest.raises(ValueError):m.original_2018(source.replace(b"1.54e-05",b"1.54e-04"))
    with pytest.raises(ValueError):m.original_2018(source.replace(b"10.1039/c8ra01329b",b"10.1039/changed"))
    with pytest.raises(ValueError):m.original_2018(source.replace("σ total".encode(),"σ bulk".encode()))

def test_2021_original_total_unit_route_mapping_and_wrong_values_rejected():
    source=article(m.DOI21,"PMC8620275",4,[["Parameter","SSR","SASSR","CP","SD"],
       ["σ total (10-4 S/cm)","3.14(7)","2.64(3)","2.02(2)","3.28(3)"],
       ["σ bulk (10-4 S/cm)","5.19(7)","3.19(3)","2.28(2)","3.44(3)"]])
    rows,meta=m.original_2021(source)
    assert len(rows)==4 and meta["original_table_number"]==4
    assert [r[3] for r in rows]==pytest.approx(m.T21)
    with pytest.raises(ValueError):m.original_2021(source.replace(b"3.28(3)",b"3.88(3)"))
    with pytest.raises(ValueError):m.original_2021(source.replace(b"total",b"bulk"))

def test_five_DOI_source_population_and_only_one_nominal_formula_new():
    assert len(m.ALL_DOIS)==5 and len(set(m.ALL_DOIS))==5
    assert len(m.S18)==5 and len(m.S21)==4
    assert m.FORMULA=="Li6.4Al0.2La3Zr2O12"
    from scripts.science.obelix_real_grouped_oof_0146 import _composition
    from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
    assert _family_proxy(_composition(m.FORMULA)[1])=="O_ONLY"

def test_opaque_official_TEST_and_transitive_training_connectivity_required():
    class Guard(dict):
        def get(self,k,default=None):
            if k!="official_split":raise AssertionError("official TEST leaked")
            return super().get(k,default)
    docs=[Guard(official_split="TEST") for _ in range(121)]
    docs += [dict(official_split="TRAIN",source_entry_id=str(i),reported_composition=m.FORMULA if i==0 else "Li6.6La3Zr1.6Nb0.4O12",reference_dois=["10.2222/"+str(i)]) for i in range(478)]
    cohort=[(m.DOI18,"sample",m.FORMULA,1e-4)]
    eligible,matched,excluded=m.embargo(docs,{"source_ids":["0","1"],"groups":["0","1"]},cohort)
    assert eligible.tolist()==[False,True] and matched==1 and excluded==1
    with pytest.raises(ValueError,match="graph"):
        m.embargo(docs,{"source_ids":["0","1"],"groups":["bogus","bogus"]},cohort)

def test_original_xml_entity_danger_denied():
    with pytest.raises(ValueError,match="entity"):
        m.table_source(b'<!DOCTYPE article [<!ENTITY a "boom">]><article>&a;</article>',m.DOI18,"PMC9079727",3)
