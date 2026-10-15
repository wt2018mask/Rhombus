"""0187 reject substituted PDF source, composite pseudo-composition and TEST leakage."""
import pytest
import numpy as np
from scripts.science import obelix_solo_oxide_independent_doi_0187 as m

def fixture(table=None):
    if table is None:
        table=("Table 2 Total ionic conductivity of the samples measured at 25 °C.\n"
               "Sample Total ionic conductivity (S cm−1)\n"
               "LLZO:Ga 1.70 × 10−3\n"
               "LLZO:Ta 0 % Li excess 7.53 × 10−4\n"
               "LLZO:Ta 10 % Li excess 6.69 × 10−4\n"
               "LLZO:Ga|LLZO:Ta 0 % Li excess 1.60 × 10−5\n"
               "LLZO:Ga|LLZO:Ta 10 % Li excess 6.22 × 10−5")
    pages=["Ga-ion migration during co-sintering of heterogeneous Ta- and Ga-substituted LLZO solid-state electrolytes W.S. Scheld Journal of the European Ceramic Society "+m.NEW_DOI]
    pages+=["Li6.45Al0.05La3Zr1.6Ta0.4O12 and Li6.4Ga0.2La3Zr2O12. EIS measurements at 25 °C.","Science context 25 °C"] 
    pages+=["body third","body fourth",table,"end"]
    return pages

def test_primary_two_doi_scope_and_composites_excluded():
    r=m.verify_pdf_text(fixture())
    assert r["DOI"]==m.NEW_DOI
    assert r["temperature_C"]==25
    assert r["single_material_reference_rows"]==3
    assert r["heterogeneous_two_layer_composite_rows_EXCLUDED"]==2
    assert m.NEW_GA==m.PAPER0186_FORMULAS[1]
    assert m.NEW_DOI!=m.PAPER0186_DOI

def test_mutated_pdf_source_or_table_rejected():
    for pages in (
        fixture()[:6],
        [p.replace(m.NEW_DOI,"10.1016/j/other") for p in fixture()],
        [p.replace("at 25 °C","at 30 °C") for p in fixture()],
        [p.replace("7.53 × 10−4","7.53 × 10−3") for p in fixture()],
        [p.replace("6.22 × 10−5","6.22 × 10−4") for p in fixture()],
        [p.replace("Li6.45Al0.05La3Zr1.6Ta0.4O12","Li7La3Zr2O12") for p in fixture()],
    ):
        with pytest.raises(ValueError):m.verify_pdf_text(pages)

def test_reference_rows_do_not_expose_co_sintered_materials_as_single_formula():
    assert len(m.NEW_REFERENCE_ROWS)==3
    assert len(m.NEW_COMPOSITE_EXCLUDED)==2
    assert [v[2] for v in m.NEW_REFERENCE_ROWS]==[1.70e-3,7.53e-4,6.69e-4]
    from scripts.science.obelix_real_grouped_oof_0146 import _composition
    from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
    assert all(_family_proxy(_composition(v[1])[1])=="O_ONLY" for v in m.NEW_REFERENCE_ROWS)
    assert m.NEW_REFERENCE_ROWS[1][1]==m.NEW_REFERENCE_ROWS[2][1]

def test_new_source_formula_or_doi_in_TRAIN_fails_closed_without_TEST_data():
    class Guard(dict):
        def get(self,key,default=None):
            if key!="official_split":raise AssertionError("TEST source leakage")
            return super().get(key,default)
    rec=[Guard(official_split="TEST") for _ in range(121)]
    rec += [dict(official_split="TRAIN",source_entry_id="r"+str(i),reported_composition="Li7La3Zr2O12" if i else m.NEW_TA,
                 reference_dois=["10.1234/"+str(i)]) for i in range(478)]
    arr={"source_ids":("r0","r1"),"groups":("r0","r1")}
    with pytest.raises(ValueError):
        m.extended_train_embargo(rec,arr)
