"""0168 fixed-algorithm actual source-process LOO and scientific false-promotion tests."""
import math
import pytest
from scripts.science import original_process_holdout_0168 as m


def original():
    points=[{
        "source_condition_index":i+1,
        "heat_treatment_C_not_measurement_temperature":t,
        "source_ionic_conductivity_mS_per_cm":sigma,
        "original_measurement_temperature_C":25,
        "green_compact_pressing_MPa":720,
        "individual_sample_identifier_verified":False,
        "admitted_as_material_level_transport_truth":False,
    } for i,(t,sigma) in enumerate(zip(
        m.y.EXPECTED_PROCESS_T_C,m.y.EXPECTED_SIGMA_MSCM))]
    return {
        "source_DOI":m.y.ORIGINAL_DOI,"source_PMCID":m.y.SOURCE_PMCID,
        "experiment_observation_unit":"HEAT_TREATMENT_PROCESS_CONDITION_OF_Li6PS5Br_MATERIAL",
        "actual_quantitative_table_condition_rows":6,"conductivity_temperature_C":25,
        "actual_independent_qualified_materials":0,"scientific_GO":False,
        "six_original_public_process_condition_points":points,
    }


def test_original_jats_six_condition_actual_values_and_LOO_no_external_pretence():
    x,y=m._admit_original(original())
    a=m.folded_predictions(x,y)
    assert a["fold_training_row_count"]==5
    assert a["rows_evaluated_as_retrospective_LOO"]==6
    assert a["independent_material_compositions"]==1
    assert a["no_heldout_source_label_in_any_fit"] is True
    assert a["exploratory_source_selected_after_public_labels_seen"] is True
    assert a["within_one_paper_LOO_not_blind_material_generalization"] is True
    assert a["not_a_causal_effect_of_heat_treatment"] is True
    assert a["chemistry_only_five_fold_train_median_LOO_MAE_log10_S_per_cm"]==0.55728689
    assert a["process_temp_five_fold_train_OLS_LOO_MAE_log10_S_per_cm"]==0.13095762
    assert a["process_OLS_minus_chemistry_median_MAE"]<0
    assert a["process_temp_OLS_relative_MAE_reduction_over_training_median"]==0.76500861
    assert a["five_row_treatment_slope_positive_each_fold"]


def test_frozen_original_temperature_of_ionic_measurement_not_heat_treatment():
    a=original()
    a["six_original_public_process_condition_points"][3]["original_measurement_temperature_C"]=400
    with pytest.raises(ValueError,match="measurement T"):
        m._admit_original(a)
    a=original()
    a["conductivity_temperature_C"]=550
    with pytest.raises(ValueError,match="measured 25 C"):
        m._admit_original(a)


def test_reject_pretend_independent_pellet_or_cherry_picked_source_paper():
    for key,val in [
        ("actual_independent_qualified_materials",6),
        ("scientific_GO",True),
        ("source_DOI","10.fake/2019")]:
        z=original()
        z[key]=val
        with pytest.raises(ValueError,match="identity drift"):
            m._admit_original(z)
    z=original()
    z["six_original_public_process_condition_points"][2]["individual_sample_identifier_verified"]=True
    with pytest.raises(ValueError,match="physical pellet"):
        m._admit_original(z)


def test_value_or_treatment_mutation_forbidden_without_paper_revision():
    z=original()
    z["six_original_public_process_condition_points"][4]["source_ionic_conductivity_mS_per_cm"]=1.25
    with pytest.raises(ValueError,match="data values"):
        m._admit_original(z)
    z=original()
    z["six_original_public_process_condition_points"][1]["heat_treatment_C_not_measurement_temperature"]=201
    with pytest.raises(ValueError,match="data values"):
        m._admit_original(z)


def test_heldout_predictions_are_not_median_of_six_including_truth():
    x,y=m._admit_original(original())
    result=m.folded_predictions(x,y)
    # Six-point retrospective median fitted ON all labels is misleadingly better.
    all_six_fit_mae=sum(abs(v-__import__("statistics").median(y)) for v in y)/6
    assert all_six_fit_mae<result["chemistry_only_five_fold_train_median_LOO_MAE_log10_S_per_cm"]
    assert math.isclose(all_six_fit_mae,0.37447227,abs_tol=1e-8)


def test_limited_six_point_population_no_fabricated_materials_or_unchecked_nonfinite():
    x,y=m._admit_original(original())
    for i in (0,1,3,5):
        wrong=list(y)
        wrong[i]=float("inf")
        with pytest.raises(ValueError,match="six finite"):
            m.folded_predictions(x,wrong)
    with pytest.raises(ValueError,match="six finite"):
        m.folded_predictions(x,[0,1,2,3,4])
    xx=list(x);xx[0]=xx[1]
    with pytest.raises(ValueError,match="six finite"):
        m.folded_predictions(xx,y)
