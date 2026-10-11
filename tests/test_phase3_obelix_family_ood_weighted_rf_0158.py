"""0158 chemical family-out stress tests: synthetic controls, no source TEST."""
import json
import numpy as np
import pytest

from scripts.science.obelix_family_ood_weighted_rf_0158 import (
    SCHEMA, evaluate_original_family_out_0158,
    separate_family_with_group_embargo, paired_group_uncertainty,
)


def synthetic_sources():
    # Every row is synthetic. Two chemistry classes plus explicit halides.
    n=60
    fractions=np.zeros((n,118),dtype=float)
    raw=np.zeros((n,118),dtype=float)
    for i in range(n):
        raw[i,2]=1.0
        if i<30:
            raw[i,7]=2.0+i/50
        elif i<50:
            raw[i,15]=1.5+i/80
        else:
            raw[i,8]=1.8+i/60
    fractions=raw/raw.sum(axis=1,keepdims=True)
    geo=np.tile(np.asarray([225,5.0,5.2,5.5,90,90,90],dtype=float),(n,1))
    geo[:,1]+=np.arange(n)*0.002
    geo[3,1]=np.nan
    geo[42,0]=np.nan
    y=np.asarray([(-4+i/30 if i<30 else -6+(i-30)/10 if i<50
                   else -3+(i-50)/12) for i in range(n)],dtype=float)
    groups=tuple("group-"+str(i) for i in range(n))
    p={
        "original_official_test_reserved_unread":1,
        "original_source_train_count":60,
        "original_raw_censored_upper_bounds_excluded":0,
        "all_folds_have_zero_group_identity_leakage":True,
        "scientific_qualification_authorized":False,
        "out_of_fold_numeric_source_records_scored":n,
        "original_upstream_commit":"FAKE_FIXTURE_NO_ORIGINAL_SOURCE",
    }
    e={"x":fractions,"y":y,"groups":groups,
       "fold_indices":tuple(np.arange(i*12,(i+1)*12) for i in range(5))}
    return p,e,raw,geo


def test_0150_chemical_family_masks_and_comparator_exact_on_fixture():
    p,e,raw,geo=synthetic_sources()
    out=evaluate_original_family_out_0158(p,e,raw,geo,strict_official=False)
    assert out["schema_version"]==SCHEMA
    assert out["original_uncensored_numeric_source_rows"]==60
    assert out["original_public_TEST_reserved_unread"]==1
    assert not out["original_public_TEST_features_or_labels_used"]
    assert out["source_family_count_scored"]==3
    assert all(out["source_chemistry_transfer_by_family"][s]["status"]==
               "REAL_RETROSPECTIVE_CLASS_SHIFT_SCORED"
               for s in ("O_ONLY","S_ONLY","HALIDE_NO_O_S"))
    assert out["source_chemistry_transfer_by_family"]["O_AND_S"]["status"]!=\
           "REAL_RETROSPECTIVE_CLASS_SHIFT_SCORED"
    assert all((v["original_0150_RF_log10_MAE"] is None
                or np.isfinite(v["balanced_0158_RF_log10_MAE"]))
               for v in out["source_chemistry_transfer_by_family"].values())
    assert out["scientific_GO"] is False
    assert out["unqualified_default_model_adoption"] in (
        "BLOCKED_FAMILY_TRANSFER_UNSAFE","STILL_BLOCKED_PENDING_NEW_INDEPENDENT_BLIND")
    s=json.dumps(out)
    for forbidden in ("per_row_truth","private_features","source_ids",
                      "synthetic-secret-test","per_record_predictions"):
        assert forbidden not in s


def test_family_embargo_removes_other_class_rows_with_same_source_group():
    groups=("BRIDGE","BRIDGE","G2","G3","G4","G5","G6")
    labels=("O_ONLY","S_ONLY","O_ONLY","S_ONLY","S_ONLY","HALIDE_NO_O_S","S_ONLY")
    held,train,embargo=separate_family_with_group_embargo(groups,labels,"O_ONLY")
    assert list(held)==[0,2]
    assert 1 not in train and 3 in train
    assert embargo==1
    assert not set(groups[i] for i in held)&set(groups[i] for i in train)


def test_unequal_group_weights_fit_only_on_unseen_family_training_groups():
    p,e,raw,geo=synthetic_sources()
    groups=list(e["groups"])
    groups[31]=groups[32]
    e["groups"]=tuple(groups)
    out=evaluate_original_family_out_0158(p,e,raw,geo,strict_official=False)
    record=out["source_chemistry_transfer_by_family"]["O_ONLY"]
    assert record["train_only_source_group_weight_fitting"] is True
    assert record["weighted_train_fold_min"]<record["weighted_train_fold_max"]


def test_0158_fails_closed_on_production_TEST_cohort_or_source_claim():
    p,e,raw,geo=synthetic_sources()
    with pytest.raises(ValueError,match="official"):
        evaluate_original_family_out_0158(p,e,raw,geo)
    broken=dict(p)
    broken["scientific_qualification_authorized"]=True
    with pytest.raises(ValueError,match="TEST embargo"):
        evaluate_original_family_out_0158(broken,e,raw,geo,strict_official=False)


def test_invalid_chemistry_labels_or_numeric_rows_are_not_admitted():
    p,e,raw,geo=synthetic_sources()
    with pytest.raises(ValueError,match="unaligned"):
        separate_family_with_group_embargo(["A"],["B","C"],"S_ONLY")
    e=dict(e)
    y=e["y"].copy()
    y[1]=np.nan
    e["y"]=y
    with pytest.raises(ValueError,match="source descriptor"):
        evaluate_original_family_out_0158(p,e,raw,geo,strict_official=False)


def test_original_model_group_interval_is_heuristic_not_independent_samples():
    y=np.asarray([0.,0.,1.,1.,2.,2.])
    orig=np.asarray([2.,2.,0.,0.,1.,1.])
    weighted=np.asarray([1.,1.,2.,2.,0.,0.])
    g=tuple(["A","A","B","B","C","C"])
    stat=paired_group_uncertainty(y,orig,weighted,g,np.arange(6))
    assert stat["source_groups_are_independent_physical_experimental_samples"] is False
    assert len(stat["group_bootstrap_512_heuristic_95pct_interval"])==2
