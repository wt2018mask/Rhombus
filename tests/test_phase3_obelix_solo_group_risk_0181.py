"""0181: no TRAIN/TEST leakage, no physically false uncertainty claims."""
import math
import numpy as np
import pytest
from scripts.science import obelix_solo_group_risk_0181 as m


def public_fixture():
    # 16 fake groups, deliberately unbalanced row sizes, not source secrets.
    g=[f"fixture{i:02d}" for i in range(16)]
    sizes=[1,2,5,8]*4
    groups=tuple(name for name,k in zip(g,sizes) for _ in range(k))
    y=np.arange(len(groups),dtype=float)/13.0
    mean=y+1.5
    rf=y+np.where(np.arange(len(y))%2,0.6,1.1)
    uncertainty=np.linspace(.03,2,len(y))
    return y,mean,rf,uncertainty,groups

def test_group_scoped_stable_no_pellet_inference():
    y,mean,rf,u,g=public_fixture()
    a=m.risk_and_size_report(y,mean,rf,u,g,[1,3,4,4,4])
    b=m.risk_and_size_report(y,mean,rf,u,g,[1,3,4,4,4])
    assert a==b
    assert a["source_connected_groups"]==16
    assert a["group_size_distribution"]["largest_connected_group_rows"]==8
    assert sum(v["source_connected_groups"] for v in a["group_size_strata"].values())==16
    assert set(a["risk_coverage"])=={"60pct","80pct"}
    assert all(x["blind_uniform_group_selection_trials"]==128 for x in a["risk_coverage"].values())
    assert all(x["selected_using_RF_tree_disagreement_NO_public_holdout_labels"] for x in a["risk_coverage"].values())
    assert a["RF_ensemble_tree_std_NOT_validated_uncertainty_probability"]
    assert a["solo_public_risk_diagnostic"] in {
        "PASS_RETROSPECTIVE_GROUP_RISK_SIGNAL_ONLY",
        "FAIL_NO_RELIABLE_SOURCE_GROUP_RISK_SIGNAL",
        "INCONCLUSIVE_PUBLIC_GROUP_RISK_DIAGNOSTIC"
    }

def test_unsafe_original_arrays_rejected():
    y,mean,rf,u,g=public_fixture()
    for candidate in ((y,mean,rf[:-1],u,g),(y,mean,rf,np.full(len(y),np.nan),g),
                      (y,mean,rf,np.full(len(y),-2.),g)):
        with pytest.raises(ValueError):m.risk_and_size_report(*candidate,[1,3,4,4,4])
    with pytest.raises(ValueError):m.risk_and_size_report(y,mean,rf,u,g[:-1],[1,3,4,4,4])

def test_group_coverage_is_not_row_coverage_or_confident_physical_specimens():
    y,mean,rf,u,g=public_fixture()
    result=m.risk_and_size_report(y,mean,rf,u,g,[1,3,4,4,4])
    assert result["risk_coverage"]["60pct"]["selected_connected_groups"]==math.ceil(16*.60)
    assert result["risk_coverage"]["80pct"]["selected_connected_groups"]==math.ceil(16*.80)
    assert result["risk_coverage"]["60pct"]["selected_public_source_rows"]>=10
    assert result["risk_coverage"]["60pct"]["selected_public_source_rows"]!=int(.6*len(y))
    assert all(v["selected_rows_are_NOT_independent_pellets"] for v in result["risk_coverage"].values())

def test_rank_ties_constant_proxy_has_no_fabricated_correlations():
    assert m._rank_correlation([1]*20,list(range(20))) is None
    assert m._rank_correlation(list(range(20)),list(range(20)))==1.0
    assert m._rank_correlation(list(range(20)),list(range(19,-1,-1)))==-1.0
    with pytest.raises(ValueError):m._rank_correlation([1]*3,[1]*3)

def test_original_0147_frozen_RF_constants_and_published_train_only_guard():
    from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
    assert m.RF_PARAMS is RF_PARAMS
    assert m.RF_EXPECTED_MAE==1.94487886
    assert m.MEAN_EXPECTED_MAE==1.86702336
    assert m.RF_EXPECTED_MACRO==1.90046024
    assert m.MEAN_EXPECTED_MACRO==2.26818583
    assert m.COVERAGES==(0.60,0.80)
    assert m.BLIND_SEEDS==128
