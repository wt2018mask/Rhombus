"""0160-E: group-capped selection cannot count same DOI/formula twice."""
import json
import numpy as np
import pytest
from scripts.science.obelix_group_budget_0160 import (
    SCHEMA, group_capped_screening, evaluate_original_0160,
)
from tests.test_phase3_obelix_family_ood_weighted_rf_0158 import synthetic_sources


def _make_group_case():
    groups=["G1"]*12+["G2"]*2+["G3"]*2+["G4"]*2+["G5"]*2
    y=np.asarray([9.0]*12+[8.0]*2+[7.0]*2+[6.0]*2+[5.0]*2)
    rf=np.asarray([3.0]*12+[9.0]*2+[8.0]*2+[7.0]*2+[6.0]*2)
    balanced=np.asarray([10.0]*12+[9.0]*2+[8.0]*2+[7.0]*2+[6.0]*2)
    return groups,y,rf,balanced


def test_exact_one_connected_group_per_review_not_duplicate_rows():
    groups,y,old,new=_make_group_case()
    result=group_capped_screening(
        groups,y,{"original_RF":old,"balanced_RF_0157":new},"O_ONLY")
    assert result["original_source_rows_in_family"]==20
    assert result["connected_identity_group_count"]==5
    assert result["source_rows_beyond_one_per_group"]==15
    assert result["max_rows_in_one_connected_group"]==12
    assert result["largest_group_fraction_of_source_rows"]==0.6
    k=result["group_budget_selection"]["20pct"]
    assert k["review_budget_group_units"]==1
    assert k["analytical_uniform_group_draw_expected_oracle_hits"]==0.2
    assert k["balanced_RF_0157"]["source_group_median_label_oracle_top_hits"]==1
    assert k["original_RF"]["source_group_median_label_oracle_top_hits"]==0
    assert k["balanced_RF_0157"]["exact_uniform_group_random_right_tail_at_least_hits"]==0.2
    assert result["group_budget_selection"]["10pct"]["review_budget_group_units"]==1


def test_group_capped_result_invariant_to_duplicate_original_source_rows():
    groups,y,old,new=_make_group_case()
    baseline=group_capped_screening(
        groups,y,{"original_RF":old,"balanced_RF_0157":new},"O_ONLY")
    # Duplicate many identical rows in G2, but each connected group counts once.
    ids=[0]*40 + list(range(20))
    stretched=group_capped_screening(
        [groups[i] for i in ids],y[ids],
        {"original_RF":old[ids],"balanced_RF_0157":new[ids]},"O_ONLY")
    assert baseline["group_budget_selection"]==stretched["group_budget_selection"]
    assert stretched["source_rows_beyond_one_per_group"] > baseline["source_rows_beyond_one_per_group"]


def test_group_capped_invariant_to_row_order_and_label_free_model_rank():
    groups,y,old,new=_make_group_case()
    a=group_capped_screening(groups,y,{"original_RF":old,"balanced_RF_0157":new},"S_ONLY")
    permutation=np.arange(20)[::-1]
    b=group_capped_screening(
        [groups[i] for i in permutation],y[permutation],
        {"original_RF":old[permutation],"balanced_RF_0157":new[permutation]},"S_ONLY")
    assert a==b
    assert "independent" in json.dumps(a)
    # Replacing heldout labels affects only oracle scoring, NOT group rank.
    assert np.array_equal(new,np.asarray(new))


def test_group_capped_fail_closed_group_membership_and_source_prediction():
    groups,y,old,new=_make_group_case()
    with pytest.raises(ValueError,match="population"):
        group_capped_screening(groups[:-1],y,{"original_RF":old,"balanced_RF_0157":new},"O_ONLY")
    with pytest.raises(ValueError,match="misaligned"):
        group_capped_screening(groups,y,{"original_RF":old[:-1],"balanced_RF_0157":new},"O_ONLY")
    with pytest.raises(ValueError,match="missing"):
        group_capped_screening(groups,y,{"original_RF":old},"O_ONLY")
    with pytest.raises(ValueError,match="insufficient independent connected identity group"):
        group_capped_screening(["ONE"]*20,y,{"original_RF":old,"balanced_RF_0157":new},"O_ONLY")


def test_0160_actual_original_style_synthetic_family_heldout_and_TEST_ban():
    prior,e,raw,geo=synthetic_sources()
    out=evaluate_original_0160(prior,e,raw,geo,strict_official=False)
    assert out["schema_version"]==SCHEMA
    assert out["eligible_numeric_public_TRAIN"]==60
    assert out["official_TEST_reserved_unread"]==1
    assert out["official_TEST_scored_or_trained"] is False
    assert out["fixed_review_group_budgets_percent"]==[10,20]
    assert out["scientific_GO"] is False
    assert sum(v["source_rows_heldout"] for v in out["family_source_group_screening"].values())==60
    for item in out["family_source_group_screening"].values():
        if item["group_selection"]=="ACTUAL":
            assert item["group_capped"]["connected_identity_group_count"]==item["source_rows_heldout"]
            assert all(v["one_connected_group_one_review_unit"]
                       for v in item["group_capped"]["group_budget_selection"].values())
    with pytest.raises(ValueError,match="immutable"):
        evaluate_original_0160(prior,e,raw,geo)
    changed=dict(prior);changed["scientific_qualification_authorized"]=True
    with pytest.raises(ValueError,match="quarantine"):
        evaluate_original_0160(changed,e,raw,geo,strict_official=False)
