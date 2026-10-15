"""0176 actual external provider inquiry and negative scientific P0 audit."""
import copy
import pytest
from scripts.science import mace_provider_frame_request_0176 as m

def inputs():
    base=f"https://github.com/{m.REPO}/issues/42#issuecomment-"
    url=f"https://api.github.com/repos/{m.REPO}/issues/42"
    a={"id":m.UPSTREAM_DISCLOSURE_ID,"user":{"login":m.AUTHOR},
       "body":"For the MACE-MPA-0 we used the following data: sAlex and MPtraj training set from here:",
       "issue_url":url,"html_url":base+str(m.UPSTREAM_DISCLOSURE_ID),
       "created_at":"2025-09-02T09:56:55Z"}
    b={"id":m.EXTERNAL_EVIDENCE_REQUEST_ID,"user":{"login":m.REQUESTOR},
       "body":"Request selected-frame identity manifest, energy/force/stress labels, historical checkpoint mapping.",
       "issue_url":url,"html_url":base+str(m.EXTERNAL_EVIDENCE_REQUEST_ID),
       "created_at":"2026-10-15T06:37:52Z"}
    tree={"sha":m.GIT_TREE_SHA,"truncated":False,
          "tree":[{"path":"README.md"},{"path":"mace_omat/mace-omat-medium.sh"}]}
    return [a,b],tree

def test_actual_contact_verified_without_fake_external_attestation():
    comments,tree=inputs()
    r=m.parse_original_thread(comments,tree)
    assert r["request_public_url"].endswith(str(m.EXTERNAL_EVIDENCE_REQUEST_ID))
    assert r["publisher_response_after_request_count"]==0
    assert r["P0_02"]=="BLOCKED"
    assert r["scientific_GO"] is False
    assert not r["external_provider_training_manifest_delivered_and_audited"]
    assert r["independently_attested_individual_experimental_samples"]==0

@pytest.mark.parametrize("mutation",[
    lambda c,t:c[0]["user"].update(login="unknown"),
    lambda c,t:c[1]["user"].update(login="someone-else"),
    lambda c,t:c[1].update(body="What is MACE?"),
    lambda c,t:c[1].update(issue_url="https://api.github.com/repos/wrong/repo/issues/42"),
    lambda c,t:c[1].update(created_at="2020-01-01T00:00:00Z"),
    lambda c,t:c[0].update(body="MPA-0 uses unspecified data"),
    lambda c,t:t.update(truncated=True),
    lambda c,t:t.update(sha="0"*40),
    lambda c,t:t["tree"].append({"path":"README.md"}),
    lambda c,t:c[1].update(id=m.EXTERNAL_EVIDENCE_REQUEST_ID+1),
])
def test_forged_provider_and_corrupt_snapshot_rejected(mutation):
    c,t=inputs();mutation(c,t)
    with pytest.raises(ValueError):m.parse_original_thread(c,t)

def test_later_actual_provider_reply_requires_manual_review_not_auto_go():
    c,t=inputs()
    c.append({"id":9999999999,"user":{"login":m.AUTHOR},
       "body":"Here is a link to a future signed manifest.",
       "issue_url":c[0]["issue_url"],
       "html_url":c[0]["html_url"].split("#")[0]+"#issuecomment-9999999999",
       "created_at":"2026-10-16T12:00:00Z"})
    r=m.parse_original_thread(c,t)
    assert r["publisher_response_after_request_count"]==1
    assert r["upstream_reply_ids_for_manual_review"]==[9999999999]
    assert r["checkpoint_selected_MPtrj_and_sAlex_frames_authenticated"] is False
    assert r["scientific_GO"] is False
