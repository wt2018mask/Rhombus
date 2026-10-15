"""0185 source mutation and quarantine tests."""
import pytest
from scripts.science import obelix_solo_oxide_external_0185 as m
HEADER="source,li_sto,la_sto,zr_sto,li_dop_sto,la_dop_sto,zr_dop_sto,li_dopant,la_dopant,zr_dopant,conductivity,log_cond"
def row(doi="10.1000/aa",sig="0.001",zr="2",dop="",dopqty="0"):
    return f"{doi},7,3,{zr},0,0,{dopqty},,,{dop},{sig},-3"
def raw(*r):return (HEADER+"\n"+"\n".join(r)+"\n").encode()
def test_fixed_oxide_scope():
    assert "O_ONLY_RF" in m.MODELS and "S_ONLY_RF" not in m.MODELS
    assert len(m.EXT_COMMIT)==40 and len(m.EXT_BLOB)==40
def test_oxide_formula_and_sulfur_rejected():
    d=dict(zip(HEADER.split(","),row().split(",")))
    p=m.source_formula(d)
    assert p[1][7]>0 and p[1][15]==0
    d=dict(zip(HEADER.split(","),row(zr="1.5",dop="Ta",dopqty=".5").split(",")))
    assert m.source_formula(d)[1][72]>0
    d["zr_dopant"]="S"
    with pytest.raises(ValueError,match="NON_O_ONLY"):
        m.source_formula(d)
def test_doi_and_formula_train_collision_quarantined():
    base=m.source_formula(dict(zip(HEADER.split(","),row().split(","))))[0]
    d=m.intake_external(raw(row("10.1000/a"),row("10.1000/b"),row("10.1000/c",zr="1.5",dop="Ta",dopqty=".5")),{"10.1000/a"},{base},pinned=False)
    assert d["eligible"]==1
    assert d["excluded"]["OVERLAP_ORIGINAL_TRAIN_DOI"]==1
    assert d["excluded"]["OVERLAP_ORIGINAL_TRAIN_FORMULA"]==1
def test_bad_blob_headers_and_broken_sigma_not_falsely_scored():
    with pytest.raises(ValueError,match="source bytes"):
        m.intake_external(raw(row()),set(),set())
    with pytest.raises(ValueError,match="headers"):
        m.intake_external(b"source,conductivity\n",set(),set(),pinned=False)
    v=m.intake_external(raw(row(sig="-1")),set(),set(),pinned=False)
    assert v["excluded"]["NONPOSITIVE_OR_NONFINITE"]==1
    v=m.intake_external(raw(row(sig="0.01")),set(),set(),pinned=False)
    assert v["excluded"]["SOURCE_LOG_MISMATCH"]==1
def test_transitive_connected_source_groups_not_independent_rows():
    a=m.intake_external(raw(row("10.1000/a",zr="1.5",dop="Ta",dopqty=".5"),
                            row("10.1000/b",zr="1.5",dop="Ta",dopqty=".5"),
                            row("10.1000/b",zr="1.8",dop="Nb",dopqty=".2")),set(),set(),pinned=False)
    assert a["eligible"]==3 and a["connected_groups"]==1
def test_bad_substitution_stoichiometry_and_unknown_DOI_denied():
    a=m.intake_external(raw(row("10.1000/a",zr="1.5",dop="",dopqty=".5"),row("wrong")),set(),set(),pinned=False)
    assert a["eligible"]==0 and a["excluded"]["INVALID_OR_NON_O_ONLY_FORMULA"]==1 and a["excluded"]["INVALID_DOI"]==1
def test_TEST_rows_dont_allow_any_field_read():
    class Guard(dict):
        def get(self,key,default=None):
            if key!="official_split":raise AssertionError("TEST fields touched")
            return super().get(key,default)
    rows=[Guard(official_split="TEST") for _ in range(121)]
    rows += [dict(official_split="TRAIN",reported_composition="Li7La3Zr2O12",reference_dois=["10.1000/a"]) for _ in range(478)]
    dois,formulas=m.original_train_signatures(rows)
    assert dois=={"10.1000/a"} and len(formulas)==1
