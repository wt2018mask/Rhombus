"""0174 publisher/source split count vs checkpoint membership negative audit."""
import base64
import hashlib
import pytest
from scripts.science import mace_publisher_source_metadata_0174 as m
from scripts.science import mace_author_training_splits_0173 as prior


def fixture_readme():
    return ("""# Meta OMat24 official public dataset\n### sAlex Dataset\n
sAlex was created by removing structures matched in WBM.
| Dataset | Split | Size | Download |
| sAlex | train | 10,447,765 | [train.tar.gz](https://dl.fbaipublicfiles.com/opencatalystproject/data/omat/241018/sAlex/train.tar.gz) |
| sAlex | val | 553,218 | [val.tar.gz](https://dl.fbaipublicfiles.com/opencatalystproject/data/omat/241018/sAlex/val.tar.gz) |
## How to read the data
""").encode()


def fake_blob():
    # Use exact source content SHA gate by monkeypatch for synthetic fixture
    script=(
        """python ./mace/mace/cli/run_train.py \\
    --name="mace-omat-medium" \\
    --train_file="/train/all_data" \\
    --valid_file="/val/all_data" \\
    --energy_key='energy' \\
    --forces_key='forces' \\
    --stress_key='stress' \\
    --energy_weight=1 \\
    --forces_weight=10 \\
    --compute_stress=True \\
    --stress_weight=10 \\
    --default_dtype="float64"
""").encode()
    digest=hashlib.sha1(b"blob "+str(len(script)).encode()+b"\0"+script).hexdigest()
    return {"sha":digest,"size":len(script),"encoding":"base64",
            "content":base64.b64encode(script).decode()},digest


def authors():
    return {"original_comment_author":prior.AUTHOR,
            "independent_author_comments_verified":2,
            "MACE_MPA0_author_stated_source_training_validation_URLs":prior.DATASET_LINKS}


def test_correct_public_meta_is_not_model_selected_frames(monkeypatch):
    blob,sha=fake_blob()
    monkeypatch.setattr(m,"BLOB_SHA",sha)
    d=m.parse_meta(fixture_readme(),blob,authors())
    assert d["meta_reported_sAlex_train_records_NOT_checkpoint_selected"]==10447765
    assert d["meta_reported_sAlex_valid_records_NOT_checkpoint_selected"]==553218
    assert d["data_row_counts_from_publisher_are_NOT_MACE_MPA0_training_selection"]
    assert d["source_archive_SHA256_independently_computed"] is False
    assert d["dataset_selected_frame_ids_for_exact_MACE_checkpoint_authenticated"] is False
    assert d["template_explicitly_named_OMAT_not_historical_MPA_training_receipt"]
    assert d["scientific_GO"] is False
    assert all(d[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))


@pytest.mark.parametrize("needle,replacement",[
    ("10,447,765","10,447,764"),
    ("553,218","553,219"),
    ("[val.tar.gz]","[train.tar.gz]"),
    ("/sAlex/val.tar.gz","/sAlex/train.tar.gz"),
    ("matched in WBM","matched in a secret private test"),
    ("### sAlex Dataset","### OMAT Dataset"),
])
def test_source_count_split_and_paper_method_drift_rejected(monkeypatch,needle,replacement):
    b,sha=fake_blob();monkeypatch.setattr(m,"BLOB_SHA",sha)
    with pytest.raises(ValueError):
        m.parse_meta(fixture_readme().replace(needle.encode(),replacement.encode()),b,authors())


def test_no_fake_author_promotion(monkeypatch):
    b,sha=fake_blob();monkeypatch.setattr(m,"BLOB_SHA",sha)
    author=authors();author["independent_author_comments_verified"]=0
    with pytest.raises(ValueError):
        m.parse_meta(fixture_readme(),b,author)


@pytest.mark.parametrize("alter",["sha","content","size","encoding"])
def test_git_template_digest_scope_and_content_change_rejected(monkeypatch,alter):
    b,sha=fake_blob();monkeypatch.setattr(m,"BLOB_SHA",sha)
    if alter=="sha":b["sha"]="0"*40
    elif alter=="size":b["size"]+=1
    elif alter=="encoding":b["encoding"]="utf8"
    else:b["content"]=base64.b64encode(b"the wrong MPA template").decode()
    with pytest.raises(ValueError):
        m.parse_meta(fixture_readme(),b,authors())
