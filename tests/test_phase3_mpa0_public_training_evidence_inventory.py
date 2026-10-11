"""0141 adversarial P0-02 source availability: never infer actual training members."""
import copy
import json

import pytest

from scripts.science.mpa0_public_training_evidence_inventory import (
    ASSET_BYTES, FOUNDATIONS_COMMIT, MACE_COMMIT, MODEL_PATH,
    GOLDEN_TEST_MANIFEST_PATH, GENERIC_FINE_TUNING_SELECTOR_PATH,
    RELEASE_ASSET_ID, RELEASE_TAG, RELEASE_URL, SCHEMA,
    _paths_of_exact_tree, audit_public_availability, read_bounded_json,
)


def item(path, size=120):
    return {"path": path, "mode": "100644", "type": "blob", "sha": "f"*40, "size": size}


def fixture():
    return {
        "foundations_tree": {
            "sha": FOUNDATIONS_COMMIT, "truncated": False,
            "tree": [item("README.md")]},
        "mace_tree": {
            "sha": MACE_COMMIT, "truncated": False,
            "tree": [
                item(MODEL_PATH, ASSET_BYTES),
                item(GOLDEN_TEST_MANIFEST_PATH),
                item(GENERIC_FINE_TUNING_SELECTOR_PATH),
            ]},
        "release": {
            "tag_name": RELEASE_TAG,
            "assets": [{
                "id": RELEASE_ASSET_ID, "name": "mace-mpa-0-medium.model",
                "size": ASSET_BYTES, "browser_download_url": RELEASE_URL,
            }]},
    }


def test_exact_pinned_repository_paths_not_real_training_membership():
    r = audit_public_availability(**fixture())
    assert r["schema_version"] == SCHEMA
    assert r["model_implementation_git_tree_entries"] == 3
    assert r["foundations_git_tree_entries"] == 1
    assert r["test_golden_manifest_present_NOT_training_frame_manifest"] is True
    assert r["generic_fine_tuning_selector_present_NOT_actual_selection"] is True
    assert r["selected_training_membership_verdict"] == "UNKNOWN"
    assert r["P0_02_status"] == "BLOCKED"
    assert r["P0_01_status"] == "BLOCKED"
    assert r["P0_03_status"] == "BLOCKED"
    assert r["scientific_release_authorized"] is False


@pytest.mark.parametrize("target,mutation", [
    ("foundations_tree", lambda x: x.update(sha="a"*40)),
    ("mace_tree", lambda x: x.update(truncated=True)),
    ("mace_tree", lambda x: x.update(truncated=None)),
    ("mace_tree", lambda x: x["tree"].append(copy.deepcopy(x["tree"][0]))),
    ("mace_tree", lambda x: x["tree"][0].update(path="../evil.model")),
    ("mace_tree", lambda x: x["tree"][0].update(mode="120000")),
    ("mace_tree", lambda x: x["tree"][0].update(size=ASSET_BYTES-1)),
    ("mace_tree", lambda x: x["tree"][0].update(sha="zzzz")),
    ("mace_tree", lambda x: x["tree"].pop(1)),
    ("release", lambda x: x.update(tag_name="not-this-checkpoint")),
    ("release", lambda x: x["assets"][0].update(size=ASSET_BYTES+1)),
    ("release", lambda x: x["assets"][0].update(id=RELEASE_ASSET_ID+1)),
    ("release", lambda x: x["assets"][0].update(browser_download_url="https://evil")),
])
def test_hostile_source_tree_or_release_rejected(target, mutation):
    f = fixture()
    mutation(f[target])
    with pytest.raises(ValueError):
        audit_public_availability(**f)


def test_generic_trained_string_in_test_files_cannot_promote_lineage():
    f = fixture()
    f["mace_tree"]["tree"].append(item(
        "tests/golden/datasets/actual-selected-mptrj-salex-training-MANIFEST.json"))
    r = audit_public_availability(**f)
    assert r["actual_selected_MPTrj_frame_ids_authenticated"] is False
    assert r["actual_selected_sAlex_frame_ids_authenticated"] is False
    assert r["publisher_signed_checkpoint_specific_training_manifest_available"] is False
    assert r["selected_training_membership_verdict"] == "UNKNOWN"


def test_strict_json_parser_rejects_duplicate_and_nan_and_oversized(tmp_path):
    for txt in ('{"sha":"a","sha":"b"}', '{"sha":NaN}', '{"sha":Infinity}'):
        p = tmp_path / "test.json"
        p.write_text(txt)
        with pytest.raises(ValueError):
            read_bounded_json(p)
    p.write_bytes(b" " * 1000001)
    with pytest.raises(ValueError, match="byte limit"):
        read_bounded_json(p)


def test_external_tree_file_symlink_is_denied(tmp_path):
    raw = tmp_path / "valid.json"
    raw.write_text(json.dumps(fixture()["mace_tree"]))
    link = tmp_path / "alias"
    link.symlink_to(raw)
    with pytest.raises(ValueError, match="regular JSON"):
        read_bounded_json(link)


def test_no_public_tree_can_count_as_independent_training_auditor():
    f = fixture()
    r = audit_public_availability(**f)
    assert r["independent_training_manifest_auditor_available"] is False
    assert r["source_tree_audit_scope_EXCLUDES_other_repositories_releases_external_storage"]
    assert r["training_data_source_SHA256_and_preprocessing_authenticated"] is False
