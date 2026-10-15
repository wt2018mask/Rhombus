"""0182: fixed family embargo + zero posthoc heldout-label selection tests."""
import numpy as np
import pytest
from scripts.science import obelix_solo_family_out_risk_0182 as s

def make_source():
    y=np.linspace(-5,-1,30)
    g=tuple(f"source-{i//2}" for i in range(30))
    rf=y+np.where(np.arange(30)%2,.5,1.5)
    mean=y+1.
    uncertainty=np.linspace(.1,2,30)
    return g,y,rf,mean,uncertainty

def test_group_risk_selects_equal_groups_no_outcome_in_rank():
    g,y,rf,mean,unc=make_source()
    a=s.select_family_groups(g,y,rf,mean,unc)
    b=s.select_family_groups(g,y,rf,mean,unc)
    assert a==b
    assert a["heldout_connected_groups"]==15
    assert set(a["risk_coverage"])=={"60pct","80pct"}
    assert a["risk_coverage"]["60pct"]["selected_connected_groups"]==9
    assert a["risk_coverage"]["80pct"]["selected_connected_groups"]==12
    assert all(x["blind_uniform_draws"]==128 for x in a["risk_coverage"].values())
    assert all(x["selection_predetermined_by_RF_dispersion_NOT_heldout_labels"] for x in a["risk_coverage"].values())
    assert all(x["source_group_coverage_not_physical_material_fraction"] for x in a["risk_coverage"].values())

def test_y_truth_changing_does_not_change_model_only_group_selection():
    g,y,rf,mean,unc=make_source()
    a=s.select_family_groups(g,y,rf,mean,unc)
    b=s.select_family_groups(g,y+5,rf,mean,unc)
    for cov in ("60pct","80pct"):
        assert a["risk_coverage"][cov]["selected_connected_groups"]==b["risk_coverage"][cov]["selected_connected_groups"]
        assert a["risk_coverage"][cov]["selected_source_rows"]==b["risk_coverage"][cov]["selected_source_rows"]

@pytest.mark.parametrize("bad",["nan","negative","missing","tiny"])
def test_source_errors_fail_closed(bad):
    g,y,rf,mean,unc=make_source()
    if bad=="nan":rf[0]=np.nan
    elif bad=="negative":unc[0]=-1
    elif bad=="missing":g=g[:-1]
    else:g=tuple("shared" for _ in y)
    with pytest.raises(ValueError):s.select_family_groups(g,y,rf,mean,unc)

def test_predeclared_anion_family_proxy_and_original_0158_embargo():
    from scripts.science.obelix_family_ood_weighted_rf_0158 import separate_family_with_group_embargo
    from scripts.science.obelix_group_failure_audit_0148 import ANION_PROXY_BINS
    assert len(ANION_PROXY_BINS)==5
    groups=["A","A","B","C","D","E","F"]
    labels=["O_ONLY","S_ONLY","O_ONLY","S_ONLY","S_ONLY","HALIDE_NO_O_S","S_ONLY"]
    held,train,removed=separate_family_with_group_embargo(groups,labels,"O_ONLY")
    assert list(held)==[0,2]
    assert 1 not in train and removed==1
    assert not set(groups[i] for i in held)&set(groups[i] for i in train)

def test_no_blind_claim_or_unfrozen_new_weights():
    from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
    assert s.RF_PARAMS is RF_PARAMS
    assert s.COVERAGES==(.60,.80)
    assert s.BLIND_TRIALS==128
    assert s.MIN_CLASS_ROWS==10
    assert s.MIN_CLASS_GROUPS==3
