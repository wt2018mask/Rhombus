"""0162: physical target validity, source TRAIN conductivity ≠ specimen truth."""
import hashlib
import json
from types import SimpleNamespace
import pytest
from scripts.science import obelix_lagp_measurement_target_0162 as m
from scripts.science.obelix_lagp_nominal_series_0156 import MATCHES


def fixture():
    rows=[]
    for i in range(599):
        if i not in (0,1):
            rows.append({"official_split":"TEST" if i>=478 else "TRAIN","source_entry_id":str(i)})
        else:
            rid="0fh" if i==0 else "1dm"
            rows.append({
                "official_split":"TRAIN","source_entry_id":rid,
                "source_snapshot_commit":m.SOURCE_COMMIT,
                "reference_dois":[m.PAPER_DOI],
                "reported_ionic_conductivity_unit":"S/cm",
                "measurement_kind":"PROCESSED_REPORTED_POINT",
                "reported_temperature_scope":m.MEASUREMENT_SCOPE,
                "source_cif_match_status":"Match",
                "cif_content_sha256":MATCHES[rid][0],
                "reported_ionic_conductivity_text":"1e-5" if i==0 else "1e-4",
                "qualified_transport_truth":False,
            })
    links=[]
    for rid,nominal in m.IDS.items():
        links.append({"OBELiX_TRAIN_entry":rid,
                      "original_source_CIF_sha256":MATCHES[rid][0],
                      "publisher_original_CIF_sha256":MATCHES[rid][1],
                      "CIF_filename_nominal_series_x":nominal,
                      "publisher_Rietveld_refined_x_Al":nominal+0.01})
    return rows,links


def test_real_paper_to_CIF_source_pair_numeric_ratio_is_not_sample_measurement():
    a,b=fixture()
    result=m.audited_original_TRAIN_target_rows(a,b)
    assert result["source_label_ratio_log10_x0p6_minus_x0p2"]==1.
    assert result["processed_source_pair_reported_trend"]=="HIGHER_AT_NOMINAL_0P6"
    assert result["the_ratio_is_NOT_a_matched_specimen_transport_effect"] is True
    assert len(result["two_original_TRAIN_literature_source_records"])==2
    assert all(x["independently_qualified_transport_truth"] is False for x in
               result["two_original_TRAIN_literature_source_records"])
    assert all(x["bulk_or_total_measurement_identity_verified"] is False for x in
               result["two_original_TRAIN_literature_source_records"])
    assert "reported_ionic_conductivity_text" not in json.dumps(result)


def test_processed_label_requires_exact_train_DOI_source_CIF_hash_measurement_scope():
    rows,links=fixture()
    for change in (
        {"reference_dois":["10.bad/doi"]},
        {"measurement_kind":"UPPER_BOUND"},
        {"reported_temperature_scope":"MEASURED_298_K_VERIFIED"},
        {"qualified_transport_truth":True},
        {"cif_content_sha256":"0"*64},
        {"reported_ionic_conductivity_unit":"UNKNOWN"},
    ):
        altered=[dict(x) for x in rows]
        altered[0].update(change)
        with pytest.raises(ValueError,match="drift|false truth"):
            m.audited_original_TRAIN_target_rows(altered,links)
    with pytest.raises(ValueError,match="census"):
        m.audited_original_TRAIN_target_rows(rows[:-1],links)


def test_numeric_censored_or_zero_never_matched_to_paper():
    rows,links=fixture()
    for bad in ("<1e-4","0","-0.001","NaN","Inf","garbage"):
        changed=[dict(r) for r in rows]
        changed[0]["reported_ionic_conductivity_text"]=bad
        with pytest.raises(ValueError,match="label|positive|numeric"):
            m.audited_original_TRAIN_target_rows(changed,links)


def test_actual_paper_method_context_is_only_page_scope(monkeypatch):
    class Page:
        def __init__(self,s):self.s=s
        def extract_text(self):return self.s
    class Reader:
        def __init__(self,stream):
            self.pages=[Page("Materials and neutron diffraction") for _ in range(26)]
            self.pages[14]=Page(
                "Impedance spectroscopy: the bulk resistance and grain boundary "
                "response. The reciprocal resistance was used instead of "
                "conductivity. Figure 6 Li1.6Al0.6 sample 25 °C.")
            self.pages[2]=Page("Li1.2Al0.2 sample prepared; temperature unspecified.")
    monkeypatch.setattr("pypdf.PdfReader",Reader)
    raw=b"pinned-original-fixture"
    r=m.paper_transport_method_audit(raw,pdf_hash=hashlib.sha256(raw).hexdigest())
    assert r["transport_method_indicator_pages"]["reciprocal_resistance"]==[15]
    assert r["transport_method_indicator_pages"]["not_equivalent_to_conductivity"]==[15]
    assert r["transport_method_indicator_pages"]["figure_six"]==[15]
    assert r["transport_method_indicator_pages"]["nominal_lagp_1p2"]==[3]
    assert r["transport_method_indicator_pages"]["nominal_lagp_1p6"]==[15]
    assert r["definite_temperature_bulk_total_sample_label_links"]==0
    assert r["graph_or_page_cooccurrence_is_not_sample_specific_measurement"]
    with pytest.raises(ValueError,match="SHA"):
        m.paper_transport_method_audit(raw,pdf_hash="0"*64)


def test_second_page_cooccurrence_is_not_a_transport_measurement(monkeypatch):
    class P:
        def extract_text(self):return "Figure 6 Li1.6Al0.6 bulk conductivity 25C 1e-4"
    class Reader:
        def __init__(self,_):self.pages=[P() for _ in range(26)]
    monkeypatch.setattr("pypdf.PdfReader",Reader)
    raw=b"some-verified-pdf"
    q=m.paper_transport_method_audit(raw,pdf_hash=hashlib.sha256(raw).hexdigest())
    assert q["transport_method_indicator_pages"]["nominal_lagp_1p6"]
    assert q["definite_temperature_bulk_total_sample_label_links"]==0
    assert q["full_experimental_figure_numeric_data_independently_digitized"] is False
