"""0167 falsifiable two-paper physically non-equivalent observables and identity."""
import copy
import math
import statistics
import pytest
from scripts.science import original_cross_source_identifiability_0167 as s
from scripts.science import original_sulfide_measurement_table_0166 as sulf
from xml.sax.saxutils import escape

def fixture():
    rows=[
      ["HT temperature/°C","150","200","300","400","500","550"],
      ["Conductivity at 25 °C/mS cm−1","0.19","0.20","0.53","1.49","1.23","1.94"],
      ["Activation energy/kJ mol−1","42.3","40.3","38.3","31.2","27.7","34.9"],
    ]
    table="".join("<tr>"+"".join(f"<td>{escape(v)}</td>" for v in row)+"</tr>" for row in rows)
    return (f'<article><front><article-meta><article-id pub-id-type="doi">10.1039/c9ra00949c</article-id><title-group><article-title>Quantitative analysis of crystallinity in an argyrodite sulfide-based solid electrolyte synthesized via solution processing</article-title></title-group></article-meta></front><body><table-wrap><caption><p>Conductivities and activation energies of the argyrodite electrolytes. Green compacts pressed at 720 MPa were used.</p></caption><table><tbody>{table}</tbody></table></table-wrap></body></article>').encode('utf-8')



def inputs():
    source=sulf.extract_table(fixture())
    other={
      "DOI":"10.1021/jacs.8b10282",
      "original_S17_canonical_numeric_table_SHA256":
          "1eb7ad5527b18040239b341ba6171aad3453113c700c2edf4ca271a1eba84d7d",
      "scientific_GO":False,
      "quantitative_physical_bulk_R_temperature_evidence":{
        "raw_source_fit_resistance_values_read_NOT_REPUBLISHED":120,
        "original_distinct_nominal_compositions":10,
        "unique_temperatures_K":11,
        "duplicate_298K_Rbulk_records":10,
        "R_bulk_ohm_NOT_S_per_cm":True,
        "individual_true_sample_labels_qualified":0,
      }}
    return source,other


def test_actual_original_six_source_points_yield_log10_constant_error_lower_bound():
    a,b=inputs()
    x=s.analyze_actual_sources(a,b)
    log=[math.log10(v/1000.) for v in [.19,.20,.53,1.49,1.23,1.94]]
    for constant in (-10,-5,-4,-3,-2,math.log10(.5/1000)):
        assert statistics.mean(abs(v-constant) for v in log)+1e-10>=x[
            "source1_STOICHIOMETRY_ONLY_or_any_single_constant_MIN_EMPIRICAL_log10_MAE"]
    assert x["source1_log10_S_per_cm_label_range"]==round(math.log10(1.94/.19),8)
    assert x["source1_actual_original_same_formula_max_to_min_sigma_ratio"]==round(1.94/.19,8)
    assert x["source1_distinct_material_compositions"]==1
    assert x["source1_number_nonmonotonic_heat_steps"]==1
    assert x["source1_thermal_processing_condition_for_min_Ea_C"]==500
    assert x["source1_thermal_processing_condition_for_max_sigma_C"]==550
    assert x["source1_exploratory_same_paper_retroactive_error_NOT_validated_test_performance"] is True
    assert x["physical_specimens_jointly_qualified"]==0
    assert x["scientific_GO"] is False


def test_cross_paper_bulk_ohm_is_not_ionic_sigma_and_120_values_are_not_new_materials():
    x=s.analyze_actual_sources(*inputs())
    assert x["source2_published_original_bulk_R_number_of_numeric_values"]==120
    assert x["source2_nominal_compositions"]==10
    assert x["source2_measurement_unit"]=="BULK_RESISTANCE_OHM_NOT_SIGMA"
    assert x["source1_measurement_unit"]=="CONDUCTIVITY_S_PER_CM"
    assert x["sources_can_pool_into_single_conductivity_accuracy_target"] is False
    assert x["sources_are_two_papers_not_126_independent_new_materials"] is True
    assert x["source_external_prospective_blind"] is False
    assert x["MLIP_finite_T_ion_transport_executed"] is False
    assert [x[f"P0_0{i}"] for i in (1,2,3)]==["BLOCKED"]*3


@pytest.mark.parametrize("mutate",[
    lambda a,b:a.update({"source_DOI":"10.fake/external"}),
    lambda a,b:a.update({"experiment_observation_unit":"SIX_INDEPENDENT_MATERIALS"}),
    lambda a,b:a.update({"actual_independent_qualified_materials":6}),
    lambda a,b:a["six_original_public_process_condition_points"][0].update(
        {"original_measurement_temperature_C":150}),
    lambda a,b:a["six_original_public_process_condition_points"][1].update(
        {"source_ionic_conductivity_mS_per_cm":0.123}),
    lambda a,b:a["six_original_public_process_condition_points"][2].update(
        {"individual_sample_identifier_verified":True}),
    lambda a,b:a["six_original_public_process_condition_points"][3].update(
        {"admitted_as_material_level_transport_truth":True}),
    lambda a,b:b.update({"DOI":"10.fake/resistance"}),
    lambda a,b:b.update({"original_S17_canonical_numeric_table_SHA256":"0"*64}),
    lambda a,b:b["quantitative_physical_bulk_R_temperature_evidence"].update(
        {"R_bulk_ohm_NOT_S_per_cm":False}),
    lambda a,b:b["quantitative_physical_bulk_R_temperature_evidence"].update(
        {"individual_true_sample_labels_qualified":120}),
])
def test_fail_closed_on_falsified_primary_source_or_units(mutate):
    a,b=inputs();mutate(a,b)
    with pytest.raises(ValueError):
        s.analyze_actual_sources(a,b)


def test_live_builder_requires_both_genuine_source_pipelines(monkeypatch):
    a,b=inputs()
    monkeypatch.setattr(s.sulfide,"fetch_original_public_jats",lambda:(fixture(),sulf.SOURCE_URL))
    monkeypatch.setattr(s.kraft,"run_original",lambda:b)
    x=s.build_live_actual_original_report()
    assert x["source_papers"]==2
    assert x["physical_specimens_jointly_qualified"]==0
    assert x["source1_log10_S_per_cm_label_range"]>1.0
