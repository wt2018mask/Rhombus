"""0183 anti-leakage tests for train-only distance and diagnostic-only new proxy."""
import numpy as np
import pytest
from scripts.science import obelix_solo_ood_distance_risk_0183 as m


def fixture():
    rng=np.random.default_rng(183)
    train=np.abs(rng.normal(.10,.07,size=(34,118)))
    held=np.abs(rng.normal(.12,.07,size=(20,118)))
    ids=tuple(f"G{i//2}" for i in range(20))
    y=rng.normal(-3,1.0,size=20)
    rf=y+.7
    mean=y+1.1
    std=np.linspace(.10,1.,20)
    return train,held,ids,y,rf,mean,std


def test_training_only_distance_has_fixed_proxy_and_finite_values():
    train,held,*_=fixture()
    a=m.nearest_training_composition_distance(train,held)
    b=m.nearest_training_composition_distance(train,held)
    assert np.all(a==b) and a.shape==(20,)
    assert np.all(np.isfinite(a)) and np.all(a>=0)
    # Every source row has distance zero when it is in its own TRAIN.
    assert np.allclose(m.nearest_training_composition_distance(train,train),0,atol=1e-9)
    assert m.SCALE_FLOOR==.02 and m.BATCH_ROWS==64


def test_group_ranking_is_model_only_not_labels():
    train,held,ids,y,rf,mean,std=fixture()
    d=m.nearest_training_composition_distance(train,held)
    a=m.score_source_family(ids,y,rf,mean,std,d,name="O_ONLY")
    b=m.score_source_family(ids,y+17,rf,mean,std,d,name="O_ONLY")
    assert set(a["methods"])==set(m.METHODS)
    assert set(a["methods"]["EQUAL_RANK_FUSION"]["risk_coverage"])=={"60pct","80pct"}
    assert a["source_connected_groups"]==10
    for method in m.METHODS:
        for key in ("60pct","80pct"):
            x=a["methods"][method]["risk_coverage"][key]
            z=b["methods"][method]["risk_coverage"][key]
            assert x["selected_source_rows"]==z["selected_source_rows"]
            assert x["selected_source_connected_groups"]==z["selected_source_connected_groups"]
            assert not x["selection_uses_original_heldout_labels"]


def test_forged_source_descriptors_bad_label_or_negative_variance_denied():
    train,held,ids,y,rf,mean,std=fixture()
    with pytest.raises(ValueError):
        m.nearest_training_composition_distance(train[:2],held)
    train[0,4]=np.nan
    with pytest.raises(ValueError):
        m.nearest_training_composition_distance(train,held)
    train,held,ids,y,rf,mean,std=fixture()
    d=m.nearest_training_composition_distance(train,held)
    std[0]=-1
    with pytest.raises(ValueError):
        m.score_source_family(ids,y,rf,mean,std,d,name="O_ONLY")
    with pytest.raises(ValueError):
        m.score_source_family(ids,y,rf,mean,std,d,name="FAKE")


def test_same_original_0182_RF_risk_not_replaced_by_new_model():
    train,held,ids,y,rf,mean,std=fixture()
    d=m.nearest_training_composition_distance(train,held)
    a=m.score_source_family(ids,y,rf,mean,std,d,name="O_ONLY")
    from scripts.science.obelix_solo_family_out_risk_0182 import select_family_groups
    b=select_family_groups(ids,y,rf,mean,std)
    for key in ("60pct","80pct"):
        assert a["methods"]["RF_TREE_STD"]["risk_coverage"][key]["selected_RF_macro_group_MAE"]==b["risk_coverage"][key]["selected_RF_group_MAE"]
    assert a["no_heldout_labels_in_distance_or_uncertainty_or_fusion_rank"]
    assert a["no_same_physical_specimen_asserted"]
