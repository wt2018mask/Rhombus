"""0189 deterministic lower-bound mathematics and source leakage regression."""
import math
import pytest
from scripts.science import obelix_solo_oxide_process_identifiability_0189 as m

def scores(row,macro):
    return {name:{"row_MAE_log10":row,"equal_DOI_macro_MAE_log10":macro} for name in m.MODEL_NAMES}

def test_weighted_median_exact_L1_and_nonfinite_denied():
    assert m.weighted_median_objective([(0.,1.),(1.,1.),(10.,1.)])==(10.,1.)
    loss,med=m.weighted_median_objective([(0.,10.),(2.,1.)])
    assert med==0. and loss==2.
    with pytest.raises(ValueError):m.weighted_median_objective([(math.nan,1.)])
    with pytest.raises(ValueError):m.weighted_median_objective([(1.,0.)])

def fixture_rows():
    # 22 conditions, 5 original DOI IDs; same nominal formula in 20 cases.
    rows=[]
    for d,n in zip(m.ALL_DOIS,m.SIZES):
        for j in range(n):
            formula="Li6.4Al0.2La3Zr2O12" if j else "Li6.5La3Zr1.5Ta0.5O12"
            sig=10**(-4-(j%3)/2)
            rows.append((d,f"{d}:{j}",formula,sig))
    return rows

def test_mathematical_oracle_is_only_an_in_sample_lower_bound():
    z=m.audit_process_identifiability(fixture_rows(),scores(2.,2.))
    assert z["source_reference_conditions"]==22
    assert z["original_DOI_groups"]==5
    assert z["distinct_nominal_reduced_formulas"]==2
    assert z["nominal_formulas_with_nonidentical_target_values"]>=1
    assert z["row_MAE_best_truth_selected_composition_constant_lower_bound_log10"]>0
    assert z["equal_DOI_macro_MAE_best_truth_selected_composition_constant_lower_bound_log10"]>0
    assert z["oracle_uses_all_external_truth_NO_valid_out_of_sample_prediction"]
    assert z["process_metadata_required_for_state_specific_output_but_gain_unproven"]

def test_swapping_source_labels_does_not_fake_DOI_independence():
    rows=fixture_rows()
    rows[0]=("10.1234/other",rows[0][1],rows[0][2],rows[0][3])
    with pytest.raises(ValueError,match="DOI"):m.audit_process_identifiability(rows,scores(2.,2.))

def test_invalid_author_conductivity_and_nonoxide_fail_closed():
    rows=fixture_rows()
    rows[1]=(rows[1][0],rows[1][1],rows[1][2],0)
    with pytest.raises(ValueError):m.audit_process_identifiability(rows,scores(2.,2.))
    rows=fixture_rows()
    rows[2]=(rows[2][0],rows[2][1],"Li6PS5Cl",rows[2][3])
    with pytest.raises(ValueError):m.audit_process_identifiability(rows,scores(2.,2.))

def test_model_score_population_and_nonnegative_oracle_gap():
    rows=fixture_rows()
    with pytest.raises(ValueError,match="identities"):
        m.audit_process_identifiability(rows,{"O_ONLY_RF":{}})
    with pytest.raises(ValueError,match="lower bound exceeded"):
        m.audit_process_identifiability(rows,scores(0.,0.))

def test_0188_original_input_population_and_DOI_are_frozen():
    assert m.SIZES==(2,6,5,5,4)
    assert len(m.ALL_DOIS)==5 and m.EXPECTED_ROWS==22
    assert m.EXPECTED_DOIS==5
    assert m.SCHEMA.startswith("rhombus-0189")
    assert m.SOURCE_COMMIT
