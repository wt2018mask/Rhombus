"""0176: real upstream MACE model-author follow-up and public-source scope audit.

Never conflate asking an upstream developer with receiving evidence.
This source fetch is read-only and bounded. It exposes no sealed cohort data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SCHEMA="rhombus-0176-mpa0-frame-membership-public-provider-outreach-v1"
REPO="ACEsuit/mace-foundations"
ISSUE=42
AUTHOR="ilyes319"
UPSTREAM_DISCLOSURE_ID=3244634298
EXTERNAL_EVIDENCE_REQUEST_ID=6186104995
REQUESTOR="wt2018mask"
GIT_TREE_SHA="16a9f178706ce053f3ca8531efbab00a305d0854"
COMMENT_API=f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments?per_page=100"
TREE_API=f"https://api.github.com/repos/{REPO}/git/trees/{GIT_TREE_SHA}"
MAX_BYTES=180000


def _parse_stamp(value):
    if not isinstance(value,str) or not re.fullmatch(
        r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ",value):
        raise ValueError("original upstream comment date unavailable")
    return datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def parse_original_thread(comments: list[dict], tree: dict) -> dict:
    if not isinstance(comments,list) or not 2<=len(comments)<100:
        raise ValueError("source thread incomplete, duplicate or unbounded pagination")
    if not isinstance(tree,dict) or tree.get("sha")!=GIT_TREE_SHA or tree.get("truncated") is not False:
        raise ValueError("not the expected complete immutable official source tree")
    paths=tree.get("tree")
    if not isinstance(paths,list) or not paths or len(paths)>5000:
        raise ValueError("invalid official repository file tree")
    source_paths=set()
    for entry in paths:
        if not isinstance(entry,dict) or not isinstance(entry.get("path"),str):
            raise ValueError("invalid source tree path")
        path=entry["path"]
        if not path or path.startswith("/") or ".." in path.split("/") or path in source_paths:
            raise ValueError("invalid/duplicate repository path")
        source_paths.add(path)
    seen=set()
    by_id={}
    for c in comments:
        if (not isinstance(c,dict) or type(c.get("id")) is not int
            or c["id"] in seen or not isinstance(c.get("user"),dict)
            or not isinstance(c.get("body"),str) or not c["body"]
            or len(c["body"])>20000):
            raise ValueError("untrusted author comment metadata")
        seen.add(c["id"])
        ident=c["id"]
        if c.get("issue_url") != f"https://api.github.com/repos/{REPO}/issues/{ISSUE}":
            raise ValueError("comment not bound to upstream issue #42")
        if c.get("html_url") != (
            f"https://github.com/{REPO}/issues/{ISSUE}#issuecomment-{ident}"):
            raise ValueError("misbound upstream original comment URL")
        by_id[ident]=c
        _parse_stamp(c.get("created_at"))
    if UPSTREAM_DISCLOSURE_ID not in by_id or EXTERNAL_EVIDENCE_REQUEST_ID not in by_id:
        raise ValueError("known upstream author disclosure or real external question missing")
    author=by_id[UPSTREAM_DISCLOSURE_ID]
    request=by_id[EXTERNAL_EVIDENCE_REQUEST_ID]
    if (author["user"].get("login")!=AUTHOR or
        "For the MACE-MPA-0 we used the following data:" not in author["body"] or
        "MPtraj training set from here:" not in author["body"]):
        raise ValueError("not the actual prior original developer disclosure")
    req_body=request["body"]
    if (request["user"].get("login")!=REQUESTOR or
        "selected-frame identity manifest" not in req_body or
        "energy/force/stress labels" not in req_body or
        "checkpoint" not in req_body):
        raise ValueError("specific selected frame/preprocessing author request not verified")
    query_time=_parse_stamp(request["created_at"])
    if _parse_stamp(author["created_at"])>=query_time:
        raise ValueError("disclosure chronology drift")
    after=[c for c in comments if _parse_stamp(c["created_at"])>query_time
           and c["id"]!=EXTERNAL_EVIDENCE_REQUEST_ID]
    provider_replies=[c for c in after if c["user"].get("login")==AUTHOR]
    provider_replies.sort(key=lambda c:(c["created_at"],c["id"]))
    # Even when the model provider replies, public answers require separate
    # frame-by-frame scientific audit. There is NO auto-qualification.
    candidate_paths=sorted(x for x in source_paths
        if ("mpa" in x.lower() or "train" in x.lower()
            or "split" in x.lower() or "manifest" in x.lower()))
    return {
        "schema_version":SCHEMA,
        "upstream_original_repository":REPO,
        "external_evidence_request_issue":ISSUE,
        "request_public_url":request["html_url"],
        "request_created_at":request["created_at"],
        "request_sha256":hashlib.sha256(req_body.encode()).hexdigest(),
        "requested_selected_frame_IDs_training_revisions_and_labels":True,
        "upstream_original_disclosure_url":author["html_url"],
        "publisher_response_after_request_count":len(provider_replies),
        "upstream_reply_ids_for_manual_review":[c["id"] for c in provider_replies],
        "any_provider_response_is_NOT_automatic_training_certification":True,
        "current_git_tree_immutable_snapshot_SHA1":GIT_TREE_SHA,
        "original_git_tree_file_count":len(source_paths),
        "original_tree_candidate_training_path_count":len(candidate_paths),
        "original_tree_candidate_training_paths":candidate_paths[:100],
        "absence_in_one_public_repo_snapshot_not_absence_of_external_run_records":True,
        "external_provider_training_manifest_delivered_and_audited":False,
        "checkpoint_selected_MPtrj_and_sAlex_frames_authenticated":False,
        "checkpoint_historical_label_preprocessing_attested":False,
        "exact_source_archives_checkpoint_join_attested":False,
        "real_training_material_exposure_audit_authorized":False,
        "independent_external_steward_recruited":False,
        "independently_attested_individual_experimental_samples":0,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_GO":False,
        "status":"PUBLIC_PROVIDER_OUTREACH_SENT_PROVENANCE_STILL_BLOCKED",
    }


def _json_from_original(url: str, max_bytes=MAX_BYTES):
    req=Request(url,headers={
        "Accept":"application/vnd.github+json",
        "User-Agent":"Rhombus-0176-real-author-membership-question-evidence",
        "X-GitHub-Api-Version":"2022-11-28",
    })
    with urlopen(req,timeout=40) as r:
        a=urlsplit(url);b=urlsplit(r.geturl())
        if (a.scheme,a.netloc,a.path,a.query)!=(b.scheme,b.netloc,b.path,b.query):
            raise ValueError("upstream public original GitHub API URL redirect drift")
        if r.status!=200:raise ValueError("upstream API source not available")
        raw=r.read(max_bytes+1)
    if not raw or len(raw)>max_bytes:
        raise ValueError("unbounded upstream provider source content")
    def no_dup(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError("ambiguous upstream response field")
            out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=no_dup,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--live-upstream-source",action="store_true")
    ap.add_argument("--output-dir",type=Path,required=True)
    args=ap.parse_args()
    if not args.live_upstream_source:ap.error("actual original public upstream API source required")
    out=args.output_dir.resolve()
    if out.exists() or out.is_symlink():ap.error("new unique report directory required")
    data=parse_original_thread(_json_from_original(COMMENT_API),_json_from_original(TREE_API))
    out.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".rhombus-0176-",dir=out.parent))
    try:
        (stage/"provider_selected_frames_request_0176.json").write_text(
            json.dumps(data,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n",
            encoding="utf-8")
        if out.exists():raise ValueError("source receipt directory collision")
        stage.rename(out)
    finally:
        if stage.exists():shutil.rmtree(stage)
    print("0176_ACTUAL_EXTERNAL_MACE_PROVIDER_REQUEST_ORIGIN_PASS")
    print(json.dumps({"provider_replies":data["publisher_response_after_request_count"],
        "scientific_GO":False,"P0_02":data["P0_02"]},sort_keys=True))


if __name__=="__main__":
    main()
