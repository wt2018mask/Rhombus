"""0164 negative science target tests: Fig7 mean ≠ specific pellet and Fig6 1/R ≠ S/cm."""
import hashlib
import json
import sys
from types import SimpleNamespace
import pytest
from scripts.science import obelix_lagp_figure_population_0164 as f


def test_fig6_inverse_resistance_cannot_be_mislabeled_as_sigma():
    with pytest.raises(ValueError,match="inverse resistance"):
        f.classify_figure_source_unit(fig=6,observable="BULK_SIGMA",mean_over_samples=False,
           physical_pellet_id=None,exact_temperature_k=None,
           original_CIF_same_pellet_verified=False,bulk_total_method_traceable=False)
    with pytest.raises(ValueError,match="not inverse R"):
        f.classify_figure_source_unit(fig=7,observable="RECIPROCAL_RESISTANCE",mean_over_samples=True,
           physical_pellet_id=None,exact_temperature_k=None,
           original_CIF_same_pellet_verified=False,bulk_total_method_traceable=False)


def test_fig7_average_is_never_an_individual_pellet():
    x=f.classify_figure_source_unit(fig=7,observable="TOTAL_SIGMA",mean_over_samples=True,
        physical_pellet_id=None,exact_temperature_k=None,
        original_CIF_same_pellet_verified=False,bulk_total_method_traceable=False)
    assert x["scientific_unit"]=="NOMINAL_COMPOSITION_PELLET_POPULATION"
    assert "FIGURE7_POPULATION_MEAN_NOT_AN_INDIVIDUAL_SPECIMEN" in x["blockers"]
    assert x["individual_sample_cond_S_per_cm_qualified"] is False
    with pytest.raises(ValueError,match="average multiple pellets"):
        f.classify_figure_source_unit(fig=7,observable="BULK_SIGMA",mean_over_samples=False,
          physical_pellet_id="author-example",exact_temperature_k=298,
          original_CIF_same_pellet_verified=True,bulk_total_method_traceable=True)


def test_synthetic_filled_fields_cannot_self_certify_independent_original_measurement():
    x=f.classify_figure_source_unit(fig=7,observable="BULK_SIGMA",mean_over_samples=True,
        physical_pellet_id="invented",exact_temperature_k=298.15,
        original_CIF_same_pellet_verified=True,bulk_total_method_traceable=True)
    assert "INDEPENDENT_EXPERIMENTAL_CUSTODIAN_ATTESTATION_ABSENT" in x["blockers"]
    assert x["individual_sample_cond_S_per_cm_qualified"] is False
    for t in (-1,0,1000,True,float("inf")):
        with pytest.raises(ValueError,match="temperature"):
            f.classify_figure_source_unit(fig=6,observable="RECIPROCAL_RESISTANCE",
                mean_over_samples=False,physical_pellet_id=None,exact_temperature_k=t,
                original_CIF_same_pellet_verified=False,bulk_total_method_traceable=False)


def test_bounded_SHA_verified_primary_PDF_figure_word_locations_not_numeric_truth(monkeypatch):
    class Page:
        def __init__(self,t):self.t=t
        def extract_text(self):return self.t
    class Reader:
        def __init__(self,_):
            self.pages=[Page("Other Materials and methods") for _ in range(26)]
            self.pages[14]=Page("Figure 6 Li1.6Al0.6 with reciprocal resistance "
                "instead of the conductivity. The sample was sintered at 800 °C")
            self.pages[15]=Page("The results were measured at 25 °C")
            self.pages[16]=Page("Figure 7. All data points are calculated as average values "
                "from multiple samples with identical nominal composition; "
                "the uncertainties reflect the standard deviation. "
                "Bulk conductivity and total conductivity.")
            self.pages[18]=Page("At higher Al content phase fraction decreases, "
                "side phases form and solubility limit is observed.")
    monkeypatch.setitem(sys.modules,"pypdf",SimpleNamespace(PdfReader=Reader))
    raw=b"only verified fake original source"
    x=f.inspect_original_paper_figures(raw,expected_sha=hashlib.sha256(raw).hexdigest())
    idx=x["bounded_PDF_page_indicator_index"]
    assert x["figure6_reciprocal_R_cue_pages_NOT_a_S_per_cm"]==[15]
    assert x["figure7_population_word_cue_pages_NOT_a_singular_sample"]==[17]
    assert idx["temperature_25C"]==[16]
    assert idx["uncertainty_standard_deviation"]==[17]
    assert x["exact_per_sample_figure7_sigma_S_per_cm_NOT_extracted"]
    assert "Li1.6" not in json.dumps(x)
    with pytest.raises(ValueError,match="SHA"):
        f.inspect_original_paper_figures(raw,expected_sha="0"*64)


def test_figure_page_cooccurrence_does_not_admit_physical_pellet(monkeypatch):
    class P:
        def extract_text(self):
            return ("Figure 6 Figure 7 25C 800C "
                "reciprocal resistance instead of conductivity "
                "average values from multiple samples "
                "with identical nominal composition and standard deviation.")
    class Reader:
        def __init__(self,_):self.pages=[P() for _ in range(26)]
    monkeypatch.setitem(sys.modules,"pypdf",SimpleNamespace(PdfReader=Reader))
    raw=b"original-to-test"
    q=f.inspect_original_paper_figures(raw,expected_sha=hashlib.sha256(raw).hexdigest())
    assert q["figure7_population_word_cue_pages_NOT_a_singular_sample"]
    assert q["original_replicate_count_NOT_published_here"] is None
    assert q["original_primary_PDF_words_do_NOT_digitize_any_figure"]


def test_frozen_source_semantic_report_keeps_two_labels_disqualified(monkeypatch,tmp_path):
    fake={
        "original_SOURCE_git_commit":f.SOURCE_COMMIT,
        "original_TWO_source_TRAIN_structure_and_label_leads":[
          {"original_TRAIN_id":"0fh","publisher_nominal_Al_x":0.2,"publisher_refined_Al_x":0.242},
          {"original_TRAIN_id":"1dm","publisher_nominal_Al_x":0.6,"publisher_refined_Al_x":0.480},
        ],
        "processed_source_TRAIN_label_log10_ratio_1dm_minus_0fh":0.76937121,
    }
    monkeypatch.setattr(f,"strict_train_physical_targets",lambda _:fake)
    raw=b"fake-author-pdf-fully-pinned"
    monkeypatch.setattr(f,"MANUSCRIPT_SHA",hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(f,"fetch_with_bounded_transient_retries",lambda fun:raw)
    monkeypatch.setattr(f,"audit_manuscript",lambda data:{"document_text_DOI_match":True})
    monkeypatch.setattr(f,"inspect_original_paper_figures",lambda pdf:{
      "figure7_population_word_cue_pages_NOT_a_singular_sample":[17]})
    z=f.actual_original_paper_adjudication(tmp_path)
    assert len(z["original_TRAIN_CIF_contexts"])==2
    assert z["original_measured_physical_pellets_qualified"]==0
    assert z["original_fig7_group_means_digitized_qualified"]==0
    assert z["TEST_original_CSV_formula_DOI_conductivity_fields_parsed"]==0
    assert z["P0_01"]==z["P0_02"]==z["P0_03"]=="BLOCKED"
    assert z["scientific_GO"] is False
    assert all(not v["source_row_qualified_to_any_figure_point"]
               for v in z["original_TRAIN_CIF_contexts"])
