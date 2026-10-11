"""0157 balanced source-group RF diagnostics and fail-closed source boundaries."""
import json
import numpy as np
import pytest

from scripts.science.obelix_balanced_rf_0157 import (
    train_only_group_weights, evaluate_balanced_rf,
)
from scripts.science.obelix_original_author_features_0149 import (
    evaluate_predeclared_author_features,
)
from tests.test_phase3_obelix_author_features_0149 import load_fixture


def test_large_connected_source_group_shrinks_weights_train_only():
    groups=["major"]*16+["minor"]*4+["future"]*4
    train=np.arange(20)
    weights=train_only_group_weights(groups,train)
    assert len(weights)==20 and np.isfinite(weights).all()
    assert abs(np.mean(weights)-1)<1e-10
    assert weights[0]<weights[17]
    # Heldout-only group exists but must not affect weight fitting.
    extended=groups+["future"]*100
    assert np.allclose(weights,train_only_group_weights(extended,train))


def test_invalid_training_index_or_duplicate_refused():
    groups=["A","A","B","C"]
    with pytest.raises(ValueError):
        train_only_group_weights(groups,[0,0,2])
    with pytest.raises(ValueError):
        train_only_group_weights(groups,[0,4])
    with pytest.raises(ValueError):
        train_only_group_weights(groups,[0,1])


def _synthetic(tmp_path):
    _,prior,ephemeral,baseline,raw,geometry=load_fixture(tmp_path)
    source, preds=evaluate_predeclared_author_features(
        prior,ephemeral,baseline,raw,geometry,return_internal=True)
    original=preds["raw_stoichiometry_plus_seven_lattice_spacegroup"]["RF"]
    return prior,ephemeral,source,original,raw,geometry


def test_original_frozen_fold_source_rf_training_weights_identical_for_equal_groups(tmp_path):
    p,e,s,old,raw,geo=_synthetic(tmp_path)
    report=evaluate_balanced_rf(p,e,s,old,raw,geo,strict_official=False)
    assert report["real_numeric_source_rows"]==35
    assert report["source_DOI_formula_connected_groups"]==35
    assert report["original_public_TEST_reserved_unread"]==1
    assert report["original_public_TEST_predictions"]==0
    assert report["all_real_original_TRAIN_out_of_fold_predictions_one_each"]==35
    assert report["new_weighted_minus_existing_geometry_RF_record_MAE"]==0.0
    assert report["weight_exponent_frozen"]==0.5
    assert report["original_exact_five_0146_DOI_formula_folds_reused"] is True
    assert report["scientific_GO"] is False
    assert all(report[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))
    assert "source_ids" not in json.dumps(report) and "per_record_predictions" not in json.dumps(report)


def test_group_identity_leakage_must_fail(tmp_path):
    p,e,s,old,raw,geo=_synthetic(tmp_path)
    changed=dict(e)
    groups=list(e["groups"])
    i=int(e["fold_indices"][0][0])
    j=int(e["fold_indices"][1][0])
    groups[i]=groups[j]
    changed["groups"]=tuple(groups)
    with pytest.raises(ValueError,match="leakage"):
        evaluate_balanced_rf(p,changed,s,old,raw,geo,strict_official=False)


def test_official_population_cannot_be_synthetic_in_production(tmp_path):
    p,e,s,old,raw,geo=_synthetic(tmp_path)
    with pytest.raises(ValueError,match="TEST leakage"):
        evaluate_balanced_rf(p,e,s,old,raw,geo)


def test_prior_model_source_predictions_cannot_be_modified(tmp_path):
    p,e,s,old,raw,geo=_synthetic(tmp_path)
    modified=old.copy()
    modified[0]+=100
    with pytest.raises(ValueError,match="previous|unaligned|prior"):
        evaluate_balanced_rf(p,e,s,modified,raw,geo,strict_official=False)
