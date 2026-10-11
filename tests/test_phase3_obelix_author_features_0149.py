"""Synthetic anti-leakage regression for 0149 posthoc author-feature study."""
import csv
import hashlib
import json

import numpy as np
import pytest

from tests.test_phase3_rf_mlp_frozen_group_oof_0147 import synthetic_evaluation
from tests.test_phase3_obelix_real_grouped_oof_0146 import fixture
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import evaluate_frozen_baselines
from scripts.science.obelix_original_author_features_0149 import (
    ARMS,GEOMETRY_FIELDS,_parse_source_field,_fold_impute_geometry,
    evaluate_predeclared_author_features,load_original_train_features,
)


def source_csv(tmp_path, *, corrupt_test=True):
    records,_=fixture()
    original=tmp_path/"original"
    (original/"data").mkdir(parents=True)
    path=original/"data"/"processed.csv"
    fields=["ID","Composition",*GEOMETRY_FIELDS]
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for i,row in enumerate(records):
            if row["official_split"] == "TEST":
                # Parser may read only TEST ID, not any corrupted feature field.
                writer.writerow({"ID":row["source_entry_id"],"Composition":"TEST_NOT_SAFE_TO_PARSE",
                    **{field:"bad-TEST-payload" for field in GEOMETRY_FIELDS}})
            else:
                writer.writerow({"ID":row["source_entry_id"],"Composition":row["reported_composition"],
                    "Space group number": "225" if i%2 else "",
                    "a": "5.1" if i%2 else "nan",
                    "b":"5.3","c":"7.1","alpha":"90","beta":"90","gamma":"90"})
    return original,hashlib.sha256(path.read_bytes()).hexdigest()


def load_fixture(tmp_path):
    prior, ephemeral=synthetic_evaluation()
    base=evaluate_frozen_baselines(prior,ephemeral)
    original,digest=source_csv(tmp_path)
    raw,geom=load_original_train_features(
        original,source_ids=ephemeral["source_ids"],
        expected_processed_sha256=digest,
        reference_fractions=ephemeral["x"],
    )
    return original,prior,ephemeral,base,raw,geom


def test_original_row_ids_match_0146_true_private_folds(tmp_path):
    original,prior,ephemeral,base,raw,geom=load_fixture(tmp_path)
    assert raw.shape==(35,118)
    assert geom.shape==(35,7)
    assert np.isnan(geom[:,0]).any()
    assert np.isfinite(geom[:,2:]).all()
    assert len(ephemeral["source_ids"])==35
    assert "nevertest" not in ephemeral["source_ids"]
    assert prior["original_official_test_reserved_unread"]==1


def test_actual_synthetic_fixed_fold_feature_predictions_not_independent_science(tmp_path):
    original,prior,ephemeral,base,raw,geo=load_fixture(tmp_path)
    report=evaluate_predeclared_author_features(prior,ephemeral,base,raw,geo)
    assert report["real_source_numeric_rows_scored_per_model"]==35
    assert report["connected_source_DOI_formula_groups"]==35
    assert report["official_public_TEST_reserved_unread"]==1
    assert report["official_public_TEST_predictions"]==0
    assert report["original_exact_0146_fold_assignments_reused"] is True
    assert report["two_predeclared_feature_arms"]==list(ARMS)
    assert len(report["per_fold_scores"])==5
    assert sum(f["heldout_source_records"] for f in report["per_fold_scores"])==35
    assert report["train_only_median_geometry_imputation_and_MLP_feature_scaling"] is True
    assert report["original_author_paper_exact_feature_tuning_cv_reproduction"] is False
    assert report["unseen_fresh_holdout_evaluated"] is False
    assert report["science_go"] is False
    assert all(report[f"P0_0{i}_status"]=="BLOCKED" for i in (1,2,3))
    for arm in ARMS:
        for model in ("RF","MLP"):
            assert np.isfinite(report["actual_oof_results"][arm][model]["log10_MAE"])
            assert report["actual_oof_results"][arm][model]["all_frozen_source_records_predicted_once"]==35
            assert report["actual_oof_results"][arm][model]["independent_test_generalization_claim_authorized"] is False
    body=json.dumps(report)
    assert "nevertest" not in body and "10.5555/artificial" not in body
    assert "s000" not in body and "per_record_predictions" not in body


def test_same_fixed_data_predictions_reproducible(tmp_path):
    original,prior,ephemeral,base,raw,geo=load_fixture(tmp_path)
    one=evaluate_predeclared_author_features(prior,ephemeral,base,raw,geo)
    two=evaluate_predeclared_author_features(prior,ephemeral,base,raw,geo)
    assert one==two


def test_source_digest_tamper_and_test_row_is_never_scored(tmp_path):
    original,prior,ephemeral,base,raw,geo=load_fixture(tmp_path)
    with pytest.raises(ValueError,match="modified"):
        load_original_train_features(original,source_ids=ephemeral["source_ids"],
                                     expected_processed_sha256="0"*64,
                                     reference_fractions=ephemeral["x"])
    with pytest.raises(ValueError,match="missing entries"):
        load_original_train_features(original,source_ids=ephemeral["source_ids"]+("ghost",),
                                     expected_processed_sha256=hashlib.sha256((original/"data"/"processed.csv").read_bytes()).hexdigest(),
                                     reference_fractions=ephemeral["x"])


def test_refuse_any_processed_source_formula_feature_drift(tmp_path):
    original,prior,ephemeral,base,raw,geo=load_fixture(tmp_path)
    wrong=ephemeral["x"].copy()
    wrong[0,0] = 0.5
    with pytest.raises(ValueError,match="differ"):
        load_original_train_features(original,source_ids=ephemeral["source_ids"],
          expected_processed_sha256=hashlib.sha256((original/"data"/"processed.csv").read_bytes()).hexdigest(),
          reference_fractions=wrong)


def test_no_test_and_transitive_train_group_leak(tmp_path):
    original,prior,ephemeral,base,raw,geo=load_fixture(tmp_path)
    bad=dict(ephemeral)
    g=list(ephemeral["groups"])
    f0=int(ephemeral["fold_indices"][0][0])
    f1=int(ephemeral["fold_indices"][1][0])
    g[f1]=g[f0]
    bad["groups"]=tuple(g)
    with pytest.raises(ValueError,match="crosses heldout"):
        evaluate_predeclared_author_features(prior,bad,base,raw,geo)
    bad=dict(prior)
    bad["original_official_test_reserved_unread"]=0
    with pytest.raises(ValueError,match="drift"):
        evaluate_predeclared_author_features(bad,ephemeral,base,raw,geo)


def test_training_only_missing_imputation_no_heldout_statistics():
    train=np.array([[np.nan,1,2,3,4,5,6],[2,1,2,3,4,5,6],[10,1,2,3,4,5,6.]])
    held=np.array([[100,1,2,3,4,5,6.],[np.nan,1,2,3,4,5,6.]])
    t,h,_=_fold_impute_geometry(train,held)
    assert t.shape==(3,14)
    assert h.shape==(2,14)
    assert h[1,0]==6
    assert h[1,7]==1
    assert h[0,0]==100


@pytest.mark.parametrize("raw,index",[
    ("",0),("nan",0),("231",0),("3.5",0),("0",1),("-1",2),
    ("nan",5),("180",6),("not-a-number",2),("Inf",1)
])
def test_invalid_geometry_metadata_is_missing_not_fake_physical_cell(raw,index):
    assert np.isnan(_parse_source_field(raw,index))


def test_legal_publisher_columns_and_malformed_model_geometry():
    assert len(GEOMETRY_FIELDS)==7
    assert _parse_source_field("225",0)==225
    assert _parse_source_field("90",4)==90
    with pytest.raises(ValueError,match="shape"):
        _fold_impute_geometry(np.zeros((3,5)),np.zeros((2,5)))
