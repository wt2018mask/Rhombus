"""0165 hard barriers between drawn graph, calibrated population data and a pellet."""
import hashlib
import io
import json
import sys
from types import SimpleNamespace
import pytest
from scripts.science import obelix_lagp_figure7_numeric_0165 as s

def test_missing_original_numeric_figure7_values_is_NOT_a_validated_population_mean():
    x=s.decide_population_target(graph_axis_calibrated=False,
         source_mean_numeric=None,source_sd_numeric=None,replicate_count=None,
         bulk_total_defined=False,individual_pellet_ids_verified=False)
    assert x["observation_unit"]=="NOMINAL_COMPOSITION_PELLET_GROUP_MEAN_SD"
    assert x["group_summary_numerically_ready"] is False
    assert x["individual_pellet_truth_ready"] is False
    assert "SOURCE_MEAN_VALUE_NOT_DIGITIZED" in x["blockers"]
    assert "EXACT_INDEPENDENT_PELLET_N_UNKNOWN" in x["blockers"]


def test_even_complete_author_graph_group_mean_cannot_self_certify_pellet_identity():
    x=s.decide_population_target(graph_axis_calibrated=True,
       source_mean_numeric=0.0003,source_sd_numeric=0.0001,
       replicate_count=4,bulk_total_defined=True,individual_pellet_ids_verified=True)
    assert x["group_summary_numerically_ready"] is True
    assert x["individual_pellet_truth_ready"] is False
    assert x["independent_blind_qualified"] is False
    assert "INDIVIDUAL_CIF_TO_PELLET_EXPERIMENTAL_IDENTITY_UNVERIFIED" in x["blockers"]


@pytest.mark.parametrize("value",[-3.0,float("nan"),float("inf"),"1e-3",True])
def test_bad_measured_mean_and_SD_never_promoted(value):
    with pytest.raises(ValueError,match="invalid inferred numerical"):
        s.decide_population_target(graph_axis_calibrated=True,
            source_mean_numeric=value,source_sd_numeric=0.00002,replicate_count=3,
            bulk_total_defined=True,individual_pellet_ids_verified=True)
    with pytest.raises(ValueError,match="invalid inferred numerical"):
        s.decide_population_target(graph_axis_calibrated=True,
            source_mean_numeric=0.0002,source_sd_numeric=value,replicate_count=3,
            bulk_total_defined=True,individual_pellet_ids_verified=True)


@pytest.mark.parametrize("n",[0,1,True,2.3,"3"])
def test_replicate_count_requires_real_integer_at_least_two(n):
    with pytest.raises(ValueError,match="multiple experimental samples"):
        s.decide_population_target(graph_axis_calibrated=True,
            source_mean_numeric=0.01,source_sd_numeric=0.002,replicate_count=n,
            bulk_total_defined=True,individual_pellet_ids_verified=False)


def test_pinned_PDF_page_graphics_are_only_readiness_not_digitized_data(monkeypatch):
    class Resource:
        def __init__(self,kind):self.kind=kind
        def get_object(self):return self
        def get(self,key,default=None):
            if key=="/Subtype":return "/"+self.kind
            if key=="/XObject":return FakeRefs()
            return default
    class FakeRefs(dict):
        def get_object(self):return self
    class Content:
        def get_data(self):return b"q 0 0 m 1 1 l S /Im1 Do Q"
    class Page:
        def __init__(self,index):self.index=index
        def get_contents(self):return Content()
        def get(self,k):
            if k=="/Resources":return Resource("Page")
        def extract_text(self):return "Figure 7 10 -4 σ RT 0.4 0.6"
    class Reader:
        def __init__(self,_):self.pages=[Page(i) for i in range(26)]
    class Stream:
        def __init__(self,*args):
            self.operations=[([],b"m"),([],b"l"),([],b"S"),([],b"Do"),([],b"Tj"),([],b"rg")]
    monkeypatch.setitem(sys.modules,"pypdf",SimpleNamespace(PdfReader=Reader))
    monkeypatch.setitem(sys.modules,"pypdf.generic",SimpleNamespace(ContentStream=Stream))
    raw=b"fixture-only-original-PDF"
    result=s.page_graphics_diagnostic(raw,expected_sha=hashlib.sha256(raw).hexdigest())
    assert [v["pdf_page_one_based"] for v in result["figure_neighborhood_graphics"]]==[15,16,17]
    assert all(v["vector_drawing_operations"]==3 for v in result["figure_neighborhood_graphics"])
    assert result["per_point_figure7_numeric_data_extracted"]==0
    assert result["figure7_mean_errorbar_digitization"] is False
    assert result["coordinate_axis_calibration_independently_verified"] is False
    with pytest.raises(ValueError,match="SHA"):
        s.page_graphics_diagnostic(raw,expected_sha="0"*64)


def test_actual_main_function_cannot_upgrade_source_semantics_by_fake_paper_word(monkeypatch,tmp_path):
    fake={"original_SOURCE_git_commit":s.SOURCE_COMMIT,
          "processed_source_TRAIN_label_log10_ratio_1dm_minus_0fh":0.76937121}
    monkeypatch.setattr(s,"strict_train_physical_targets",lambda _:fake)
    raw=b"pinned fake PDF content"
    monkeypatch.setattr(s,"MANUSCRIPT_SHA",hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(s,"fetch_with_bounded_transient_retries",lambda _:raw)
    monkeypatch.setattr(s,"audit_manuscript",lambda _:{"document_text_DOI_match":True})
    monkeypatch.setattr(s,"inspect_original_paper_figures",lambda _:{
        "figure7_anchor_pages":[16],
        "figure7_population_word_cue_pages_NOT_a_singular_sample":[17]})
    monkeypatch.setattr(s,"page_graphics_diagnostic",lambda _:{
        "per_point_figure7_numeric_data_extracted":0,"figure_neighborhood_graphics":[]})
    report=s.build_original_source_report(tmp_path)
    assert report["scientific_GO"] is False
    assert report["actual_group_mean_and_SD_numeric_points_qualified"]==0
    assert report["original_TEST_composition_DOI_conductivity_cells_parsed"]==0
    assert report["individual_experimental_pellet_truths_qualified"]==0
    assert not report["physical_experimental_target_eligibility"]["group_summary_numerically_ready"]
    assert "reported_ionic_conductivity_text" not in json.dumps(report)
