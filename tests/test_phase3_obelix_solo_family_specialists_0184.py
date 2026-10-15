"""0184 family-specialist experiment: group leaks, failures and no domain GO."""
import numpy as np
import pytest
from scripts.science import obelix_solo_family_specialists_0184 as m


def test_balanced_outer_folds_do_not_split_source_identity():
    groups=tuple(f"group-{i//3}" for i in range(60))
    ids=np.arange(60,dtype=int)
    folds=m.connected_group_folds(ids,groups)
    assert len(folds)==5
    assert sorted(i for fold in folds for i in fold.tolist())==list(range(60))
    for fold in folds:
        held=set(groups[i] for i in fold)
        remain=set(groups[i] for i in ids if i not in set(fold.tolist()))
        assert not held&remain
    assert [x.tolist() for x in folds]==[x.tolist() for x in m.connected_group_folds(ids,groups)]


def test_bad_connected_family_population_rejected():
    with pytest.raises(ValueError):
        m.connected_group_folds(np.arange(8),tuple("same" for _ in range(8)))
    with pytest.raises(ValueError):
        m.source_scores(np.array([1.,2.]),np.array([1.]),["a","b"])
    with pytest.raises(ValueError):
        m.source_scores(np.array([1.,2.]),np.array([np.nan,2.]),["a","b"])


def test_predeclared_supported_scope_and_threshold_not_fit_from_outer_error():
    assert m.TARGETS==("O_ONLY","S_ONLY")
    assert m.FOLDS==5
    assert m.MODEL_NAMES==("POOLED_RF","FAMILY_RF","FAMILY_RIDGE","FAMILY_TRAIN_MEAN")
    assert m.RIDGE_ALPHA==10.
    assert m.ABSOLUTE_GROUP_MAE_CANDIDATE_THRESHOLD==1.
    assert m.BOOTSTRAPS==512
    from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
    assert m.RF_PARAMS is RF_PARAMS


def test_group_delta_not_per_sample_physical_bootstrap():
    y=np.arange(30,dtype=float)
    ids=[f"g{i//3}" for i in range(30)]
    rf=y+.5
    mean=y+1.5
    r=m.paired_group_delta(y,rf,mean,ids)
    assert r["number_of_connected_source_groups"]==10
    assert r["family_specialist_minus_reference_group_macro_MAE"]<0
    assert r["heuristic_group_bootstrap_95pct_interval"][1]<0
    assert r["diagnostic_NOT_independent_physical_experimental_CI"]


def test_original_fraction_presence_proxy_is_not_crystal_phase():
    from scripts.science.obelix_group_failure_audit_0148 import ANION_PROXY_BINS
    assert len(ANION_PROXY_BINS)==5
    assert m.TARGETS[0] in ANION_PROXY_BINS
    assert m.TARGETS[1] in ANION_PROXY_BINS
