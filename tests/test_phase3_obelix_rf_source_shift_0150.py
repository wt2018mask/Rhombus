"""0150 synthetic adversarial tests. All numbers in this file are fake fixtures."""
import copy
import json
import numpy as np
import pytest

from tests.test_phase3_rf_mlp_frozen_group_oof_0147 import synthetic_evaluation
from tests.test_phase3_obelix_author_features_0149 import source_csv
from scripts.science.obelix_original_author_features_0149 import (
    load_original_train_features,evaluate_predeclared_author_features,
)
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import evaluate_frozen_baselines
from scripts.science.obelix_rf_source_shift_0150 import (
    SCHEMA,MODELS,_source_weight_slices,_chemistry_slices,
    _leave_chemical_class_out,evaluate_real_source_0150,
)


def _fixture(tmp_path):
    prior,ephemeral=synthetic_evaluation()
    prior.update({
        "original_upstream_commit":"synthetic-not-author",
        "source_processed_csv_sha256":"0"*64,
        "original_raw_workbook_sha256":"1"*64,
    })
    old,old_p=evaluate_frozen_baselines(prior,ephemeral,return_internal=True)
    root,sha=source_csv(tmp_path)
    raw,geometry=load_original_train_features(
        root,source_ids=ephemeral["source_ids"],
        expected_processed_sha256=sha,
        reference_fractions=ephemeral["x"],
    )
    feature,new_p=evaluate_predeclared_author_features(
        prior,ephemeral,old,raw,geometry,return_internal=True
    )
    return prior,ephemeral,old,old_p,feature,new_p,raw,geometry


def test_0149_returns_same_metrics_with_ephemeral_predictions(tmp_path):
    prior,e,old,old_p,new,new_p,raw,geo=_fixture(tmp_path)
    actual=evaluate_predeclared_author_features(prior,e,old,raw,geo)
    assert actual==new
    assert set(new_p)=={
        "raw_stoichiometry","raw_stoichiometry_plus_seven_lattice_spacegroup"
    }
    assert all(set(x)=={"RF","MLP"} for x in new_p.values())
    assert all(v.shape==(35,) for models in new_p.values() for v in models.values())


def test_group_robustness_source_count_and_claims(tmp_path):
    prior,e,old,old_p,new,new_p,raw,geo=_fixture(tmp_path)
    r=evaluate_real_source_0150(prior,e,old,old_p,new,new_p,raw,geo)
    assert r["schema_version"]==SCHEMA
    assert r["original_uncensored_numeric_source_rows"]==35
    assert r["DOI_formula_connected_groups"]==35
    assert r["original_official_test_reserved_unread"]==1
    assert r["official_public_TEST_predictions"]==0
    assert r["all_prior_0146_0147_0149_group_folds_and_model_config_unchanged"]
    assert r["scientific_GO"] is False
    assert r["P0_01_status"]==r["P0_02_status"]==r["P0_03_status"]=="BLOCKED"
    assert r["true_independent_material_count"] is None
    allg=r["source_group_size_robustness"]
    assert allg["largest_five"]["connected_group_count"]==5
    assert allg["remaining_groups"]["connected_group_count"]==30
    assert allg["largest_five"]["source_record_count"]+allg["remaining_groups"]["source_record_count"]==35
    for model in MODELS:
        assert np.isfinite(allg["all_groups"]["models"][model]["record_weighted_log10_MAE"])
        assert allg["all_groups"]["models"][model]["independent_material_confidence_interval"] is False
    assert len(r["predeclared_chemical_anion_proxy_slices"])==5
    assert sum(x["source_record_count"] for x in r["predeclared_chemical_anion_proxy_slices"].values())==35
    assert len(r["retrospective_leave_proxy_class_out"])==5
    assert all(x["independent_chemistry_generalization_test"] is False
               for x in r["retrospective_leave_proxy_class_out"].values())
    as_json=json.dumps(r)
    for sensitive in ("s000","10.5555/artificial","nevertest","per_row_true"):
        assert sensitive not in as_json


def test_group_size_reversal_group_macro_vs_record_score():
    y=np.array([0.,0.,0.,0.,0.,0.,0.,0.,0.,0.,10.,10.,10.,10.,10.])
    g=tuple(["big"]*10+["a","b","c","d","e"])
    # RF worse in high-weight big group, better in smaller groups.
    pred={"mean_0146":y+1,"fraction_rf_0147":y+2,"stoich_rf_0149":y+1,
          "geometry_rf_0149":np.array([3]*10+[0]*5,dtype=float)}
    res=_source_weight_slices(y,g,pred)
    assert res["all_groups"]["connected_group_count"]==6
    assert res["largest_five"]["connected_group_count"]==5
    assert res["all_groups"]["models"]["geometry_rf_0149"]["independent_material_confidence_interval"] is False
    assert res["all_groups"]["models"]["mean_0146"]["equal_group_macro_minus_mean_log10_MAE"]==0


def test_chemical_proxy_rows_with_suppressed_slices(tmp_path):
    prior,e,old,old_p,new,new_p,raw,geo=_fixture(tmp_path)
    pred={
        "mean_0146":old_p["training_fold_mean_0146"],
        "fraction_rf_0147":old_p["random_forest"],
        "stoich_rf_0149":new_p["raw_stoichiometry"]["RF"],
        "geometry_rf_0149":new_p["raw_stoichiometry_plus_seven_lattice_spacegroup"]["RF"],
    }
    labels,cats=_chemistry_slices(e["x"],e["y"],e["groups"],pred)
    assert len(labels)==35
    assert cats["O_AND_S"]["source_record_count"]==0
    assert cats["O_AND_S"]["scores_suppressed"] is True
    assert cats["O_AND_S"].get("MAE") is None
    assert all(not cat["structural_family_independently_authenticated"] for cat in cats.values())


def test_cross_chemical_group_embargo_for_nonheld_class_rows():
    y=np.arange(30,dtype=float)
    grp=tuple(["bridge"]*6 + [f"g{i}" for i in range(6,30)])
    labels=tuple(["O_ONLY"]*3+["S_ONLY"]*11+["HALIDE_NO_O_S"]*16)
    raw=np.zeros((30,118),dtype=float);raw[:,2]=1
    geometry=np.ones((30,7),dtype=float)
    score=_leave_chemical_class_out(y,grp,labels,raw,geometry)
    assert score["O_ONLY"]["other_proxy_rows_embargoed_due_to_shared_identity_group"]==3
    assert score["O_ONLY"]["status"]=="NOT_ADMITTED_TOO_FEW_ROWS_OR_GROUPS"
    assert score["HALIDE_NO_O_S"]["independent_chemistry_generalization_test"] is False


def test_falsified_source_membership_and_outputs_rejected(tmp_path):
    prior,e,old,old_p,new,new_p,raw,geo=_fixture(tmp_path)
    bad=dict(prior);bad["original_official_test_reserved_unread"]=0
    with pytest.raises(ValueError,match="invalid"):
        evaluate_real_source_0150(bad,e,old,old_p,new,new_p,raw,geo)
    bad=dict(new_p)
    bad["raw_stoichiometry"]={key:val.copy() for key,val in new_p["raw_stoichiometry"].items()}
    bad["raw_stoichiometry"]["RF"][0]=float("nan")
    with pytest.raises(ValueError,match="predictions"):
        evaluate_real_source_0150(prior,e,old,old_p,new,bad,raw,geo)
    bad=dict(old);bad["scientific_qualification_authorized"]=True
    with pytest.raises(ValueError,match="invalid"):
        evaluate_real_source_0150(prior,e,bad,old_p,new,new_p,raw,geo)


def test_not_allow_mixed_unknown_proxy_rows():
    y=np.arange(10,dtype=float);x=np.zeros((10,118),dtype=float)
    x[:,7]=1.0
    pred={m:y.copy() for m in MODELS}
    labels,cats=_chemistry_slices(x,y,tuple(str(i) for i in range(10)),pred)
    assert set(labels)=={"O_ONLY"}
    assert cats["O_ONLY"]["scores_suppressed"] is False
    assert cats["S_ONLY"]["scores_suppressed"] is True
