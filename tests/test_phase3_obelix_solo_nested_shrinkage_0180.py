"""0180 training-only nested shrinkage and scientific negative eligibility."""
import numpy as np
import pytest
from scripts.science import obelix_solo_nested_shrinkage_0180 as m

def toy_data(seed=180):
    rng=np.random.default_rng(seed)
    x=rng.normal(size=(36,118))
    y=np.arange(36,dtype=float)/4+rng.normal(size=36)
    groups=tuple(f"g{i//3}" for i in range(36))
    return x,y,groups

def test_inner_calibration_source_groups_frozen_and_no_outer_truth_input():
    x,y,g=toy_data()
    f=m.inner_assignments(g)
    assert len(f)==3
    assert sorted(i for fold in f for i in fold)==list(range(len(y)))
    a,b=m.choose_weight_from_inner_groups(x,y,g)
    a2,b2=m.choose_weight_from_inner_groups(x,y,g)
    assert a in m.WEIGHTS and a==a2 and b==b2
    assert all(x>0 for x in b["inner_group_count_per_fold"])
    assert b["inner_group_identity_overlap"]==0
    assert b["label_access"]=="OUTER_TRAIN_ONLY_INNER_GROUP_CV"

def test_paired_group_bootstrap_is_not_independent_pellet_evidence():
    x,y,g=toy_data()
    mean=np.full(len(y),np.mean(y))
    rf=mean+0.5
    shrink=mean+0.25
    r=m.paired_group_comparison(y,shrink,mean,rf,g)
    assert r["source_group_count"]==12
    assert r["bootstrap_is_heuristic_shared_source_DOI_groups_NOT_individual_pellets"]
    assert len(r["group_bootstrap_delta_95pct_interval"])==2
    assert (r["source_groups_where_shrink_beats_mean"]+
            r["source_groups_tied_with_mean"]+
            r["source_groups_where_shrink_worse_than_mean"])==12

def test_source_identity_leakage_and_nonfinite_array_rejected():
    x,y,g=toy_data()
    with pytest.raises(ValueError):m.choose_weight_from_inner_groups(x[:8],y[:8],g[:8])
    xx=x.copy();xx[1,10]=np.nan
    with pytest.raises(ValueError):m.choose_weight_from_inner_groups(xx,y,g)
    with pytest.raises(ValueError):m.paired_group_comparison(
        y,np.zeros(36),np.zeros(36),np.zeros(35),g)

def test_candidates_and_frozen_0147_rf_identical():
    from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
    assert m.RF_PARAMS is RF_PARAMS
    assert m.WEIGHTS==(0,0.25,0.50,0.75,1)
    assert m.INNER_FOLDS==3
    assert m.BOOTSTRAPS==512


def test_group_fold_assignments_are_permutation_of_train_identity_only():
    x,y,g=toy_data()
    a=m.inner_assignments(g)
    b=m.inner_assignments(g)
    assert all(np.array_equal(i,j) for i,j in zip(a,b))
    # Group folding depends on ID, not label or feature values.
    assert all(np.array_equal(i,j) for i,j in zip(a,m.inner_assignments(g)))
