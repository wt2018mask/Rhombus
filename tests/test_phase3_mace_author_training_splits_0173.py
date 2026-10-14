"""0173 original MACE upstream author TRAIN/VALID provenance, fail-closed."""
import copy
import json
import pytest
from scripts.science import mace_author_training_splits_0173 as m


def comments():
    a={"id":3244634298,"user":{"login":"ilyes319"},
       "issue_url":"https://api.github.com/repos/ACEsuit/mace-foundations/issues/42",
       "html_url":"https://github.com/ACEsuit/mace-foundations/issues/42#issuecomment-3244634298",
       "created_at":"2025-09-02T09:56:55Z"}
    a["body"]=(
        "Hey, For the MACE-MPA-0 we used the following data:\n"
        "- training is the combination of sAlex here: "+m.DATASET_LINKS["sAlex_training"]
        +" and MPtraj training set from here: "+m.DATASET_LINKS["MPTrj_training"]+"\n"
        "- the validation set is the sAlex valid set from here: "+m.DATASET_LINKS["sAlex_validation"]
        +" and the Mptraj valid: "+m.DATASET_LINKS["MPTrj_validation"]+"\n"
        "For the MACE-MATPES-PBE-0: different datasets")
    b={"id":3291737675,"user":{"login":"ilyes319"},
       "issue_url":"https://api.github.com/repos/ACEsuit/mace-foundations/issues/29",
       "html_url":"https://github.com/ACEsuit/mace-foundations/issues/29#issuecomment-3291737675",
       "created_at":"2025-09-15T11:41:42Z",
       "body":"MPA model is the same input as: "+m.SCRIPT+
       "\nBut you need to replace the omat data is the sAlex + Mptraj dataset."}
    return [a,b]


def test_real_author_replies_bind_both_source_splits_and_do_not_close_p0():
    r=m.parse_comments(comments())
    assert r["independent_author_comments_verified"]==2
    assert r["MACE_MPA0_author_stated_source_training_validation_URLs"]==m.DATASET_LINKS
    assert r["training_script_requires_OMAT_replacement_with_sAlex_and_MPTrj"]
    assert r["MPTrj_and_sAlex_exact_selected_frame_ids_attested"] is False
    assert r["original_archive_SHA256_and_sizes_rehashed"] is False
    assert r["full_exact_model_training_lineage_independent_ACCEPTED"] is False
    assert r["scientific_GO"] is False
    assert all(r[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))


@pytest.mark.parametrize("mutation",[
    lambda c: c[0].update(user={"login":"imposter"}),
    lambda c: c[0].update(issue_url="https://api.github.com/repos/ACEsuit/mace-foundations/issues/29"),
    lambda c: c[0].update(id=3291737675),
    lambda c: c[1].update(html_url="https://evil.test/fake"),
    lambda c: c[1].update(body="same MPA training config"),
    lambda c: c[0].update(body=c[0]["body"].replace("MACE-MPA-0","MACE-MATPES-PBE-0")),
    lambda c: c[0].update(body=c[0]["body"].replace("/sAlex/train.tar.gz","/sAlex/val.tar.gz")),
    lambda c: c[0].update(body=c[0]["body"].replace("12RsjlEtSlBldhoQVJapfC9lIFZwpnVk6","other_folder")),
    lambda c: c[0].update(body=c[0]["body"].replace("/sAlex/val.tar.gz","/sAlex/train.tar.gz")),
    lambda c: c[1].update(body=c[1]["body"].replace("sAlex + Mptraj","OMAT")),
])
def test_false_training_selected_source_origin_and_split_drift_rejected(mutation):
    c=comments();mutation(c)
    with pytest.raises(ValueError):
        m.parse_comments(c)


def test_no_duplicate_metadata_and_no_user_supplied_public_ids():
    with pytest.raises(ValueError):
        m.strict_pairs([("id",1),("id",2)])
    with pytest.raises(ValueError):
        m.parse_comments([comments()[0],comments()[0]])
    with pytest.raises(ValueError):
        m.fetch_author_comment(1)
