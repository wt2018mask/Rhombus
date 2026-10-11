"""0159 science controls: frozen equal-budget material screening and label-blind abstention."""
import json
import numpy as np
import pytest

from scripts.science.obelix_budget_selective_0159 import (
    SCHEMA, chemical_train_similarity, stable_blind_rank, screening_at_budgets,
    selective_risk, evaluate_original_0159,
)
from tests.test_phase3_obelix_family_ood_weighted_rf_0158 import synthetic_sources


def test_chemistry_support_uses_training_composition_only():
    a=np.zeros((3,118));b=np.zeros((2,118))
    a[0,7]=1;a[1,15]=1;a[2,8]=1
    b[0,7]=1;b[1,15]=0.5;b[1,7]=0.5
    v=chemical_train_similarity(a,b)
    assert v[0]==pytest.approx(1)
    assert v[1]==pytest.approx(2**-0.5)
    with pytest.raises(ValueError):
        chemical_train_similarity(a,np.zeros((2,118)))


def test_fixed_budget_10_and_20_percent_rank_known_true_highest():
    truth=np.arange(20,dtype=float)
    prediction=truth.copy()
    out=screening_at_budgets(truth,{"original_RF":prediction},"S_ONLY")
    assert set(out)=={"10pct","20pct"}
    assert out["10pct"]["original_RF"]["selected_original_source_rows"]==2
    assert out["10pct"]["original_RF"]["source_oracle_recall_at_budget"]==1
    assert out["20pct"]["original_RF"]["source_oracle_recall_at_budget"]==1
    assert "blind_random_order" in out["10pct"]
    assert np.array_equal(stable_blind_rank(20,"S_ONLY"),stable_blind_rank(20,"S_ONLY"))
    assert not np.array_equal(stable_blind_rank(20,"O_ONLY"),stable_blind_rank(20,"S_ONLY"))


def test_label_blind_support_and_disagreement_risk_curve():
    tr=np.zeros((15,118));tr[:,7]=1
    te=np.zeros((12,118));te[:6,7]=1;te[6:,15]=1
    y=np.arange(12,dtype=float)
    pred=np.zeros(12)
    trees=np.asarray([np.arange(12)*.05,np.arange(12)*-.05,
                      np.arange(12)*.01,np.arange(12)*-.01])
    risk=selective_risk(y,pred,tr,te,trees,"O_ONLY")
    assert risk["support_and_uncertainty_score_depend_on_heldout_labels"] is False
    assert risk["trained_RF_num_trees"]==4
    assert set(risk["coverage_curves"])=={"25pct","50pct","75pct"}
    for coverage,expected in (("25pct",3),("50pct",6),("75pct",9)):
        for method in risk["coverage_curves"][coverage].values():
            assert method["source_rows_accepted"]==expected
            assert method["source_rows_abstained"]==12-expected


def test_0159_original_family_exclusion_and_source_test_prohibition():
    prior,ephemeral,raw,geo=synthetic_sources()
    d=evaluate_original_0159(prior,ephemeral,raw,geo,strict_official=False)
    assert d["schema_version"]==SCHEMA
    assert d["original_uncensored_numeric_source_rows"]==60
    assert d["original_public_TEST_reserved_unread"]==1
    assert d["original_public_TEST_training_or_scoring"] is False
    assert d["screening_budgets_percent"]==[10,20]
    assert d["selective_acceptance_percent"]==[25,50,75]
    assert sum(q["heldout_rows"] for q in d["family_results"].values())==60
    assert all("screening_budget_top_conductivity" in q for q in d["family_results"].values()
               if q["state"]=="ACTUAL_BUDGET_SCORING")
    assert d["scientific_GO"] is False
    assert all(d[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))
    output=json.dumps(d)
    assert "per_record_prediction" not in output
    assert "per_record_true_label" not in output
    with pytest.raises(ValueError,match="pinned"):
        evaluate_original_0159(prior,ephemeral,raw,geo,strict_official=True)


def test_0159_source_qualification_must_never_be_promoted():
    prior,ephemeral,raw,geo=synthetic_sources()
    fake=dict(prior);fake["scientific_qualification_authorized"]=True
    with pytest.raises(ValueError,match="gate"):
        evaluate_original_0159(fake,ephemeral,raw,geo,strict_official=False)
    bad=dict(ephemeral);labels=bad["y"].copy();labels[2]=float("nan")
    bad["y"]=labels
    with pytest.raises(ValueError,match="numerical source"):
        evaluate_original_0159(prior,bad,raw,geo,strict_official=False)
