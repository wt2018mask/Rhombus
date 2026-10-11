"""0161 Caltech external cross-corpus: no original TEST access or false independence."""
import csv
import io
import json
import numpy as np
import pytest
from scripts.science.obelix_external_caltech_0161 import (
    SCHEMA, CALTECH_COLS, original_train_identity,
    prepare_crosssource_candidates, evaluate_crosssource,
    _parse_external,
)


def sample():
    from scripts.science.obelix_real_grouped_oof_0146 import _composition
    formulas=("Li2O","Li2S","Li3PO4","LiCl","Li7La3Zr2O12",
              "Li3PS4","Li2CO3","LiBr","LiF","Li3N",
              "Li4GeO4","Li4SiO4","LiAlO2","Li2SO4","Li3BO3",
              "Li2Se","Li3P","LiI","Li2TiO3","Li3VO4")
    records=[]
    for i,f in enumerate(formulas):
        records.append({"official_split":"TRAIN","reported_composition":f,
                        "reference_dois":["10.test/ref"+str(i%4)]})
    # Forbidden fields deliberately throw if any reader accesses TEST metadata.
    class Protected(dict):
        def get(self,k,default=None):
            if k!="official_split":
                raise AssertionError("ORIGINAL_PUBLIC_TEST_METADATA_READ")
            return super().get(k,default)
    records.append(Protected({"official_split":"TEST","reported_composition":"SEAL",
                              "reference_dois":["10.test/never-read"]}))
    x=np.stack([_composition(f)[1] for f in formulas])
    y=np.asarray([-6.0+(i%6)/4 for i in range(len(formulas))])
    groups=tuple("group-"+str(i%8) for i in range(len(formulas)))
    return records,x,y,groups


def mock_csv(rows):
    stream=io.StringIO()
    writer=csv.DictWriter(stream,fieldnames=CALTECH_COLS)
    writer.writeheader()
    for data in rows:
        writer.writerow(dict(zip(CALTECH_COLS,data)))
    return stream.getvalue().encode("utf-8")


def test_train_identity_reads_only_split_for_TEST():
    records,*_=sample()
    result=original_train_identity(records,strict_official=False)
    assert result["train_rows"]==20
    assert result["reserved_test_rows_UNREAD"]==1
    assert "Li2O" in result["train_reduced_formulas"]
    assert "10.test/ref0" in result["train_doi_tokens"]
    assert "10.test/never-read" not in result["train_doi_tokens"]
    with pytest.raises(ValueError,match="canonical"):
        original_train_identity(records)


def test_source_DIO_overlap_formula_eligibility_and_invalid_censored_values():
    records,*_=sample()
    identity=original_train_identity(records,strict_official=False)
    rows=[
      dict(zip(CALTECH_COLS,("Li3PS4","123","10.test/ref1","1e-5","280"))),
      dict(zip(CALTECH_COLS,("Li3PS4","456","10.some/other","2e-4","290"))),
      dict(zip(CALTECH_COLS,("Li6PS5Cl","555","10.other/ref","1e-3",""))),
      dict(zip(CALTECH_COLS,("Li6PS5Cl","556","10.other/ref","0","100"))),
      dict(zip(CALTECH_COLS,("polymer","999","10.other/new","2e-4","300"))),
    ]
    data,counters=prepare_crosssource_candidates(rows,identity)
    assert counters["external_original_rows"]==5
    assert counters["exact_original_train_DOI_signal_rows"]==1
    assert counters["without_original_train_DOI_signal_rows"]==4
    assert counters["strict_no_TRAIN_DOI_or_reduced_formula_signal"]==1
    assert len(data)==3
    assert data[0]["no_train_doi"] is False
    assert data[1]["no_train_formula"] is False
    assert data[2]["no_train_doi"] and data[2]["no_train_formula"]


def test_cross_corpus_synthetic_model_scoring_and_no_row_dump():
    records,x,y,groups=sample()
    rows=[
      ("Li6PS5Cl",str(i),"10.other/journal-"+str(i%9),
       str(10**(-6+i%4)),"")
      for i in range(30)
    ]
    rows+= [
      ("Li2O","S","10.test/ref0","1e-5","299"),
      ("Li2O","T","10.some/2025","1e-3",""),
      ("Li3PS4","U","10.new/2026","1e-4","")
    ]
    result=evaluate_crosssource(
        x,y,groups,records,mock_csv(rows),strict_official=False)
    assert result["schema_version"]==SCHEMA
    assert result["original_obelix_public_TRAIN_numeric_fit"]==20
    assert result["original_obelix_public_TEST_reserved_unread"]==1
    assert result["original_TEST_features_DOIs_or_labels_read"] is False
    assert result["external_labels_opened_after_models_fit"]
    assert result["external_reported_original_records"]==len(rows)
    tiers=result["external_zero_shot_cohorts"]
    assert set(tiers)=={"ALL_ORIGINAL_VALID","NO_EXACT_ORIGINAL_TRAIN_DOI",
                         "NO_EXACT_TRAIN_DOI_AND_REDUCED_FORMULA"}
    assert tiers["ALL_ORIGINAL_VALID"]["source_records"]==len(rows)
    assert tiers["NO_EXACT_TRAIN_DOI_AND_REDUCED_FORMULA"]["source_records"]==30
    assert all(r["independently_verified_new_experimental_materials"]==0
               for r in tiers.values())
    assert result["scientific_GO"] is False
    assert all(result[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))
    serialized=json.dumps(result)
    assert "10.other/" not in serialized
    assert "Li6PS5Cl" not in serialized
    assert "icsd_collectioncode" not in serialized


def test_malformed_caltech_external_fields_fail_and_never_create_score():
    records,x,y,groups=sample()
    data=mock_csv([("Li2O","a","10.other/ref","1e-3","298")])
    with pytest.raises(ValueError,match="Caltech|file|source"):
        _parse_external(data,strict_official=True)
    malformed=b"not,a,published,source\nhi,bye,no,thanks\n"
    with pytest.raises(ValueError,match="dataset schema"):
        _parse_external(malformed,strict_official=False)
    with pytest.raises(ValueError,match="dataset schema"):
        evaluate_crosssource(x,y,groups,records,b"",strict_official=False)
    with pytest.raises(ValueError,match="frozen"):
        evaluate_crosssource(x,y,groups,records,data,strict_official=True)
