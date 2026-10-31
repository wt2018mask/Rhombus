"""Synthetic source identity tests only; no model bytes or external HTTP."""
from copy import deepcopy
import pytest
from scripts.benchmark import audit_tier_a_small_checkpoint_0205 as m


def example():
    return {"tag_name": "mace_mp_0", "draft": False, "prerelease": False,
            "assets": [{"id": m.ASSET_ID, "name": m.NAME, "size": m.SIZE,
                        "state": "uploaded", "browser_download_url": m.URL,
                        "digest": None}]}


def test_expected_official_small_asset_not_a_publisher_signature():
    o = m.verify_release(example())
    assert o["asset_id"] == 145021750
    assert o["asset_bytes"] == 32581838
    assert o["official_api_sha256"] is None
    assert "NOT_PUBLISHER_SIGNED" in o["expected_sha256_origin"]


@pytest.mark.parametrize("mutator", [
    lambda x: x.update(tag_name="other"),
    lambda x: x.update(draft=True),
    lambda x: x["assets"][0].update(size=0),
    lambda x: x["assets"][0].update(id=213937064),
    lambda x: x["assets"][0].update(digest="sha256:" + "0"*64),
    lambda x: x["assets"][0].update(browser_download_url="https://evil.invalid"),
    lambda x: x["assets"].append(deepcopy(x["assets"][0])),
])
def test_wrong_or_ambiguous_model_release_fails_closed(mutator):
    d = example()
    mutator(d)
    with pytest.raises(ValueError):
        m.verify_release(d)


def test_model_source_requires_explicit_optin(tmp_path):
    with pytest.raises(SystemExit):
        m.main(["--output-dir", str(tmp_path / "out")])
    assert not (tmp_path / "out").exists()
